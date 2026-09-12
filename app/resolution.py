import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from sqlalchemy.orm import Session
from rapidfuzz import fuzz, process

from app.models import Item, ItemAlias
from app.normalizer import normalize_item_name

logger = logging.getLogger("entity_resolution")


@dataclass
class ResolutionResult:
    canonical_item: Optional[Item]
    confidence: float
    matched_via: str  # exact_alias, rapidfuzz, heuristic_fallback, unresolved
    matched_term: str


class EntityResolver:
    """Multi-tier entity resolution engine for grocery items:
    1. Exact alias lookup
    2. RapidFuzz similarity matching against canonical catalogue & alias dictionary
    3. Heuristic / Semantic fallback
    """

    def __init__(self, db: Session, similarity_threshold: float = 75.0):
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

    def resolve(self, raw_product_name: str) -> ResolutionResult:
        """Execute 3-tier entity resolution on raw product name."""
        normalized = normalize_item_name(raw_product_name)
        if not normalized:
            return ResolutionResult(
                canonical_item=None,
                confidence=0.0,
                matched_via="unresolved",
                matched_term=""
            )

        # Tier 1: Exact alias or canonical name match
        if normalized in self.canonical_map:
            return ResolutionResult(
                canonical_item=self.canonical_map[normalized],
                confidence=1.0,
                matched_via="exact_canonical",
                matched_term=normalized
            )

        if normalized in self.alias_map:
            item, conf = self.alias_map[normalized]
            return ResolutionResult(
                canonical_item=item,
                confidence=conf,
                matched_via="exact_alias",
                matched_term=normalized
            )

        # Tier 2: RapidFuzz similarity matching against corpus
        if self.fuzzy_corpus:
            choices = list(self.fuzzy_corpus.keys())
            # Use token_set_ratio or WRatio for handling words in different orders or subsets
            match = process.extractOne(
                normalized,
                choices,
                scorer=fuzz.token_set_ratio,
                score_cutoff=self.similarity_threshold
            )

            if match:
                best_term, score, _ = match
                item = self.fuzzy_corpus[best_term]
                confidence = round(score / 100.0, 2)
                return ResolutionResult(
                    canonical_item=item,
                    confidence=confidence,
                    matched_via="rapidfuzz",
                    matched_term=best_term
                )

        # Tier 3: Heuristic token overlap fallback
        tokens = set(normalized.split())
        for norm_term, item in self.fuzzy_corpus.items():
            candidate_tokens = set(norm_term.split())
            if tokens and candidate_tokens and (tokens.issubset(candidate_tokens) or candidate_tokens.issubset(tokens)):
                return ResolutionResult(
                    canonical_item=item,
                    confidence=0.70,
                    matched_via="heuristic_fallback",
                    matched_term=norm_term
                )

        # Unresolved
        return ResolutionResult(
            canonical_item=None,
            confidence=0.0,
            matched_via="unresolved",
            matched_term=""
        )
