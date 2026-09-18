from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Item, ItemAlias, PurchaseLog, Inventory, InventoryStatus, GuestEvent, Household
from app.seed import seed_database
from app.services.analytics import compute_item_velocity, generate_household_velocity_report
from app.services.guest_engine import calculate_guest_discount_factor

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


# --- 1. Test Consumption Velocity Engine ---
def test_consumption_velocity_calculation(db_session):
    # Retrieve Whole Milk (canonical item id = 1)
    milk = db_session.query(Item).filter(Item.canonical_name == "Whole Milk").first()
    assert milk is not None

    today = date.today()
    # Simulate 3 milk purchases: 20 days ago, 10 days ago, and today (1 gal each = 3 gal)
    p1 = PurchaseLog(household_id=1, purchase_date=today - timedelta(days=20), raw_text="MILK 1 GAL", canonical_item_id=milk.id, quantity=1.0, unit="gallon", price=4.99)
    p2 = PurchaseLog(household_id=1, purchase_date=today - timedelta(days=10), raw_text="MILK 1 GAL", canonical_item_id=milk.id, quantity=1.0, unit="gallon", price=4.99)
    p3 = PurchaseLog(household_id=1, purchase_date=today, raw_text="MILK 1 GAL", canonical_item_id=milk.id, quantity=1.0, unit="gallon", price=4.99)
    db_session.add_all([p1, p2, p3])

    # Current active stock: 1 gallon remaining
    inv = Inventory(household_id=1, canonical_item_id=milk.id, current_quantity=1.0, unit="gallon", purchase_date=today, status=InventoryStatus.ACTIVE)
    db_session.add(inv)
    db_session.commit()

    velocity_out = compute_item_velocity(milk, db_session, household_id=1, as_of_date=today)
    assert velocity_out.canonical_item_id == milk.id
    assert velocity_out.purchase_count == 3
    # 3 purchased - 1 remaining = 2 consumed over 20 days = 0.10 gal/day
    assert velocity_out.daily_velocity == pytest.approx(0.10, abs=0.02)
    # 1 gal stock / 0.10 gal/day = ~10 days remaining
    assert velocity_out.estimated_days_remaining == pytest.approx(10.0, abs=2.0)
    assert velocity_out.confidence in ["moderate", "high"]


# --- 2. Test Dual Sliding Windows (Bulk vs Perishable) ---
def test_dual_sliding_windows(db_session):
    milk = db_session.query(Item).filter(Item.canonical_name == "Whole Milk").first()
    rice = db_session.query(Item).filter(Item.canonical_name == "Jasmine Rice").first()
    assert milk.is_bulk is False
    assert rice.is_bulk is True

    today = date.today()
    v_milk = compute_item_velocity(milk, db_session, household_id=1, as_of_date=today)
    v_rice = compute_item_velocity(rice, db_session, household_id=1, as_of_date=today)

    assert v_milk.lookback_days == 30
    assert v_rice.lookback_days == 180


# --- 3. Test Guest Event Allocations ---
def test_guest_event_deduction(db_session):
    today = date.today()
    # Log a guest dinner event with 4 guests
    guest_event = GuestEvent(household_id=1, event_date=today - timedelta(days=5), guest_count=4, notes="Dinner party")
    db_session.add(guest_event)
    db_session.commit()

    discount = calculate_guest_discount_factor(db_session, household_id=1, start_date=today - timedelta(days=30), end_date=today)
    # Should discount a fraction between 0.01 and 0.50
    assert discount > 0.0
    assert discount <= 0.50


# --- 4. Test Inventory Adjustment & Spoilage ---
def test_inventory_adjust_endpoint(client, db_session):
    today = date.today()
    milk = db_session.query(Item).filter(Item.canonical_name == "Whole Milk").first()
    inv = Inventory(household_id=1, canonical_item_id=milk.id, current_quantity=2.0, unit="gallon", purchase_date=today, status=InventoryStatus.ACTIVE)
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)

    # Adjust stock to 0.5 and mark status
    payload = {
        "inventory_id": inv.id,
        "new_quantity": 0.5,
        "status": "SPOILED",
        "reason": "spoiled",
        "notes": "Milk went sour"
    }
    res = client.post("/inventory/adjust", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["previous_quantity"] == 2.0
    assert data["current_quantity"] == 0.5
    assert data["status"] == "SPOILED"


# --- 5. Test Household Active Stock & Consumed on Zero Quantity ---
def test_household_active_stock_and_consumed_on_zero_quantity(client, db_session):
    today = date.today()
    spinach = db_session.query(Item).filter(Item.canonical_name == "Baby Spinach").first()

    # Household 1 item
    inv1 = Inventory(household_id=1, canonical_item_id=spinach.id, current_quantity=2.0, unit="oz", purchase_date=today - timedelta(days=5), status=InventoryStatus.ACTIVE)
    # Household 2 item
    inv2 = Inventory(household_id=2, canonical_item_id=spinach.id, current_quantity=5.0, unit="oz", purchase_date=today - timedelta(days=2), status=InventoryStatus.ACTIVE)
    db_session.add_all([inv1, inv2])
    db_session.commit()

    # Verify Household 1 sees only inv1
    res1 = client.get("/inventory/active?household_id=1")
    assert res1.status_code == 200
    h1_items = res1.json()
    assert all(it["household_id"] == 1 for it in h1_items)
    # Verify no expiration fields
    assert all("expiration_date" not in it and "days_until_expiration" not in it for it in h1_items)

    # Adjust inv1 quantity to 0 -> status MUST become CONSUMED
    adj_res = client.post("/inventory/adjust", json={"inventory_id": inv1.id, "new_quantity": 0.0})
    assert adj_res.status_code == 200
    adj_data = adj_res.json()
    assert adj_data["current_quantity"] == 0.0
    assert adj_data["status"] == "CONSUMED" 


# --- 6. Test Velocity API Endpoint ---
def test_velocity_report_endpoint(client):
    res = client.get("/analytics/velocity?household_id=1")
    assert res.status_code == 200
    data = res.json()
    assert data["household_id"] == 1
    assert "items" in data
    assert len(data["items"]) >= 1
    first_item = data["items"][0]
    assert "daily_velocity" in first_item
    assert "per_capita_velocity" in first_item
    assert "lookback_days" in first_item


# --- 7. Test Item Details Purchase History Actual Weight and Price ---
def test_item_details_purchase_history_actual_weight_and_price(client, db_session):
    tomato = db_session.query(Item).filter(Item.canonical_name == "Roma Tomatoes").first()
    assert tomato is not None

    log = PurchaseLog(
        household_id=1,
        canonical_item_id=tomato.id,
        purchase_date=date(2026, 8, 30),
        store_name="New India Bazar",
        raw_text="TOMATO ROUND",
        quantity=1.45,
        unit="lb",
        price=1.87,
        unit_price=1.29,
        matched_via="fuzzy",
        confidence=0.95
    )
    db_session.add(log)
    db_session.commit()

    res = client.get(f"/items/{tomato.id}/details?household_id=1")
    assert res.status_code == 200
    data = res.json()
    assert "purchase_history" in data
    assert len(data["purchase_history"]) >= 1

    entry = next((p for p in data["purchase_history"] if p["id"] == log.id), None)
    assert entry is not None
    assert entry["quantity"] == 1.45
    assert entry["unit"] == "lb"
    assert entry["price"] == 1.87
    assert entry["unit_price"] == 1.29
    assert entry["store_name"] == "New India Bazar"

