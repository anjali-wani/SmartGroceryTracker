import React, { useState } from "react";
import { Layers, Search, Plus, Minus, Clock } from "lucide-react";
import type { InventoryItem } from "../types";
import { adjustInventoryStock } from "../api/client";

interface InventoryTabProps {
  inventory: InventoryItem[];
  householdId: number;
  onRefresh: () => void;
}

export const InventoryTab: React.FC<InventoryTabProps> = ({
  inventory,
  onRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [viewStatus, setViewStatus] = useState<"ACTIVE" | "CONSUMED">("ACTIVE");
  const [adjustingId, setAdjustingId] = useState<number | null>(null);

  const categories = ["All", ...Array.from(new Set(inventory.map((i) => i.category)))];

  const filtered = inventory.filter((item) => {
    const matchesStatus = item.status === viewStatus;
    const matchesCat = selectedCategory === "All" || item.category === selectedCategory;
    const matchesSearch = item.item_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesCat && matchesSearch;
  });

  const handleAdjustQuantity = async (invId: number, currentQty: number, delta: number) => {
    try {
      setAdjustingId(invId);
      const newQty = Math.max(0, currentQty + delta);
      await adjustInventoryStock(invId, newQty);
      onRefresh();
    } catch (err) {
      alert("Failed to adjust inventory");
    } finally {
      setAdjustingId(null);
    }
  };

  const handleMarkConsumed = async (invId: number) => {
    try {
      setAdjustingId(invId);
      await adjustInventoryStock(invId, 0);
      onRefresh();
    } catch (err) {
      alert("Failed to mark item consumed");
    } finally {
      setAdjustingId(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div className="glass-panel" style={{ padding: "16px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
          <div style={{ display: "flex", background: "rgba(255, 255, 255, 0.05)", borderRadius: "10px", padding: "3px" }}>
            <button
              onClick={() => setViewStatus("ACTIVE")}
              style={{
                background: viewStatus === "ACTIVE" ? "linear-gradient(135deg, #10B981, #059669)" : "transparent",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                padding: "6px 14px",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px"
              }}
            >
              <Layers size={14} />
              <span>Active Stock ({inventory.filter(i => i.status === "ACTIVE").length})</span>
            </button>
            <button
              onClick={() => setViewStatus("CONSUMED")}
              style={{
                background: viewStatus === "CONSUMED" ? "linear-gradient(135deg, #6366F1, #4F46E5)" : "transparent",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                padding: "6px 14px",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px"
              }}
            >
              <Clock size={14} />
              <span>Consumed History ({inventory.filter(i => i.status === "CONSUMED").length})</span>
            </button>
          </div>

          <div style={{
            position: "relative",
            minWidth: "260px",
            flex: 1,
            maxWidth: "400px"
          }}>
            <Search size={16} color="#6B7280" style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)" }} />
            <input
              type="text"
              placeholder="Search pantry items..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: "100%",
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "10px",
                padding: "8px 12px 8px 36px",
                color: "#F3F4F6",
                fontSize: "0.85rem",
                outline: "none"
              }}
            />
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px", marginTop: "14px", overflowX: "auto", paddingBottom: "2px" }}>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              style={{
                background: selectedCategory === cat ? "rgba(255, 255, 255, 0.15)" : "rgba(255, 255, 255, 0.04)",
                border: selectedCategory === cat ? "1px solid rgba(255, 255, 255, 0.3)" : "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "4px 12px",
                color: selectedCategory === cat ? "#fff" : "#9CA3AF",
                fontSize: "0.8rem",
                fontWeight: 500,
                cursor: "pointer",
                whiteSpace: "nowrap"
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
        {filtered.length === 0 ? (
          <div className="glass-panel" style={{ gridColumn: "1 / -1", padding: "40px", textAlign: "center", color: "#6B7280" }}>
            No {viewStatus.toLowerCase()} items found matching your filters.
          </div>
        ) : (
          filtered.map((item) => (
            <div key={item.id} className="glass-panel" style={{ padding: "18px", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: "12px" }}>
              <div>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px" }}>
                  <h4 style={{ fontSize: "1rem", fontWeight: 600, color: "#F3F4F6", lineHeight: 1.3 }}>
                    {item.item_name}
                  </h4>
                  <span className="badge badge-emerald" style={{ fontSize: "0.7rem", flexShrink: 0 }}>
                    {item.category}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.78rem", color: "#9CA3AF", marginTop: "6px", flexWrap: "wrap" }}>
                  <span style={{ color: "#10B981", fontWeight: 600 }}>
                    🏪 {item.store_name || "Grocery Store"}
                  </span>
                  {item.price !== undefined && item.price !== null && (
                    <span style={{ color: "#34D399", fontWeight: 600 }}>
                      • ${item.price.toFixed(2)}
                    </span>
                  )}
                  <span style={{ color: "#6B7280" }}>• {item.purchase_date}</span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "8px", paddingTop: "12px", borderTop: "1px solid var(--border-subtle)" }}>
                <div>
                  <span style={{ fontSize: "0.75rem", color: "#6B7280", display: "block" }}>Current Quantity</span>
                  <span style={{ fontSize: "1.25rem", fontWeight: 700, color: item.current_quantity > 0 ? "#10B981" : "#EF4444" }}>
                    {item.current_quantity} <span style={{ fontSize: "0.8rem", fontWeight: 500, color: "#9CA3AF" }}>{item.unit}</span>
                  </span>
                </div>

                {viewStatus === "ACTIVE" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <button
                      disabled={adjustingId === item.id}
                      onClick={() => handleAdjustQuantity(item.id, item.current_quantity, -1)}
                      style={{
                        width: "28px",
                        height: "28px",
                        borderRadius: "6px",
                        background: "rgba(255, 255, 255, 0.08)",
                        border: "1px solid var(--border-subtle)",
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer"
                      }}
                    >
                      <Minus size={14} />
                    </button>
                    <button
                      disabled={adjustingId === item.id}
                      onClick={() => handleAdjustQuantity(item.id, item.current_quantity, 1)}
                      style={{
                        width: "28px",
                        height: "28px",
                        borderRadius: "6px",
                        background: "rgba(255, 255, 255, 0.08)",
                        border: "1px solid var(--border-subtle)",
                        color: "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer"
                      }}
                    >
                      <Plus size={14} />
                    </button>
                    <button
                      disabled={adjustingId === item.id}
                      onClick={() => handleMarkConsumed(item.id)}
                      className="btn-danger"
                      style={{ padding: "5px 10px", fontSize: "0.75rem" }}
                      title="Mark consumed (quantity reaches 0)"
                    >
                      Finished
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
