from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GroceryListEntry, Item
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
    """Add a manual item to the shopping list with canonical linking and price estimation."""
    clean_name = payload.item_name.strip()
    matched_item = db.query(Item).filter(Item.canonical_name.ilike(clean_name)).first()
    canonical_id = matched_item.id if matched_item else None

    if canonical_id:
        db.query(GroceryListEntry).filter(
            GroceryListEntry.household_id == household_id,
            GroceryListEntry.canonical_item_id == canonical_id
        ).update({"is_dismissed": False})

    bench = 3.49
    if matched_item and matched_item.default_unit_price:
        bench = matched_item.default_unit_price
    est_cost = round((payload.quantity or 1.0) * bench, 2)

    entry = GroceryListEntry(
        household_id=household_id,
        canonical_item_id=canonical_id,
        custom_item_name=clean_name,
        category=payload.category or (matched_item.category if matched_item else "General"),
        target_store=payload.target_store or (matched_item.preferred_store if matched_item and matched_item.preferred_store else "Any Store"),
        recommended_quantity=payload.quantity,
        unit=payload.unit,
        estimated_cost=est_cost,
        priority_reason="MANUAL",
        is_checked=False,
        is_dismissed=False
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return GroceryListItemOut(
        id=entry.id,
        canonical_item_id=entry.canonical_item_id,
        item_name=clean_name,
        category=entry.category,
        target_store=entry.target_store,
        recommended_quantity=entry.recommended_quantity,
        unit=entry.unit,
        estimated_cost=entry.estimated_cost,
        priority_reason=entry.priority_reason,
        is_checked=entry.is_checked,
        estimated_runout_date=None
    )


@router.post("/items/{item_id}/toggle", response_model=GroceryListItemOut)
@router.patch("/items/{item_id}/check", response_model=GroceryListItemOut)
def toggle_check_grocery_item(
    item_id: int,
    is_checked: Optional[bool] = Query(None, description="Optional target checked state"),
    db: Session = Depends(get_db)
):
    """Toggle or set item checked state on the active grocery list."""
    entry = db.query(GroceryListEntry).filter(GroceryListEntry.id == item_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grocery list entry not found.")

    if is_checked is not None:
        entry.is_checked = is_checked
    else:
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
    if entry.priority_reason == "MANUAL":
        db.delete(entry)
    else:
        if entry.canonical_item_id:
            db.query(GroceryListEntry).filter(
                GroceryListEntry.household_id == entry.household_id,
                GroceryListEntry.canonical_item_id == entry.canonical_item_id
            ).update({"is_dismissed": True, "is_checked": True}, synchronize_session=False)
        else:
            entry.is_dismissed = True
            entry.is_checked = True
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
