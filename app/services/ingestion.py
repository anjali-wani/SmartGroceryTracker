import io
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from sqlalchemy.orm import Session

from app.models import PurchaseLog, Inventory, InventoryStatus, Item, ItemAlias, ReceiptUpload
from app.services.inventory_service import reconcile_repurchased_inventory
from app.services.analytics import determine_preferred_store
from app.normalizer import extract_quantity_and_unit, UNIT_MAP, normalize_item_name, format_store_name, convert_quantity
from app.services.mapping_service import save_product_mapping, load_product_mappings
from app.services.llm_resolver import parse_total_quantity

NON_GROCERY_KEYWORDS = [
    "shoe", "shoes", "sneaker", "sneakers", "sandal", "sandals", "boot", "boots",
    "shirt", "pants", "sock", "socks", "clothing", "apparel", "wear", "jacket",
    "hanger", "hangers", "planter", "pot", "plant pot", "soil", "pomix", "potting",
    "hardware", "battery", "batteries", "cable", "electronic", "electronics", "charger",
    "appliance", "tool", "tools", "bag", "paper bag", "shopping bag", "bagfee",
    "cleaner", "detergent", "soap", "shampoo", "candle", "candles", "towel", "blanket",
    "bedsheet", "pillow", "canvas", "paint", "clay", "crayon", "memo book", "ribbon", "pen", "bic"
]

NON_GROCERY_CATEGORIES = [
    "non-grocery", "non grocery", "apparel", "shoes", "footwear", "clothing",
    "crafts", "art supplies", "craft", "home goods", "household / apparel",
    "household / bags", "supplies", "stationery", "office supplies", "lawn & garden",
    "lawn", "garden", "electronics", "hardware", "personal care"
]

def is_non_grocery_text(name: str, cat: Optional[str] = None) -> bool:
    if cat and any(k in cat.lower() for k in NON_GROCERY_CATEGORIES):
        return True
    text = f"{name} {cat or ''}".lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in NON_GROCERY_KEYWORDS)

from app.resolution import EntityResolver
from app.schemas import CSVUploadSummary, ProcessedLineItem

DEFAULT_9_COLUMNS = [
    "Date", "Store Name", "Item Description", "Category", 
    "Total Price", "Quantity", "Unit", "Unit Price", "Pricing Type"
]


def is_date_string(val: Any) -> bool:
    """Check if value starts with a date pattern YYYY-MM-DD or MM/DD/YYYY."""
    s = str(val).strip()
    return bool(re.match(r"^(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", s))


