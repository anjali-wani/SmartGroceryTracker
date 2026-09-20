import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import bills, items, inventory, events, analytics, grocery_list, system

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("grocery_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: initializes tables on startup.
    Production is never seeded. Test database is initialized with test seed.
    """
    logger.info("Initializing database schemas...")
    init_db(mode="both")
    logger.info("Smart Grocery Tracker & Nutrition Engine ready.")
    yield


app = FastAPI(
    title="Smart Grocery Tracker & Nutrition Engine API",
    description="""
    Phase 1: Foundation (Database, Normalization, RapidFuzz Entity Resolution, CSV Ingestion)
    Phase 2: Core Logic (Consumption Velocity Analytics, Guest Event Allocations, Inventory Adjustments)
    """,
    version="3.0.0",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(bills.router)
app.include_router(items.router)
app.include_router(inventory.router)
app.include_router(events.router)
app.include_router(analytics.router)
app.include_router(grocery_list.router)
app.include_router(system.router)


@app.get("/", tags=["System"])
def root_status():
    return {
        "app": "Smart Grocery Tracker & Nutrition Engine",
        "phase": "Phase 3: Automated Grocery List Generation & Data Management",
        "version": "2.0.0",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy"}

from typing import Optional
from fastapi import Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import GroceryListEntry, Inventory, PurchaseLog, GuestEvent


@app.post("/system/reset", tags=["System"])
def reset_database(
    household_id: Optional[int] = Query(None, description="Reset only a specific household. If omitted, resets all test data."),
    reseed: bool = Query(True, description="Re-seed default catalog"),
    db: Session = Depends(get_db)
):
    """Reset transactional data (inventory, purchases, grocery lists, guest events) for testing."""
    if household_id is not None:
        db.query(GroceryListEntry).filter(GroceryListEntry.household_id == household_id).delete(synchronize_session=False)
        db.query(Inventory).filter(Inventory.household_id == household_id).delete(synchronize_session=False)
        db.query(PurchaseLog).filter(PurchaseLog.household_id == household_id).delete(synchronize_session=False)
        db.query(GuestEvent).filter(GuestEvent.household_id == household_id).delete(synchronize_session=False)
        db.commit()
        return {
            "status": "reset",
            "household_id": household_id,
            "message": f"All data for Household {household_id} has been reset."
        }
    else:
        db.query(GroceryListEntry).delete(synchronize_session=False)
        db.query(Inventory).delete(synchronize_session=False)
        db.query(PurchaseLog).delete(synchronize_session=False)
        db.query(GuestEvent).delete(synchronize_session=False)
        db.commit()

        if reseed:
            seed_database(db)

        return {
            "status": "reset",
            "all_households": True,
            "message": "All test transactional data cleared and catalog ready."
        }
