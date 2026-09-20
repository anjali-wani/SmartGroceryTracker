#!/usr/bin/env python3
"""Script to clear all data from the SmartGroceryTracker test database."""
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import clear_database, TEST_DB_PATH, TestSessionLocal
from app.models import (
    GroceryListEntry,
    GuestEvent,
    Inventory,
    PurchaseLog,
    ReceiptUpload,
    ItemAlias,
    Item,
    Household,
)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clear test database with optional product mappings reseeding.")
    parser.add_argument(
        "--seed-mappings",
        "--seed",
        "-s",
        action="store_true",
        help="Re-seed canonical items and aliases from data/product_mappings.json after wipe"
    )
    args = parser.parse_args()

    print(f"Target test database: {TEST_DB_PATH}")

    session = TestSessionLocal()
    try:
        before_counts = {
            "items": session.query(Item).count(),
            "inventory": session.query(Inventory).count(),
            "purchase_logs": session.query(PurchaseLog).count(),
            "receipt_uploads": session.query(ReceiptUpload).count(),
            "aliases": session.query(ItemAlias).count(),
            "grocery_list": session.query(GroceryListEntry).count(),
            "guest_events": session.query(GuestEvent).count(),
        }
        print("Record counts before cleanup:", before_counts)
    finally:
        session.close()

    print("Clearing test database...")
    clear_database("test")

    if args.seed_mappings:
        from app.services.mapping_service import seed_database_from_mappings
        print("🌱 Re-seeding database from data/product_mappings.json...")
        sess = TestSessionLocal()
        try:
            if not sess.query(Household).filter(Household.id == 1).first():
                sess.add(Household(id=1, name="My Household", member_count=2))
                sess.commit()
            seed_database_from_mappings(sess)
        finally:
            sess.close()

    session = TestSessionLocal()
    try:
        after_counts = {
            "items": session.query(Item).count(),
            "inventory": session.query(Inventory).count(),
            "purchase_logs": session.query(PurchaseLog).count(),
            "receipt_uploads": session.query(ReceiptUpload).count(),
            "aliases": session.query(ItemAlias).count(),
            "grocery_list": session.query(GroceryListEntry).count(),
            "guest_events": session.query(GuestEvent).count(),
        }
        print("Record counts after cleanup:", after_counts)
        print("Successfully wiped all data from test database! Ready for fresh receipt upload.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