def load_dataframe_safely(file_bytes: bytes) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Load DataFrame and detect if CSV has a header row or is headerless.
    
    If headerless and contains 9 columns, maps directly to user's format:
    Date, Store Name, Item Description, Category, Total Price, Quantity, Unit, Unit Price, Pricing Type
    """
    # First, attempt to read first line to inspect
    sample_text = file_bytes[:1024].decode("utf-8", errors="replace")
    first_line = sample_text.splitlines()[0] if sample_text.splitlines() else ""
    first_tokens = [t.strip() for t in first_line.split(",")]

    # Check if first line is a data row (e.g. begins with a date like 2026-09-06)
    is_headerless = False
    if first_tokens and is_date_string(first_tokens[0]):
        is_headerless = True

    if is_headerless and len(first_tokens) == 9:
        df = pd.read_csv(io.BytesIO(file_bytes), header=None, names=DEFAULT_9_COLUMNS, skipinitialspace=True)
    elif is_headerless:
        # Fallback headerless with generic N columns
        df = pd.read_csv(io.BytesIO(file_bytes), header=None, skipinitialspace=True)
        if df.shape[1] == 9:
            df.columns = DEFAULT_9_COLUMNS
    else:
        df = pd.read_csv(io.BytesIO(file_bytes), skipinitialspace=True)

    col_map = detect_csv_columns(df)
    return df, col_map


def detect_csv_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Auto-map common CSV header aliases to required internal fields."""
    col_map = {}
    normalized_cols = {str(c).strip().lower().replace("_", " "): c for c in df.columns}

    # Item / Product Description column
    for candidate in [
        "item description", "product description", "item", "product", 
        "description", "name", "item name", "product name", "raw text"
    ]:
        if candidate in normalized_cols:
            col_map["item"] = normalized_cols[candidate]
            break

    # Total Price / Cost column
    for candidate in [
        "receipt price ($)", "receipt price", "total price ($)", "price ($)",
        "total price", "total", "price", "cost", "amount", 
        "subtotal", "item price", "total amount", "receipt amount"
    ]:
        if candidate in normalized_cols:
            col_map["price"] = normalized_cols[candidate]
            break

    # Unit Price column
    for candidate in [
        "normalized unit price ($)", "normalized unit price", "unit price ($)",
        "unit price", "price per unit", "unit cost", "rate"
    ]:
        if candidate in normalized_cols:
            col_map["unit_price"] = normalized_cols[candidate]
            break

    # Quantity column
    for candidate in [
        "weight / qty", "weight/qty", "weight qty", "qty / weight",
        "weight", "quantity", "qty", "count", "units"
    ]:
        if candidate in normalized_cols:
            col_map["quantity"] = normalized_cols[candidate]
            break

    # Unit of Measure column
    for candidate in ["unit", "uom", "measure", "unit of measure"]:
        if candidate in normalized_cols:
            col_map["unit"] = normalized_cols[candidate]
            break

    # Standard Unit column
    for candidate in ["std unit", "standard unit", "std_unit", "pricing unit", "pricing type", "std uom"]:
        if candidate in normalized_cols:
            col_map["std_unit"] = normalized_cols[candidate]
            break

    # Date column
    for candidate in ["date", "purchase date", "bill date", "transaction date"]:
        if candidate in normalized_cols:
            col_map["date"] = normalized_cols[candidate]
            break

    # Store Name column
    for candidate in [
        "store / outlet", "store/outlet", "outlet",
        "store name", "store", "vendor", "merchant", "retailer"
    ]:
        if candidate in normalized_cols:
            col_map["store"] = normalized_cols[candidate]
            break

    # Category column
    for candidate in ["category", "dept", "department", "food category"]:
        if candidate in normalized_cols:
            col_map["category"] = normalized_cols[candidate]
            break

    return col_map


def parse_std_unit(std_unit_str: Optional[str], item_unit: Optional[str] = None) -> Tuple[float, str]:
    """Extract (scale_factor, base_unit) from standard unit string like 'per 100g', 'per oz', 'per lb'.
    
    scale_factor represents how many base units (item_unit) the normalized unit price represents.
    For example:
      'per 100g' with item_unit='g'     -> factor=100.0, base_unit='g'
      'per oz'   with item_unit='oz'    -> factor=1.0,   base_unit='oz'
      'per lb'   with item_unit='lb'    -> factor=1.0,   base_unit='lb'
      'per unit' with item_unit='count' -> factor=1.0,   base_unit='count'
    """
    if not std_unit_str or pd.isna(std_unit_str):
        return 1.0, (item_unit or "count")

    clean = re.sub(r"^(?:per|/)\s*", "", str(std_unit_str).strip().lower())
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?", clean)
    if m:
        factor = float(m.group(1))
        unit_str = (m.group(2) or "").strip()
    else:
        factor = 1.0
        unit_str = clean.strip()

    norm_unit = UNIT_MAP.get(unit_str, unit_str or item_unit or "count")
    if norm_unit in ["unit", "ea", "ct"]:
        norm_unit = "count"

    # Scale factor relative to item_unit if there is a known prefix/unit difference
    if item_unit == "g" and norm_unit == "kg":
        factor = factor * 1000.0
    elif item_unit == "kg" and norm_unit == "g":
        factor = factor / 1000.0
    elif item_unit == "oz" and norm_unit == "lb":
        factor = factor * 16.0
    elif item_unit == "lb" and norm_unit == "oz":
        factor = factor / 16.0

    return (factor if factor > 0 else 1.0), (norm_unit or item_unit or "count")


def parse_date_safely(date_val: Any) -> date:
    """Parse date from string or timestamp with common formats."""
    if pd.isna(date_val) or not date_val:
        return date.today()

    date_str = str(date_val).strip()
    for fmt in [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", 
        "%m-%d-%Y", "%d-%m-%Y", "%Y.%m.%d", "%b %d, %Y", "%B %d, %Y"
    ]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return date.today()


