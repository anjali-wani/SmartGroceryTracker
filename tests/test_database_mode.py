from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_system_database_mode_status():
    """Verify /system/database-mode returns current mode and both databases."""
    res = client.get("/system/database-mode")
    assert res.status_code == 200
    data = res.json()
    assert "current_mode" in data
    assert "databases" in data
    assert "production" in data["databases"]
    assert "test" in data["databases"]
    assert data["databases"]["production"]["file"] == "grocery_tracker.db"
    assert data["databases"]["test"]["file"] == "grocery_tracker_test.db"


def test_switch_server_database_mode():
    """Verify switching server-level default database mode."""
    # Switch to test
    res = client.post("/system/database-mode", json={"mode": "test"})
    assert res.status_code == 200
    assert res.json()["current_mode"] == "test"

    # Switch to production
    res = client.post("/system/database-mode", json={"mode": "production"})
    assert res.status_code == 200
    assert res.json()["current_mode"] == "production"


def test_request_header_database_isolation():
    """Verify that requests with X-Database-Mode: test do not affect production DB."""
    test_item_name = "Mode Isolation Test Produce Item"
    
    # 1. Create item in Test DB
    create_res = client.post(
        "/items",
        json={
            "canonical_name": test_item_name,
            "category": "Produce",
            "standard_unit": "count",
            "default_shelf_life_days": 7
        },
        headers={"X-Database-Mode": "test"}
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # 2. Check existence in Test DB
    test_get = client.get(f"/items?search={test_item_name}", headers={"X-Database-Mode": "test"})
    assert test_get.status_code == 200
    assert any(i["canonical_name"] == test_item_name for i in test_get.json())

    # 3. Verify it does NOT exist in Production DB
    prod_get = client.get(f"/items?search={test_item_name}", headers={"X-Database-Mode": "production"})
    assert prod_get.status_code == 200
    assert not any(i["canonical_name"] == test_item_name for i in prod_get.json())

    # Cleanup from test DB
    from app.database import TestSessionLocal
    from app.models import Item
    db = TestSessionLocal()
    it = db.query(Item).filter(Item.id == created_id).first()
    if it:
        db.delete(it)
        db.commit()
    db.close()


def test_clear_system_database_endpoint():
    """Verify that /system/clear-database endpoint successfully wipes databases."""
    res = client.post("/system/clear-database", json={"target": "both"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cleared"
    assert data["target"] == "both"
    # Verify counts are 0
    prod_counts = data["current_status"]["databases"]["production"]
    test_counts = data["current_status"]["databases"]["test"]
    assert prod_counts["items_count"] == 0
    assert prod_counts["inventory_count"] == 0
    assert test_counts["items_count"] == 0
    assert test_counts["inventory_count"] == 0

