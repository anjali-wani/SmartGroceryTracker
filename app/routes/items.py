from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Item, ItemAlias, Inventory, InventoryStatus
from app.schemas import ItemOut, ItemCreate, ItemAliasOut, InventoryOut, ItemArchiveResponse, ItemScheduleUpdate

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

    item = Item(
        canonical_name=item_in.canonical_name,
        category=item_in.category,
        standard_unit=item_in.standard_unit,
        default_shelf_life_days=item_in.default_shelf_life_days,
        is_bulk=item_in.is_bulk
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
    status_filter: InventoryStatus = Query(InventoryStatus.ACTIVE, description="Inventory item status"),
    db: Session = Depends(get_db)
):
    """View current active inventory items with remaining quantities and expiration countdowns."""
    inventory_items = (
        db.query(Inventory)
        .filter(Inventory.status == status_filter)
        .order_by(Inventory.expiration_date.asc())
        .all()
    )

    out = []
    for inv in inventory_items:
        out.append(InventoryOut(
            id=inv.id,
            canonical_item_id=inv.canonical_item_id,
            item_name=inv.item.canonical_name if inv.item else "Unknown",
            category=inv.item.category if inv.item else "General",
            current_quantity=inv.current_quantity,
            unit=inv.unit,
            purchase_date=inv.purchase_date,
            expiration_date=inv.expiration_date,
            status=inv.status
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

    db.commit()
    db.refresh(item)
    return item
