import os
import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("llm_resolver")

class LLMResolvedItem(BaseModel):
    canonical_name: str = Field(..., description="Clean title-case product name")
    generic_name: Optional[str] = Field(None, description="Generic base grocery name in lowercase, e.g. 'milk' for 'Kirkland Signature Organic Milk' or 'KS_ORG_A2_MLK', 'apples' for 'Gala Apples', 'rice' for 'Basmati Rice'")
    category: str = Field(..., description="Category: Produce, Dairy, Pantry, Bakery, Meat, Snacks, Grains & Pasta")
    standard_unit: str = Field("count", description="Standard unit (lb, oz, gallon, count, g)")
    is_bulk: bool = Field(False, description="Whether item is typically bulk")
    matched_existing_canonical_name: Optional[str] = Field(None, description="Matched existing item name if alias")
    total_quantity: str = Field(
        ...,
        description="The aggregated total volume, weight, or count across the package or multi-pack items, taking into account store context (e.g. warehouse clubs like Costco sell Kirkland Signature Organic A2 milk 'KS ORG A2 PR' as a 3-pack of 0.5 gal = '1.5 gallons', while retail supermarkets like Safeway sell individual cartons = '1 gallon'). Always return the total net amount with its unit."
    )
    llm_success: bool = Field(False, description="Whether the LLM API call was successfully executed and returned valid data")


from pathlib import Path
from datetime import datetime
from app.normalizer import format_store_name

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GEMINI_CALLS_LOG_PATH = PROJECT_ROOT / "gemini_api_calls.log"

_last_gemini_call_time = 0.0


def wait_between_gemini_calls(delay: float = 4.0):
    """Enforce a 4-second sleep between successive Gemini API calls."""
    global _last_gemini_call_time
    if _last_gemini_call_time > 0:
        logger.info(f"Sleeping {delay}s between successive Gemini API calls...")
        time.sleep(delay)
    _last_gemini_call_time = time.time()


