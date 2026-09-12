import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.models import Item, Inventory, InventoryStatus, PurchaseLog, GroceryListEntry, Household
from app.services.analytics import compute_item_velocity
from app.schemas import GroceryListItemOut, GroceryListResponse


def generate_smart_grocery_list(
    db: Session,
    household_id: int = 1,
    forecast_days: int = 7,
    target_store: Optional[str] = None,
    as_of_date: Optional[date] = None
) -> GroceryListResponse:
    """Evaluates inventory, daily velocity, and periodic schedules to generate a smart shopping list."""
    if as_of_date is None:
        as_of_date = date.today()

    # Clear previously generated unchecked auto-items for this household to refresh draft
    db.query(GroceryListEntry).filter(
        GroceryListEntry.household_id == household_id,
        GroceryListEntry.is_checked == False,
        GroceryListEntry.priority_reason != "MANUAL"
    ).delete(synchronize_session=False)
    db.commit()

    # Query active canonical items (ignore soft-archived is_active=False)
    active_items: List[Item] = (
        db.query(Item)
        .filter(Item.is_active == True)
        .order_by(Item.category, Item.canonical_name)
        .all()
    )

    for item in active_items:
        # Check store filter if specified
        if target_store and item.preferred_store and item.preferred_store.lower() != target_store.lower():
            continue

        velocity_data = compute_item_velocity(item, db, household_id=household_id, as_of_date=as_of_date)
        stock = velocity_data.current_stock
        daily_v = velocity_data.daily_velocity
        unit = item.standard_unit

        should_reorder = False
        priority = "RUNNING_LOW"
        est_runout_date = None

        # 1. Periodic Purchase Scheduler (Date-Modulo Trigger) takes priority for recurring staples
        if item.reorder_cadence_days and item.reorder_cadence_days > 0:
            last_purchase = velocity_data.last_purchased
            if last_purchase:
                days_since_purchase = (as_of_date - last_purchase).days
                if days_since_purchase >= item.reorder_cadence_days:
                    should_reorder = True
                    priority = "SCHEDULED_PERIODIC"
                    est_runout_date = as_of_date
            else:
                # Never bought before but cadence is set
                should_reorder = True
                priority = "SCHEDULED_PERIODIC"
                est_runout_date = as_of_date

        # 2. Expiration Trigger: Active inventory will expire within forecast_days
        if not should_reorder:
            expiring_stock = (
                db.query(Inventory)
                .filter(
                    Inventory.household_id == household_id,
                    Inventory.canonical_item_id == item.id,
                    Inventory.status == InventoryStatus.ACTIVE,
                    Inventory.expiration_date <= as_of_date + timedelta(days=forecast_days)
                )
                .all()
            )
            if expiring_stock:
                should_reorder = True
                priority = "EXPIRING_SOON"
                min_exp = min(inv.expiration_date for inv in expiring_stock)
                est_runout_date = min_exp

        # 3. Depletion Trigger: For items household actually consumes, stock is depleted or will run out
        if not should_reorder and (velocity_data.last_purchased is not None or stock > 0):
            if stock <= 0:
                should_reorder = True
                priority = "CRITICAL_DEPLETION"
                est_runout_date = as_of_date
            elif daily_v > 0:
                days_left = stock / daily_v
                if days_left <= forecast_days:
                    should_reorder = True
                    priority = "CRITICAL_DEPLETION" if days_left <= 2.0 else "RUNNING_LOW"
                    est_runout_date = as_of_date + timedelta(days=math.floor(days_left))

        if should_reorder:
            # Calculate Recommended Reorder Quantity (7-day buffer or typical package quantity)
            if item.is_bulk:
                reorder_qty = 1.0  # e.g., 1 bulk unit (20lb rice, 1 liter oil)
            elif daily_v > 0:
                # 7-day supply buffer minus any remaining stock
                needed = (daily_v * 7) - max(0.0, stock)
                reorder_qty = max(1.0, math.ceil(needed))
            else:
                reorder_qty = 1.0

            # Estimate cost based on last purchase price
            last_p = (
                db.query(PurchaseLog)
                .filter(PurchaseLog.canonical_item_id == item.id, PurchaseLog.price.isnot(None))
                .order_by(PurchaseLog.purchase_date.desc())
                .first()
            )
            est_cost = round(last_p.price * (reorder_qty / max(1.0, last_p.quantity)), 2) if last_p and last_p.price else None

            store = item.preferred_store or (last_p.store_name if last_p else "Any Store")

            entry = GroceryListEntry(
                household_id=household_id,
                canonical_item_id=item.id,
                custom_item_name=None,
                category=item.category,
                target_store=store,
                recommended_quantity=float(reorder_qty),
                unit=unit,
                estimated_cost=est_cost,
                priority_reason=priority,
                is_checked=False,
                estimated_runout_date=est_runout_date
            )
            db.add(entry)

    db.commit()

    # Query all entries (including manual ones)
    all_entries = (
        db.query(GroceryListEntry)
        .filter(GroceryListEntry.household_id == household_id)
        .order_by(GroceryListEntry.is_checked.asc(), GroceryListEntry.priority_reason.asc())
        .all()
    )

    items_out: List[GroceryListItemOut] = []
    items_by_store: Dict[str, List[dict]] = {}
    items_by_cat: Dict[str, List[dict]] = {}
    total_cost = 0.0

    for e in all_entries:
        name = e.item.canonical_name if e.item else (e.custom_item_name or "Item")
        cost = e.estimated_cost or 0.0
        if not e.is_checked:
            total_cost += cost

        item_dict = {
            "id": e.id,
            "canonical_item_id": e.canonical_item_id,
            "item_name": name,
            "category": e.category,
            "target_store": e.target_store,
            "recommended_quantity": e.recommended_quantity,
            "unit": e.unit,
            "estimated_cost": e.estimated_cost,
            "priority_reason": e.priority_reason,
            "is_checked": e.is_checked,
            "estimated_runout_date": e.estimated_runout_date
        }

        items_out.append(GroceryListItemOut(**item_dict))

        # Grouping
        store_key = e.target_store or "Any Store"
        items_by_store.setdefault(store_key, []).append(item_dict)

        cat_key = e.category or "General"
        items_by_cat.setdefault(cat_key, []).append(item_dict)

    return GroceryListResponse(
        household_id=household_id,
        forecast_days=forecast_days,
        generated_date=as_of_date,
        total_items=len(items_out),
        total_estimated_cost=round(total_cost, 2),
        items=items_out,
        items_by_store=items_by_store,
        items_by_category=items_by_cat
    )
