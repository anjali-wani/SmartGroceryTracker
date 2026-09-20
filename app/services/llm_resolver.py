import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger("llm_resolver")

class LLMResolvedItem(BaseModel):
    canonical_name: str = Field(..., description="Clean title-case product name")
    generic_name: Optional[str] = Field(None, description="Generic base grocery name in lowercase, e.g. 'milk' for 'Kirkland Signature Organic Milk' or 'KS_ORG_A2_MLK', 'apples' for 'Gala Apples', 'rice' for 'Basmati Rice'")
    category: str = Field(..., description="Category: Produce, Dairy, Pantry, Bakery, Meat, Snacks, Grains & Pasta")
    standard_unit: str = Field("count", description="Standard unit (lb, oz, gallon, count, g)")
    is_bulk: bool = Field(False, description="Whether item is typically bulk")
    matched_existing_canonical_name: Optional[str] = Field(None, description="Matched existing item name if alias")
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
    purchase_date: Optional[Any] = None
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
        prompt = (
            f"You are a grocery classification engine. Identify the product name, generic name, category, and unit for raw receipt item: '{raw_text}' from '{store_clean}'.\n"
            f"Return the following fields:\n"
            f"1. canonical_name: Clean, title-case brand/product name (e.g. 'Kirkland Signature Organic Milk').\n"
            f"2. generic_name: The base/generic grocery name in lowercase. E.g. for 'KS_ORG_A2_MLK' or 'Kirkland Signature Organic Milk', generic_name is 'milk'; for 'Gala Apples', generic_name is 'apples'; for 'Deep Rice Flour', generic_name is 'rice flour'; for 'Veer Cashew Split', generic_name is 'cashews'.\n"
            f"3. category: Category (Produce, Dairy, Pantry, Bakery, Meat & Seafood, Snacks, Grains & Pasta, Spices / Pantry, etc.).\n"
            f"4. standard_unit: Standard unit (count, lb, oz, g, gallon, ml, etc.).\n"
            f"5. is_bulk: Boolean indicating if typically purchased in bulk."
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
        matched_existing_canonical_name=matched_existing
    )