def clean_currency_val(val: Any) -> Optional[float]:
    """Helper to convert string like '$5.99' or '5,99' to float."""
    if pd.isna(val) or val is None:
        return None
    try:
        s = str(val).replace("$", "").replace(",", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return None


def process_receipt_csv(file_bytes: bytes, db: Session, household_id: int = 1, filename: str = "receipt.csv") -> CSVUploadSummary:
    """Process raw CSV bill upload, run normalization, entity resolution, and update inventory.
    
    Seamlessly handles CSVs WITH or WITHOUT header row.
    """
    df, col_map = load_dataframe_safely(file_bytes)

    if "item" not in col_map:
        raise ValueError(
            f"Could not detect an item/product description column in CSV. "
            f"Please ensure your CSV either includes a header row with 'Item Description', "
            f"or follows the standard 9-column format: "
            f"Date, Store Name, Item Description, Category, Total Price, Quantity, Unit, Unit Price, Pricing Type."
        )

    resolver = EntityResolver(db)

    processed_items: List[ProcessedLineItem] = []
    total_amount = 0.0
    matched_count = 0
    unresolved_count = 0

    latest_date = date.today()
    primary_store = "Grocery Store"

    # Maintain separate bill records per (store_name, date) combination
    bills_map: Dict[Tuple[str, date], ReceiptUpload] = {}
    touched_canonical_ids: set = set()

    for _, row in df.iterrows():
        raw_item_str = str(row[col_map["item"]]).strip()
        if not raw_item_str or raw_item_str.lower() in ["nan", "none", ""]:
            continue

        # Extract units and clean name from raw string
        clean_name, extracted_qty, extracted_unit = extract_quantity_and_unit(raw_item_str)

        # 1. Quantity handling
        if "quantity" in col_map and pd.notna(row[col_map["quantity"]]):
            try:
                explicit_qty = float(row[col_map["quantity"]])
                if explicit_qty > 0:
                    extracted_qty = explicit_qty
            except (ValueError, TypeError):
                pass

        # 2. Unit handling
        if "unit" in col_map and pd.notna(row[col_map["unit"]]):
            raw_unit = str(row[col_map["unit"]]).strip().lower()
            if raw_unit in UNIT_MAP:
                extracted_unit = UNIT_MAP[raw_unit]
            elif raw_unit and raw_unit not in ["nan", "none"]:
                extracted_unit = raw_unit

        # 2b. Standard Unit handling (e.g. 'per 100g', 'per oz', 'per lb', 'per unit')
        std_unit_str = None
        if "std_unit" in col_map and pd.notna(row[col_map["std_unit"]]):
            std_unit_str = str(row[col_map["std_unit"]]).strip()
        scale_factor, _ = parse_std_unit(std_unit_str, extracted_unit)

        # 3. Price handling: Total Price or fallback to (Quantity / scale_factor) * Unit Price
        price_val = None
        if "price" in col_map and pd.notna(row[col_map["price"]]):
            price_val = clean_currency_val(row[col_map["price"]])

        raw_unit_price_val = None
        if "unit_price" in col_map and pd.notna(row[col_map["unit_price"]]):
            raw_unit_price_val = clean_currency_val(row[col_map["unit_price"]])

        if raw_unit_price_val is None:
            rate_m = re.search(r"@\s*\$?(\d+(?:\.\d+)?)(?:\s*/\s*[a-zA-Z]+)?", raw_item_str)
            if rate_m:
                try:
                    raw_unit_price_val = float(rate_m.group(1))
                except ValueError:
                    pass

        if price_val is None and raw_unit_price_val is not None and extracted_qty > 0:
            price_val = round((extracted_qty / scale_factor) * raw_unit_price_val, 2)

        if price_val is not None:
            total_amount += price_val

        # Base unit price (per single base unit like 1g, 1oz, 1lb, 1 count)
        calc_unit_price = None
        if raw_unit_price_val is not None and scale_factor > 0:
            calc_unit_price = round(raw_unit_price_val / scale_factor, 4)
        elif price_val is not None and extracted_qty > 0:
            calc_unit_price = round(price_val / extracted_qty, 4)

        # 4. Row-level Date and Store Name
        row_date = date.today()
        if "date" in col_map and pd.notna(row[col_map["date"]]):
            row_date = parse_date_safely(row[col_map["date"]])
            latest_date = row_date

        row_store = primary_store
        if "store" in col_map and pd.notna(row[col_map["store"]]):
            row_store = format_store_name(row[col_map["store"]])
            primary_store = row_store
        else:
            row_store = format_store_name(row_store)

        # Bill record per (row_store, row_date)
        bill_key = (row_store, row_date)
        if bill_key not in bills_map:
            existing_bill = db.query(ReceiptUpload).filter(
                ReceiptUpload.household_id == household_id,
                ReceiptUpload.store_name == row_store,
                ReceiptUpload.bill_date == row_date
            ).first()
            if not existing_bill:
                existing_bill = ReceiptUpload(
                    household_id=household_id,
                    filename=filename,
                    store_name=row_store,
                    bill_date=row_date,
                    total_items=0,
                    total_amount=0.0
                )
                db.add(existing_bill)
                db.flush()
            bills_map[bill_key] = existing_bill

        bill_record = bills_map[bill_key]
        bill_record.total_items += 1
        if price_val:
            bill_record.total_amount += price_val

        # 5. Row-level Category
        row_category = None
        if "category" in col_map and pd.notna(row[col_map["category"]]):
            row_category = str(row[col_map["category"]]).strip()

        # 6. Entity Resolution (Exact -> RapidFuzz -> Fallback)
        raw_receipt_unit = str(row[col_map["unit"]]).strip() if "unit" in col_map and pd.notna(row[col_map["unit"]]) else extracted_unit
        res = resolver.resolve(
            clean_name,
            store_name=row_store,
            purchase_date=row_date,
            price=price_val,
            receipt_unit=raw_receipt_unit,
            receipt_category=row_category,
            raw_line=raw_item_str
        )

        # Check if quantity is mentioned in counts / pack units
        is_count_quantity = (
            extracted_unit in ("count", "pack", "piece", "ea", "ct", "pk", "box", "dozen", "unit")
            or ("unit" in col_map and str(row[col_map["unit"]]).strip().lower() in ("count", "ea", "each", "ct", "pk", "pack", "pc", "pcs", "unit", "units"))
        )

        # If quantity is in counts/pack units, extract total_quantity from LLM response or product_mappings.json
        if is_count_quantity:
            total_qty_str = None
            if res.llm_resolved and getattr(res.llm_resolved, "total_quantity", None):
                total_qty_str = res.llm_resolved.total_quantity

            # Check in product_mappings.json cache if not already found in res.llm_resolved
            if not total_qty_str and hasattr(resolver, "file_mappings") and resolver.file_mappings:
                for candidate_key in [raw_item_str, clean_name, getattr(res.canonical_item, "canonical_name", None)]:
                    if candidate_key:
                        norm_cand = normalize_item_name(candidate_key)
                        if norm_cand in resolver.file_mappings and resolver.file_mappings[norm_cand].get("total_quantity"):
                            total_qty_str = resolver.file_mappings[norm_cand]["total_quantity"]
                            break

            if total_qty_str:
                t_qty, t_unit = parse_total_quantity(total_qty_str)
                if t_qty and t_qty > 0 and t_unit:
                    if t_unit not in ("count", "pack", "piece"):
                        extracted_qty = t_qty
                        extracted_unit = t_unit
                    else:
                        extracted_qty = max(extracted_qty, t_qty)
                        extracted_unit = "count"
                    if price_val is not None and extracted_qty > 0:
                        calc_unit_price = round(price_val / extracted_qty, 4)

        if res.canonical_item:
            matched_count += 1
            canonical_id = res.canonical_item.id
            canonical_name = res.canonical_item.canonical_name
            category = res.canonical_item.category
            shelf_life = res.canonical_item.default_shelf_life_days
            status = "matched"
            matched_via_val = res.matched_via
            confidence_val = res.confidence

            if (not res.canonical_item.preferred_store or res.canonical_item.preferred_store == "Grocery Store") and row_store and row_store != "Grocery Store":
                res.canonical_item.preferred_store = row_store

            # If item or resolution indicates Non-Grocery, enforce on canonical item
            is_non_groc = (
                category.lower() in ("non-grocery", "non grocery")
                or (res.llm_resolved and res.llm_resolved.category and res.llm_resolved.category.lower() in ("non-grocery", "non grocery"))
                or (row_category and row_category.lower() in ("non-grocery", "non grocery"))
                or is_non_grocery_text(canonical_name, row_category)
            )
            if is_non_groc:
                res.canonical_item.category = "Non-Grocery"
                res.canonical_item.is_grocery = False
                category = "Non-Grocery"

            # If resolved via Gemini or persistent mapping cache, register aliases & update mapping file
            if res.matched_via in ("gemini_llm", "product_mapping") or res.llm_resolved:
                aliases_to_add = set()
                if raw_item_str:
                    aliases_to_add.add(raw_item_str.strip().lower())
                if clean_name:
                    aliases_to_add.add(clean_name.strip().lower())
                if res.llm_resolved and res.llm_resolved.canonical_name:
                    aliases_to_add.add(res.llm_resolved.canonical_name.strip().lower())

                for a_str in aliases_to_add:
                    if a_str and not db.query(ItemAlias).filter(ItemAlias.raw_alias == a_str).first():
                        db.add(ItemAlias(
                            canonical_item_id=res.canonical_item.id,
                            raw_alias=a_str,
                            match_confidence=res.confidence,
                            source="gemini_mapped" if res.matched_via == "gemini_llm" else "mappings_cache"
                        ))
                        resolver.alias_map[normalize_item_name(a_str)] = (res.canonical_item, 1.0)
                        resolver.fuzzy_corpus[normalize_item_name(a_str)] = res.canonical_item

                # Only save to product_mappings.json if LLM call was successful
                if res.llm_resolved and getattr(res.llm_resolved, "llm_success", False):
                    try:
                        brand_val = res.llm_resolved.canonical_name if res.llm_resolved.canonical_name else (clean_name or raw_item_str)
                        save_product_mapping(
                            raw_name=raw_item_str,
                            clean_name=clean_name,
                            brand_name=brand_val,
                            generic_name=res.canonical_item.canonical_name,
                            category=res.canonical_item.category,
                            standard_unit=res.canonical_item.standard_unit,
                            is_bulk=res.canonical_item.is_bulk,
                            total_quantity=getattr(res.llm_resolved, "total_quantity", None)
                        )
                        resolver.file_mappings = load_product_mappings()
                    except Exception as e:
                        logger.error(f"Error saving product mapping for '{raw_item_str}': {e}")
        else:
            # Automated Canonical Item Creation using generic_name from LLM / file mapping
            if res.llm_resolved and res.llm_resolved.generic_name:
                canonical_title = res.llm_resolved.generic_name.strip().title()
                category = res.llm_resolved.category or row_category or "Pantry"
                item_standard_unit = res.llm_resolved.standard_unit or extracted_unit or "count"
                is_bulk = res.llm_resolved.is_bulk
            elif res.llm_resolved and res.llm_resolved.canonical_name:
                canonical_title = res.llm_resolved.canonical_name.strip().title()
                category = res.llm_resolved.category or row_category or "Pantry"
                item_standard_unit = res.llm_resolved.standard_unit or extracted_unit or "count"
                is_bulk = res.llm_resolved.is_bulk
            else:
                canonical_title = clean_name.strip().title() if clean_name else raw_item_str.strip().title()
                category = row_category or "Pantry"
                item_standard_unit = extracted_unit or "count"
                is_bulk = False
            
            # Check if this item is non-grocery (e.g. shoes, planter, apparel, hardware, electronics, crafts)
            if category.lower() in ("non-grocery", "non grocery") or is_non_grocery_text(canonical_title, row_category):
                category = "Non-Grocery"
                is_grocery = False
                shelf_life = 365
                is_bulk = False
            else:
                is_grocery = True
                cat_lower = category.lower()
                if any(k in cat_lower for k in ["produce", "fruit", "veg"]):
                    shelf_life = 7
                elif any(k in cat_lower for k in ["dairy", "cheese", "milk", "egg", "bakery", "bread"]):
                    shelf_life = 10
                elif any(k in cat_lower for k in ["meat", "seafood", "poultry", "fish"]):
                    shelf_life = 5
                elif any(k in cat_lower for k in ["grain", "rice", "flour", "spice", "oil", "pantry"]):
                    shelf_life = 180
                else:
                    shelf_life = 14

            # Check if canonical_title exists in db already (case-insensitive)
            existing_item = db.query(Item).filter(Item.canonical_name.ilike(canonical_title)).first()
            if not existing_item:
                new_item = Item(
                    canonical_name=canonical_title,
                    category=category,
                    standard_unit=item_standard_unit,
                    default_shelf_life_days=shelf_life,
                    is_bulk=is_bulk,
                    is_active=True,
                    is_grocery=is_grocery,
                    default_unit_price=calc_unit_price,
                    preferred_store=row_store
                )
                db.add(new_item)
                db.flush()
            else:
                new_item = existing_item
                if (not new_item.default_unit_price or new_item.default_unit_price <= 0) and calc_unit_price:
                    new_item.default_unit_price = calc_unit_price
                if (not new_item.preferred_store or new_item.preferred_store == "Grocery Store") and row_store and row_store != "Grocery Store":
                    new_item.preferred_store = row_store
                if category == "Non-Grocery" or is_grocery is False:
                    new_item.category = "Non-Grocery"
                    new_item.is_grocery = False

            # Register raw receipt text, clean name, and brand name as permanent aliases
            aliases_to_add = set()
            if raw_item_str:
                aliases_to_add.add(raw_item_str.strip().lower())
            if clean_name:
                aliases_to_add.add(clean_name.strip().lower())
            if res.llm_resolved and res.llm_resolved.canonical_name:
                aliases_to_add.add(res.llm_resolved.canonical_name.strip().lower())

            for alias_text in aliases_to_add:
                if alias_text and not db.query(ItemAlias).filter(ItemAlias.raw_alias == alias_text).first():
                    new_alias = ItemAlias(
                        canonical_item_id=new_item.id,
                        raw_alias=alias_text,
                        match_confidence=1.0,
                        source="gemini_mapped" if res.llm_resolved else "auto_created"
                    )
                    db.add(new_alias)
                    resolver.alias_map[normalize_item_name(alias_text)] = (new_item, 1.0)
                    resolver.fuzzy_corpus[normalize_item_name(alias_text)] = new_item

            # Save mapping to data/product_mappings.json ONLY if LLM call was successful and no errors occurred
            if res.llm_resolved and getattr(res.llm_resolved, "llm_success", False):
                try:
                    brand_val = res.llm_resolved.canonical_name if res.llm_resolved.canonical_name else (clean_name or raw_item_str)
                    save_product_mapping(
                        raw_name=raw_item_str,
                        clean_name=clean_name,
                        brand_name=brand_val,
                        generic_name=canonical_title,
                        category=category,
                        standard_unit=item_standard_unit,
                        is_bulk=is_bulk,
                        total_quantity=getattr(res.llm_resolved, "total_quantity", None)
                    )
                    resolver.file_mappings = load_product_mappings()
                except Exception as e:
                    logger.error(f"Error saving product mapping for '{raw_item_str}': {e}")

            # Update resolver in-memory corpus so subsequent rows in this CSV resolve immediately
            resolver.canonical_map[normalize_item_name(new_item.canonical_name)] = new_item
            resolver.fuzzy_corpus[normalize_item_name(new_item.canonical_name)] = new_item
            if new_item not in resolver.items:
                resolver.items.append(new_item)

            canonical_id = new_item.id
            canonical_name = new_item.canonical_name
            shelf_life = new_item.default_shelf_life_days
            matched_count += 1
            status = "auto_created"
            matched_via_val = res.matched_via or "auto_created"
            confidence_val = res.confidence or 1.0

        if canonical_id:
            touched_canonical_ids.add(canonical_id)

        # Standardize quantity and unit to match the canonical item's standard_unit if compatible
        target_item = db.query(Item).filter(Item.id == canonical_id).first() if canonical_id else None
        if target_item and extracted_unit not in ("count", "pack", "piece") and target_item.standard_unit in ("count", "pack", "piece"):
            target_item.standard_unit = extracted_unit

        target_std_unit = (target_item.standard_unit if target_item else extracted_unit) or "count"

        log_qty = extracted_qty
        log_unit = extracted_unit
        log_unit_price = calc_unit_price

        if target_std_unit and extracted_unit and target_std_unit != extracted_unit:
            conv = convert_quantity(extracted_qty, from_unit=extracted_unit, to_unit=target_std_unit)
            if conv is not None:
                log_qty = round(conv, 2)
                log_unit = target_std_unit
                if price_val is not None and log_qty > 0:
                    log_unit_price = round(price_val / log_qty, 4)
                elif calc_unit_price is not None:
                    conv_1 = convert_quantity(1.0, from_unit=target_std_unit, to_unit=extracted_unit)
                    if conv_1:
                        log_unit_price = round(calc_unit_price * conv_1, 4)

        if target_item and log_unit_price and (not target_item.default_unit_price or target_item.default_unit_price <= 0):
            target_item.default_unit_price = log_unit_price

        # 7. Record into PurchaseLog
        purchase_log = PurchaseLog(
            household_id=household_id,
            purchase_date=row_date,
            store_name=row_store,
            raw_text=raw_item_str,
            canonical_item_id=canonical_id,
            quantity=log_qty,
            unit=log_unit,
            price=price_val,
            unit_price=log_unit_price,
            matched_via=matched_via_val,
            confidence=confidence_val,
            bill_id=bill_record.id
        )
        db.add(purchase_log)
        db.flush()

        # 8. Update Active Inventory with Repurchase Auto-Consumption:
        # Check if item is grocery
        item_is_grocery = target_item.is_grocery if (target_item and hasattr(target_item, 'is_grocery')) else True
        if target_item and target_item.category == "Non-Grocery":
            item_is_grocery = False

        if canonical_id and item_is_grocery and "supplies" not in (category or "").lower():
            # If purchased again, previous active stock is consumed!
            prev_active = (
                db.query(Inventory)
                .filter(
                    Inventory.household_id == household_id,
                    Inventory.canonical_item_id == canonical_id,
                    Inventory.status == InventoryStatus.ACTIVE,
                    Inventory.purchase_date <= row_date
                )
                .all()
            )
            for old_inv in prev_active:
                old_inv.current_quantity = 0.0
                old_inv.status = InventoryStatus.CONSUMED

            inventory_item = Inventory(
                household_id=household_id,
                canonical_item_id=canonical_id,
                purchase_log_id=purchase_log.id,
                current_quantity=log_qty,
                unit=log_unit,
                purchase_date=row_date,
                expiration_date=None,
                status=InventoryStatus.ACTIVE,
                store_name=row_store,
                price=price_val
            )
            db.add(inventory_item)

        processed_items.append(ProcessedLineItem(
            raw_line=raw_item_str,
            clean_name=clean_name,
            canonical_name=canonical_name,
            category=category,
            quantity=log_qty,
            unit=log_unit,
            price=price_val,
            matched_via=matched_via_val,
            confidence=confidence_val,
            status=status
        ))

    # Finalize all bill records
    for b in bills_map.values():
        b.total_amount = round(b.total_amount, 2)
    
    first_bill_id = list(bills_map.values())[0].id if bills_map else None

    # Update preferred_store and default_unit_price for all touched items based on purchase frequency (if tied, take the store from the last entry)
    for cid in touched_canonical_ids:
        c_item = db.query(Item).filter(Item.id == cid).first()
        if c_item:
            best_store = determine_preferred_store(cid, db, household_id=household_id, fallback_store=c_item.preferred_store)
            if best_store:
                c_item.preferred_store = best_store

            # Synchronize default_unit_price with preferred store's most recent purchase
            c_logs = (
                db.query(PurchaseLog)
                .filter(
                    PurchaseLog.canonical_item_id == cid,
                    PurchaseLog.household_id == household_id,
                    PurchaseLog.unit_price.isnot(None),
                    PurchaseLog.unit_price > 0
                )
                .order_by(PurchaseLog.purchase_date.desc(), PurchaseLog.id.desc())
                .all()
            )
            pref_store_clean = (c_item.preferred_store or "").lower()
            target_unit = c_item.standard_unit or "count"

            def get_compatible_rate(p: PurchaseLog) -> Optional[float]:
                if not p.unit_price or p.unit_price <= 0:
                    return None
                if p.unit == target_unit:
                    return p.unit_price
                conv_f = convert_quantity(1.0, from_unit=p.unit, to_unit=target_unit)
                if conv_f and conv_f > 0:
                    return round(p.unit_price / conv_f, 4)
                return None

            best_rate = None
            # 1. Look for preferred store with compatible unit
            for p in c_logs:
                if p.store_name and format_store_name(p.store_name).lower() == pref_store_clean:
                    rate = get_compatible_rate(p)
                    if rate is not None:
                        best_rate = rate
                        break

            # 2. Look for any store with compatible unit
            if best_rate is None:
                for p in c_logs:
                    rate = get_compatible_rate(p)
                    if rate is not None:
                        best_rate = rate
                        break

            if best_rate is not None:
                c_item.default_unit_price = best_rate

    reconcile_repurchased_inventory(db, household_id)
    db.commit()

    return CSVUploadSummary(
        store_name=primary_store,
        purchase_date=latest_date,
        total_rows=len(processed_items),
        matched_rows=matched_count,
        unresolved_rows=unresolved_count,
        total_amount=round(total_amount, 2),
        processed_items=processed_items,
        bill_id=first_bill_id or 1
    )
