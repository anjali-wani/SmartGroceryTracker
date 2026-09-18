from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
from collections import Counter
from sqlalchemy.orm import Session

from app.models import PurchaseLog, Inventory, InventoryStatus, Item, Household
from app.schemas import ItemVelocityOut, HouseholdVelocityReport
from app.services.guest_engine import calculate_guest_discount_factor


def calculate_modal_quantity(quantities: List[float]) -> float:
    """Calculate most frequent purchase quantity with larger quantity tie-breaker."""
    if not quantities:
        return 1.0
    counts = Counter(quantities)
    max_freq = max(counts.values())
    candidates = [qty for qty, freq in counts.items() if freq == max_freq]
    # If frequencies are same, pick bigger quantity
    return max(candidates)


def compute_item_velocity(
    item: Item,
    db: Session,
    household_id: int = 1,
    as_of_date: Optional[date] = None
) -> ItemVelocityOut:
    """Calculates consumption velocity and runouts purely from purchase cycles.
    No expiration dates used.
    """
    if as_of_date is None:
        as_of_date = date.today()

    household = db.query(Household).filter(Household.id == household_id).first()
    members = household.member_count if household else 2

    # Query purchases ordered by date
    purchases: List[PurchaseLog] = (
        db.query(PurchaseLog)
        .filter(
            PurchaseLog.household_id == household_id,
            PurchaseLog.canonical_item_id == item.id,
            PurchaseLog.purchase_date <= as_of_date
        )
        .order_by(PurchaseLog.purchase_date.asc())
        .all()
    )

    # Active inventory on hand
    active_inv: List[Inventory] = (
        db.query(Inventory)
        .filter(
            Inventory.household_id == household_id,
            Inventory.canonical_item_id == item.id,
            Inventory.status == InventoryStatus.ACTIVE
        )
        .all()
    )
    current_stock = sum(inv.current_quantity for inv in active_inv)
    unit = item.standard_unit

    if not purchases:
        return ItemVelocityOut(
            canonical_item_id=item.id,
            item_name=item.canonical_name,
            category=item.category,
            is_bulk=item.is_bulk,
            daily_velocity=0.0,
            per_capita_velocity=0.0,
            current_stock=round(current_stock, 2),
            unit=unit,
            estimated_days_remaining=None,
            lookback_days=(180 if item.is_bulk else 30),
            purchase_count=0,
            confidence="cold_start",
            last_purchased=None,
            days_per_unit=None,
            modal_quantity=1.0,
            projected_runout_date=None,
            needs_availability_check=False,
            prompt_message=None
        )

    all_quantities = [p.quantity for p in purchases if p.quantity > 0]
    modal_qty = calculate_modal_quantity(all_quantities)
    last_p = purchases[-1]
    last_date = last_p.purchase_date
    last_qty = last_p.quantity

    # --- CASE 1: Only 1 purchase (Cold start - no arbitrary guesses, no user prompts) ---
    if len(purchases) == 1:
        elapsed = max(1, (as_of_date - last_date).days)
        # Never prompt user for availability; single purchase does not trigger auto-reorders
        return ItemVelocityOut(
            canonical_item_id=item.id,
            item_name=item.canonical_name,
            category=item.category,
            is_bulk=item.is_bulk,
            daily_velocity=0.0,
            per_capita_velocity=0.0,
            current_stock=round(current_stock, 2),
            unit=unit,
            estimated_days_remaining=None,
            lookback_days=max(180 if item.is_bulk else 30, elapsed),
            purchase_count=1,
            confidence="cold_start",
            last_purchased=last_date,
            days_per_unit=None,
            modal_quantity=modal_qty,
            projected_runout_date=None,
            needs_availability_check=False,
            prompt_message=None
        )

    # --- CASE 2: 2 or more purchases (Empirical Repurchase Rate) ---
    unit_durations: List[float] = []
    purchase_intervals: List[int] = []

    for i in range(1, len(purchases)):
        prev_p = purchases[i - 1]
        curr_p = purchases[i]
        interval_days = (curr_p.purchase_date - prev_p.purchase_date).days
        if interval_days > 0:
            purchase_intervals.append(interval_days)
            if prev_p.quantity > 0:
                # E.g. 1 lb lasted 14 days -> 14 days per 1 lb
                unit_durations.append(interval_days / prev_p.quantity)

    avg_days_per_unit = sum(unit_durations) / len(unit_durations) if unit_durations else 14.0
    avg_interval = sum(purchase_intervals) / len(purchase_intervals) if purchase_intervals else 14.0

    daily_velocity = round(1.0 / avg_days_per_unit, 4) if avg_days_per_unit > 0 else 0.05
    per_capita = round(daily_velocity / members, 4)

    # Duration the last purchase goes:
    # E.g. 2 lb * 14 days/lb = 28 days
    projected_duration_days = round(last_qty * avg_days_per_unit, 1)
    projected_runout = last_date + timedelta(days=round(projected_duration_days))

    # Estimated days remaining from as_of_date
    days_remaining = (projected_runout - as_of_date).days
    total_window_span = (as_of_date - purchases[0].purchase_date).days

    return ItemVelocityOut(
        canonical_item_id=item.id,
        item_name=item.canonical_name,
        category=item.category,
        is_bulk=item.is_bulk,
        daily_velocity=daily_velocity,
        per_capita_velocity=per_capita,
        current_stock=round(current_stock, 2),
        unit=unit,
        estimated_days_remaining=float(days_remaining),
        lookback_days=max(30, total_window_span),
        purchase_count=len(purchases),
        confidence="high" if len(purchases) >= 3 else "moderate",
        last_purchased=last_date,
        days_per_unit=round(avg_days_per_unit, 2),
        modal_quantity=modal_qty,
        projected_runout_date=projected_runout,
        needs_availability_check=False,
        prompt_message=None,
        avg_purchase_interval_days=round(avg_interval, 1)
    )


def generate_household_velocity_report(
    db: Session,
    household_id: int = 1,
    as_of_date: Optional[date] = None
) -> HouseholdVelocityReport:
    """Generate complete consumption velocity report for all tracked items."""
    if as_of_date is None:
        as_of_date = date.today()

    household = db.query(Household).filter(Household.id == household_id).first()
    members = household.member_count if household else 2

    item_ids_with_purchases = db.query(PurchaseLog.canonical_item_id).filter(
        PurchaseLog.household_id == household_id,
        PurchaseLog.canonical_item_id.isnot(None)
    ).distinct()

    item_ids_with_inv = db.query(Inventory.canonical_item_id).filter(
        Inventory.household_id == household_id
    ).distinct()

    active_item_ids = {r[0] for r in item_ids_with_purchases}.union({r[0] for r in item_ids_with_inv})
    items = db.query(Item).filter(Item.id.in_(active_item_ids)).order_by(Item.category, Item.canonical_name).all()

    reports: List[ItemVelocityOut] = []
    for item in items:
        rep = compute_item_velocity(item, db, household_id=household_id, as_of_date=as_of_date)
        reports.append(rep)

    return HouseholdVelocityReport(
        household_id=household_id,
        total_tracked_items=len(reports),
        household_members=members,
        report_date=as_of_date,
        items=reports
    )
