import io
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from sqlalchemy.orm import Session

from app.models import PurchaseLog, Inventory, InventoryStatus, Item
from app.normalizer import extract_quantity_and_unit, UNIT_MAP
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
        df = pd.read_csv(io.BytesIO(file_bytes), header=None, names=DEFAULT_9_COLUMNS)
    elif is_headerless:
        # Fallback headerless with generic N columns
        df = pd.read_csv(io.BytesIO(file_bytes), header=None)
        if df.shape[1] == 9:
            df.columns = DEFAULT_9_COLUMNS
    else:
        df = pd.read_csv(io.BytesIO(file_bytes))

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
        "total price", "total", "price", "cost", "amount", 
        "subtotal", "item price", "total amount"
    ]:
        if candidate in normalized_cols:
            col_map["price"] = normalized_cols[candidate]
            break

    # Unit Price column
    for candidate in ["unit price", "price per unit", "unit cost", "rate"]:
        if candidate in normalized_cols:
            col_map["unit_price"] = normalized_cols[candidate]
            break

    # Quantity column
    for candidate in ["quantity", "qty", "count", "units"]:
        if candidate in normalized_cols:
            col_map["quantity"] = normalized_cols[candidate]
            break

    # Unit of Measure column
    for candidate in ["unit", "uom", "measure", "unit of measure"]:
        if candidate in normalized_cols:
            col_map["unit"] = normalized_cols[candidate]
            break

    # Date column
    for candidate in ["date", "purchase date", "bill date", "transaction date"]:
        if candidate in normalized_cols:
            col_map["date"] = normalized_cols[candidate]
            break

    # Store Name column
    for candidate in ["store name", "store", "vendor", "merchant", "retailer"]:
        if candidate in normalized_cols:
            col_map["store"] = normalized_cols[candidate]
            break

    # Category column
    for candidate in ["category", "dept", "department", "food category"]:
        if candidate in normalized_cols:
            col_map["category"] = normalized_cols[candidate]
            break

    return col_map


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


def process_receipt_csv(file_bytes: bytes, db: Session, household_id: int = 1) -> CSVUploadSummary:
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

        # 3. Price handling: Total Price or fallback to Quantity * Unit Price
        price_val = None
        if "price" in col_map and pd.notna(row[col_map["price"]]):
            price_val = clean_currency_val(row[col_map["price"]])

        if price_val is None and "unit_price" in col_map and pd.notna(row[col_map["unit_price"]]):
            unit_price_val = clean_currency_val(row[col_map["unit_price"]])
            if unit_price_val is not None and extracted_qty > 0:
                price_val = round(extracted_qty * unit_price_val, 2)

        if price_val is not None:
            total_amount += price_val

        # 4. Row-level Date and Store Name
        row_date = date.today()
        if "date" in col_map and pd.notna(row[col_map["date"]]):
            row_date = parse_date_safely(row[col_map["date"]])
            latest_date = row_date

        row_store = primary_store
        if "store" in col_map and pd.notna(row[col_map["store"]]):
            row_store = str(row[col_map["store"]]).strip()
            primary_store = row_store

        # 5. Row-level Category
        row_category = None
        if "category" in col_map and pd.notna(row[col_map["category"]]):
            row_category = str(row[col_map["category"]]).strip()

        # 6. Entity Resolution (Exact -> RapidFuzz -> Fallback)
        res = resolver.resolve(clean_name)

        if res.canonical_item:
            matched_count += 1
            canonical_id = res.canonical_item.id
            canonical_name = res.canonical_item.canonical_name
            category = res.canonical_item.category
            shelf_life = res.canonical_item.default_shelf_life_days
            status = "matched"
        else:
            unresolved_count += 1
            canonical_id = None
            canonical_name = None
            category = row_category or "Uncategorized"
            shelf_life = 7
            status = "unresolved"

        # 7. Record into PurchaseLog
        purchase_log = PurchaseLog(
            household_id=household_id,
            purchase_date=row_date,
            store_name=row_store,
            raw_text=raw_item_str,
            canonical_item_id=canonical_id,
            quantity=extracted_qty,
            unit=extracted_unit,
            price=price_val,
            matched_via=res.matched_via,
            confidence=res.confidence
        )
        db.add(purchase_log)

        # 8. Update Active Inventory (skip non-food supplies like Paper Bag)
        if canonical_id and "supplies" not in (category or "").lower():
            expiration_date = row_date + timedelta(days=shelf_life)
            inventory_item = Inventory(
                household_id=household_id,
                canonical_item_id=canonical_id,
                current_quantity=extracted_qty,
                unit=extracted_unit,
                purchase_date=row_date,
                expiration_date=expiration_date,
                status=InventoryStatus.ACTIVE
            )
            db.add(inventory_item)

        processed_items.append(ProcessedLineItem(
            raw_line=raw_item_str,
            clean_name=clean_name,
            canonical_name=canonical_name,
            category=category,
            quantity=extracted_qty,
            unit=extracted_unit,
            price=price_val,
            matched_via=res.matched_via,
            confidence=res.confidence,
            status=status
        ))

    db.commit()

    return CSVUploadSummary(
        store_name=primary_store,
        purchase_date=latest_date,
        total_rows=len(processed_items),
        matched_rows=matched_count,
        unresolved_rows=unresolved_count,
        total_amount=round(total_amount, 2),
        processed_items=processed_items
    )
