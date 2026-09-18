import os
import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger("llm_resolver")

class LLMResolvedItem(BaseModel):
    canonical_name: str = Field(..., description="Clean title-case product name")
    category: str = Field(..., description="Category: Produce, Dairy, Pantry, Bakery, Meat, Snacks, Grains & Pasta")
    standard_unit: str = Field("count", description="Standard unit (lb, oz, gallon, count, g)")
    is_bulk: bool = Field(False, description="Whether item is typically bulk")
    matched_existing_canonical_name: Optional[str] = Field(None, description="Matched existing item name if alias")


def resolve_with_gemini(
    raw_text: str,
    store_name: Optional[str] = None,
    existing_items: Optional[List[str]] = None
) -> Optional[LLMResolvedItem]:
    """Resolve unrecognized item using Gemini Flash, with local heuristic fallback."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback_heuristic_resolve(raw_text, store_name, existing_items)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        catalog_str = ", ".join(existing_items[:40]) if existing_items else ""
        prompt = (
            f"You are a grocery classification engine. Identify the product name, category, and unit for raw receipt item: '{raw_text}' from '{store_name or 'Grocery'}'. "
            f"Known catalog items: {catalog_str}. If it matches a known item, set matched_existing_canonical_name."
        )

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMResolvedItem,
                temperature=0.1
            )
        )
        if response.text:
            return LLMResolvedItem(**json.loads(response.text))
    except Exception as e:
        logger.warning(f"Gemini API resolution error: {e}")

    return fallback_heuristic_resolve(raw_text, store_name, existing_items)


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

    is_bulk = any(k in lower for k in ["20lb", "10lb", "5lb", "bulk"]) or ("rice" in lower and "lb" in lower)

    matched_existing = None
    if existing_items:
        for ex in existing_items:
            if ex.lower() in lower or lower in ex.lower():
                matched_existing = ex
                break

    return LLMResolvedItem(
        canonical_name=title,
        category=category,
        standard_unit=unit,
        is_bulk=is_bulk,
        matched_existing_canonical_name=matched_existing
    )
