from datetime import date, datetime, timedelta
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.models import PurchaseLog, Inventory, InventoryStatus, Item, Household
from app.schemas import ItemVelocityOut, HouseholdVelocityReport
from app.services.guest_engine import calculate_guest_discount_factor


def compute_item_velocity(
    item: Item,
    db: Session,
    household_id: int = 1,
    as_of_date: Optional[date] = None
) -> ItemVelocityOut:
    """Compute consumption velocity for an item using dual sliding windows and guest discounts.
    
    - Standard perishables (is_bulk=False): 30-day lookback window
    - Bulk goods (is_bulk=True): 180-day lookback window
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Determine sliding window
    window_days = 180 if item.is_bulk else 30
    start_date = as_of_date - timedelta(days=window_days)

    household = db.query(Household).filter(Household.id == household_id).first()
    members = household.member_count if household else 2

    # Query purchases for this item within the window
    purchases: List[PurchaseLog] = (
        db.query(PurchaseLog)
        .filter(
            PurchaseLog.household_id == household_id,
            PurchaseLog.canonical_item_id == item.id,
            PurchaseLog.purchase_date >= start_date,
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
        # Check if there is any older purchase outside window
        older = (
            db.query(PurchaseLog)
            .filter(
                PurchaseLog.household_id == household_id,
                PurchaseLog.canonical_item_id == item.id
            )
            .order_by(PurchaseLog.purchase_date.desc())
            .first()
        )
        last_date = older.purchase_date if older else None

        # Cold start heuristic based on shelf life
        default_days = max(3, item.default_shelf_life_days)
        estimated_daily = 1.0 / default_days
        return ItemVelocityOut(
            canonical_item_id=item.id,
            item_name=item.canonical_name,
            category=item.category,
            is_bulk=item.is_bulk,
            daily_velocity=round(estimated_daily, 3),
            per_capita_velocity=round(estimated_daily / members, 3),
            current_stock=round(current_stock, 2),
            unit=unit,
            estimated_days_remaining=round(current_stock / estimated_daily, 1) if estimated_daily > 0 else None,
            lookback_days=window_days,
            purchase_count=0,
            confidence="cold_start",
            last_purchased=last_date
        )

    # Calculate total purchased in window
    total_purchased = sum(p.quantity for p in purchases)
    last_purchased_date = purchases[-1].purchase_date

    # Spoiled items during this window should NOT count as consumed
    spoiled_inv: List[Inventory] = (
        db.query(Inventory)
        .filter(
            Inventory.household_id == household_id,
            Inventory.canonical_item_id == item.id,
            Inventory.status == InventoryStatus.SPOILED,
            Inventory.purchase_date >= start_date
        )
        .all()
    )
    total_spoiled = sum(inv.current_quantity for inv in spoiled_inv)

    # Effective consumed = Total purchased - current active stock - spoiled waste
    gross_consumed = max(0.0, total_purchased - current_stock - total_spoiled)

    # Apply guest meal discount
    guest_factor = calculate_guest_discount_factor(db, household_id, start_date, as_of_date)
    net_consumed = max(0.0, gross_consumed * (1.0 - guest_factor))

    # Calculate time span
    if len(purchases) > 1:
        first_date = purchases[0].purchase_date
        elapsed_days = max(1, (as_of_date - first_date).days)
        confidence = "high" if len(purchases) >= 3 else "moderate"
    else:
        elapsed_days = max(1, (as_of_date - purchases[0].purchase_date).days)
        confidence = "moderate" if elapsed_days >= 7 else "cold_start"

    # Daily consumption velocity
    if net_consumed > 0 and elapsed_days > 0:
        daily_velocity = net_consumed / elapsed_days
    else:
        # Fallback to total purchased divided by window or package shelf-life
        shelf_life = max(3, item.default_shelf_life_days)
        daily_velocity = total_purchased / max(elapsed_days, shelf_life)

    daily_velocity = round(daily_velocity, 3)
    per_capita = round(daily_velocity / members, 3)

    # Estimated days remaining before stock reaches zero
    if daily_velocity > 0:
        days_remaining = round(current_stock / daily_velocity, 1)
    else:
        days_remaining = None

    return ItemVelocityOut(
        canonical_item_id=item.id,
        item_name=item.canonical_name,
        category=item.category,
        is_bulk=item.is_bulk,
        daily_velocity=daily_velocity,
        per_capita_velocity=per_capita,
        current_stock=round(current_stock, 2),
        unit=unit,
        estimated_days_remaining=days_remaining,
        lookback_days=window_days,
        purchase_count=len(purchases),
        confidence=confidence,
        last_purchased=last_purchased_date
    )


def generate_household_velocity_report(
    db: Session,
    household_id: int = 1,
    as_of_date: Optional[date] = None
) -> HouseholdVelocityReport:
    """Generate complete consumption velocity report for all items tracked by household."""
    if as_of_date is None:
        as_of_date = date.today()

    household = db.query(Household).filter(Household.id == household_id).first()
    members = household.member_count if household else 2

    # Query all items that have either purchases or active inventory
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
