from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GroceryListEntry
from app.schemas import GroceryListResponse, GroceryListItemOut, ManualListItemCreate
from app.services.list_generator import generate_smart_grocery_list

router = APIRouter(prefix="/grocery-list", tags=["Automated Grocery List Generator"])


@router.get("/generate", response_model=GroceryListResponse)
def get_or_generate_grocery_list(
    days_ahead: int = Query(7, ge=1, le=30, description="Depletion forecast horizon in days"),
    store: Optional[str] = Query(None, description="Filter list by specific store"),
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Evaluates 7-day inventory runout predictions and periodic schedules to auto-generate shopping list."""
    return generate_smart_grocery_list(db, household_id=household_id, forecast_days=days_ahead, target_store=store)


@router.post("/items", response_model=GroceryListItemOut, status_code=status.HTTP_201_CREATED)
def add_custom_grocery_item(
    payload: ManualListItemCreate,
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Add a manual item to the shopping list (e.g. Party napkins, birthday candles)."""
    entry = GroceryListEntry(
        household_id=household_id,
        canonical_item_id=None,
        custom_item_name=payload.item_name.strip(),
        category=payload.category or "General",
        target_store=payload.target_store or "Any Store",
        recommended_quantity=payload.quantity,
        unit=payload.unit,
        priority_reason="MANUAL",
        is_checked=False
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return GroceryListItemOut(
        id=entry.id,
        canonical_item_id=None,
        item_name=entry.custom_item_name,
        category=entry.category,
        target_store=entry.target_store,
        recommended_quantity=entry.recommended_quantity,
        unit=entry.unit,
        estimated_cost=None,
        priority_reason=entry.priority_reason,
        is_checked=entry.is_checked,
        estimated_runout_date=None
    )


@router.patch("/items/{item_id}/check", response_model=GroceryListItemOut)
def toggle_check_grocery_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    """Toggle item bought/checked state on the active grocery list."""
    entry = db.query(GroceryListEntry).filter(GroceryListEntry.id == item_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grocery list entry not found.")

    entry.is_checked = not entry.is_checked
    db.commit()
    db.refresh(entry)

    name = entry.item.canonical_name if entry.item else (entry.custom_item_name or "Item")
    return GroceryListItemOut(
        id=entry.id,
        canonical_item_id=entry.canonical_item_id,
        item_name=name,
        category=entry.category,
        target_store=entry.target_store,
        recommended_quantity=entry.recommended_quantity,
        unit=entry.unit,
        estimated_cost=entry.estimated_cost,
        priority_reason=entry.priority_reason,
        is_checked=entry.is_checked,
        estimated_runout_date=entry.estimated_runout_date
    )


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grocery_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    """Remove or dismiss an item from the shopping list."""
    entry = db.query(GroceryListEntry).filter(GroceryListEntry.id == item_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grocery list entry not found.")
    db.delete(entry)
    db.commit()
    return None


@router.get("/export")
def export_grocery_list_text(
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Export the active shopping checklist formatted for mobile sharing (Notes/Messaging)."""
    data = generate_smart_grocery_list(db, household_id=household_id, forecast_days=7)

    lines = [
        f"🛒 GROCERY SHOPPING LIST ({data.generated_date})",
        f"Total Items: {data.total_items} | Est. Cost: ${data.total_estimated_cost:.2f}",
        "=" * 40
    ]

    for store, items in data.items_by_store.items():
        lines.append("")
        lines.append(f"📍 {store.upper()}")
        for it in items:
            check_box = "[x]" if it["is_checked"] else "[ ]"
            reason_badge = f"({it['priority_reason']})"
            cost_badge = f" - ${it['estimated_cost']:.2f}" if it['estimated_cost'] else ""
            lines.append(f"  {check_box} {it['item_name']} - {it['recommended_quantity']} {it['unit']}{cost_badge} {reason_badge}")

    content = chr(10).join(lines)
    return Response(content=content, media_type="text/plain")
