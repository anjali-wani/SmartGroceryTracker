import React, { useState, useEffect } from "react";
import {
  X,
  Sparkles,
  Plus,
  Calendar,
  Store,
  Flame,
  DollarSign,
  Edit2,
  Check,
  Clock,
  ShoppingBag,
  Trash2,
  Loader2
} from "lucide-react";
import type { ItemDetails, ItemPurchaseHistoryEntry } from "../types";
import {
  fetchItemDetails,
  addAliasToItem,
  deleteItemAlias,
  updateItemPrice,
  updateItemName,
  deletePurchaseItem
} from "../api/client";

interface ItemDetailsModalProps {
  itemId: number | null;
  householdId: number;
  onClose: () => void;
  onItemUpdated?: () => void;
}

export const ItemDetailsModal: React.FC<ItemDetailsModalProps> = ({
  itemId,
  householdId,
  onClose,
  onItemUpdated
}) => {
  const [details, setDetails] = useState<ItemDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Inline Price Editing State
  const [isEditingPrice, setIsEditingPrice] = useState(false);
  const [priceInput, setPriceInput] = useState("");
  const [savingPrice, setSavingPrice] = useState(false);

  // Inline Canonical Name Editing State
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [savingName, setSavingName] = useState(false);

  // New alias input state
  const [newAlias, setNewAlias] = useState("");
  const [addingAlias, setAddingAlias] = useState(false);
  const [deletingAliasId, setDeletingAliasId] = useState<number | null>(null);

  // Deleting purchase log state
  const [deletingPurchaseId, setDeletingPurchaseId] = useState<number | null>(null);

  const loadDetails = async () => {
    if (!itemId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchItemDetails(itemId, householdId);
      setDetails(data);
      setNameInput(data.item.canonical_name);
      if (data.item.default_unit_price != null) {
        setPriceInput(data.item.default_unit_price.toFixed(2));
      }
    } catch (err: any) {
      console.error("Failed to load item details", err);
      setError(err.message || "Failed to load item details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetails();
  }, [itemId, householdId]);

  // Derived effective benchmark unit rate
  const displayPrice: number | null = details
    ? details.item.default_unit_price != null && details.item.default_unit_price > 0
      ? details.item.default_unit_price
      : details.active_inventory?.unit_price != null && details.active_inventory.unit_price > 0
      ? details.active_inventory.unit_price
      : details.purchase_history.find((p) => p.unit_price != null && p.unit_price > 0)?.unit_price
      ?? (details.purchase_history[0]?.price != null && details.purchase_history[0]?.quantity && details.purchase_history[0].quantity > 0
          ? Number((details.purchase_history[0].price / details.purchase_history[0].quantity).toFixed(2))
          : null)
    : null;

  const formatPriceAndUnit = (priceVal: number | null | undefined, unitVal: string | null | undefined) => {
    if (priceVal == null || priceVal <= 0) return { priceText: "No price", unitText: "" };
    const u = (unitVal || "").toLowerCase();
    if (u === "g" || u === "gm" || u === "gram" || u === "grams") {
      return { priceText: `$${(priceVal * 100).toFixed(2)}`, unitText: "/ 100g" };
    }
    if (u === "ml") {
      return { priceText: `$${(priceVal * 100).toFixed(2)}`, unitText: "/ 100ml" };
    }
    if (priceVal < 0.01) {
      return { priceText: `$${priceVal.toFixed(4)}`, unitText: `/ ${unitVal || "unit"}` };
    }
    return { priceText: `$${priceVal.toFixed(2)}`, unitText: `/ ${unitVal || "unit"}` };
  };

  const handleSavePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemId) return;
    const parsed = parseFloat(priceInput);
    if (isNaN(parsed) || parsed < 0) {
      alert("Please enter a valid price (e.g. 4.99)");
      return;
    }

    const u = (details?.item.standard_unit || "").toLowerCase();
    const isGrams = u === "g" || u === "gm" || u === "gram" || u === "grams";
    const priceToSend = isGrams ? Number((parsed / 100).toFixed(6)) : parsed;

    try {
      setSavingPrice(true);
      const updatedItem = await updateItemPrice(itemId, priceToSend);
      setDetails((prev) => (prev ? { ...prev, item: updatedItem } : prev));
      setIsEditingPrice(false);
      if (onItemUpdated) onItemUpdated();
    } catch (err: any) {
      alert(err.message || "Failed to update item price");
    } finally {
      setSavingPrice(false);
    }
  };

  const handleSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemId) return;
    const cleanName = nameInput.trim();
    if (!cleanName) {
      alert("Please enter a valid item name.");
      return;
    }

    try {
      setSavingName(true);
      const updatedItem = await updateItemName(itemId, cleanName);
      setDetails((prev) => (prev ? { ...prev, item: updatedItem } : prev));
      setIsEditingName(false);
      await loadDetails();
      if (onItemUpdated) onItemUpdated();
    } catch (err: any) {
      alert(err.message || "Failed to rename item");
    } finally {
      setSavingName(false);
    }
  };

  const handleAddAlias = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemId || !newAlias.trim()) return;

    try {
      setAddingAlias(true);
      const added = await addAliasToItem(itemId, newAlias.trim());
      setDetails((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          aliases: [added, ...prev.aliases]
        };
      });
      setNewAlias("");
      if (onItemUpdated) onItemUpdated();
    } catch (err: any) {
      alert(err.message || "Failed to add alias");
    } finally {
      setAddingAlias(false);
    }
  };

  const handleDeleteAlias = async (aliasId: number) => {
    try {
      setDeletingAliasId(aliasId);
      await deleteItemAlias(aliasId);
      setDetails((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          aliases: prev.aliases.filter((a) => a.id !== aliasId)
        };
      });
      if (onItemUpdated) onItemUpdated();
    } catch (err: any) {
      alert(err.message || "Failed to delete alias");
    } finally {
      setDeletingAliasId(null);
    }
  };

  const handleDeletePurchaseEntry = async (entry: ItemPurchaseHistoryEntry) => {
    const confirmMsg = `Delete purchase record from ${entry.store_name} on ${entry.purchase_date} (${entry.quantity} ${entry.unit})?\n\nThis will remove the entry and roll back corresponding active stock in your pantry if applicable.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setDeletingPurchaseId(entry.id);
      await deletePurchaseItem(entry.id);
      await loadDetails();
      if (onItemUpdated) {
        onItemUpdated();
      }
    } catch (err: any) {
      alert(err.message || "Failed to delete purchase record");
    } finally {
      setDeletingPurchaseId(null);
    }
  };

  if (!itemId) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1100,
        padding: "20px"
      }}
      onClick={onClose}
    >
      <div
        className="glass-panel"
        style={{
          width: "100%",
          maxWidth: "840px",
          maxHeight: "90vh",
          overflowY: "auto",
          background: "#111827",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "16px",
          padding: "24px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
          position: "relative"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Title and Prominent Price */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "18px", gap: "16px", flexWrap: "wrap" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              {isEditingName ? (
                <form onSubmit={handleSaveName} style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <input
                    type="text"
                    required
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    className="input-field"
                    style={{ fontSize: "1.1rem", fontWeight: 700, padding: "4px 8px", minWidth: "220px" }}
                    autoFocus
                  />
                  <button
                    type="submit"
                    disabled={savingName || !nameInput.trim()}
                    className="btn-success"
                    style={{ padding: "5px 10px", fontSize: "0.75rem" }}
                    title="Save item name"
                  >
                    {savingName ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <Check size={14} />}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setNameInput(details?.item.canonical_name || "");
                      setIsEditingName(false);
                    }}
                    className="btn-secondary"
                    style={{ padding: "5px 8px", fontSize: "0.75rem" }}
                    title="Cancel"
                  >
                    <X size={14} />
                  </button>
                </form>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#F3F4F6", margin: 0 }}>
                    {details?.item.canonical_name || "Item Details"}
                  </h2>
                  <button
                    onClick={() => {
                      setNameInput(details?.item.canonical_name || "");
                      setIsEditingName(true);
                    }}
                    style={{
                      background: "rgba(255, 255, 255, 0.05)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "6px",
                      padding: "3px 8px",
                      color: "#9CA3AF",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "0.75rem",
                      transition: "all 0.15s ease"
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "#F3F4F6";
                      e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "#9CA3AF";
                      e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)";
                    }}
                    title="Rename canonical item"
                  >
                    <Edit2 size={12} />
                    <span>Rename</span>
                  </button>
                </div>
              )}
              {details?.item.category && (
                <span className="badge badge-emerald" style={{ fontSize: "0.75rem" }}>
                  {details.item.category}
                </span>
              )}
              {details?.item.is_grocery === false && (
                <span className="badge badge-amber" style={{ fontSize: "0.75rem" }}>
                  Non-Grocery
                </span>
              )}
            </div>
            <p style={{ fontSize: "0.8rem", color: "#9CA3AF", margin: "4px 0 0 0" }}>
              Canonical ID: #{itemId} • Standard Unit: {details?.item.standard_unit || "count"}
              {details?.item.preferred_store && ` • Preferred Store: ${details.item.preferred_store}`}
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            {/* Price badge */}
            <div
              style={{
                background: "rgba(16, 185, 129, 0.12)",
                border: "1px solid rgba(16, 185, 129, 0.35)",
                borderRadius: "10px",
                padding: "6px 14px",
                textAlign: "right"
              }}
            >
              <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
                <span style={{ fontSize: "1.45rem", fontWeight: 700, color: "#34D399" }}>
                  {formatPriceAndUnit(displayPrice, details?.item.standard_unit).priceText}
                </span>
                {formatPriceAndUnit(displayPrice, details?.item.standard_unit).unitText && (
                  <span style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>
                    {formatPriceAndUnit(displayPrice, details?.item.standard_unit).unitText}
                  </span>
                )}
              </div>
              <div style={{ fontSize: "0.7rem", color: "#9CA3AF" }}>
                {details?.item.default_unit_price != null
                  ? "Standard Price"
                  : displayPrice != null
                  ? "Last Recorded Price"
                  : "Price Not Configured"}
              </div>
            </div>

            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "#9CA3AF",
                cursor: "pointer",
                padding: "4px"
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: "50px", textAlign: "center", color: "#9CA3AF" }}>
            Loading item metrics and purchase history...
          </div>
        ) : error ? (
          <div style={{ padding: "30px", textAlign: "center", color: "#EF4444" }}>
            {error}
          </div>
        ) : details ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Top Cards: Pricing & Profile + Consumption Rhythm */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              
              {/* Card 1: Pricing & Product Profile */}
              <div
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "12px",
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <DollarSign size={18} color="#10B981" />
                      <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#F3F4F6", margin: 0 }}>
                        Pricing & Unit Profile
                      </h4>
                    </div>

                    {!isEditingPrice && (
                      <button
                        onClick={() => {
                          const u = (details.item.standard_unit || "").toLowerCase();
                          const isGrams = u === "g" || u === "gm" || u === "gram" || u === "grams";
                          setPriceInput(displayPrice != null ? (isGrams ? (displayPrice * 100).toFixed(2) : displayPrice.toFixed(2)) : "");
                          setIsEditingPrice(true);
                        }}
                        className="btn-secondary"
                        style={{ padding: "4px 8px", fontSize: "0.72rem", gap: "4px", borderRadius: "6px" }}
                        title="Edit benchmark unit price"
                      >
                        <Edit2 size={12} />
                        <span>Edit Price</span>
                      </button>
                    )}
                  </div>

                  {isEditingPrice ? (
                    <form onSubmit={handleSavePrice} style={{ display: "flex", gap: "6px", alignItems: "center", marginBottom: "10px" }}>
                      <span style={{ color: "#10B981", fontWeight: 700, fontSize: "1.1rem" }}>$</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        required
                        placeholder="3.99"
                        value={priceInput}
                        onChange={(e) => setPriceInput(e.target.value)}
                        className="input-field"
                        style={{ width: "90px", padding: "4px 8px", fontSize: "0.85rem" }}
                        autoFocus
                      />
                      <span style={{ fontSize: "0.8rem", color: "#9CA3AF" }}>
                        / {((details.item.standard_unit || "").toLowerCase() === "g" || (details.item.standard_unit || "").toLowerCase() === "gm") ? "100g" : (details.item.standard_unit || "count")}
                      </span>
                      <button
                        type="submit"
                        disabled={savingPrice}
                        className="btn-success"
                        style={{ padding: "5px 10px", fontSize: "0.75rem" }}
                      >
                        <Check size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setIsEditingPrice(false)}
                        className="btn-secondary"
                        style={{ padding: "5px 8px", fontSize: "0.75rem" }}
                      >
                        <X size={14} />
                      </button>
                    </form>
                  ) : (
                    <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "10px" }}>
                      <span style={{ fontSize: "1.6rem", fontWeight: 700, color: "#10B981" }}>
                        {formatPriceAndUnit(displayPrice, details.item.standard_unit).priceText}
                      </span>
                      <span style={{ fontSize: "0.85rem", color: "#9CA3AF" }}>
                        {formatPriceAndUnit(displayPrice, details.item.standard_unit).unitText || `per ${details.item.standard_unit || "count"}`}
                      </span>
                    </div>
                  )}

                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "0.8rem", color: "#9CA3AF" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Store size={14} color="#9CA3AF" />
                      <span>Preferred Store: <strong style={{ color: "#E5E7EB" }}>{details.item.preferred_store || details.active_inventory?.store_name || details.purchase_history[0]?.store_name || "Any Store"}</strong></span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Clock size={14} color="#9CA3AF" />
                      <span>Est. Shelf Life: <strong style={{ color: "#E5E7EB" }}>{details.item.default_shelf_life_days} days</strong></span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <ShoppingBag size={14} color="#9CA3AF" />
                      <span>Type: <strong style={{ color: details.item.is_grocery !== false ? "#34D399" : "#FBBF24" }}>{details.item.is_grocery !== false ? "Grocery" : "Non-Grocery"}</strong></span>
                    </div>
                  </div>
                </div>

                {details.purchase_history.length > 0 && details.purchase_history[0].price != null && (
                  <div style={{ marginTop: "10px", paddingTop: "8px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", fontSize: "0.75rem", color: "#9CA3AF" }}>
                    Latest purchase: <strong style={{ color: "#34D399" }}>${details.purchase_history[0].price.toFixed(2)}</strong> for <strong style={{ color: "#F3F4F6" }}>{details.purchase_history[0].quantity} {details.purchase_history[0].unit}</strong> on {details.purchase_history[0].purchase_date}
                  </div>
                )}
              </div>

              {/* Card 2: Consumption Rhythm Card */}
              <div
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "12px",
                  padding: "16px"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                  <Flame size={18} color="#F59E0B" />
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#F3F4F6", margin: 0 }}>
                    Consumption Rhythm
                  </h4>
                </div>

                <div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
                    <span style={{ fontSize: "1.5rem", fontWeight: 700, color: "#F59E0B" }}>
                      {details.consumption_rhythm.daily_rate > 0
                        ? details.consumption_rhythm.daily_rate.toFixed(3)
                        : "0.00"}
                    </span>
                    <span style={{ fontSize: "0.85rem", color: "#9CA3AF" }}>
                      {details.item.standard_unit}/day
                    </span>
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "#9CA3AF", marginTop: "6px" }}>
                    <div>Burn Rate: ~{details.consumption_rhythm.burn_rate_weekly} {details.item.standard_unit}/week</div>
                    {details.consumption_rhythm.days_left !== undefined && details.consumption_rhythm.days_left !== null && (
                      <div style={{ color: "#34D399", fontWeight: 600, marginTop: "2px" }}>
                        Estimated {details.consumption_rhythm.days_left} days left (runout ~{details.consumption_rhythm.runout_date})
                      </div>
                    )}
                    {details.consumption_rhythm.avg_purchase_interval_days && (
                      <div>Purchase Cadence: every ~{details.consumption_rhythm.avg_purchase_interval_days.toFixed(0)} days</div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Past Purchase History Table */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                <Calendar size={18} color="#6366F1" />
                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#F3F4F6", margin: 0 }}>
                  Past Purchase History ({details.purchase_history.length})
                </h4>
                <span style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>Actual weight & total price paid per receipt</span>
              </div>

              {details.purchase_history.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "#6B7280", background: "rgba(255, 255, 255, 0.02)", borderRadius: "8px" }}>
                  No historical receipts recorded for this item yet.
                </div>
              ) : (
                <div style={{
                  maxHeight: "240px",
                  overflowY: "auto",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "10px",
                  background: "rgba(0, 0, 0, 0.2)"
                }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                    <thead>
                      <tr style={{ background: "rgba(255, 255, 255, 0.05)", borderBottom: "1px solid var(--border-subtle)" }}>
                        <th style={{ padding: "10px 12px", textAlign: "left", color: "#9CA3AF" }}>Date</th>
                        <th style={{ padding: "10px 12px", textAlign: "left", color: "#9CA3AF" }}>Store</th>
                        <th style={{ padding: "10px 12px", textAlign: "right", color: "#9CA3AF" }}>Actual Weight / Qty</th>
                        <th style={{ padding: "10px 12px", textAlign: "right", color: "#9CA3AF" }}>Unit Rate</th>
                        <th style={{ padding: "10px 12px", textAlign: "right", color: "#9CA3AF" }}>Actual Price Paid</th>
                        <th style={{ padding: "10px 12px", textAlign: "left", color: "#9CA3AF" }}>Receipt Label</th>
                        <th style={{ padding: "10px 12px", textAlign: "center", color: "#9CA3AF", width: "48px" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {details.purchase_history.map((p) => {
                        const actualTotal =
                          p.price != null && p.price > 0
                            ? p.price
                            : p.unit_price != null && p.unit_price > 0 && p.quantity && p.quantity > 0
                            ? p.unit_price * p.quantity
                            : displayPrice != null && displayPrice > 0
                            ? displayPrice * (p.quantity && p.quantity > 0 ? p.quantity : 1)
                            : null;

                        const isDeleting = deletingPurchaseId === p.id;

                        return (
                          <tr key={p.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                            <td style={{ padding: "10px 12px", color: "#F3F4F6", whiteSpace: "nowrap" }}>
                              {p.purchase_date}
                            </td>
                            <td style={{ padding: "10px 12px", color: "#10B981", fontWeight: 500 }}>
                              {p.store_name}
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "right" }}>
                              <span style={{ color: "#F3F4F6", fontWeight: 600, background: "rgba(255, 255, 255, 0.06)", padding: "2px 8px", borderRadius: "4px" }}>
                                {p.quantity} {p.unit}
                              </span>
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "right", color: "#9CA3AF", fontSize: "0.8rem" }}>
                              {p.unit_price != null ? `${formatPriceAndUnit(p.unit_price, p.unit).priceText} ${formatPriceAndUnit(p.unit_price, p.unit).unitText}` : "-"}
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "right" }}>
                              <span style={{ color: "#34D399", fontWeight: 700, fontSize: "0.88rem" }}>
                                {actualTotal != null ? `$${actualTotal.toFixed(2)}` : "-"}
                              </span>
                            </td>
                            <td style={{ padding: "10px 12px", color: "#6B7280", fontStyle: "italic", maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {p.raw_text || "-"}
                            </td>
                            <td style={{ padding: "10px 12px", textAlign: "center" }}>
                              <button
                                onClick={() => handleDeletePurchaseEntry(p)}
                                disabled={isDeleting}
                                title="Delete this purchase entry"
                                style={{
                                  background: "rgba(239, 68, 68, 0.1)",
                                  border: "1px solid rgba(239, 68, 68, 0.25)",
                                  color: "#EF4444",
                                  borderRadius: "6px",
                                  padding: "5px 8px",
                                  cursor: isDeleting ? "not-allowed" : "pointer",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  transition: "all 0.15s ease",
                                  opacity: isDeleting ? 0.5 : 1
                                }}
                                onMouseEnter={(e) => {
                                  if (!isDeleting) {
                                    e.currentTarget.style.background = "rgba(239, 68, 68, 0.2)";
                                    e.currentTarget.style.borderColor = "rgba(239, 68, 68, 0.5)";
                                  }
                                }}
                                onMouseLeave={(e) => {
                                  if (!isDeleting) {
                                    e.currentTarget.style.background = "rgba(239, 68, 68, 0.1)";
                                    e.currentTarget.style.borderColor = "rgba(239, 68, 68, 0.25)";
                                  }
                                }}
                              >
                                {isDeleting ? (
                                  <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                                ) : (
                                  <Trash2 size={13} />
                                )}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Registered Store Aliases & Editor */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                <Sparkles size={18} color="#A855F7" />
                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#F3F4F6", margin: 0 }}>
                  Registered Store Aliases ({details.aliases.length})
                </h4>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "12px" }}>
                {details.aliases.map((alias) => (
                  <div
                    key={alias.id}
                    style={{
                      background: "rgba(168, 85, 247, 0.15)",
                      border: "1px solid rgba(168, 85, 247, 0.3)",
                      borderRadius: "8px",
                      padding: "4px 10px",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontSize: "0.82rem",
                      color: "#E9D5FF"
                    }}
                  >
                    <span>{alias.raw_alias}</span>
                    <button
                      disabled={deletingAliasId === alias.id}
                      onClick={() => handleDeleteAlias(alias.id)}
                      title="Remove alias"
                      style={{
                        background: "transparent",
                        border: "none",
                        color: "#F87171",
                        cursor: "pointer",
                        padding: 0,
                        display: "flex",
                        alignItems: "center"
                      }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Add New Alias form */}
              <form onSubmit={handleAddAlias} style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  placeholder="Add new receipt alias (e.g. 'org whl mlk')..."
                  value={newAlias}
                  onChange={(e) => setNewAlias(e.target.value)}
                  className="input-field"
                  style={{ flex: 1, padding: "8px 12px", fontSize: "0.85rem" }}
                />
                <button
                  type="submit"
                  disabled={addingAlias || !newAlias.trim()}
                  className="btn-primary"
                  style={{
                    padding: "8px 14px",
                    fontSize: "0.82rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px"
                  }}
                >
                  <Plus size={16} />
                  <span>{addingAlias ? "Adding..." : "Add Alias"}</span>
                </button>
              </form>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
