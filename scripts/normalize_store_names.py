#!/usr/bin/env python3
"""Script to normalize and migrate store names across all database records to Title Case."""
import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import ProdSessionLocal, TestSessionLocal, PROD_DB_PATH, TEST_DB_PATH
from app.models import ReceiptUpload, PurchaseLog, Inventory, Item, GroceryListEntry
from app.normalizer import format_store_name


def normalize_stores_for_session(session, env_name: str):
    print(f"\n--- Processing {env_name.upper()} Database ---")
    
    # 1. Update Items preferred_store
    items = session.query(Item).filter(Item.preferred_store.isnot(None)).all()
    items_updated = 0
    for it in items:
        cleaned = format_store_name(it.preferred_store)
        if cleaned != it.preferred_store:
            it.preferred_store = cleaned
            items_updated += 1

    # 2. Update PurchaseLog store_name
    purchases = session.query(PurchaseLog).filter(PurchaseLog.store_name.isnot(None)).all()
    purchases_updated = 0
    for p in purchases:
        cleaned = format_store_name(p.store_name)
        if cleaned != p.store_name:
            p.store_name = cleaned
            purchases_updated += 1

    # 3. Update Inventory store_name
    inventories = session.query(Inventory).filter(Inventory.store_name.isnot(None)).all()
    inv_updated = 0
    for inv in inventories:
        cleaned = format_store_name(inv.store_name)
        if cleaned != inv.store_name:
            inv.store_name = cleaned
            inv_updated += 1

    # 4. Update GroceryListEntry target_store
    entries = session.query(GroceryListEntry).filter(GroceryListEntry.target_store.isnot(None)).all()
    entries_updated = 0
    for e in entries:
        if e.target_store and e.target_store.lower() not in ("any store", "any"):
            cleaned = format_store_name(e.target_store)
            if cleaned != e.target_store:
                e.target_store = cleaned
                entries_updated += 1

    # 5. Update ReceiptUpload store_name & merge duplicates if collision occurs
    bills = session.query(ReceiptUpload).all()
    bills_updated = 0
    bills_merged = 0

    # Group bills by (household_id, new_store_name, bill_date)
    grouped = {}
    for b in bills:
        new_store = format_store_name(b.store_name)
        key = (b.household_id, new_store, b.bill_date)
        grouped.setdefault(key, []).append((b, new_store))

    for (h_id, new_store, b_date), bill_list in grouped.items():
        primary_bill, _ = bill_list[0]
        if primary_bill.store_name != new_store:
            primary_bill.store_name = new_store
            bills_updated += 1

        # If multiple bills now share the exact same household, store, and date, merge them
        if len(bill_list) > 1:
            for duplicate_bill, _ in bill_list[1:]:
                # Re-link purchases
                session.query(PurchaseLog).filter(PurchaseLog.bill_id == duplicate_bill.id).update(
                    {"bill_id": primary_bill.id}
                )
                primary_bill.total_items += duplicate_bill.total_items
                primary_bill.total_amount = round(primary_bill.total_amount + duplicate_bill.total_amount, 2)
                session.delete(duplicate_bill)
                bills_merged += 1

    session.commit()
    print(f"  Canonical Items Updated      : {items_updated}")
    print(f"  Purchase Logs Updated        : {purchases_updated}")
    print(f"  Inventory Entries Updated    : {inv_updated}")
    print(f"  Grocery List Entries Updated : {entries_updated}")
    print(f"  Receipt Uploads Updated      : {bills_updated}")
    print(f"  Receipt Uploads Merged       : {bills_merged}")


def main():
    parser = argparse.ArgumentParser(description="Normalize existing store names across database tables.")
    parser.add_argument(
        "--env",
        choices=["test", "production", "prod", "all"],
        default="all",
        help="Target database environment (default: all)"
    )
    args = parser.parse_args()

    targets = []
    if args.env in ("test", "all"):
        targets.append(("test", TestSessionLocal, TEST_DB_PATH))
    if args.env in ("production", "prod", "all"):
        targets.append(("production", ProdSessionLocal, PROD_DB_PATH))

    for env_name, factory, path in targets:
        session = factory()
        try:
            normalize_stores_for_session(session, env_name)
        finally:
            session.close()

    print("\n✅ Store name normalization complete across target databases.")


if __name__ == "__main__":
    main()
