import React, { useState } from "react";
import { AlertCircle, ShoppingCart, Sparkles, Check } from "lucide-react";
import type { AvailabilityPrompt } from "../types";
import { confirmAvailability } from "../api/client";

interface PromptsTabProps {
  prompts: AvailabilityPrompt[];
  householdId: number;
  onRefresh: () => void;
}

export const PromptsTab: React.FC<PromptsTabProps> = ({
  prompts,
  householdId,
  onRefresh,
}) => {
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [dismissedIds, setDismissedIds] = useState<number[]>([]);

  const handleConfirm = async (canonicalItemId: number, isAvailable: boolean) => {
    try {
      setProcessingId(canonicalItemId);
      setDismissedIds((prev) => [...prev, canonicalItemId]);
      await confirmAvailability(canonicalItemId, isAvailable, householdId);
      onRefresh();
    } catch (err) {
      setDismissedIds((prev) => prev.filter((id) => id !== canonicalItemId));
      alert("Failed to confirm item availability.");
    } finally {
      setProcessingId(null);
    }
  };

  const visiblePrompts = prompts.filter((p) => !dismissedIds.includes(p.canonical_item_id));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div className="glass-panel" style={{ padding: "20px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
          <AlertCircle size={22} color="#F59E0B" />
          <span>Cold-Start Availability Verification Center</span>
        </h3>
        <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "6px", maxWidth: "700px" }}>
          When an item has only been purchased once, the tracker will not assume an arbitrary frequency.
          Confirm whether you still have stock on hand, or mark it finished so it gets queued for your Sunday grocery list!
        </p>
      </div>

      {visiblePrompts.length === 0 ? (
        <div className="glass-panel" style={{ padding: "60px 20px", textAlign: "center" }}>
          <div style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: "rgba(16, 185, 129, 0.15)",
            color: "#10B981",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 16px"
          }}>
            <Sparkles size={28} />
          </div>
          <h4 style={{ fontSize: "1.2rem", fontWeight: 600, color: "#F3F4F6" }}>All Caught Up!</h4>
          <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "4px" }}>
            No single-purchase items currently require availability verification for Household {householdId}.
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" }}>
          {visiblePrompts.map((prompt) => (
            <div
              key={prompt.canonical_item_id}
              className="glass-panel"
              style={{
                padding: "20px",
                borderLeft: "4px solid #F59E0B",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: "16px"
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span className="badge badge-amber" style={{ fontSize: "0.7rem" }}>
                    {prompt.category}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "#6B7280" }}>
                    Bought {prompt.last_purchased}
                  </span>
                </div>
                <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#F3F4F6", marginTop: "10px" }}>
                  {prompt.message}
                </h4>
                <p style={{ fontSize: "0.8rem", color: "#9CA3AF", marginTop: "4px" }}>
                  Last purchase: {prompt.last_quantity} {prompt.unit}
                </p>
              </div>

              <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
                <button
                  disabled={processingId === prompt.canonical_item_id}
                  onClick={() => handleConfirm(prompt.canonical_item_id, true)}
                  className="btn-success"
                  style={{ flex: 1, justifyContent: "center" }}
                >
                  <Check size={16} />
                  <span>Still in Stock</span>
                </button>
                <button
                  disabled={processingId === prompt.canonical_item_id}
                  onClick={() => handleConfirm(prompt.canonical_item_id, false)}
                  className="btn-primary"
                  style={{ flex: 1, justifyContent: "center", background: "linear-gradient(135deg, #EF4444 0%, #DC2626 100%)" }}
                >
                  <ShoppingCart size={16} />
                  <span>Finished (Reorder)</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
