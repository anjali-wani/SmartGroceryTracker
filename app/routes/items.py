from datetime import date, timedelta
from app.services.analytics import compute_item_velocity
from app.services.inventory_service import reconcile_repurchased_inventory
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Item, ItemAlias, Inventory, InventoryStatus, PurchaseLog
from app.schemas import ItemOut, ItemCreate, ItemAliasOut, InventoryOut, ItemArchiveResponse, ItemScheduleUpdate, ItemDetailsOut, ItemPurchaseHistoryEntry, ItemConsumptionRhythm

router = APIRouter(prefix="/items", tags=["Items & Inventory"])


@router.get("", response_model=List[ItemOut])
def list_canonical_items(
    category: Optional[str] = Query(None, description="Filter by food category"),
    search: Optional[str] = Query(None, description="Search by item name"),
    db: Session = Depends(get_db)
):
    """List canonical food items in the database with their registered aliases."""
    query = db.query(Item)
    if category:
        query = query.filter(Item.category.ilike(f"%{category}%"))
    if search:
        query = query.filter(Item.canonical_name.ilike(f"%{search}%"))
    return query.order_by(Item.category, Item.canonical_name).all()


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_canonical_item(item_in: ItemCreate, db: Session = Depends(get_db)):
    """Create a new canonical grocery item."""
    existing = db.query(Item).filter(Item.canonical_name.ilike(item_in.canonical_name)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item '{item_in.canonical_name}' already exists with ID {existing.id}."
        )

    # Check if this name is already registered as an alias for another canonical item
    clean_alias_name = item_in.canonical_name.strip().lower()
    existing_alias = db.query(ItemAlias).filter(ItemAlias.raw_alias == clean_alias_name).first()
    if existing_alias:
        parent_item = existing_alias.item
        parent_name = parent_item.canonical_name if parent_item else f"ID {existing_alias.canonical_item_id}"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot add item '{item_in.canonical_name}': this name is already registered as an alias for '{parent_name}' (Item ID {existing_alias.canonical_item_id})."
        )

    item = Item(
        canonical_name=item_in.canonical_name,
        category=item_in.category,
        standard_unit=item_in.standard_unit,
        default_shelf_life_days=item_in.default_shelf_life_days,
        is_bulk=item_in.is_bulk,
        is_grocery=item_in.is_grocery,
        default_unit_price=item_in.default_unit_price,
        preferred_store=item_in.preferred_store
    )
    db.add(item)
    db.flush()

    # Automatically add canonical name as an alias
    alias = ItemAlias(
        canonical_item_id=item.id,
        raw_alias=item_in.canonical_name.lower(),
        match_confidence=1.0,
        source="user_created"
    )
    db.add(alias)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/aliases", response_model=ItemAliasOut, status_code=status.HTTP_201_CREATED)
