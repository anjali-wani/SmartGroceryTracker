from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Item, Inventory, InventoryStatus, PurchaseLog, Household
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


def test_household_active_stock_isolation(client, db_session):
    """Verify active inventory is strictly scoped by household_id."""
    today = date.today()
    item_apple = db_session.query(Item).filter(Item.canonical_name == "Gala Apples").first()
    if not item_apple:
        item_apple = Item(canonical_name="Gala Apples", category="Produce", standard_unit="lb")
        db_session.add(item_apple)
        db_session.commit()

    # Ensure Household 1 and Household 2 exist
    h1 = db_session.query(Household).filter(Household.id == 1).first()
    if not h1:
        db_session.add(Household(id=1, name="Household 1", member_count=2))
    h2 = db_session.query(Household).filter(Household.id == 2).first()
    if not h2:
        db_session.add(Household(id=2, name="Household 2", member_count=4))
    db_session.commit()

    # Add active inventory for Household 1 and 2
    inv_h1 = Inventory(household_id=1, canonical_item_id=item_apple.id, current_quantity=3.0, unit="lb", purchase_date=today, status=InventoryStatus.ACTIVE)
    inv_h2 = Inventory(household_id=2, canonical_item_id=item_apple.id, current_quantity=10.0, unit="lb", purchase_date=today, status=InventoryStatus.ACTIVE)
    db_session.add_all([inv_h1, inv_h2])
    db_session.commit()

    # Check GET /inventory/active?household_id=1
    res1 = client.get("/inventory/active?household_id=1")
    assert res1.status_code == 200
    items1 = res1.json()
    assert all(i["household_id"] == 1 for i in items1)
    apple1 = next((i for i in items1 if i["canonical_item_id"] == item_apple.id), None)
    assert apple1 is not None
    assert apple1["current_quantity"] == 3.0

    # Check GET /inventory/active?household_id=2
    res2 = client.get("/inventory/active?household_id=2")
    assert res2.status_code == 200
    items2 = res2.json()
    assert all(i["household_id"] == 2 for i in items2)
    apple2 = next((i for i in items2 if i["canonical_item_id"] == item_apple.id), None)
    assert apple2 is not None
    assert apple2["current_quantity"] == 10.0

    # Check GET /items/inventory/current?household_id=1
    res_curr1 = client.get("/items/inventory/current?household_id=1")
    assert res_curr1.status_code == 200
    assert all(i["household_id"] == 1 for i in res_curr1.json())


def test_household_purchase_history_isolation(client, db_session):
    """Verify purchase history is strictly scoped by household_id."""
    today = date.today()
    item_bread = db_session.query(Item).filter(Item.canonical_name == "Sourdough Bread").first()
    if not item_bread:
        item_bread = Item(canonical_name="Sourdough Bread", category="Bakery", standard_unit="count")
        db_session.add(item_bread)
        db_session.commit()

    p_h1 = PurchaseLog(household_id=1, purchase_date=today, store_name="Store A", raw_text="H1 BREAD", canonical_item_id=item_bread.id, quantity=1.0, unit="count", price=4.50)
    p_h2 = PurchaseLog(household_id=2, purchase_date=today, store_name="Store B", raw_text="H2 BREAD", canonical_item_id=item_bread.id, quantity=5.0, unit="count", price=20.00)
    db_session.add_all([p_h1, p_h2])
    db_session.commit()

    res1 = client.get("/bills/purchases?household_id=1")
    assert res1.status_code == 200
    logs1 = res1.json()
    assert all(l["household_id"] == 1 for l in logs1)
    assert any(l["raw_text"] == "H1 BREAD" for l in logs1)
    assert not any(l["raw_text"] == "H2 BREAD" for l in logs1)

    res2 = client.get("/bills/purchases?household_id=2")
    assert res2.status_code == 200
    logs2 = res2.json()
    assert all(l["household_id"] == 2 for l in logs2)
    assert any(l["raw_text"] == "H2 BREAD" for l in logs2)
    assert not any(l["raw_text"] == "H1 BREAD" for l in logs2)


def test_zero_quantity_auto_status_consumed(client, db_session):
    """Verify when current_quantity becomes 0 (or negative), status automatically transitions to CONSUMED."""
    today = date.today()
    item = db_session.query(Item).first()

    # 1. Test model validator directly
    inv = Inventory(household_id=1, canonical_item_id=item.id, current_quantity=2.0, unit=item.standard_unit, purchase_date=today, status=InventoryStatus.ACTIVE)
    db_session.add(inv)
    db_session.commit()
    assert inv.status == InventoryStatus.ACTIVE

    inv.current_quantity = 0.0
    db_session.commit()
    db_session.refresh(inv)
    assert inv.status == InventoryStatus.CONSUMED
    assert inv.current_quantity == 0.0

    # 2. Test negative value clamps to 0.0 and CONSUMED
    inv.current_quantity = -1.5
    db_session.commit()
    db_session.refresh(inv)
    assert inv.status == InventoryStatus.CONSUMED
    assert inv.current_quantity == 0.0

    # 3. Test via API /inventory/adjust
    inv_active = Inventory(household_id=1, canonical_item_id=item.id, current_quantity=3.0, unit=item.standard_unit, purchase_date=today, status=InventoryStatus.ACTIVE)
    db_session.add(inv_active)
    db_session.commit()

    adj_res = client.post("/inventory/adjust", json={"inventory_id": inv_active.id, "new_quantity": 0.0})
    assert adj_res.status_code == 200
    data = adj_res.json()
    assert data["current_quantity"] == 0.0
    assert data["status"] == "CONSUMED"


def test_no_expiration_fields_in_responses(client, db_session):
    """Verify that zero expiration fields exist in API responses."""
    # 1. Velocity report
    vel_res = client.get("/analytics/velocity?household_id=1")
    assert vel_res.status_code == 200
    vel_data = vel_res.json()
    for item in vel_data.get("items", []):
        assert "days_until_expiration" not in item
        assert "expiration_date" not in item

    # 2. Active inventory
    inv_res = client.get("/inventory/active?household_id=1")
    assert inv_res.status_code == 200
    for inv in inv_res.json():
        assert "days_until_expiration" not in inv
        assert "expiration_date" not in inv

    # 3. Current inventory
    curr_res = client.get("/items/inventory/current?household_id=1")
    assert curr_res.status_code == 200
    for inv in curr_res.json():
        assert "days_until_expiration" not in inv
        assert "expiration_date" not in inv

    # 4. Confirm /inventory/expiring-soon is gone (404)
    old_res = client.get("/inventory/expiring-soon?days=3")
    assert old_res.status_code == 404
