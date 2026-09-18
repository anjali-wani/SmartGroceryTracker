import React from "react";
import {
  Layers,
  AlertCircle,
  ShoppingCart,
  DollarSign,
  ArrowRight,
  TrendingUp,
  Receipt,
  Sparkles
} from "lucide-react";
import type { InventoryItem, GroceryListResponse, AvailabilityPrompt } from "../types";

interface DashboardTabProps {
  inventory: InventoryItem[];
  groceryData: GroceryListResponse | null;
  prompts: AvailabilityPrompt[];
  onNavigate: (tab: string) => void;
}

export const DashboardTab: React.FC<DashboardTabProps> = ({
  inventory,
  groceryData,
  prompts,
  onNavigate,
}) => {
  const activeStockCount = inventory.filter((i) => i.status === "ACTIVE").length;
  const groceryItemsCount = groceryData?.total_items || 0;
  const estimatedCost = groceryData?.total_estimated_cost || 0;

  const categories: Record<string, number> = {};
  inventory
    .filter((i) => i.status === "ACTIVE")
    .forEach((i) => {
      categories[i.category] = (categories[i.category] || 0) + 1;
    });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {prompts.length > 0 && (
        <div
          className="glass-panel"
          style={{
            padding: "16px 20px",
            borderLeft: "4px solid #F59E0B",
            background: "linear-gradient(90deg, rgba(245, 158, 11, 0.1) 0%, rgba(18, 24, 38, 0.8) 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "rgba(245, 158, 11, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}>
              <AlertCircle size={20} color="#F59E0B" />
            </div>
            <div>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#FCD34D" }}>
                {prompts.length} Kitchen Item{prompts.length > 1 ? "s" : ""} Need Status Verification
              </h4>
              <p style={{ fontSize: "0.8rem", color: "#9CA3AF" }}>
                Single-purchase items need to know if they are still on hand or consumed to calibrate frequency.
              </p>
            </div>
          </div>
          <button
            className="btn-primary"
            style={{ background: "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)", boxShadow: "0 4px 12px rgba(245, 158, 11, 0.3)" }}
            onClick={() => onNavigate("prompts")}
          >
            <span>Review Items</span>
            <ArrowRight size={16} />
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
        <div className="glass-panel" style={{ padding: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.05em" }}>
              Active Pantry Stock
            </span>
            <div style={{ width: "34px", height: "34px", borderRadius: "8px", background: "rgba(16, 185, 129, 0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Layers size={18} color="#10B981" />
            </div>
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "#F3F4F6", marginTop: "12px" }}>
            {activeStockCount}
          </div>
          <p style={{ fontSize: "0.8rem", color: "#6B7280", marginTop: "4px" }}>
            Items tracked in kitchen & fridge
          </p>
        </div>

        <div className="glass-panel" style={{ padding: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.05em" }}>
              Prediction Mode
            </span>
            <div style={{ width: "34px", height: "34px", borderRadius: "8px", background: "rgba(16, 185, 129, 0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Sparkles size={18} color="#10B981" />
            </div>
          </div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#34D399", marginTop: "16px" }}>
            Autonomous
          </div>
          <p style={{ fontSize: "0.8rem", color: "#6B7280", marginTop: "4px" }}>
            Pure purchase interval modeling
          </p>
        </div>

        <div className="glass-panel" style={{ padding: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.05em" }}>
              Sunday Grocery List
            </span>
            <div style={{ width: "34px", height: "34px", borderRadius: "8px", background: "rgba(99, 102, 241, 0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <ShoppingCart size={18} color="#818CF8" />
            </div>
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "#F3F4F6", marginTop: "12px" }}>
            {groceryItemsCount}
          </div>
          <p style={{ fontSize: "0.8rem", color: "#6B7280", marginTop: "4px" }}>
            Depleted or scheduled items
          </p>
        </div>

        <div className="glass-panel" style={{ padding: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "#9CA3AF", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.05em" }}>
              Est. Reorder Budget
            </span>
            <div style={{ width: "34px", height: "34px", borderRadius: "8px", background: "rgba(6, 182, 212, 0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <DollarSign size={18} color="#06B6D4" />
            </div>
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "#34D399", marginTop: "12px" }}>
            ${estimatedCost.toFixed(2)}
          </div>
          <p style={{ fontSize: "0.8rem", color: "#6B7280", marginTop: "4px" }}>
            Forecasted total for this cycle
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
        <div className="glass-panel" style={{ padding: "20px" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Layers size={18} color="#10B981" />
            <span>Pantry Inventory by Category</span>
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {Object.keys(categories).length === 0 ? (
              <p style={{ fontSize: "0.85rem", color: "#6B7280" }}>No active inventory items found.</p>
            ) : (
              Object.entries(categories).map(([cat, count]) => (
                <div key={cat} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.85rem", color: "#D1D5DB" }}>{cat}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{
                      width: "120px",
                      height: "6px",
                      borderRadius: "3px",
                      background: "rgba(255, 255, 255, 0.08)",
                      overflow: "hidden"
                    }}>
                      <div style={{
                        width: `${Math.min(100, (count / activeStockCount) * 100)}%`,
                        height: "100%",
                        background: "linear-gradient(90deg, #10B981, #6366F1)",
                        borderRadius: "3px"
                      }} />
                    </div>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#9CA3AF", minWidth: "24px", textAlign: "right" }}>
                      {count}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: "20px" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
            <Sparkles size={18} color="#818CF8" />
            <span>Smart Automation Launchpad</span>
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <button
              onClick={() => onNavigate("grocery")}
              className="btn-secondary"
              style={{ justifyContent: "space-between", padding: "12px 16px" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <ShoppingCart size={18} color="#818CF8" />
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>Review Sunday Grocery List</div>
                  <div style={{ fontSize: "0.75rem", color: "#6B7280" }}>Grouped by Costco, Trader Joe's, and New India Bazar</div>
                </div>
              </div>
              <ArrowRight size={16} color="#6B7280" />
            </button>

            <button
              onClick={() => onNavigate("ingestion")}
              className="btn-secondary"
              style={{ justifyContent: "space-between", padding: "12px 16px" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Receipt size={18} color="#10B981" />
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>Upload New Grocery Receipt</div>
                  <div style={{ fontSize: "0.75rem", color: "#6B7280" }}>Automated RapidFuzz & LLM parsing</div>
                </div>
              </div>
              <ArrowRight size={16} color="#6B7280" />
            </button>

            <button
              onClick={() => onNavigate("velocity")}
              className="btn-secondary"
              style={{ justifyContent: "space-between", padding: "12px 16px" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <TrendingUp size={18} color="#06B6D4" />
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>Inspect Repurchase Burn Rates</div>
                  <div style={{ fontSize: "0.75rem", color: "#6B7280" }}>Purchase-interval durations & modal quantities</div>
                </div>
              </div>
              <ArrowRight size={16} color="#6B7280" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
