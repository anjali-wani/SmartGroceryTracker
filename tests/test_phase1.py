import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Item, ItemAlias, PurchaseLog, Inventory
from app.seed import seed_database
from app.normalizer import extract_quantity_and_unit, normalize_item_name
from app.resolution import EntityResolver

# Use StaticPool so all threads share the single in-memory database
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
def setup_test_database():
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


# --- Test Normalization & Unit Extraction ---
def test_unit_and_quantity_extraction():
    # 1 Gal
    name, qty, unit = extract_quantity_and_unit("ORGANIC WHOLE MILK 1 GAL")
    assert "MILK" in name
    assert qty == 1.0
    assert unit == "gallon"

    # 24 CT
    name, qty, unit = extract_quantity_and_unit("KIRKLAND LARGE EGGS 24 CT")
    assert "EGGS" in name
    assert qty == 24.0
    assert unit == "count"

    # 2.5 LB
    name, qty, unit = extract_quantity_and_unit("BANANAS 2.5 LB")
    assert "BANANAS" in name
    assert qty == 2.5
    assert unit == "lb"

    # 16OZ
    name, qty, unit = extract_quantity_and_unit("365 BABY SPINACH 16OZ")
    assert "SPINACH" in name
    assert qty == 16.0
    assert unit == "oz"


# --- Test Entity Resolution ---
def test_entity_resolution_exact_and_fuzzy(db_session):
    resolver = EntityResolver(db_session, similarity_threshold=70.0)

    # Exact alias: "kirkland whole milk"
    res = resolver.resolve("kirkland whole milk")
    assert res.canonical_item is not None
    assert res.canonical_item.canonical_name == "Whole Milk"
    assert res.confidence >= 0.95

    # RapidFuzz match: "ORG BNNAS" -> Bananas
    res = resolver.resolve("ORG BNNAS")
    assert res.canonical_item is not None
    assert res.canonical_item.canonical_name == "Bananas"
    assert res.confidence >= 0.70

    # RapidFuzz match: "chk breast" -> Boneless Skinless Chicken Breast
    res = resolver.resolve("chk breast")
    assert res.canonical_item is not None
    assert res.canonical_item.canonical_name == "Boneless Skinless Chicken Breast"

    # Unresolved edge case
    res = resolver.resolve("UNKNOWN RANDOM WIDGET XYZ123")
    assert res.canonical_item is None
    assert res.matched_via == "unresolved"


# --- Test API Endpoints ---
def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "Phase" in data["phase"]


def test_list_items(client):
    response = client.get("/items")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 20
    names = [it["canonical_name"] for it in items]
    assert "Whole Milk" in names
    assert "Bananas" in names


def test_create_item_and_alias(client):
    new_item = {
        "canonical_name": "Greek Pita Bread",
        "category": "Bakery",
        "standard_unit": "count",
        "default_shelf_life_days": 7,
        "is_bulk": False
    }
    res = client.post("/items", json=new_item)
    assert res.status_code == 201
    created = res.json()
    item_id = created["id"]

    # Add custom alias
    alias_res = client.post(f"/items/{item_id}/aliases?raw_alias=tzatziki pita pack")
    assert alias_res.status_code == 201
    assert alias_res.json()["raw_alias"] == "tzatziki pita pack"


def test_upload_csv_pipeline(client):
    sample_csv_data = b"""Item,Price,Quantity,Unit,Date,Store
KIRKLAND ORGANIC WHOLE MILK 1 GAL,5.99,1,gallon,2026-09-08,Costco Wholesale
ORG BNNAS 2.5 LB,1.89,2.5,lb,2026-09-08,Trader Joe's
LARGE GRADE A EGGS 24 CT,6.49,24,count,2026-09-08,Costco Wholesale
"""

    files = {"file": ("test_receipt.csv", sample_csv_data, "text/csv")}
    res = client.post("/bills/upload-csv", files=files)
    assert res.status_code == 201
    summary = res.json()

    assert summary["total_rows"] == 3
    assert summary["matched_rows"] == 3
    assert summary["unresolved_rows"] == 0
    assert summary["total_amount"] == 14.37

    # Check inventory was populated
    inv_res = client.get("/items/inventory/current")
    assert inv_res.status_code == 200
    inventory = inv_res.json()
    assert len(inventory) >= 3
    inv_names = [inv["item_name"] for inv in inventory]
    assert "Whole Milk" in inv_names
    assert "Bananas" in inv_names
    assert "Large Grade A Eggs" in inv_names
