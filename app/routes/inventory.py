from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Inventory, InventoryStatus, Item
from app.schemas import InventoryAdjustRequest, InventoryAdjustResponse, ExpiringItemOut

router = APIRouter(prefix="/inventory", tags=["Inventory Controls & Spoilage"])


@router.post("/adjust", response_model=InventoryAdjustResponse)
def adjust_inventory_stock(
    payload: InventoryAdjustRequest,
    db: Session = Depends(get_db)
):
    """Adjust inventory stock for spoilage, consumption, dining out, or manual correction."""
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
        if inv.current_quantity == 0:
            inv.status = InventoryStatus.CONSUMED

    # Update status if specified (e.g. SPOILED, CONSUMED, ADJUSTED)
    if payload.status is not None:
        inv.status = payload.status

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


@router.get("/expiring-soon", response_model=List[ExpiringItemOut])
def get_expiring_soon_items(
    days: int = Query(3, ge=1, le=30, description="Expiration threshold in days"),
    db: Session = Depends(get_db)
):
    """Returns active inventory items expiring within N days."""
    today = date.today()
    threshold = today + timedelta(days=days)

    expiring_items = (
        db.query(Inventory)
        .filter(
            Inventory.status == InventoryStatus.ACTIVE,
            Inventory.expiration_date <= threshold
        )
        .order_by(Inventory.expiration_date.asc())
        .all()
    )

    out = []
    for inv in expiring_items:
        days_left = (inv.expiration_date - today).days
        out.append(ExpiringItemOut(
            inventory_id=inv.id,
            canonical_item_id=inv.canonical_item_id,
            item_name=inv.item.canonical_name if inv.item else "Unknown",
            category=inv.item.category if inv.item else "General",
            current_quantity=inv.current_quantity,
            unit=inv.unit,
            purchase_date=inv.purchase_date,
            expiration_date=inv.expiration_date,
            days_until_expiration=days_left
        ))
    return out
