import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { ItemsTab } from "./components/ItemsTab";
import { GroceryListTab } from "./components/GroceryListTab";
import { IngestionTab } from "./components/IngestionTab";
import {
  fetchCurrentInventory,
  fetchGroceryList,
  checkBackendHealth,
  resetDatabase,
  getDatabaseMode,
  setDatabaseMode,
  type DatabaseMode
} from "./api/client";
import type { InventoryItem, GroceryListResponse } from "./types";

export function App() {
  // 3 tabs: "items", "grocery", "bills"
  const [currentTab, setCurrentTab] = useState<string>("items");
  const [householdId, setHouseholdId] = useState<number>(() => {
    const saved = localStorage.getItem("sgt_household_id");
    return saved ? Number(saved) : 1;
  });

  const [dbMode, setDbMode] = useState<DatabaseMode>(() => getDatabaseMode());
  const [modeNotice, setModeNotice] = useState<string | null>(null);

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [groceryData, setGroceryData] = useState<GroceryListResponse | null>(null);
  const [backendOnline, setBackendOnline] = useState(true);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const isOnline = await checkBackendHealth();
      setBackendOnline(isOnline);

      const [inv, groc] = await Promise.all([
        fetchCurrentInventory(householdId),
        fetchGroceryList(householdId, 7),
      ]);
      setInventory(inv);
      setGroceryData(groc);
    } catch (err) {
      console.error("Failed to load initial data", err);
      setBackendOnline(false);
    }
  };

  const handleDbModeChange = (newMode: DatabaseMode) => {
    setDatabaseMode(newMode);
    setDbMode(newMode);
    setModeNotice(
      newMode === "production"
        ? "🟢 Active Database: Production (grocery_tracker.db) — Live user data mode."
        : "🟡 Active Database: Test (grocery_tracker_test.db) — Sandbox data mode."
    );
    setTimeout(() => setModeNotice(null), 4000);
  };

  useEffect(() => {
    localStorage.setItem("sgt_household_id", String(householdId));
    loadData();
  }, [householdId, dbMode]);

  const handleResetData = async () => {
    const confirmReset = window.confirm(
      `⚠️ Reset Test Database?\n\nThis will clear test inventory, purchase logs, and test grocery lists for Household ${householdId} in the test database.\n\nProceed?`
    );
    if (!confirmReset) return;

    try {
      const res = await resetDatabase(householdId);
      setResetMessage(res.message || "Test database reset successfully!");
      setTimeout(() => setResetMessage(null), 4000);
      await loadData();
    } catch (err: any) {
      alert(`Reset failed: ${err.message || "Unknown error"}`);
    }
  };

  return (
    <div style={{ maxWidth: "1400px", margin: "0 auto", paddingBottom: "40px" }}>
      <Navbar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        householdId={householdId}
        setHouseholdId={setHouseholdId}
        groceryCount={groceryData?.total_items || 0}
        inventoryCount={inventory.filter((i) => i.status === "ACTIVE" && i.current_quantity > 0).length}
        backendOnline={backendOnline}
        onResetData={handleResetData}
        dbMode={dbMode}
        onDbModeChange={handleDbModeChange}
      />

      {modeNotice && (
        <div
          style={{
            margin: "0 24px 16px",
            padding: "10px 18px",
            background: dbMode === "production"
              ? "linear-gradient(90deg, rgba(16, 185, 129, 0.15), rgba(18, 24, 38, 0.8))"
              : "linear-gradient(90deg, rgba(245, 158, 11, 0.15), rgba(18, 24, 38, 0.8))",
            border: dbMode === "production"
              ? "1px solid rgba(16, 185, 129, 0.4)"
              : "1px solid rgba(245, 158, 11, 0.4)",
            borderRadius: "12px",
            color: dbMode === "production" ? "#34D399" : "#FBBF24",
            fontWeight: 600,
            fontSize: "0.82rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            animation: "fadeIn 0.2s ease-in-out"
          }}
        >
          <span>{modeNotice}</span>
          <button
            onClick={() => setModeNotice(null)}
            style={{ background: "transparent", border: "none", color: "#9CA3AF", cursor: "pointer", fontSize: "0.85rem" }}
          >
            ✕
          </button>
        </div>
      )}

      {resetMessage && (
        <div
          style={{
            margin: "0 24px 16px",
            padding: "12px 18px",
            background: "linear-gradient(90deg, rgba(16, 185, 129, 0.2), rgba(18, 24, 38, 0.9))",
            border: "1px solid rgba(16, 185, 129, 0.4)",
            borderRadius: "12px",
            color: "#34D399",
            fontWeight: 600,
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}
        >
          <span>✓ {resetMessage}</span>
          <button
            onClick={() => setResetMessage(null)}
            style={{ background: "transparent", border: "none", color: "#9CA3AF", cursor: "pointer", fontSize: "0.85rem" }}
          >
            ✕
          </button>
        </div>
      )}

      <main style={{ padding: "0 24px" }}>
        {currentTab === "items" && (
          <ItemsTab key={`items-${dbMode}-${householdId}`} householdId={householdId} />
        )}

        {currentTab === "grocery" && (
          <GroceryListTab
            key={`grocery-${dbMode}-${householdId}`}
            groceryData={groceryData}
            householdId={householdId}
            onRefresh={loadData}
          />
        )}

        {currentTab === "bills" && (
          <IngestionTab
            key={`bills-${dbMode}-${householdId}`}
            householdId={householdId}
            onRefresh={loadData}
          />
        )}
      </main>
    </div>
  );
}

export default App;
