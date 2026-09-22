import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Item, ItemAlias
from app.normalizer import normalize_item_name

logger = logging.getLogger("mapping_service")

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MAPPINGS_FILE_PATH = PROJECT_ROOT / "data" / "product_mappings.json"


def get_mappings_file_path() -> Path:
    """Return path to product_mappings.json."""
    return MAPPINGS_FILE_PATH


def load_product_mappings() -> Dict[str, Dict[str, Any]]:
    """Load product-to-generic mappings from JSON file."""
    if not MAPPINGS_FILE_PATH.exists():
        return {}
    try:
        if MAPPINGS_FILE_PATH.stat().st_size == 0:
            return {}
        content = MAPPINGS_FILE_PATH.read_text(encoding="utf-8").strip()
        if not content or content == "{}":
            return {}
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.error(f"Failed to read {MAPPINGS_FILE_PATH}: {e}")
    return {}


def save_product_mapping(
    raw_name: str,
    generic_name: str,
    category: Optional[str] = None,
    standard_unit: Optional[str] = None,
    brand_name: Optional[str] = None,
    clean_name: Optional[str] = None,
    is_bulk: bool = False,
    total_quantity: Optional[str] = None
) -> bool:
    """Save or update a product name -> generic name mapping in product_mappings.json."""
    if not raw_name or not generic_name:
        return False

    raw_clean = raw_name.strip()
    norm_key = normalize_item_name(raw_clean)
    if not norm_key:
        return False

    clean_title = generic_name.strip().title()
    category_val = (category or "Pantry").strip()
    unit_val = (standard_unit or "count").strip().lower()

    mappings = load_product_mappings()

    entry = {
        "raw_name": raw_clean,
        "clean_name": clean_name.strip() if clean_name else raw_clean,
        "brand_name": brand_name.strip() if brand_name else (clean_name or raw_clean).strip().title(),
        "generic_name": clean_title,
        "category": category_val,
        "standard_unit": unit_val,
        "is_bulk": bool(is_bulk)
    }
    if total_quantity:
        entry["total_quantity"] = total_quantity

    # Store under primary normalized raw key
    mappings[norm_key] = entry

    # Also map clean_name if different
    if clean_name:
        clean_norm = normalize_item_name(clean_name)
        if clean_norm and clean_norm != norm_key:
            mappings[clean_norm] = entry

    # Also map brand_name if different
    if brand_name:
        brand_norm = normalize_item_name(brand_name)
        if brand_norm and brand_norm not in (norm_key, clean_norm if clean_name else None):
            mappings[brand_norm] = entry

    try:
        MAPPINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MAPPINGS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(mappings, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved product mapping for '{raw_clean}' -> '{clean_title}' to {MAPPINGS_FILE_PATH.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to write to {MAPPINGS_FILE_PATH}: {e}")
        return False


def seed_database_from_mappings(db: Session) -> Dict[str, int]:
    """Seed the provided database session with canonical items and aliases from product_mappings.json.
    Reuses existing generic items if already present and avoids duplicate alias insertions.
    """
    mappings = load_product_mappings()
    if not mappings:
        logger.info("No product mappings found to seed.")
        return {"items_created": 0, "aliases_created": 0}

    items_created = 0
    aliases_created = 0

    # In-memory tracking to prevent duplicates across mappings
    seen_items: Dict[str, Item] = {it.canonical_name.lower(): it for it in db.query(Item).all()}
    seen_aliases = {a[0].lower() for a in db.query(ItemAlias.raw_alias).all()}

    # Group unique generic items
    for norm_key, entry in mappings.items():
        generic_title = entry.get("generic_name", "").strip().title()
        if not generic_title:
            continue

        gen_key = generic_title.lower()
        category = entry.get("category", "Pantry")
        standard_unit = entry.get("standard_unit", "count")
        is_bulk = entry.get("is_bulk", False)

        # Get or create canonical generic item
        if gen_key in seen_items:
            item = seen_items[gen_key]
        else:
            item = Item(
                canonical_name=generic_title,
                category=category,
                standard_unit=standard_unit,
                default_shelf_life_days=14 if "produce" in category.lower() else (10 if "dairy" in category.lower() else 180),
                is_bulk=is_bulk,
                is_active=True,
                is_grocery=True
            )
            db.add(item)
            db.flush()
            seen_items[gen_key] = item
            items_created += 1

        # Collect candidate aliases for this entry
        aliases_to_check = set()
        raw_name = entry.get("raw_name")
        if raw_name:
            aliases_to_check.add(raw_name.strip().lower())
        clean_name = entry.get("clean_name")
        if clean_name:
            aliases_to_check.add(clean_name.strip().lower())
        brand_name = entry.get("brand_name")
        if brand_name:
            aliases_to_check.add(brand_name.strip().lower())

        for alias_str in aliases_to_check:
            a_clean = alias_str.strip().lower()
            if not a_clean or a_clean in seen_aliases:
                continue
            seen_aliases.add(a_clean)
            alias = ItemAlias(
                canonical_item_id=item.id,
                raw_alias=a_clean,
                match_confidence=1.0,
                source="mappings_seed"
            )
            db.add(alias)
            aliases_created += 1

    db.commit()
    logger.info(f"Seeded {items_created} generic items and {aliases_created} aliases from product_mappings.json.")
    return {"items_created": items_created, "aliases_created": aliases_created}
