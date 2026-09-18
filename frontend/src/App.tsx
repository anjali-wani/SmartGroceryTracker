import { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { ItemsTab } from "./components/ItemsTab";
import { GroceryListTab } from "./components/GroceryListTab";
import { IngestionTab } from "./components/IngestionTab";
import {
  fetchCurrentInventory,
  fetchGroceryList,
  checkBackendHealth,
  resetDatabase
} from "./api/client";
import type { InventoryItem, GroceryListResponse } from "./types";

export function App() {
  // 3 tabs: "items", "grocery", "bills"
  const [currentTab, setCurrentTab] = useState<string>("items");
  const [householdId, setHouseholdId] = useState<number>(() => {
    const saved = localStorage.getItem("sgt_household_id");
    return saved ? Number(saved) : 1;
  });

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

  useEffect(() => {
    localStorage.setItem("sgt_household_id", String(householdId));
    loadData();
  }, [householdId]);

  const handleResetData = async () => {
    const confirmReset = window.confirm(
      `⚠️ Reset Database in Test Mode?\n\nThis will clear all active/consumed inventory, purchase logs, and grocery lists for Household ${householdId} from the database.\n\nProceed?`
    );
    if (!confirmReset) return;

    try {
      const res = await resetDatabase(householdId);
      setResetMessage(res.message || "Database reset successfully!");
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
      />

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
          <ItemsTab householdId={householdId} />
        )}

        {currentTab === "grocery" && (
          <GroceryListTab
            groceryData={groceryData}
            householdId={householdId}
            onRefresh={loadData}
          />
        )}

        {currentTab === "bills" && (
          <IngestionTab
            householdId={householdId}
            onRefresh={loadData}
          />
        )}
      </main>
    </div>
  );
}

export default App;
