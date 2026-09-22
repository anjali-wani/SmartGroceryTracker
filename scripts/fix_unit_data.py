import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def fix_db(db_path: Path):
    if not db_path.exists():
        return
    print(f"Fixing database: {db_path.name}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Fix 907g deep flour and dals incorrectly saved as 907 lb
    fixes = [
        # (raw_text_pattern, correct_qty, correct_unit, correct_unit_price)
        ("%DEEP RICE FLOUR%", 2.0, "lb", 1.495),
        ("%DEEP MASOOR DAL%", 2.0, "lb", 1.895),
        ("%DEEP TOOR DAL%", 2.0, "lb", 1.995),
        ("%GARVI GUJARAT BHEL SEV%", 10.05, "oz", 0.3274),
        ("%Ashoka Grated Coconut%", 10.93, "oz", 0.3925),
        ("%Vadilal Green Peas Mutter%", 11.01, "oz", 0.3170),
    ]

    for pattern, new_qty, new_unit, new_up in fixes:
        # Update purchase logs
        c.execute("""
            UPDATE purchase_logs
            SET quantity = ?, unit = ?, unit_price = ?
            WHERE raw_text LIKE ? AND quantity > 50
        """, (new_qty, new_unit, new_up, pattern))
        print(f"  Updated purchase_logs for {pattern}: {c.rowcount} rows")

        # Update inventory where linked to these purchases
        c.execute("""
            UPDATE inventory
            SET current_quantity = ?, unit = ?
            WHERE purchase_log_id IN (
                SELECT id FROM purchase_logs WHERE raw_text LIKE ?
            ) AND current_quantity > 50
        """, (new_qty, new_unit, pattern))
        print(f"  Updated inventory for {pattern}: {c.rowcount} rows")

    # 2. Fix canonical item default_unit_price if stored in cents per gram instead of dollars per lb
    c.execute("""
        UPDATE items
        SET default_unit_price = 1.995
        WHERE canonical_name LIKE '%Toor Dal%' AND (default_unit_price < 0.1 OR default_unit_price IS NULL)
    """)
    c.execute("""
        UPDATE items
        SET default_unit_price = 1.495
        WHERE canonical_name LIKE '%Rice Flour%' AND (default_unit_price < 0.1 OR default_unit_price IS NULL)
    """)
    c.execute("""
        UPDATE items
        SET default_unit_price = 1.895
        WHERE canonical_name LIKE '%Masoor%' AND (default_unit_price < 0.1 OR default_unit_price IS NULL)
    """)

    conn.commit()
    conn.close()
    print(f"Database {db_path.name} fix completed.\n")


if __name__ == "__main__":
    fix_db(PROJECT_ROOT / "grocery_tracker_test.db")
    fix_db(PROJECT_ROOT / "grocery_tracker.db")
