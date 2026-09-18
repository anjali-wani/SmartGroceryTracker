from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import Inventory, InventoryStatus, Item, PurchaseLog


def reconcile_repurchased_inventory(db: Session, household_id: int = 1):
    """Ensures that whenever an item is purchased again, previous purchases of that item
    are considered consumed, marked as CONSUMED with current_quantity = 0.0,
    and no longer displayed in the active kitchen pantry.
    Also ensures Non-Grocery items are never active in the kitchen pantry.
    """
    # 1. Mark any active inventory batch as CONSUMED if a newer purchase exists for this item
    db.execute(text("""
        UPDATE inventory
        SET status = 'CONSUMED', current_quantity = 0.0
        WHERE id IN (
            SELECT i.id
            FROM inventory i
            JOIN (
                SELECT canonical_item_id, MAX(purchase_date) as max_date
                FROM purchase_logs
                WHERE household_id = :household_id
                GROUP BY canonical_item_id
            ) p ON i.canonical_item_id = p.canonical_item_id
            WHERE i.household_id = :household_id
              AND i.status = 'ACTIVE'
              AND i.purchase_date < p.max_date
        )
    """), {"household_id": household_id})

    # 2. Also ensure non-grocery items are never active in kitchen pantry
    db.execute(text("""
        UPDATE inventory
        SET status = 'CONSUMED', current_quantity = 0.0
        WHERE id IN (
            SELECT i.id
            FROM inventory i
            JOIN items it ON i.canonical_item_id = it.id
            WHERE i.household_id = :household_id
              AND i.status = 'ACTIVE'
              AND (it.is_grocery = 0 OR it.category = 'Non-Grocery')
        )
    """), {"household_id": household_id})

    db.commit()
