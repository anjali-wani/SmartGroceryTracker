from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.models import GroceryListEntry, Item, PurchaseLog, Inventory, InventoryStatus
from app.schemas import GroceryListResponse, GroceryListItemOut, AvailabilityPrompt
from app.services.analytics import compute_item_velocity, determine_preferred_store
from app.normalizer import convert_quantity, format_store_name


def generate_smart_grocery_list(
    db: Session,
    household_id: int = 1,
    forecast_days: int = 7,
    target_store: Optional[str] = None,
    as_of_date: Optional[date] = None
) -> GroceryListResponse:
    """Evaluates purchase intervals, runout projections, and periodic schedules.
    Completely decoupled from expiration dates.
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Clear previously generated unchecked auto-items, preserving manual, dismissed, and confirmed depleted items
    db.query(GroceryListEntry).filter(
        GroceryListEntry.household_id == household_id,
        GroceryListEntry.is_checked == False,
        (GroceryListEntry.is_dismissed == False) | (GroceryListEntry.is_dismissed == None),
        GroceryListEntry.priority_reason.notin_(["MANUAL", "CONFIRMED_DEPLETED"])
    ).delete(synchronize_session=False)

    # Immediately purge any non-grocery entries from the grocery list
    db.query(GroceryListEntry).filter(
        GroceryListEntry.household_id == household_id,
        (GroceryListEntry.category.ilike("%non%grocery%")) |
        (GroceryListEntry.canonical_item_id.in_(
            db.query(Item.id).filter(
                (Item.is_grocery == False) | (Item.category.ilike("%non%grocery%"))
            )
        ))
    ).delete(synchronize_session=False)
    db.commit()

    # Track items already queued on the list
    existing_queued_ids = set(
        x[0] for x in db.query(GroceryListEntry.canonical_item_id).filter(
            GroceryListEntry.household_id == household_id,
            GroceryListEntry.is_checked == False,
            GroceryListEntry.canonical_item_id.isnot(None)
        ).all()
    )
    dismissed_canonical_ids = set(
        x[0] for x in db.query(GroceryListEntry.canonical_item_id).filter(
            GroceryListEntry.household_id == household_id,
            GroceryListEntry.is_dismissed == True,
            GroceryListEntry.canonical_item_id.isnot(None)
        ).all()
    )

    # Find items relevant to this household (purchased or in inventory)
    household_item_ids = set(
        x[0] for x in db.query(PurchaseLog.canonical_item_id)
        .filter(PurchaseLog.household_id == household_id, PurchaseLog.canonical_item_id.isnot(None))
        .distinct()
        .all()
    ) | set(
        x[0] for x in db.query(Inventory.canonical_item_id)
        .filter(Inventory.household_id == household_id)
        .distinct()
        .all()
    )

    active_items: List[Item] = (
        db.query(Item)
        .filter(
            Item.is_active == True,
            Item.is_grocery == True,
            ~Item.category.ilike("%non%grocery%"),
            Item.id.in_(household_item_ids)
        )
        .order_by(Item.category, Item.canonical_name)
        .all()
    )

    availability_prompts: List[AvailabilityPrompt] = []

    for item in active_items:
        if not item.is_grocery or (item.category and "non" in item.category.lower() and "grocery" in item.category.lower()):
            continue

        # Determine preferred store by purchase frequency; if tied, take the store from the last entry
        pref_from_history = determine_preferred_store(item.id, db, household_id=household_id, fallback_store=item.preferred_store)
        if pref_from_history and item.preferred_store != pref_from_history:
            item.preferred_store = pref_from_history
            db.add(item)

        if target_store and item.preferred_store and format_store_name(item.preferred_store).lower() != format_store_name(target_store).lower():
            continue

        if item.id in existing_queued_ids or item.id in dismissed_canonical_ids:
            continue

        velocity_data = compute_item_velocity(item, db, household_id=household_id, as_of_date=as_of_date)

        should_reorder = False
        priority = "RUNNING_LOW"
        est_runout_date = None

        # 1. Periodic Purchase Scheduler takes priority if configured
        if item.reorder_cadence_days and item.reorder_cadence_days > 0:
            last_purchase = velocity_data.last_purchased
            if last_purchase:
                days_since_purchase = (as_of_date - last_purchase).days
                if days_since_purchase >= item.reorder_cadence_days:
                    should_reorder = True
                    priority = "SCHEDULED_PERIODIC"
                    est_runout_date = as_of_date
            else:
                should_reorder = True
                priority = "SCHEDULED_PERIODIC"
                est_runout_date = as_of_date

        # 2. Single-purchase items without periodic cadence: do not auto-reorder
        elif velocity_data.purchase_count <= 1:
            continue

        # 3. Purchase-Interval Runout Trigger:
        # Trigger reorder if projected runout date is reached or within forecast_days
        if not should_reorder and velocity_data.projected_runout_date:
            days_until_runout = (velocity_data.projected_runout_date - as_of_date).days
            if days_until_runout <= forecast_days:
                should_reorder = True
                priority = "CRITICAL_DEPLETION" if days_until_runout <= 0 else "RUNNING_LOW"
                est_runout_date = velocity_data.projected_runout_date

        if should_reorder:
            # Recommended quantity is the modal purchase quantity (with larger tie-breaker)
            reorder_qty = velocity_data.modal_quantity if velocity_data.modal_quantity else 1.0

            CATEGORY_BENCHMARKS = {
                "Produce": 2.49,
                "Dairy": 4.29,
                "Bakery": 3.99,
                "Meat & Seafood": 8.99,
                "Grains & Pasta": 4.49,
                "Snacks": 3.29,
                "Beverages": 3.99,
                "Pantry": 3.99,
                "General": 3.49
            }
            est_cost = None

            last_p = (
                db.query(PurchaseLog)
                .filter(
                    PurchaseLog.household_id == household_id,
                    PurchaseLog.canonical_item_id == item.id,
                    PurchaseLog.price.isnot(None),
                    PurchaseLog.price > 0
                )
                .order_by(PurchaseLog.purchase_date.desc(), PurchaseLog.id.desc())
                .first()
            )

            # 1. Try to compute from most recent purchase if unit is compatible
            if last_p and last_p.price and last_p.price > 0 and last_p.quantity and last_p.quantity > 0:
                p_unit = (last_p.unit or "").strip().lower()
                target_unit = (item.standard_unit or "").strip().lower()

                if p_unit == target_unit:
                    est_cost = round(last_p.price * (reorder_qty / last_p.quantity), 2)
                else:
                    converted_p_qty = convert_quantity(last_p.quantity, p_unit, target_unit)
                    if converted_p_qty and converted_p_qty > 0:
                        est_cost = round(last_p.price * (reorder_qty / converted_p_qty), 2)

            # 2. Fall back to item's default unit price (keyed to item.standard_unit)
            if est_cost is None and item.default_unit_price and item.default_unit_price > 0:
                est_cost = round(item.default_unit_price * reorder_qty, 2)

            # 3. Fall back to category benchmark
            if est_cost is None:
                benchmark = CATEGORY_BENCHMARKS.get(item.category, 3.49)
                est_cost = round(benchmark * reorder_qty, 2)
            # Determine preferred store by purchase frequency; if tied, take the store from the last entry
            pref_from_history = determine_preferred_store(item.id, db, household_id=household_id, fallback_store=item.preferred_store)
            store = pref_from_history or (format_store_name(item.preferred_store) if item.preferred_store else "Any Store")
            if pref_from_history and item.preferred_store != pref_from_history:
                item.preferred_store = pref_from_history
                db.add(item)

            entry = GroceryListEntry(
                household_id=household_id,
                canonical_item_id=item.id,
                custom_item_name=None,
                category=item.category,
                target_store=store,
                recommended_quantity=float(reorder_qty),
                unit=item.standard_unit,
                estimated_cost=est_cost,
                priority_reason=priority,
                is_checked=False,
                estimated_runout_date=est_runout_date
            )
            db.add(entry)

    db.commit()

    dismissed_canonical_ids = set(
        x[0] for x in db.query(GroceryListEntry.canonical_item_id).filter(
            GroceryListEntry.household_id == household_id,
            GroceryListEntry.is_dismissed == True,
            GroceryListEntry.canonical_item_id.isnot(None)
        ).all()
    )

    query = (
        db.query(GroceryListEntry)
        .outerjoin(Item, GroceryListEntry.canonical_item_id == Item.id)
        .filter(
            GroceryListEntry.household_id == household_id,
            (GroceryListEntry.is_dismissed == False) | (GroceryListEntry.is_dismissed == None),
            ~GroceryListEntry.category.ilike("%non%grocery%"),
            (Item.id == None) | ((Item.is_grocery == True) & (~Item.category.ilike("%non%grocery%")))
        )
    )
    if dismissed_canonical_ids:
        query = query.filter(
            (GroceryListEntry.canonical_item_id.notin_(dismissed_canonical_ids)) | (GroceryListEntry.canonical_item_id == None)
        )
    all_entries = query.order_by(GroceryListEntry.is_checked.asc(), GroceryListEntry.priority_reason.asc()).all()

    items_out: List[GroceryListItemOut] = []
    items_by_store: Dict[str, List[dict]] = {}
    items_by_cat: Dict[str, List[dict]] = {}
    total_cost = 0.0

    for e in all_entries:
        cat_lower = (e.category or (e.item.category if e.item else "") or "").lower()
        if "non" in cat_lower and "grocery" in cat_lower:
            continue
        if e.item and (not e.item.is_grocery or (e.item.category and "non" in e.item.category.lower() and "grocery" in e.item.category.lower())):
            continue

        # Automatically synchronize target_store with canonical item's preferred_store based on frequency & recency (unless manually overridden)
        if e.item and e.priority_reason != "MANUAL":
            pref_store = determine_preferred_store(e.item.id, db, household_id=household_id, fallback_store=e.item.preferred_store)
            if pref_store:
                if e.item.preferred_store != pref_store:
                    e.item.preferred_store = pref_store
                    db.add(e.item)
                if e.target_store != pref_store:
                    e.target_store = pref_store
                    db.add(e)

        name = e.item.canonical_name if e.item else (e.custom_item_name or "Item")
        cost = e.estimated_cost
        if cost is None or cost <= 0:
            bench = 3.49
            for k, val in CATEGORY_BENCHMARKS.items():
                if k in cat_lower:
                    bench = val
                    break
            cost = round((e.recommended_quantity or 1.0) * bench, 2)
            e.estimated_cost = cost
            db.add(e)
            
        if not e.is_checked:
            total_cost += (cost or 0.0)

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
        store_key = format_store_name(e.target_store) if e.target_store and e.target_store.lower() not in ("any store", "any") else "Any Store"
        items_by_store.setdefault(store_key, []).append(item_dict)
        cat_key = e.category or "General"
        items_by_cat.setdefault(cat_key, []).append(item_dict)

    db.commit()
    return GroceryListResponse(
        household_id=household_id,
        forecast_days=forecast_days,
        generated_date=as_of_date,
        total_items=len(items_out),
        total_estimated_cost=round(total_cost, 2),
        items=items_out,
        items_by_store=items_by_store,
        items_by_category=items_by_cat,
        availability_prompts=availability_prompts
    )
