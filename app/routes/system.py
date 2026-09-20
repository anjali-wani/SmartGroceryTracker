from typing import Literal, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.database import (
    get_active_db_mode,
    set_active_db_mode,
    PROD_DB_PATH,
    TEST_DB_PATH,
    ProdSessionLocal,
    TestSessionLocal,
)
from app.models import Item, Inventory, PurchaseLog, ReceiptUpload

router = APIRouter(prefix="/system", tags=["System & Settings"])


class SwitchModeRequest(BaseModel):
    mode: Literal["production", "test"]


def _get_counts_for_session(session_factory):
    sess = session_factory()
    try:
        return {
            "items_count": sess.query(Item).count(),
            "inventory_count": sess.query(Inventory).count(),
            "active_inventory_count": sess.query(Inventory).filter(Inventory.status == "ACTIVE").count(),
            "purchase_logs_count": sess.query(PurchaseLog).count(),
            "receipts_count": sess.query(ReceiptUpload).count(),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        sess.close()


@router.get("/database-mode")
def get_database_mode_status() -> Dict[str, Any]:
    """Check current database mode, filenames, and item/inventory counts in both databases."""
    active_mode = get_active_db_mode()
    prod_counts = _get_counts_for_session(ProdSessionLocal)
    test_counts = _get_counts_for_session(TestSessionLocal)

    return {
        "current_mode": active_mode,
        "active_file": str(PROD_DB_PATH) if active_mode == "production" else str(TEST_DB_PATH),
        "databases": {
            "production": {
                "name": "Production Database",
                "file": PROD_DB_PATH.name,
                "path": str(PROD_DB_PATH),
                "is_active": active_mode == "production",
                "description": "Clean live database for real grocery purchases (unseeded).",
                **prod_counts,
            },
            "test": {
                "name": "Test Database",
                "file": TEST_DB_PATH.name,
                "path": str(TEST_DB_PATH),
                "is_active": active_mode == "test",
                "description": "Sandbox database for synthetic receipts, unit testing, and experimentation.",
                **test_counts,
            },
        },
    }


@router.post("/database-mode")
def switch_database_mode(payload: SwitchModeRequest) -> Dict[str, Any]:
    """Switch server-level default database mode between 'production' and 'test'."""
    new_mode = set_active_db_mode(payload.mode)
    return {
        "message": f"Server default database switched to {new_mode.upper()}",
        "current_mode": new_mode,
        "active_file": str(PROD_DB_PATH) if new_mode == "production" else str(TEST_DB_PATH),
    }


class ClearDatabaseRequest(BaseModel):
    target: Literal["both", "production", "test"] = "both"


@router.post("/clear-database")
def clear_system_databases(payload: ClearDatabaseRequest = ClearDatabaseRequest()) -> Dict[str, Any]:
    """Completely wipe all tables from specified database(s).
    Leaves clean, 100% blank database(s).
    """
    from app.database import clear_database
    clear_database(payload.target)
    return {
        "status": "cleared",
        "target": payload.target,
        "message": f"Successfully cleared all data from {payload.target} database(s).",
        "current_status": get_database_mode_status(),
    }

