import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, SessionLocal
from app.seed import seed_database
from app.routes import bills, items, inventory, events, analytics, grocery_list

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("grocery_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: initializes tables and seeds database on startup."""
    logger.info("Initializing database tables...")
    init_db()
    db = SessionLocal()
    try:
        logger.info("Seeding canonical grocery items & aliases...")
        seed_database(db)
    finally:
        db.close()
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