def add_item_alias(
    item_id: int,
    raw_alias: str = Query(..., min_length=2, description="New alias string"),
    db: Session = Depends(get_db)
):
    """Add a custom store alias for a canonical grocery item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    clean_alias = raw_alias.strip().lower()
    existing_alias = db.query(ItemAlias).filter(ItemAlias.raw_alias == clean_alias).first()
    if existing_alias:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alias '{clean_alias}' already mapped to item ID {existing_alias.canonical_item_id}"
        )

    alias = ItemAlias(
        canonical_item_id=item_id,
        raw_alias=clean_alias,
        match_confidence=1.0,
        source="user_defined"
    )
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


@router.get("/inventory/current", response_model=List[InventoryOut])
def get_current_inventory(
    household_id: int = Query(1, description="Household ID"),
    status_filter: Optional[InventoryStatus] = Query(None, description="Inventory item status (ACTIVE, CONSUMED, etc.). If omitted, returns all items."),
    db: Session = Depends(get_db)
):
    """View current inventory items for a household with remaining quantities and purchase dates."""
    reconcile_repurchased_inventory(db, household_id)
    query = (
        db.query(Inventory)
        .join(Item, Inventory.canonical_item_id == Item.id)
        .filter(
            Inventory.household_id == household_id,
            Item.is_grocery == True,
            Item.category != "Non-Grocery"
        )
    )
    if status_filter is not None:
        query = query.filter(Inventory.status == status_filter)
    inventory_items = query.order_by(Inventory.purchase_date.desc(), Inventory.id.desc()).all()

    out = []
    for inv in inventory_items:
        store = inv.store_name
        price = inv.price
        if not store or not price:
            log = None
            if inv.purchase_log_id:
                log = db.query(PurchaseLog).filter(PurchaseLog.id == inv.purchase_log_id).first()
            if not log:
                log = (
                    db.query(PurchaseLog)
                    .filter(
                        PurchaseLog.household_id == inv.household_id,
                        PurchaseLog.canonical_item_id == inv.canonical_item_id,
                        PurchaseLog.purchase_date == inv.purchase_date
                    )
                    .order_by(PurchaseLog.id.desc())
                    .first()
                )
            if not log:
                log = (
                    db.query(PurchaseLog)
                    .filter(
                        PurchaseLog.household_id == inv.household_id,
                        PurchaseLog.canonical_item_id == inv.canonical_item_id
                    )
                    .order_by(PurchaseLog.purchase_date.desc(), PurchaseLog.id.desc())
                    .first()
                )
            if not store:
                store = log.store_name if log and log.store_name else (inv.item.preferred_store if inv.item else "Grocery Store")
            if not price:
                price = log.price if log and log.price and log.price > 0 else (inv.item.default_unit_price if inv.item and inv.item.default_unit_price else 2.99)

        out.append(InventoryOut(
            id=inv.id,
            household_id=inv.household_id,
            canonical_item_id=inv.canonical_item_id,
            item_name=inv.item.canonical_name if inv.item else "Unknown",
            category=inv.item.category if inv.item else "General",
            current_quantity=inv.current_quantity,
            unit=inv.unit,
            purchase_date=inv.purchase_date,
            status=inv.status,
            store_name=store or "Grocery Store",
            price=round(price, 2) if price else 2.99
        ))
    return out


@router.patch("/{item_id}/archive", response_model=ItemArchiveResponse)
def toggle_archive_item(
    item_id: int,
    archive: bool = Query(True, description="True to archive, False to restore"),
    db: Session = Depends(get_db)
):
    """Soft-archive an item (is_active=False).
    
    Preserves historical spending records and velocity metrics while excluding the item
    from future automated grocery lists.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

    item.is_active = not archive
    db.commit()
    db.refresh(item)

    status_str = "archived (excluded from grocery lists)" if archive else "restored to active status"
    return ItemArchiveResponse(
        id=item.id,
        canonical_name=item.canonical_name,
        is_active=item.is_active,
        message=f"Item '{item.canonical_name}' {status_str}."
    )