def log_gemini_api_call(
    product_name: str,
    store_name: Optional[str] = None,
    purchase_date: Optional[Any] = None,
    response_text: Optional[str] = None,
    error: Optional[str] = None,
):
    """Log Gemini API request and full response to gemini_api_calls.log."""
    date_str = str(purchase_date).strip() if purchase_date else "N/A"
    store_str = format_store_name(store_name) if store_name else "Unknown Store"
    prod_str = str(product_name).strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_entry = f"[{timestamp}] REQUEST  | Date: {date_str} | Store: {store_str} | Product: {prod_str}\n"
    if response_text:
        log_entry += f"[{timestamp}] RESPONSE | {response_text.strip()}\n"
    if error:
        log_entry += f"[{timestamp}] ERROR    | {error.strip()}\n"

    try:
        with open(GEMINI_CALLS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
            f.flush()
        logger.info(f"Logged Gemini API call for '{prod_str}' to {GEMINI_CALLS_LOG_PATH.name}")
    except Exception as e:
        logger.error(f"Failed to log Gemini API request to {GEMINI_CALLS_LOG_PATH}: {e}")


def resolve_with_gemini(
    raw_text: str,
    store_name: Optional[str] = None,
    existing_items: Optional[List[str]] = None,
    purchase_date: Optional[Any] = None,
    price: Optional[float] = None,
    receipt_unit: Optional[str] = None
) -> Optional[LLMResolvedItem]:
    """Resolve unrecognized item using Gemini Flash, with local heuristic fallback."""
    if os.getenv("DISABLE_LLM", "").lower() in ("true", "1", "yes"):
        fallback = fallback_heuristic_resolve(raw_text, store_name, existing_items)
        fallback.llm_success = False
        log_gemini_api_call(
            product_name=raw_text,
            store_name=store_name,
            purchase_date=purchase_date,
            response_text=f"(Local Heuristic - DISABLE_LLM=true) {fallback.model_dump_json()}"
        )
        return fallback

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        fallback = fallback_heuristic_resolve(raw_text, store_name, existing_items)
        fallback.llm_success = False
        log_gemini_api_call(
            product_name=raw_text,
            store_name=store_name,
            purchase_date=purchase_date,
            response_text=f"(Local Heuristic - No GEMINI_API_KEY) {fallback.model_dump_json()}"
        )
        return fallback

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        store_clean = format_store_name(store_name) if store_name else "Grocery Store"
        price_str = f" Receipt line price: ${price:.2f}." if price is not None and price > 0 else ""
        unit_str = f" Receipt unit: '{receipt_unit.strip()}'." if receipt_unit and receipt_unit.strip().lower() not in ("none", "nan", "") else ""
        prompt = (
            f"You are a grocery classification engine. Identify the product name, generic name, category, and unit for raw receipt item: '{raw_text}' from '{store_clean}'.{price_str}{unit_str}\n"
            f"Return the following fields:\n"
            f"1. canonical_name: Clean, title-case brand/product name (e.g. 'Kirkland Signature Organic Milk').\n"
            f"2. generic_name: The base/generic grocery name in lowercase. E.g. for 'KS_ORG_A2_MLK' or 'Kirkland Signature Organic Milk', generic_name is 'milk'; for 'Gala Apples', generic_name is 'apples'; for 'Deep Rice Flour', generic_name is 'rice flour'; for 'Veer Cashew Split', generic_name is 'cashews'.\n"
            f"3. category: Category (Produce, Dairy, Pantry, Bakery, Meat & Seafood, Snacks, Grains & Pasta, Spices / Pantry, etc.).\n"
            f"4. standard_unit: Standard unit (count, lb, oz, g, gallon, ml, etc.). If the receipt unit is 'EA', 'count', or 'unit', standard_unit for bunched or individual items should be 'count'.\n"
            f"5. is_bulk: Boolean indicating if typically purchased in bulk.\n"
            f"6. total_quantity: The aggregated total volume, weight, or count across the package or multi-pack items, taking into account the STORE CONTEXT and RECEIPT UNIT:\n"
            f"   - For warehouse clubs and bulk stores (e.g., Costco, Sam's Club, BJ's), use warehouse-specific packaging standards and multi-packs (e.g., at Costco, Kirkland Signature Organic A2 Milk 'KS ORG A2 PR' is sold as a 3-pack of 0.5 gallon cartons, so return '1.5 gallons'; Kirkland Signature organic whole milk is a 2-pack of 1-gallon jugs, so return '2 gallons'; eggs are sold as 2-dozen or 5-dozen).\n"
            f"   - For standard retail supermarkets (e.g., Safeway, Kroger, Ralphs), where milk is typically sold as individual 1-gallon or half-gallon cartons, return the individual retail carton size (e.g., '1 gallon' or '0.5 gallon').\n"
            f"   - For bunched produce, herbs, and leafy greens (e.g., 'CILANTRO', 'METHI', 'MINT', 'PALAK', 'SPINACH BUNCH', 'CURRY LEAVES', 'GREEN ONIONS') especially when receipt unit is 'EA', 'count', or 'unit', return '1 count'.\n"
            f"   - For ethnic or specialty grocers (e.g., New India Bazar, Apni Mandi), use standard package sizes indicated in the item name or typical packaging (e.g., '200g' for 'VEER FENNEL SEEDS 200GM').\n"
            f"   - For single produce items (e.g., 'LEMON', 'AVOCADO'), return '1 count'.\n"
            f"   Do not return pack count alone (e.g. do not return '3 packs' or '1 unit') and do not return null; always return the aggregated net total amount with its measurement unit (e.g., '1.5 gallons', '48 oz', '2 lb', '1 count')."
        )

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

        # Sleep 4 seconds between successive Gemini API calls
        wait_between_gemini_calls(4.0)

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMResolvedItem,
                temperature=0.1
            )
        )
        if response.text:
            log_gemini_api_call(
                product_name=raw_text,
                store_name=store_name,
                purchase_date=purchase_date,
                response_text=response.text
            )
            item_data = json.loads(response.text)
            item_data["llm_success"] = True
            return LLMResolvedItem(**item_data)
        else:
            log_gemini_api_call(
                product_name=raw_text,
                store_name=store_name,
                purchase_date=purchase_date,
                error="Empty response text received from Gemini API"
            )
    except Exception as e:
        logger.warning(f"Gemini API resolution error: {e}")
        log_gemini_api_call(
            product_name=raw_text,
            store_name=store_name,
            purchase_date=purchase_date,
            error=f"Gemini API error: {e}"
        )

    fallback = fallback_heuristic_resolve(raw_text, store_name, existing_items)
    fallback.llm_success = False
    return fallback


