from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Item, PurchaseLog, Inventory, InventoryStatus, GroceryListEntry
from app.seed import seed_database
from app.services.analytics import compute_item_velocity, calculate_modal_quantity
from app.services.llm_resolver import resolve_with_gemini, fallback_heuristic_resolve
from app.resolution import EntityResolver

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


# --- 1. Test User Rice Scenario: 1 lb -> 14d, then 2 lb -> 28d ---
def test_user_rice_repurchase_scenario(db_session, client):
    """Scenario:
    - 1 lb rice purchased first.
    - After 14 days, 2 lb rice purchased.
    - 2 lb rice must last for 28 days.
    - After 28 days, 2 lb rice added to grocery list.
    """
    rice = db_session.query(Item).filter(Item.canonical_name == "Jasmine Rice").first()
    assert rice is not None

    base_date = date(2026, 1, 1)

    # Purchase 1: 1 lb on Day 0
    p1 = PurchaseLog(
        household_id=1,
        purchase_date=base_date,
        store_name="Asian Market",
        raw_text="JASMINE RICE 1LB",
        canonical_item_id=rice.id,
        quantity=1.0,
        unit="lb",
        price=2.50
    )
    # Purchase 2: 2 lb on Day 14 (14 days after purchase 1)
    p2 = PurchaseLog(
        household_id=1,
        purchase_date=base_date + timedelta(days=14),
        store_name="Asian Market",
        raw_text="JASMINE RICE 2LB",
        canonical_item_id=rice.id,
        quantity=2.0,
        unit="lb",
        price=4.50
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    # Calculate velocity as of Day 14 (the day 2 lb was bought)
    v_on_day_14 = compute_item_velocity(rice, db_session, household_id=1, as_of_date=base_date + timedelta(days=14))
    
    # Rate: 1 lb lasted 14 days -> 14 days per unit
    assert v_on_day_14.days_per_unit == 14.0
    # 2 lb * 14 days/lb = 28 days remaining
    assert v_on_day_14.estimated_days_remaining == 28.0
    # Projected runout date = Day 14 + 28 days = Day 42
    expected_runout = base_date + timedelta(days=14 + 28)
    assert v_on_day_14.projected_runout_date == expected_runout
    # Modal quantity tie-breaker between 1 lb and 2 lb -> 2 lb
    assert v_on_day_14.modal_quantity == 2.0

    # On Day 42 (28 days after purchase 2): Runout reached!
    from app.services.list_generator import generate_smart_grocery_list
    list_day_42 = generate_smart_grocery_list(db_session, household_id=1, forecast_days=7, as_of_date=expected_runout)
    
    rice_entry = next((it for it in list_day_42.items if it.canonical_item_id == rice.id), None)
    assert rice_entry is not None
    # Recommended quantity must be 2 lb!
    assert rice_entry.recommended_quantity == 2.0
    assert rice_entry.priority_reason in ["CRITICAL_DEPLETION", "RUNNING_LOW"]


# --- 2. Test Modal Quantity with Larger Tie-Breaker ---
def test_modal_quantity_tie_breaker():
    # Tie between 1.0 and 2.0 -> should pick 2.0
    assert calculate_modal_quantity([1.0, 2.0]) == 2.0
    # Tie between 1.0, 5.0, 2.0 -> should pick 5.0
    assert calculate_modal_quantity([1.0, 5.0, 2.0]) == 5.0
    # Clear mode: [1.0, 1.0, 2.0] -> should pick 1.0
    assert calculate_modal_quantity([1.0, 1.0, 2.0]) == 1.0
    # Clear mode: [2.0, 2.0, 1.0] -> should pick 2.0
    assert calculate_modal_quantity([2.0, 2.0, 1.0]) == 2.0


# --- 3. Test Autonomous Single-Purchase: No Prompts & No Auto-Reorder ---
def test_single_purchase_autonomous_behavior(client, db_session):
    """When an item has only 1 purchase in entire history:
    - Never prompt the user for availability (no availability_prompts).
    - Do NOT add the item automatically to the grocery list.
    - Active stock remains safely tracked in inventory.
    """
    today = date.today()
    apple = db_session.query(Item).filter(Item.canonical_name == "Gala Apples").first()
    assert apple is not None

    p = PurchaseLog(
        household_id=1,
        purchase_date=today - timedelta(days=12),
        store_name="Trader Joe's",
        raw_text="GALA APPLES 3LB",
        canonical_item_id=apple.id,
        quantity=3.0,
        unit="lb",
        price=3.99
    )
    inv = Inventory(
        household_id=1,
        canonical_item_id=apple.id,
        current_quantity=3.0,
        unit="lb",
        purchase_date=today - timedelta(days=12),
        status=InventoryStatus.ACTIVE
    )
    db_session.add_all([p, inv])
    db_session.commit()

    # Generate grocery list -> MUST have NO availability prompts and NO auto-reorder for this single purchase
    res = client.get("/grocery-list/generate?days_ahead=7")
    assert res.status_code == 200
    data = res.json()
    # Availability prompts must be empty
    assert len(data.get("availability_prompts", [])) == 0
    # Gala Apples must NOT be on grocery list because it only has 1 purchase
    apple_entry = next((it for it in data["items"] if it["canonical_item_id"] == apple.id), None)
    assert apple_entry is None

    # Inventory active stock remains untouched
    active_inv = db_session.query(Inventory).filter(
        Inventory.canonical_item_id == apple.id,
        Inventory.status == InventoryStatus.ACTIVE
    ).first()
    assert active_inv is not None
    assert active_inv.current_quantity == 3.0


# --- 4. Test Bill Upload Tracking, Line Items List & Granular Deletion ---
def test_bill_upload_and_deletion_workflows(client, db_session):
    """Test receipt bill upload, listing bills, retrieving bill items,
    deleting single line items, and deleting an entire bill with inventory rollback.
    """
    csv_content = (
        "Date,Store Name,Item Description,Category,Total Price,Quantity,Unit,Unit Price,Pricing Type\n"
        "2026-09-01,Test Market,WHOLE MILK 1 GAL,Dairy,5.99,1,gallon,5.99,Fixed\n"
        "2026-09-01,Test Market,GALA APPLES 3LB,Produce,4.50,3,lb,1.50,Fixed\n"
    )

    # 1. Upload bill CSV
    upload_res = client.post(
        "/bills/upload-csv?household_id=1",
        files={"file": ("september_receipt.csv", csv_content, "text/csv")}
    )
    assert upload_res.status_code == 201
    summary = upload_res.json()
    assert summary["total_rows"] == 2
    bill_id = summary.get("bill_id")
    assert bill_id is not None

    # 2. List uploaded bills
    bills_res = client.get("/bills?household_id=1")
    assert bills_res.status_code == 200
    bills = bills_res.json()
    my_bill = next((b for b in bills if b["id"] == bill_id), None)
    assert my_bill is not None
    assert my_bill["filename"] == "september_receipt.csv"
    assert my_bill["total_items"] == 2

    # 3. Retrieve line items for this bill
    items_res = client.get(f"/bills/{bill_id}/items")
    assert items_res.status_code == 200
    bill_items = items_res.json()
    assert len(bill_items) == 2

    first_item = bill_items[0]
    first_purchase_id = first_item["id"]

    # 4. Delete single line item from purchase history
    del_item_res = client.delete(f"/bills/purchases/{first_purchase_id}")
    assert del_item_res.status_code == 200

    # Bill line items should now be 1
    items_after = client.get(f"/bills/{bill_id}/items").json()
    assert len(items_after) == 1

    # 5. Delete entire bill
    del_bill_res = client.delete(f"/bills/{bill_id}")
    assert del_bill_res.status_code == 200
    assert del_bill_res.json()["success"] is True

    # Bill should no longer exist in /bills
    bills_after = client.get("/bills?household_id=1").json()
    assert not any(b["id"] == bill_id for b in bills_after)


# --- 4. Test LLM Fallback Resolution ---
def test_llm_fallback_resolution(db_session):
    resolver = EntityResolver(db_session)
    # Test unrecognized item resolution via LLM fallback
    res = resolver.resolve("HLDRM BHL PURI 200G")
    assert res.confidence >= 0.70
    assert res.matched_via in ["gemini_llm", "heuristic_fallback", "rapidfuzz"]

    # Heuristic unit & category test
    heur = fallback_heuristic_resolve("ORGANIC BASMATI RICE 20LB", "Costco")
    assert heur.canonical_name == "Basmati Rice 20Lb"
    assert heur.category == "Grains & Pasta"
    assert heur.is_bulk is True


# --- 5. Test Repurchase Auto-Consumption ---
def test_repurchase_auto_consumes_previous_active_stock(client, db_session):
    """When an item is purchased again, the previous batch is consumed and
    removed from active pantry stock.
    """
    csv_1 = (
        "Date,Store Name,Item Description,Category,Total Price,Quantity,Unit,Unit Price,Pricing Type\n"
        "2026-09-01,Test Store,WHOLE MILK 1 GAL,Dairy,4.99,1,gallon,4.99,Fixed\n"
    )
    res1 = client.post("/bills/upload-csv?household_id=1", files={"file": ("bill1.csv", csv_1, "text/csv")})
    assert res1.status_code == 201

    # Check active inventory has 1 gallon Whole Milk from 2026-09-01
    milk = db_session.query(Item).filter(Item.canonical_name == "Whole Milk").first()
    assert milk is not None
    inv_active_1 = db_session.query(Inventory).filter(
        Inventory.household_id == 1,
        Inventory.canonical_item_id == milk.id,
        Inventory.status == InventoryStatus.ACTIVE
    ).all()
    assert len(inv_active_1) == 1
    assert inv_active_1[0].current_quantity == 1.0
    assert inv_active_1[0].purchase_date == date(2026, 9, 1)

    # Now repurchase Whole Milk on 2026-09-10
    csv_2 = (
        "Date,Store Name,Item Description,Category,Total Price,Quantity,Unit,Unit Price,Pricing Type\n"
        "2026-09-10,Test Store,WHOLE MILK 1 GAL,Dairy,4.99,1,gallon,4.99,Fixed\n"
    )
    res2 = client.post("/bills/upload-csv?household_id=1", files={"file": ("bill2.csv", csv_2, "text/csv")})
    assert res2.status_code == 201

    # Previous batch on 2026-09-01 MUST now be CONSUMED with quantity 0.0
    old_batch = db_session.query(Inventory).filter(
        Inventory.household_id == 1,
        Inventory.canonical_item_id == milk.id,
        Inventory.purchase_date == date(2026, 9, 1)
    ).first()
    assert old_batch is not None
    assert old_batch.status == InventoryStatus.CONSUMED
    assert old_batch.current_quantity == 0.0

    # Only the new batch on 2026-09-10 is ACTIVE
    inv_active_2 = db_session.query(Inventory).filter(
        Inventory.household_id == 1,
        Inventory.canonical_item_id == milk.id,
        Inventory.status == InventoryStatus.ACTIVE
    ).all()
    assert len(inv_active_2) == 1
    assert inv_active_2[0].purchase_date == date(2026, 9, 10)


# --- 6. Test Non-Grocery Categorization and Strict Exclusion ---
def test_non_grocery_items_excluded_from_pantry_and_grocery_list(client, db_session):
    """Items like shoes, apparel, planters, electronics:
    - Tagged as category 'Non-Grocery' with is_grocery=False.
    - Excluded from Kitchen Pantry active stock.
    - Excluded from Sunday Grocery List auto-reorders.
    """
    csv_non_grocery = (
        "Date,Store Name,Item Description,Category,Total Price,Quantity,Unit,Unit Price,Pricing Type\n"
        "2026-09-05,Department Store,RUNNING SNEAKERS SHOES,Apparel,65.00,1,count,65.00,Fixed\n"
        "2026-09-05,Garden Store,MS 6 CERAMIC PLANTER,Supplies,15.00,1,count,15.00,Fixed\n"
    )
    res = client.post("/bills/upload-csv?household_id=1", files={"file": ("merchandise.csv", csv_non_grocery, "text/csv")})
    assert res.status_code == 201

    # Check that canonical items were created with is_grocery=False and category='Non-Grocery'
    shoes = db_session.query(Item).filter(Item.canonical_name.ilike("%Shoes%")).first()
    assert shoes is not None
    assert shoes.is_grocery is False
    assert shoes.category == "Non-Grocery"

    # Verify NOT in kitchen active inventory
    inv_res = client.get("/items/inventory/current?household_id=1&status_filter=ACTIVE")
    assert inv_res.status_code == 200
    active_names = [it["item_name"] for it in inv_res.json()]
    assert not any("shoes" in n.lower() or "planter" in n.lower() for n in active_names)

    # Verify NOT on Sunday grocery list
    groc_res = client.get("/grocery-list/generate?household_id=1&days_ahead=7")
    assert groc_res.status_code == 200
    groc_names = [it["item_name"] for it in groc_res.json()["items"]]
    assert not any("shoes" in n.lower() or "planter" in n.lower() for n in groc_names)


# --- 7. Test Grocery List Toggle and Estimated Cost Calculation ---
def test_grocery_list_toggle_and_cost_calculation(client, db_session):
    """Test POST /grocery-list/items/{id}/toggle succeeds and estimated cost is > 0."""
    groc_res = client.get("/grocery-list/generate?household_id=1&days_ahead=7")
    assert groc_res.status_code == 200
    data = groc_res.json()
    assert data["total_estimated_cost"] > 0
    assert len(data["items"]) > 0

    first_item = data["items"][0]
    item_id = first_item["id"]
    assert first_item["estimated_cost"] is not None
    assert first_item["estimated_cost"] > 0

    # Toggle item
    toggle_res = client.post(f"/grocery-list/items/{item_id}/toggle?is_checked=true")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_checked"] is True

    # Toggle back
    toggle_res2 = client.post(f"/grocery-list/items/{item_id}/toggle?is_checked=false")
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["is_checked"] is False


# --- 8. Test Active Pantry Store Name and Price Attribution ---
def test_active_pantry_store_name_and_price_attribution(client, db_session):
    """Active kitchen pantry items must include the purchase store name and unit price."""
    csv_data = (
        "Date,Store Name,Item Description,Category,Total Price,Quantity,Unit,Unit Price,Pricing Type\n"
        "2026-09-15,Costco Wholesale,KIRKLAND ORGANIC WHOLE MILK 1 GAL,Dairy,5.99,1,gallon,5.99,Fixed\n"
    )
    res = client.post("/bills/upload-csv?household_id=1", files={"file": ("milk_bill.csv", csv_data, "text/csv")})
    assert res.status_code == 201

    inv_res = client.get("/items/inventory/current?household_id=1&status_filter=ACTIVE")
    assert inv_res.status_code == 200
    items = inv_res.json()
    assert len(items) > 0

    milk_item = next((i for i in items if "milk" in i["item_name"].lower()), None)
    assert milk_item is not None
    assert milk_item["store_name"] is not None
    assert "costco" in milk_item["store_name"].lower()
    assert milk_item["price"] is not None
    assert milk_item["price"] > 0


# --- 9. Test Sunday Grocery List Store Ambiguity and Permanent Removal ---
def test_grocery_list_store_ambiguity_and_permanent_removal(client, db_session):
    """Items in Sunday Grocery List have store attributed, and removing an item
    ensures it does not regenerate on subsequent generate calls.
    """
    groc_res = client.get("/grocery-list/generate?household_id=1&days_ahead=7")
    assert groc_res.status_code == 200
    data = groc_res.json()
    assert len(data["items"]) > 0

    # Pick an item to remove
    target = data["items"][0]
    target_id = target["id"]
    target_name = target["item_name"]
    assert target["target_store"] is not None

    # Delete the item
    del_res = client.delete(f"/grocery-list/items/{target_id}")
    assert del_res.status_code == 204

    # Re-generate list and verify target item is gone
    re_groc = client.get("/grocery-list/generate?household_id=1&days_ahead=7")
    assert re_groc.status_code == 200
    re_data = re_groc.json()
    assert not any(i["id"] == target_id for i in re_data["items"])
    assert not any(i["item_name"] == target_name for i in re_data["items"])


# --- 10. Test Manual Add Grocery Item with Canonical Linking and Price ---
def test_manual_add_grocery_item_with_canonical_linking(client, db_session):
    """Manually adding an item links to canonical item and calculates estimated cost."""
    add_payload = {
        "item_name": "Whole Milk",
        "quantity": 2,
        "unit": "gallon",
        "category": "Dairy",
        "target_store": "Costco Wholesale"
    }
    res = client.post("/grocery-list/items?household_id=1", json=add_payload)
    assert res.status_code == 201
    entry = res.json()
    assert entry["item_name"] == "Whole Milk"
    assert entry["canonical_item_id"] is not None
    assert entry["priority_reason"] == "MANUAL"
    assert entry["recommended_quantity"] == 2.0
    assert entry["estimated_cost"] is not None
    assert entry["estimated_cost"] > 0
    assert entry["target_store"] == "Costco Wholesale"


def test_item_details_endpoint_and_purchase_history_desc(client, db_session):
    from app.models import ItemAlias
    """Verify GET /items/{id}/details returns:
    - Item metadata
    - Active pantry stock
    - Consumption rhythm
    - Purchase history sorted in descending order by date
    - Aliases list
    """
    # Create test item
    item = Item(
        canonical_name="Test Golden Honey",
        category="Pantry",
        standard_unit="bottle",
        default_shelf_life_days=180,
        is_bulk=False,
        is_active=True,
        is_grocery=True,
        preferred_store="Trader Joe's",
        default_unit_price=4.99
    )
    db_session.add(item)
    db_session.flush()

    # Add aliases
    alias1 = ItemAlias(canonical_item_id=item.id, raw_alias="tj golden honey", match_confidence=1.0, source="manual")
    alias2 = ItemAlias(canonical_item_id=item.id, raw_alias="organic raw honey", match_confidence=0.95, source="manual")
    db_session.add_all([alias1, alias2])

    # Add purchases on different dates
    p1 = PurchaseLog(household_id=1, purchase_date=date(2026, 8, 1), store_name="Trader Joe's", raw_text="TJ GOLDEN HONEY", canonical_item_id=item.id, quantity=1, unit="bottle", price=4.99, matched_via="exact")
    p2 = PurchaseLog(household_id=1, purchase_date=date(2026, 9, 1), store_name="Trader Joe's", raw_text="TJ GOLDEN HONEY", canonical_item_id=item.id, quantity=1, unit="bottle", price=5.29, matched_via="exact")
    p3 = PurchaseLog(household_id=1, purchase_date=date(2026, 7, 1), store_name="Safeway", raw_text="HONEY JAR", canonical_item_id=item.id, quantity=1, unit="bottle", price=4.50, matched_via="fuzzy")
    db_session.add_all([p1, p2, p3])

    # Add active inventory
    inv = Inventory(household_id=1, canonical_item_id=item.id, purchase_log_id=p2.id, current_quantity=1.0, unit="bottle", purchase_date=date(2026, 9, 1), status=InventoryStatus.ACTIVE)
    db_session.add(inv)
    db_session.commit()

    res = client.get(f"/items/{item.id}/details?household_id=1")
    assert res.status_code == 200
    data = res.json()

    assert data["item"]["canonical_name"] == "Test Golden Honey"
    assert data["active_inventory"] is not None
    assert data["active_inventory"]["current_quantity"] == 1.0
    assert data["active_inventory"]["store_name"] == "Trader Joe's"

    # Verify purchase history is sorted descending by date
    history = data["purchase_history"]
    assert len(history) == 3
    dates = [h["purchase_date"] for h in history]
    assert dates == ["2026-09-01", "2026-08-01", "2026-07-01"]
    assert history[0]["store_name"] == "Trader Joe's"
    assert history[0]["price"] == 5.29

    # Verify consumption rhythm
    assert "daily_rate" in data["consumption_rhythm"]

    # Verify aliases
    aliases = data["aliases"]
    assert len(aliases) == 2
    assert any(a["raw_alias"] == "tj golden honey" for a in aliases)

def test_alias_edit_and_delete(client, db_session):
    from app.models import ItemAlias
    """Test modifying and deleting an alias via /items/aliases endpoints."""
    item = Item(canonical_name="Test Green Tea", category="Beverages", standard_unit="box", default_shelf_life_days=90, is_bulk=False, is_active=True, is_grocery=True)
    db_session.add(item)
    db_session.flush()

    alias = ItemAlias(canonical_item_id=item.id, raw_alias="matcha tea box", match_confidence=1.0, source="manual")
    db_session.add(alias)
    db_session.commit()

    # Edit alias
    res = client.patch(f"/items/aliases/{alias.id}?raw_alias=organic%20matcha%20tea")
    assert res.status_code == 200
    assert res.json()["raw_alias"] == "organic matcha tea"

    # Delete alias
    res_del = client.delete(f"/items/aliases/{alias.id}")
    assert res_del.status_code == 200

    # Verify deleted
    assert db_session.query(ItemAlias).filter(ItemAlias.id == alias.id).first() is None

def test_separate_bills_for_distinct_store_and_date(client, db_session):
    """Verify that uploading a CSV with multiple stores and dates creates distinct bill records."""
    multi_store_csv = (
        "Date,Store Name,Item Description,Category,Total Price,Quantity,Unit,Unit Price,Pricing Type\n"
        "2026-09-01,Costco,BULK PAPER TOWELS,Supplies,22.99,1,pack,22.99,Fixed\n"
        "2026-09-01,Trader Joe's,ORGANIC BANANAS,Produce,1.99,1,bunch,1.99,Fixed\n"
        "2026-09-05,Costco,ALMOND BUTTER,Pantry,8.99,1,jar,8.99,Fixed\n"
    )
    res = client.post("/bills/upload-csv?household_id=2", files={"file": ("tri_bill.csv", multi_store_csv, "text/csv")})
    assert res.status_code == 201

    bills_res = client.get("/bills?household_id=2")
    assert bills_res.status_code == 200
    bills = bills_res.json()

    # Should have 3 separate bills: (Costco, 2026-09-01), (Trader Joe's, 2026-09-01), (Costco, 2026-09-05)
    bill_keys = [(b["store_name"], b["bill_date"]) for b in bills]
    assert ("Costco", "2026-09-01") in bill_keys
    assert ("Trader Joe's", "2026-09-01") in bill_keys
    assert ("Costco", "2026-09-05") in bill_keys
