from datetime import date, datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Inventory, InventoryStatus, Item, GroceryListEntry
from app.schemas import InventoryAdjustRequest, InventoryAdjustResponse, InventoryOut

router = APIRouter(prefix="/inventory", tags=["Inventory Controls"])


@router.get("/active", response_model=List[InventoryOut])
def get_active_inventory(
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """View active pantry, fridge, and freezer inventory items for a household."""
    inventory_items = (
        db.query(Inventory)
        .filter(
            Inventory.household_id == household_id,
            Inventory.status == InventoryStatus.ACTIVE
        )
        .order_by(Inventory.purchase_date.desc(), Inventory.id.desc())
        .all()
    )

    out = []
    for inv in inventory_items:
        out.append(InventoryOut(
            id=inv.id,
            household_id=inv.household_id,
            canonical_item_id=inv.canonical_item_id,
            item_name=inv.item.canonical_name if inv.item else "Unknown",
            category=inv.item.category if inv.item else "General",
            current_quantity=inv.current_quantity,
            unit=inv.unit,
            purchase_date=inv.purchase_date,
            status=inv.status
        ))
    return out


@router.post("/adjust", response_model=InventoryAdjustResponse)
def adjust_inventory_stock(
    payload: InventoryAdjustRequest,
    db: Session = Depends(get_db)
):
    """Adjust inventory stock for consumption, spoilage, or manual correction.
    If quantity reaches 0 or below, automatically marks status as CONSUMED.
    """
    inv = db.query(Inventory).filter(Inventory.id == payload.inventory_id).first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory entry with ID {payload.inventory_id} not found."
        )

    prev_qty = inv.current_quantity

    # Update quantity if specified
    if payload.new_quantity is not None:
        if payload.new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity cannot be negative."
            )
        inv.current_quantity = payload.new_quantity
        if inv.current_quantity <= 0:
            inv.current_quantity = 0.0
            inv.status = InventoryStatus.CONSUMED

    # Update status if specified (e.g. SPOILED, CONSUMED, ADJUSTED)
    if payload.status is not None:
        inv.status = payload.status
        if inv.status == InventoryStatus.CONSUMED:
            inv.current_quantity = 0.0

    db.commit()
    db.refresh(inv)

    item_name = inv.item.canonical_name if inv.item else "Unknown"

    return InventoryAdjustResponse(
        id=inv.id,
        canonical_item_id=inv.canonical_item_id,
        item_name=item_name,
        previous_quantity=prev_qty,
        current_quantity=inv.current_quantity,
        unit=inv.unit,
        status=inv.status,
        adjusted_at=datetime.utcnow()
    )


@router.post("/{canonical_item_id}/confirm-availability")
def confirm_item_availability(
    canonical_item_id: int,
    is_available: bool = Query(..., description="True if still in stock; False if finished"),
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Answers availability prompt for single-purchase items.
    If is_available=False, marks stock CONSUMED and drafts item to grocery list for the household.
    """
    item = db.query(Item).filter(Item.id == canonical_item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

    active_inv = db.query(Inventory).filter(
        Inventory.household_id == household_id,
        Inventory.canonical_item_id == canonical_item_id,
        Inventory.status == InventoryStatus.ACTIVE
    ).all()

    today = date.today()
    if not is_available:
        for inv in active_inv:
            inv.current_quantity = 0.0
            inv.status = InventoryStatus.CONSUMED
            inv.is_confirmed = True

        existing_list_entry = db.query(GroceryListEntry).filter(
            GroceryListEntry.household_id == household_id,
            GroceryListEntry.canonical_item_id == item.id,
            GroceryListEntry.is_checked == False
        ).first()

        if not existing_list_entry:
            db.add(GroceryListEntry(
                household_id=household_id,
                canonical_item_id=item.id,
                category=item.category,
                target_store=item.preferred_store or "Any Store",
                recommended_quantity=1.0,
                unit=item.standard_unit,
                priority_reason="CONFIRMED_DEPLETED",
                is_checked=False,
                estimated_runout_date=today
            ))
        db.commit()
        return {
            "canonical_item_id": item.id,
            "item_name": item.canonical_name,
            "household_id": household_id,
            "status": "CONSUMED",
            "message": f"'{item.canonical_name}' marked consumed and queued for reorder for Household {household_id}."
        }
    else:
        for inv in active_inv:
            inv.is_confirmed = True
        db.commit()
        return {
            "canonical_item_id": item.id,
            "item_name": item.canonical_name,
            "household_id": household_id,
            "status": "ACTIVE",
            "message": f"'{item.canonical_name}' confirmed active in stock for Household {household_id}."
        }
