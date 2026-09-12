from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GuestEvent
from app.schemas import GuestEventCreate, GuestEventOut

router = APIRouter(prefix="/events", tags=["Guest Event Allocations"])


@router.post("/guests", response_model=GuestEventOut, status_code=status.HTTP_201_CREATED)
def record_guest_event(
    payload: GuestEventCreate,
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Log a guest meal event (e.g. dinner party, visitors) to calibrate consumption velocity."""
    if payload.guest_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest count must be at least 1."
        )

    event = GuestEvent(
        household_id=household_id,
        event_date=payload.event_date,
        guest_count=payload.guest_count,
        notes=payload.notes
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/guests", response_model=List[GuestEventOut])
def list_guest_events(
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Retrieve logged guest events for a household."""
    events = (
        db.query(GuestEvent)
        .filter(GuestEvent.household_id == household_id)
        .order_by(GuestEvent.event_date.desc())
        .all()
    )
    return events


@router.delete("/guests/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guest_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Delete a logged guest event."""
    event = db.query(GuestEvent).filter(GuestEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest event not found."
        )
    db.delete(event)
    db.commit()
    return None
