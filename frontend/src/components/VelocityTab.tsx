import React, { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import type { ItemVelocity } from "../types";
import { fetchVelocityReport } from "../api/client";

interface VelocityTabProps {
  householdId: number;
}

export const VelocityTab: React.FC<VelocityTabProps> = ({ householdId }) => {
  const [items, setItems] = useState<ItemVelocity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetchVelocityReport(householdId)
      .then((data) => {
        if (mounted) setItems(data.items);
      })
      .catch((err) => console.error(err))
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [householdId]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div className="glass-panel" style={{ padding: "20px" }}>
        <h3 style={{ fontSize: "1.15rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
          <TrendingUp size={22} color="#06B6D4" />
          <span>Purchase-Interval Consumption Engine</span>
        </h3>
        <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "6px" }}>
          Consumption rates and runout predictions are modeled directly from sequential restock intervals (e.g. 1 lb lasts 14 days ➔ 2 lb lasts 28 days). Expiration dates are completely decoupled.
        </p>
      </div>

      {loading ? (
        <div className="glass-panel" style={{ padding: "40px", textAlign: "center", color: "#9CA3AF" }}>
          Loading velocity analytics...
        </div>
      ) : items.length === 0 ? (
        <div className="glass-panel" style={{ padding: "40px", textAlign: "center", color: "#9CA3AF" }}>
          No consumption velocity records available yet. Upload receipts to establish frequency.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" }}>
          {items.map((item) => (
            <div key={item.canonical_item_id} className="glass-panel" style={{ padding: "18px", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: "14px" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span className="badge badge-indigo" style={{ fontSize: "0.7rem" }}>
                    {item.category}
                  </span>
                  <span
                    className={`badge ${
                      item.confidence === "high"
                        ? "badge-emerald"
                        : item.confidence === "moderate"
                        ? "badge-cyan"
                        : "badge-amber"
                    }`}
                    style={{ fontSize: "0.68rem" }}
                  >
                    {item.confidence.replace("_", " ")}
                  </span>
                </div>
                <h4 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#F3F4F6", marginTop: "8px" }}>
                  {item.item_name}
                </h4>
                <div style={{ fontSize: "0.75rem", color: "#6B7280", marginTop: "2px" }}>
                  {item.purchase_count} total purchases recorded
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", padding: "12px", background: "rgba(255, 255, 255, 0.03)", borderRadius: "10px" }}>
                <div>
                  <span style={{ fontSize: "0.7rem", color: "#9CA3AF", display: "block" }}>Unit Burn Rate</span>
                  <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#06B6D4" }}>
                    {item.days_per_unit ? `${item.days_per_unit} d/${item.unit}` : "Cold Start"}
                  </span>
                </div>
                <div>
                  <span style={{ fontSize: "0.7rem", color: "#9CA3AF", display: "block" }}>Modal Restock Qty</span>
                  <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#10B981" }}>
                    {item.modal_quantity ? `${item.modal_quantity} ${item.unit}` : "1.0"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "8px", borderTop: "1px solid var(--border-subtle)", fontSize: "0.8rem" }}>
                <span style={{ color: "#9CA3AF" }}>Runout Projection:</span>
                <span style={{ fontWeight: 600, color: item.projected_runout_date ? "#FCD34D" : "#6B7280" }}>
                  {item.projected_runout_date || "Pending Restock"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