def fallback_heuristic_resolve(
    raw_text: str,
    store_name: Optional[str] = None,
    existing_items: Optional[List[str]] = None
) -> LLMResolvedItem:
    clean = raw_text.strip()
    for prefix in ["ORGANIC", "KIRKLAND", "365", "TRADER JOE", "VALU", "GREAT VALUE", "FARM FRESH"]:
        if clean.upper().startswith(prefix):
            clean = clean[len(prefix):].strip()

    title = clean.title()
    lower = raw_text.lower()
    if any(k in lower for k in ["milk", "cheese", "yogurt", "butter", "cream"]):
        category, unit = "Dairy", ("gallon" if "gal" in lower else "oz")
    elif any(k in lower for k in ["spinach", "cilantro", "onion", "banana", "apple", "tomato", "chili", "fruit", "berry", "avocado", "cucumber"]):
        category, unit = "Produce", ("lb" if "lb" in lower else "count")
    elif any(k in lower for k in ["bread", "bagel", "croissant", "bun", "toast", "pita"]):
        category, unit = "Bakery", "count"
    elif any(k in lower for k in ["chicken", "beef", "salmon", "meat", "pork", "shrimp"]):
        category, unit = "Meat & Seafood", "lb"
    elif any(k in lower for k in ["rice", "flour", "pasta", "spaghetti", "grain"]):
        category, unit = "Grains & Pasta", "lb"
    elif any(k in lower for k in ["bhel", "khari", "chips", "biscuit", "cookie", "sev", "snack"]):
        category, unit = "Snacks", ("g" if "gm" in lower or "g" in lower else "oz")
    else:
        category, unit = "Pantry", "count"

    generic_name = clean.lower()
    for kw in ["milk", "cheese", "yogurt", "butter", "spinach", "cilantro", "onion", "banana", "apple", "tomato", "chili", "bread", "chicken", "beef", "salmon", "rice", "flour", "pasta", "cookie", "cookies", "oil"]:
        if kw in lower:
            generic_name = kw
            break

    is_bulk = any(k in lower for k in ["20lb", "10lb", "5lb", "bulk"]) or ("rice" in lower and "lb" in lower)

    matched_existing = None
    if existing_items:
        for ex in existing_items:
            if ex.lower() in lower or lower in ex.lower():
                matched_existing = ex
                break

    return LLMResolvedItem(
        canonical_name=title,
        generic_name=generic_name,
        category=category,
        standard_unit=unit,
        is_bulk=is_bulk,
        matched_existing_canonical_name=matched_existing,
        total_quantity=f"1 {unit}"
    )


def parse_total_quantity(total_qty_str: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Parse string from LLM like '1.5 gallons', '32 oz', '500g' into (quantity, standard_unit)."""
    if not total_qty_str or not isinstance(total_qty_str, str):
        return None, None
    clean = total_qty_str.strip()
    if not clean or clean.lower() in ("none", "null", "n/a"):
        return None, None
    from app.normalizer import extract_quantity_and_unit
    _, qty, unit = extract_quantity_and_unit(clean)
    if qty and qty > 0 and unit:
        return qty, unit
    return None, None

