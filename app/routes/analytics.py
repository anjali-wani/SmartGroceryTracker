from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Item
from app.schemas import HouseholdVelocityReport, ItemVelocityOut
from app.services.analytics import generate_household_velocity_report, compute_item_velocity

router = APIRouter(prefix="/analytics", tags=["Consumption Analytics & Velocity"])


@router.get("/velocity", response_model=HouseholdVelocityReport)
def get_household_consumption_velocity(
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Calculates daily consumption velocity and runout forecast across all kitchen items.
    
    Uses dual sliding windows (30d standard perishables vs 180d bulk) and
    discounts guest event allocations from baseline rates.
    """
    report = generate_household_velocity_report(db, household_id=household_id)
    return report


@router.get("/velocity/{item_id}", response_model=ItemVelocityOut)
def get_single_item_velocity(
    item_id: int,
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Detailed consumption velocity breakdown for a single canonical grocery item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found."
        )
    return compute_item_velocity(item, db, household_id=household_id)
