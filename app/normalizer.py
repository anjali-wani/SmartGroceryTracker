import re
from typing import Tuple, Optional

UNIT_MAP = {
    # Volume
    "gal": "gallon",
    "gallon": "gallon",
    "gallons": "gallon",
    "1/2 gal": "half_gallon",
    "half gal": "half_gallon",
    "qt": "quart",
    "quart": "quart",
    "pt": "pint",
    "pint": "pint",
    "fl oz": "fl_oz",
    "floz": "fl_oz",
    "fl_oz": "fl_oz",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "l": "liter",
    "ltr": "liter",
    "liter": "liter",
    "liters": "liter",
    "ml": "ml",

    # Weight
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilo": "kg",
    "kilogram": "kg",

    # Count / Packaging
    "ct": "count",
    "ea": "count",
    "each": "count",
    "gm": "g",
    "gms": "g",
    "count": "count",
    "pk": "pack",
    "pack": "pack",
    "pc": "piece",
    "pcs": "piece",
    "dozen": "dozen",
    "bunch": "bunch",
    "bag": "bag",
    "box": "box",
    "can": "can",
    "bottle": "bottle",
    "jar": "jar",
}

# Regex to detect unit strings:
# Multi-character units can have optional quantity (e.g. "1 Gal" or "milk gal")
# Single-letter units (g, l, ml) MUST have an explicit number prefix (e.g. "500g", "1L")
UNIT_REGEX = re.compile(
    r"(?:(?P<qty>\d+(?:\.\d+)?|\d+\s*/\s*\d+)\s*)?(?P<unit>gal(?:lon)?s?|fl\.?\s*oz|oz|lbs?|pounds?|ct|count|pk|pack|pcs?|dozen|kg|grams?|liters?|ltr)\b|"
    r"(?P<qty_num>\d+(?:\.\d+)?|\d+\s*/\s*\d+)\s*(?P<unit_single>g|l|ml)\b",
    re.IGNORECASE
)

NOISE_PATTERNS = [
    r"^(\d{4,14})\s+",              # Leading UPC / SKU barcodes
    r"#\d+\b",                       # #1234
    r"\b(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{8,16}\b",           # Store transaction/tax hashes
    r"\$\d+(?:\.\d{2})?\b",          # Leftover prices like $4.99 with dollar sign
    r"[*@%]",                        # Asterisks or tax symbols
    r"\b(tax|subtotal|total|f)\b",   # Receipt metadata words
]


def clean_raw_string(text: str) -> str:
    """Strip noisy store prefixes, SKU barcodes, and unwanted punctuation."""
    cleaned = text.strip()
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Collapse repeated whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_quantity_and_unit(text: str) -> Tuple[str, float, str]:
    """Extract quantity and standard unit from a line item, returning clean product name.
    
    Example:
        'ORGANIC WHOLE MILK 1 GAL' -> ('ORGANIC WHOLE MILK', 1.0, 'gallon')
        'KIRKLAND EGGS 24 CT' -> ('KIRKLAND EGGS', 24.0, 'count')
        'BANANAS 2.5 LB' -> ('BANANAS', 2.5, 'lb')
        'CHEDDAR CHEESE 16OZ' -> ('CHEDDAR CHEESE', 16.0, 'oz')
        'BEETROOT 0.89 LB' -> ('BEETROOT', 0.89, 'lb')
        'Beetroot per lb' -> ('Beetroot', 1.0, 'lb')
    """
    cleaned = clean_raw_string(text)
    match = UNIT_REGEX.search(cleaned)

    extracted_qty = 1.0
    extracted_unit = "count"

    if match:
        qty_str = match.group("qty") or match.group("qty_num")
        unit_str = match.group("unit") or match.group("unit_single")

        if qty_str:
            qty_str = qty_str.strip()
            if "/" in qty_str:
                parts = qty_str.split("/")
                try:
                    extracted_qty = float(parts[0]) / float(parts[1])
                except (ValueError, ZeroDivisionError):
                    extracted_qty = 1.0
            else:
                try:
                    extracted_qty = float(qty_str)
                except ValueError:
                    extracted_qty = 1.0

        if unit_str:
            unit_lower = unit_str.lower().strip()
            if unit_lower in UNIT_MAP:
                extracted_unit = UNIT_MAP[unit_lower]

        # Remove the matched unit segment from product name
        start, end = match.span()
        product_name = (cleaned[:start] + " " + cleaned[end:]).strip()
    else:
        product_name = cleaned

    # Clean up leftover 'per' preposition or rate notations
    product_name = re.sub(r"\bper\b", " ", product_name, flags=re.IGNORECASE)
    product_name = re.sub(r"\s+", " ", product_name).strip()
    return product_name, extracted_qty, extracted_unit


def normalize_item_name(name: str) -> str:
    """Canonicalize string: lowercase, remove non-alphanumeric, strip extra whitespace."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
