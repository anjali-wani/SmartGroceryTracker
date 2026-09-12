from datetime import date
from typing import Dict, List
from sqlalchemy.orm import Session
from app.models import GuestEvent, Household


def calculate_guest_discount_factor(
    db: Session,
    household_id: int,
    start_date: date,
    end_date: date
) -> float:
    """Calculate the portion of consumption attributable to guests during a date range.
    
    Returns a discount factor between 0.0 and 0.8:
    e.g. 0.15 means 15% of food consumed in this window was eaten by guests and
    should be deducted from normal baseline household velocity.
    """
    household = db.query(Household).filter(Household.id == household_id).first()
    members = household.member_count if household else 2

    # Query guest events in window
    events: List[GuestEvent] = (
        db.query(GuestEvent)
        .filter(
            GuestEvent.household_id == household_id,
            GuestEvent.event_date >= start_date,
            GuestEvent.event_date <= end_date
        )
        .all()
    )

    if not events:
        return 0.0

    total_days = max(1, (end_date - start_date).days + 1)
    baseline_person_days = members * total_days

    # Each guest event is weighted as 1 dinner meal (approx 0.35 of daily food consumption)
    MEAL_WEIGHT = 0.35
    total_guest_person_days = sum(e.guest_count * MEAL_WEIGHT for e in events)

    total_effective_person_days = baseline_person_days + total_guest_person_days
    guest_fraction = total_guest_person_days / total_effective_person_days

    # Cap maximum discount at 50% to prevent over-reduction
    return min(0.50, round(guest_fraction, 4))
