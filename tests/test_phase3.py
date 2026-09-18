from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Item, ItemAlias, PurchaseLog, Inventory, InventoryStatus, GroceryListEntry, Household
from app.seed import seed_database

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_database(db)
    db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


# --- 1. Test 7-Day Depletion Predictor ---
def test_7_day_depletion_prediction(client, db_session):
    today = date.today()
    milk = db_session.query(Item).filter(Item.canonical_name == "Whole Milk").first()
    assert milk is not None

    # Simulate multi-purchase history (Day -20 and Day -10) -> established frequency
    p1 = PurchaseLog(household_id=1, purchase_date=today - timedelta(days=20), raw_text="WHOLE MILK 1 GAL", canonical_item_id=milk.id, quantity=1.0, unit="gallon", price=4.99)
    p2 = PurchaseLog(household_id=1, purchase_date=today - timedelta(days=10), raw_text="WHOLE MILK 1 GAL", canonical_item_id=milk.id, quantity=1.0, unit="gallon", price=4.99)
    inv = Inventory(household_id=1, canonical_item_id=milk.id, current_quantity=0.1, unit="gallon", purchase_date=today - timedelta(days=10), status=InventoryStatus.ACTIVE)
    db_session.add_all([p1, p2, inv])
    db_session.commit()

    res = client.get("/grocery-list/generate?days_ahead=7")
    assert res.status_code == 200
    data = res.json()
    assert data["forecast_days"] == 7
    assert data["total_items"] >= 1

    item_names = [it["item_name"] for it in data["items"]]
    assert "Whole Milk" in item_names
    milk_entry = next(it for it in data["items"] if it["item_name"] == "Whole Milk")
    assert milk_entry["priority_reason"] in ["CRITICAL_DEPLETION", "RUNNING_LOW"]


# --- 2. Test Periodic Purchase Scheduler (Cadence Modulo Trigger) ---
def test_periodic_purchase_scheduler(client, db_session):
    today = date.today()
    spinach = db_session.query(Item).filter(Item.canonical_name == "Baby Spinach").first()
    assert spinach is not None

    # Set bi-weekly cadence (14 days)
    client.patch(f"/items/{spinach.id}/schedule", json={"reorder_cadence_days": 14, "preferred_store": "Trader Joe's"})

    # Log purchase 15 days ago (interval exceeded)
    p = PurchaseLog(household_id=1, purchase_date=today - timedelta(days=15), raw_text="SPINACH", canonical_item_id=spinach.id, quantity=1.0, unit="oz", price=2.99)
    db_session.add(p)
    db_session.commit()

    res = client.get("/grocery-list/generate?days_ahead=7")
    assert res.status_code == 200
    data = res.json()
    spinach_entry = next((it for it in data["items"] if it["item_name"] == "Baby Spinach"), None)
    assert spinach_entry is not None
    assert spinach_entry["priority_reason"] == "SCHEDULED_PERIODIC"
    assert spinach_entry["target_store"] == "Trader Joe's"


# --- 3. Test Soft-Archiving (is_active = False) ---
def test_soft_archiving_excludes_from_grocery_list(client, db_session):
    today = date.today()
    butter = db_session.query(Item).filter(Item.canonical_name == "Unsalted Butter").first()
    assert butter is not None

    # Make butter depleted (stock = 0) so it would normally trigger reorder
    p = PurchaseLog(household_id=1, purchase_date=today - timedelta(days=5), raw_text="BUTTER", canonical_item_id=butter.id, quantity=1.0, unit="lb", price=3.99)
    db_session.add(p)
    db_session.commit()

    # Soft-archive butter
    archive_res = client.patch(f"/items/{butter.id}/archive?archive=true")
    assert archive_res.status_code == 200
    assert archive_res.json()["is_active"] is False

    # Generate list
    res = client.get("/grocery-list/generate?days_ahead=7")
    assert res.status_code == 200
    item_names = [it["item_name"] for it in res.json()["items"]]
    assert "Unsalted Butter" not in item_names

    # Restore butter
    restore_res = client.patch(f"/items/{butter.id}/archive?archive=false")
    assert restore_res.status_code == 200
    assert restore_res.json()["is_active"] is True


# --- 4. Test Manual Item Override and Checklist Toggle ---
def test_manual_grocery_item_and_toggle(client):
    # Add custom manual item
    manual_payload = {
        "item_name": "Birthday Party Candles",
        "quantity": 1.0,
        "unit": "pack",
        "category": "Party Supplies",
        "target_store": "Target"
    }
    res = client.post("/grocery-list/items", json=manual_payload)
    assert res.status_code == 201
    created = res.json()
    entry_id = created["id"]
    assert created["item_name"] == "Birthday Party Candles"
    assert created["is_checked"] is False
    assert created["priority_reason"] == "MANUAL"

    # Toggle checked state
    check_res = client.patch(f"/grocery-list/items/{entry_id}/check")
    assert check_res.status_code == 200
    assert check_res.json()["is_checked"] is True


# --- 5. Test Purchase Line-Item Deletion and Inventory Rollback ---
def test_purchase_deletion_and_rollback(client, db_session):
    today = date.today()
    eggs = db_session.query(Item).filter(Item.canonical_name == "Large Grade A Eggs").first()

    p = PurchaseLog(household_id=1, purchase_date=today, raw_text="MISTAKE EGGS", canonical_item_id=eggs.id, quantity=12.0, unit="count", price=4.00)
    inv = Inventory(household_id=1, canonical_item_id=eggs.id, current_quantity=12.0, unit="count", purchase_date=today, status=InventoryStatus.ACTIVE)
    db_session.add_all([p, inv])
    db_session.commit()
    db_session.refresh(p)
    purchase_id = p.id

    # Delete the purchase
    del_res = client.delete(f"/bills/purchases/{purchase_id}")
    assert del_res.status_code == 200

    # Verify purchase is deleted
    assert db_session.query(PurchaseLog).filter(PurchaseLog.id == purchase_id).first() is None


# --- 6. Test Grocery List Text Export ---
def test_grocery_list_text_export(client):
    res = client.get("/grocery-list/export?household_id=1")
    assert res.status_code == 200
    assert "GROCERY SHOPPING LIST" in res.text
