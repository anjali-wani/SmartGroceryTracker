#!/usr/bin/env python3
"""Script to seed the Smart Grocery Tracker database from data/product_mappings.json."""
import os
import sys
import argparse
from pathlib import Path

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import ProdSessionLocal, TestSessionLocal, PROD_DB_PATH, TEST_DB_PATH
from app.services.mapping_service import seed_database_from_mappings, get_mappings_file_path, load_product_mappings


def main():
    parser = argparse.ArgumentParser(description="Seed database with product -> generic mappings.")
    parser.add_argument(
        "--env",
        choices=["test", "production", "prod"],
        default="test",
        help="Target database environment (default: test)"
    )
    args = parser.parse_args()

    target_env = "production" if args.env in ("production", "prod") else "test"
    db_factory = ProdSessionLocal if target_env == "production" else TestSessionLocal
    db_path = PROD_DB_PATH if target_env == "production" else TEST_DB_PATH

    print("=" * 60)
    print(f"  Seeding Product Mappings into {target_env.upper()} Database")
    print(f"  Target DB : {db_path}")
    print(f"  JSON File : {get_mappings_file_path()}")
    print("=" * 60)

    mappings = load_product_mappings()
    print(f"Loaded {len(mappings)} product mappings from file.")

    session = db_factory()
    try:
        counts = seed_database_from_mappings(session)
        print(f"✅ Seeding Complete!")
        print(f"   Canonical Items Created : {counts['items_created']}")
        print(f"   Aliases Created         : {counts['aliases_created']}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