@router.patch("/{item_id}/schedule", response_model=ItemOut)
def update_item_schedule(
    item_id: int,
    payload: ItemScheduleUpdate,
    db: Session = Depends(get_db)
):
    """Configure periodic purchase schedule (e.g. Cadence of 14 days for bi-weekly spinach) and preferred store."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

    if payload.reorder_cadence_days is not None:
        item.reorder_cadence_days = payload.reorder_cadence_days
    if payload.preferred_store is not None:
        item.preferred_store = payload.preferred_store
    if payload.default_unit_price is not None:
        item.default_unit_price = payload.default_unit_price

    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}/details", response_model=ItemDetailsOut)
def get_item_full_details(
    item_id: int,
    household_id: int = Query(1, description="Household ID"),
    db: Session = Depends(get_db)
):
    """Retrieve comprehensive details for an item: past purchase history sorted descending by date,
    calculated consumption rate & rhythm, current pantry stock status, and registered aliases.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item with ID {item_id} not found.")

    # 1. Current active stock in pantry
    inv = db.query(Inventory).filter(
        Inventory.household_id == household_id,
        Inventory.canonical_item_id == item_id,
        Inventory.status == InventoryStatus.ACTIVE
    ).order_by(Inventory.purchase_date.desc(), Inventory.id.desc()).first()

    active_inv_out = None
    if inv:
        store = inv.store_name
        price = inv.price
        if not store or not price:
            last_log = db.query(PurchaseLog).filter(
                PurchaseLog.household_id == household_id,
                PurchaseLog.canonical_item_id == item_id
            ).order_by(PurchaseLog.purchase_date.desc(), PurchaseLog.id.desc()).first()
            if not store:
                store = last_log.store_name if last_log and last_log.store_name else (item.preferred_store or "Grocery Store")
            if not price:
                price = last_log.price if last_log and last_log.price and last_log.price > 0 else (item.default_unit_price or 2.99)
        active_inv_out = InventoryOut(
            id=inv.id,
            household_id=inv.household_id,
            canonical_item_id=inv.canonical_item_id,
            item_name=item.canonical_name,
            category=item.category,
            current_quantity=inv.current_quantity,
            unit=inv.unit,
            purchase_date=inv.purchase_date,
            status=inv.status,
            store_name=store or "Grocery Store",
            price=round(price, 2) if price else 2.99
        )

    # 2. Consumption rhythm calculation
    velocity_data = compute_item_velocity(item, db, household_id=household_id, as_of_date=date.today())
    daily_rate = velocity_data.daily_velocity or 0.0
    days_left = velocity_data.estimated_days_remaining
    runout_date = velocity_data.projected_runout_date
    if days_left is None and inv and inv.current_quantity > 0 and daily_rate > 0:
        days_left = round(inv.current_quantity / daily_rate, 1)
        runout_date = date.today() + timedelta(days=int(days_left))

    rhythm = ItemConsumptionRhythm(
        daily_rate=daily_rate,
        avg_purchase_interval_days=velocity_data.avg_purchase_interval_days,
        days_left=days_left,
        runout_date=runout_date,
        burn_rate_weekly=round(daily_rate * 7.0, 2)
    )

    # 3. Past purchase history sorted descending by purchase date
    purchase_logs = db.query(PurchaseLog).filter(
        PurchaseLog.household_id == household_id,
        PurchaseLog.canonical_item_id == item_id
    ).order_by(PurchaseLog.purchase_date.desc(), PurchaseLog.id.desc()).all()

    item_out = ItemOut.model_validate(item)
    if item_out.default_unit_price is None:
        recent_price = next((p.price for p in purchase_logs if p.price is not None and p.price > 0), None)
        if not recent_price and active_inv_out and active_inv_out.price:
            recent_price = active_inv_out.price
        if recent_price:
            item_out.default_unit_price = round(recent_price, 2)

    history_out = []
    for p in purchase_logs:
        price_val = p.price
        unit_price_val = p.unit_price
        if price_val is None or price_val <= 0:
            unit_rate = item_out.default_unit_price or 3.99
            qty = p.quantity if p.quantity and p.quantity > 0 else 1.0
            price_val = round(unit_rate * qty, 2)
            unit_price_val = unit_rate
        elif unit_price_val is None and p.quantity and p.quantity > 0:
            unit_price_val = round(price_val / p.quantity, 2)

        history_out.append(
            ItemPurchaseHistoryEntry(
                id=p.id,
                store_name=p.store_name or "Grocery Store",
                purchase_date=p.purchase_date,
                quantity=p.quantity,
                unit=p.unit,
                price=round(price_val, 2),
                unit_price=round(unit_price_val, 2) if unit_price_val is not None else None,
                raw_text=p.raw_text
            )
        )

    # 4. Registered store aliases
    aliases_out = [
        ItemAliasOut.model_validate(a) for a in item.aliases
    ]

    return ItemDetailsOut(
        item=item_out,
        active_inventory=active_inv_out,
        consumption_rhythm=rhythm,
        purchase_history=history_out,
        aliases=aliases_out
    )


@router.delete("/aliases/{alias_id}", status_code=status.HTTP_200_OK)
def delete_item_alias(alias_id: int, db: Session = Depends(get_db)):
    """Delete a registered alias for an item."""
    alias = db.query(ItemAlias).filter(ItemAlias.id == alias_id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found.")
    db.delete(alias)
    db.commit()
    return {"message": "Alias deleted successfully."}


@router.patch("/aliases/{alias_id}", response_model=ItemAliasOut)
def update_item_alias(
    alias_id: int,
    raw_alias: str = Query(..., min_length=2, description="Updated alias text"),
    db: Session = Depends(get_db)
):
    """Update an existing store alias string."""
    alias = db.query(ItemAlias).filter(ItemAlias.id == alias_id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found.")
    clean_alias = raw_alias.strip().lower()
    existing = db.query(ItemAlias).filter(ItemAlias.raw_alias == clean_alias, ItemAlias.id != alias_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alias already in use.")
    alias.raw_alias = clean_alias
    db.commit()
    db.refresh(alias)
    return alias
