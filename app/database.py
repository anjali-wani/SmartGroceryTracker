import os
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv
from fastapi import Request

logger = logging.getLogger("grocery_database")

# Base directory for SmartGroceryTracker
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / '.env')

# Database Paths
PROD_DB_PATH = (PROJECT_ROOT / 'grocery_tracker.db').resolve()
TEST_DB_PATH = (PROJECT_ROOT / 'grocery_tracker_test.db').resolve()

PROD_DATABASE_URL = os.getenv('DATABASE_URL_PROD', os.getenv('DATABASE_URL', f'sqlite:///{PROD_DB_PATH}'))
TEST_DATABASE_URL = os.getenv('DATABASE_URL_TEST', f'sqlite:///{TEST_DB_PATH}')

# SQLite connect args
connect_args = {'check_same_thread': False}

# Engines
prod_engine = create_engine(PROD_DATABASE_URL, connect_args=connect_args, echo=False)
test_engine = create_engine(TEST_DATABASE_URL, connect_args=connect_args, echo=False)

# Backward-compatible default engine
engine = prod_engine

# Sessionmakers
ProdSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=prod_engine)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Backward-compatible default sessionmaker
SessionLocal = ProdSessionLocal

Base = declarative_base()

# Active Server Database Mode ('production' or 'test')
ACTIVE_DB_MODE = os.getenv("APP_ENV", "production").strip().lower()
if ACTIVE_DB_MODE not in ("production", "test"):
    ACTIVE_DB_MODE = "production"


def get_active_db_mode() -> str:
    """Return current server-level default database mode."""
    return ACTIVE_DB_MODE


def set_active_db_mode(mode: str) -> str:
    """Dynamically change server-level default database mode ('production' or 'test')."""
    global ACTIVE_DB_MODE
    clean = mode.strip().lower()
    if clean in ("production", "test"):
        ACTIVE_DB_MODE = clean
        logger.info(f"Server database mode switched to: {ACTIVE_DB_MODE.upper()}")
    return ACTIVE_DB_MODE


def get_session_for_mode(mode: str) -> Session:
    """Return a fresh database session for specified mode."""
    if mode == "test":
        return TestSessionLocal()
    return ProdSessionLocal()


def get_db(request: Request = None):
    """Dependency provider for FastAPI route endpoints.
    Dynamically routes to Production or Test database based on:
    1. 'X-Database-Mode' header (from UI or client)
    2. 'db_mode' query parameter
    3. Server-level ACTIVE_DB_MODE fallback
    """
    mode = ACTIVE_DB_MODE
    if request is not None:
        header_mode = request.headers.get("x-database-mode") or request.headers.get("X-Database-Mode")
        if header_mode and header_mode.strip().lower() in ("production", "test"):
            mode = header_mode.strip().lower()
        else:
            query_mode = request.query_params.get("db_mode")
            if query_mode and query_mode.strip().lower() in ("production", "test"):
                mode = query_mode.strip().lower()

    session_maker = TestSessionLocal if mode == "test" else ProdSessionLocal
    db = session_maker()
    try:
        yield db
    finally:
        db.close()


def _run_migrations(target_engine):
    """Run incremental column schema migrations on an engine."""
    with target_engine.connect() as conn:
        migration_statements = [
            "ALTER TABLE inventory ADD COLUMN is_confirmed BOOLEAN DEFAULT 0",
            "ALTER TABLE purchase_logs ADD COLUMN bill_id INTEGER",
            "ALTER TABLE items ADD COLUMN is_grocery BOOLEAN DEFAULT 1",
            "ALTER TABLE items ADD COLUMN default_unit_price FLOAT",
            "ALTER TABLE grocery_list_entries ADD COLUMN is_dismissed BOOLEAN DEFAULT 0",
            "ALTER TABLE inventory ADD COLUMN store_name VARCHAR(200)",
            "ALTER TABLE inventory ADD COLUMN price FLOAT",
            "UPDATE items SET is_grocery = 0 WHERE LOWER(category) LIKE '%non%grocery%'",
            "DELETE FROM grocery_list_entries WHERE LOWER(category) LIKE '%non%grocery%' OR canonical_item_id IN (SELECT id FROM items WHERE is_grocery = 0 OR LOWER(category) LIKE '%non%grocery%')",
        ]
        for stmt in migration_statements:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass


def clear_database(mode: str = "both"):
    """Wipe all tables completely from target database(s).
    Leaves clean, blank databases.
    """
    import app.models
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

    models_to_clear = [
        GroceryListEntry,
        GuestEvent,
        Inventory,
        PurchaseLog,
        ReceiptUpload,
        ItemAlias,
        Item,
        Household,
    ]

    targets = []
    if mode in ("both", "production"):
        targets.append(("production", ProdSessionLocal, prod_engine))
    if mode in ("both", "test"):
        targets.append(("test", TestSessionLocal, test_engine))

    for target_name, session_factory, target_eng in targets:
        sess = session_factory()
        try:
            for model in models_to_clear:
                sess.query(model).delete()
            sess.commit()
            logger.info(f"Cleared all tables in {target_name} database.")
        except Exception as e:
            sess.rollback()
            logger.error(f"Error clearing {target_name} database: {e}")
            raise
        finally:
            sess.close()

        with target_eng.connect() as conn:
            try:
                conn.execute(text("VACUUM;"))
                conn.commit()
            except Exception:
                pass


def init_db(mode: str = "both"):
    """Initialize database schemas.
    Both Production DB (`grocery_tracker.db`) and Test DB (`grocery_tracker_test.db`)
    have tables created and migrated ONLY. Neither database is auto-seeded on startup.
    """
    import app.models

    # 1. Production Database (SCHEMA ONLY, NO SEEDING)
    if mode in ("both", "production"):
        logger.info("Initializing Production database schema (grocery_tracker.db)...")
        Base.metadata.create_all(bind=prod_engine)
        _run_migrations(prod_engine)

    # 2. Test Database (SCHEMA ONLY, NO AUTO SEEDING)
    if mode in ("both", "test"):
        logger.info("Initializing Test database schema (grocery_tracker_test.db)...")
        Base.metadata.create_all(bind=test_engine)
        _run_migrations(test_engine)

