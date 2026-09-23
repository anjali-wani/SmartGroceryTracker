import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Any
from sqlalchemy.orm import Session
from rapidfuzz import fuzz, process

from app.models import Item, ItemAlias
from app.normalizer import normalize_item_name
from app.services.llm_resolver import resolve_with_gemini, LLMResolvedItem
from app.services.mapping_service import load_product_mappings

logger = logging.getLogger("entity_resolution")


@dataclass
class ResolutionResult:
    canonical_item: Optional[Item]
    confidence: float
    matched_via: str  # exact_alias, rapidfuzz, heuristic_fallback, product_mapping, gemini_llm, unresolved
    matched_term: str
    llm_resolved: Optional[LLMResolvedItem] = None
    llm_success: bool = False


class EntityResolver:
    """Multi-tier entity resolution engine for grocery items:
    1. Exact alias/canonical lookup (Tier 1)
    2. Persistent Product Mapping Cache from data/product_mappings.json (Tier 2)
    3. Gemini LLM Fallback (Tier 3)
    (RapidFuzz similarity matching & Heuristic token overlap commented out)
    """

    def __init__(self, db: Session, similarity_threshold: float = 85.0):
        self.db = db
        self.similarity_threshold = float(os.getenv("RAPIDFUZZ_THRESHOLD", similarity_threshold))
        self._load_catalog()

    def _load_catalog(self):
        """Cache canonical items and aliases for high-speed in-memory fuzzy matching."""
        self.items: List[Item] = self.db.query(Item).all()
        self.aliases: List[ItemAlias] = self.db.query(ItemAlias).all()

        # Build alias lookup map (normalized_alias -> canonical_item)
        self.alias_map: Dict[str, Tuple[Item, float]] = {}
        for a in self.aliases:
            norm = normalize_item_name(a.raw_alias)
            self.alias_map[norm] = (a.item, a.match_confidence)

        # Build canonical lookup map
        self.canonical_map: Dict[str, Item] = {}
        for it in self.items:
            norm = normalize_item_name(it.canonical_name)
            self.canonical_map[norm] = it

        # Candidate corpus for RapidFuzz: tuple of (lookup_key, normalized_text)
        self.fuzzy_corpus: Dict[str, Item] = {}
        for norm_alias, (item, _) in self.alias_map.items():
            self.fuzzy_corpus[norm_alias] = item
        for norm_name, item in self.canonical_map.items():
            self.fuzzy_corpus[norm_name] = item

        # Cache persistent product mappings from data/product_mappings.json
        self.file_mappings = load_product_mappings()

    def resolve(
        self,
        raw_product_name: str,
        store_name: Optional[str] = None,
        purchase_date: Optional[Any] = None,
        price: Optional[float] = None,
        receipt_unit: Optional[str] = None,
        receipt_category: Optional[str] = None,
        raw_line: Optional[str] = None
    ) -> ResolutionResult:
        """Execute 4-tier entity resolution on raw product name."""
        normalized = normalize_item_name(raw_product_name)
        if not normalized:
            return ResolutionResult(
                canonical_item=None,
                confidence=0.0,
                matched_via="unresolved",
                matched_term=""
            )

        def _get_cached_meta(key: str) -> Optional[LLMResolvedItem]:
            if hasattr(self, "file_mappings") and self.file_mappings and key in self.file_mappings:
                entry = self.file_mappings[key]
                gen_title = entry.get("generic_name", "").strip().title()
                std_u = entry.get("standard_unit", "count")
                t_qty = entry.get("total_quantity") or f"1 {std_u}"
                return LLMResolvedItem(
                    canonical_name=entry.get("brand_name", raw_product_name).strip().title(),
                    generic_name=gen_title.lower(),
                    category=entry.get("category", "Pantry"),
                    standard_unit=std_u,
                    is_bulk=entry.get("is_bulk", False),
                    total_quantity=t_qty
                )
            return None

        # Tier 1: Exact alias or canonical name match
        if normalized in self.canonical_map:
            return ResolutionResult(
                canonical_item=self.canonical_map[normalized],
                confidence=1.0,
                matched_via="exact_canonical",
                matched_term=normalized,
                llm_resolved=_get_cached_meta(normalized)
            )

        if normalized in self.alias_map:
            item, conf = self.alias_map[normalized]
            return ResolutionResult(
                canonical_item=item,
                confidence=conf,
                matched_via="exact_alias",
                matched_term=normalized,
                llm_resolved=_get_cached_meta(normalized)
            )

        # Tier 2: Persistent Product Mapping Cache (data/product_mappings.json)
        if hasattr(self, "file_mappings") and self.file_mappings and normalized in self.file_mappings:
            entry = self.file_mappings[normalized]
            gen_title = entry.get("generic_name", "").strip().title()
            norm_gen = normalize_item_name(gen_title)
            cached_llm = LLMResolvedItem(
                canonical_name=entry.get("brand_name", raw_product_name).strip().title(),
                generic_name=gen_title.lower(),
                category=entry.get("category", "Pantry"),
                standard_unit=entry.get("standard_unit", "count"),
                is_bulk=entry.get("is_bulk", False),
                total_quantity=entry.get("total_quantity") or f"1 {entry.get('standard_unit', 'count')}"
            )

            # Check if canonical generic item exists in current database
            if norm_gen in self.canonical_map:
                return ResolutionResult(
                    canonical_item=self.canonical_map[norm_gen],
                    confidence=0.98,
                    matched_via="product_mapping",
                    matched_term=gen_title,
                    llm_resolved=cached_llm
                )
            else:
                return ResolutionResult(
                    canonical_item=None,
                    confidence=0.95,
                    matched_via="product_mapping",
                    matched_term=gen_title,
                    llm_resolved=cached_llm
                )

        # -------------------------------------------------------------------------
        # NOTE: RapidFuzz and Heuristic search are commented out per user request.
        # Any item not matched exactly (Tier 1) or found in product_mappings.json (Tier 2)
        # directly triggers the LLM API call below (Tier 3).
        # -------------------------------------------------------------------------
        # # RapidFuzz similarity matching against corpus
        # if self.fuzzy_corpus:
        #     choices = list(self.fuzzy_corpus.keys())
        #     # Use token_set_ratio or WRatio for handling words in different orders or subsets
        #     match = process.extractOne(
        #         normalized,
        #         choices,
        #         scorer=fuzz.token_set_ratio,
        #         score_cutoff=self.similarity_threshold
        #     )
        #
        #     if match:
        #         best_term, score, _ = match
        #         item = self.fuzzy_corpus[best_term]
        #         confidence = round(score / 100.0, 2)
        #         return ResolutionResult(
        #             canonical_item=item,
        #             confidence=confidence,
        #             matched_via="rapidfuzz",
        #             matched_term=best_term,
        #             llm_resolved=_get_cached_meta(normalized) or _get_cached_meta(best_term)
        #         )
        #
        # # Heuristic token overlap fallback
        # tokens = set(normalized.split())
        # for norm_term, item in self.fuzzy_corpus.items():
        #     candidate_tokens = set(norm_term.split())
        #     if tokens and candidate_tokens and (tokens.issubset(candidate_tokens) or candidate_tokens.issubset(tokens)):
        #         return ResolutionResult(
        #             canonical_item=item,
        #             confidence=0.70,
        #             matched_via="heuristic_fallback",
        #             matched_term=norm_term
        #         )

        # Tier 3: Gemini LLM Fallback (triggered if not found in product_mappings.json)
        existing_names = [it.canonical_name for it in self.items]
        llm_out = resolve_with_gemini(
            raw_product_name,
            store_name=store_name,
            existing_items=existing_names,
            purchase_date=purchase_date,
            price=price,
            receipt_unit=receipt_unit,
            receipt_category=receipt_category,
            raw_line=raw_line
        )
        if llm_out:
            # Use generic_name as the target canonical entity
            target_generic = (llm_out.generic_name or llm_out.canonical_name or raw_product_name).strip().title()
            norm_generic = normalize_item_name(target_generic)

            matched_item = self.canonical_map.get(norm_generic)
            if not matched_item and llm_out.matched_existing_canonical_name:
                matched_item = next(
                    (it for it in self.items if it.canonical_name.lower() == llm_out.matched_existing_canonical_name.lower()),
                    None
                )

            is_successful = getattr(llm_out, "llm_success", False)
            via = "gemini_llm" if is_successful else "heuristic_fallback"

            if matched_item:
                return ResolutionResult(
                    canonical_item=matched_item,
                    confidence=0.95 if is_successful else 0.70,
                    matched_via=via,
                    matched_term=matched_item.canonical_name,
                    llm_resolved=llm_out,
                    llm_success=is_successful
                )

            return ResolutionResult(
                canonical_item=None,
                confidence=0.90 if is_successful else 0.65,
                matched_via=via,
                matched_term=target_generic,
                llm_resolved=llm_out,
                llm_success=is_successful
            )

        # Unresolved
        return ResolutionResult(
            canonical_item=None,
            confidence=0.0,
            matched_via="unresolved",
            matched_term=""
        )
