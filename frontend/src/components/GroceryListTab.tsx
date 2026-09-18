import React, { useState, useEffect, useRef } from "react";
import {
  ShoppingCart,
  CheckSquare,
  Square,
  Plus,
  Copy,
  Store,
  Check,
  Trash2,
  X,
  Sparkles,
  Clock
} from "lucide-react";
import type { GroceryListResponse, GroceryListItem, CanonicalItem } from "../types";
import { ItemDetailsModal } from "./ItemDetailsModal";
import {
  toggleGroceryListItem,
  deleteGroceryListItem,
  addManualGroceryItem,
  exportGroceryListText,
  fetchCanonicalItems
} from "../api/client";

interface GroceryListTabProps {
  groceryData: GroceryListResponse | null;
  householdId: number;
  onRefresh: () => void;
}

export const GroceryListTab: React.FC<GroceryListTabProps> = ({
  groceryData,
  householdId,
  onRefresh,
}) => {
  const [groupBy, setGroupBy] = useState<"store" | "category">("store");
  const [copied, setCopied] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);

  // Manual Add Modal & Auto-suggestions state
  const [showModal, setShowModal] = useState(false);
  const [catalogItems, setCatalogItems] = useState<CanonicalItem[]>([]);
  const [itemName, setItemName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unit, setUnit] = useState("count");
  const [category, setCategory] = useState("Produce");
  const [targetStore, setTargetStore] = useState("Any Store");
  const [suggestions, setSuggestions] = useState<CanonicalItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const suggestionsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchCanonicalItems()
      .then((items) => {
        setCatalogItems(items.filter((i) => i.is_grocery !== false && i.category !== "Non-Grocery"));
      })
      .catch((err) => console.error("Failed to load catalog for suggestions", err));
  }, []);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleToggle = async (itemId: number, currentChecked: boolean) => {
    try {
      await toggleGroceryListItem(itemId, !currentChecked);
      onRefresh();
    } catch (err) {
      console.error("Failed to toggle item", err);
    }
  };

  const handleDeleteItem = async (e: React.MouseEvent, itemId: number) => {
    e.stopPropagation();
    try {
      setDeletingId(itemId);
      await deleteGroceryListItem(itemId);
      onRefresh();
    } catch (err) {
      console.error("Failed to delete grocery item", err);
      alert("Failed to remove item from grocery list.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleExportText = async () => {
    try {
      const text = await exportGroceryListText(householdId);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error("Export failed", err);
      alert("Failed to copy grocery list to clipboard");
    }
  };

  const handleItemNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setItemName(val);
    if (val.trim().length > 0) {
      const filtered = catalogItems.filter((i) =>
        i.canonical_name.toLowerCase().includes(val.toLowerCase().trim())
      );
      setSuggestions(filtered.slice(0, 6));
      setShowSuggestions(filtered.length > 0);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const selectSuggestion = (item: CanonicalItem) => {
    setItemName(item.canonical_name);
    setCategory(item.category || "Produce");
    setUnit(item.standard_unit || "count");
    setTargetStore(item.preferred_store || "Any Store");
    setShowSuggestions(false);
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemName.trim()) return;

    try {
      setSubmitting(true);
      await addManualGroceryItem(householdId, {
        item_name: itemName.trim(),
        quantity: parseFloat(quantity) || 1,
        unit: unit.trim() || "count",
        category,
        target_store: targetStore
      });
      setShowModal(false);
      setItemName("");
      setQuantity("1");
      setUnit("count");
      setCategory("Produce");
      setTargetStore("Any Store");
      onRefresh();
    } catch (err) {
      console.error("Failed to add manual item", err);
      alert("Failed to add item to grocery list.");
    } finally {
      setSubmitting(false);
    }
  };

  const groups: Record<string, GroceryListItem[]> =
    groupBy === "store"
      ? groceryData?.items_by_store || {}
      : groceryData?.items_by_category || {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Header controls */}
      <div className="glass-panel" style={{ padding: "16px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(168, 85, 247, 0.2))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}>
              <ShoppingCart size={20} color="#818CF8" />
            </div>
            <div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#F3F4F6", margin: 0 }}>
                Sunday Grocery Shopping Plan
              </h3>
              <p style={{ fontSize: "0.8rem", color: "#9CA3AF", margin: "2px 0 0 0" }}>
                Autonomous weekly restock predictions based on your purchase history
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {/* View Mode Toggle */}
            <div style={{ display: "flex", background: "rgba(255, 255, 255, 0.05)", borderRadius: "8px", padding: "2px" }}>
              <button
                onClick={() => setGroupBy("store")}
                style={{
                  background: groupBy === "store" ? "rgba(99, 102, 241, 0.3)" : "transparent",
                  color: groupBy === "store" ? "#fff" : "#9CA3AF",
                  border: "none",
                  borderRadius: "6px",
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                By Store
              </button>
              <button
                onClick={() => setGroupBy("category")}
                style={{
                  background: groupBy === "category" ? "rgba(99, 102, 241, 0.3)" : "transparent",
                  color: groupBy === "category" ? "#fff" : "#9CA3AF",
                  border: "none",
                  borderRadius: "6px",
                  padding: "6px 12px",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                By Category
              </button>
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="btn-success"
              style={{ padding: "7px 14px", fontSize: "0.82rem", display: "flex", alignItems: "center", gap: "6px" }}
            >
              <Plus size={16} />
              <span>Add Item</span>
            </button>

            <button
              onClick={handleExportText}
              className="btn-primary"
              style={{ padding: "7px 14px", fontSize: "0.82rem", display: "flex", alignItems: "center", gap: "6px" }}
            >
              {copied ? <Check size={16} color="#10B981" /> : <Copy size={16} />}
              <span>{copied ? "Copied List!" : "Export List"}</span>
            </button>
          </div>
        </div>

        {/* Summary metric bar */}
        {groceryData && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "24px",
            marginTop: "16px",
            paddingTop: "14px",
            borderTop: "1px solid var(--border-subtle)"
          }}>
            <div>
              <span style={{ fontSize: "0.75rem", color: "#6B7280" }}>Recommended Items</span>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F3F4F6" }}>
                {groceryData.total_items}
              </div>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "#6B7280" }}>Estimated Trip Cost</span>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#10B981" }}>
                ${groceryData.total_estimated_cost.toFixed(2)}
              </div>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "#6B7280" }}>Planning Date</span>
              <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "#9CA3AF" }}>
                {groceryData.generated_date}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Item Groups (By Store or Category) */}
      {Object.keys(groups).length === 0 ? (
        <div className="glass-panel" style={{ padding: "50px", textAlign: "center", color: "#6B7280" }}>
          No items on your grocery list for this period. Click <strong>+ Add Item</strong> to add items manually.
        </div>
      ) : (
        Object.entries(groups).map(([groupTitle, items]) => (
          <div key={groupTitle} className="glass-panel" style={{ padding: "20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
              <h4 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#F3F4F6", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                <Store size={18} color="#10B981" />
                <span>{groupTitle}</span>
                <span className="badge badge-emerald" style={{ fontSize: "0.75rem" }}>
                  {items.length} item{items.length > 1 ? "s" : ""}
                </span>
              </h4>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {items.map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleToggle(item.id, item.is_checked)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 14px",
                    borderRadius: "10px",
                    background: item.is_checked ? "rgba(255, 255, 255, 0.02)" : "rgba(255, 255, 255, 0.05)",
                    border: "1px solid var(--border-subtle)",
                    cursor: "pointer",
                    opacity: item.is_checked ? 0.5 : 1,
                    transition: "all 0.2s ease"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "12px", flex: 1 }}>
                    {item.is_checked ? (
                      <CheckSquare size={20} color="#10B981" />
                    ) : (
                      <Square size={20} color="#6B7280" />
                    )}
                    <div>
                      <div style={{
                        fontSize: "0.95rem",
                        fontWeight: 600,
                        color: item.is_checked ? "#9CA3AF" : "#F3F4F6",
                        textDecoration: item.is_checked ? "line-through" : "none"
                      }}>
                        {item.item_name}
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "#9CA3AF", display: "flex", alignItems: "center", gap: "8px", marginTop: "2px", flexWrap: "wrap" }}>
                        <span style={{ color: "#10B981", fontWeight: 600 }}>
                          🏪 {item.target_store || "Any Store"}
                        </span>
                        <span>• {item.category}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                    <div style={{ textAlign: "right" }}>
                      <div>
                        <span style={{ fontSize: "1rem", fontWeight: 700, color: "#F3F4F6" }}>
                          {item.recommended_quantity}
                        </span>{" "}
                        <span style={{ fontSize: "0.8rem", color: "#9CA3AF" }}>
                          {item.unit}
                        </span>
                      </div>
                      {item.estimated_cost !== null && item.estimated_cost !== undefined && (
                        <div style={{ fontSize: "0.78rem", color: "#34D399", fontWeight: 600, marginTop: "2px" }}>
                          ~${item.estimated_cost.toFixed(2)}
                        </div>
                      )}
                    </div>

                    <span
                      className={`badge ${
                        item.priority_reason === "CRITICAL_DEPLETION"
                          ? "badge-rose"
                          : item.priority_reason === "CONFIRMED_DEPLETED"
                          ? "badge-amber"
                          : item.priority_reason === "SCHEDULED_PERIODIC"
                          ? "badge-indigo"
                          : item.priority_reason === "MANUAL"
                          ? "badge-emerald"
                          : "badge-cyan"
                      }`}
                      style={{ fontSize: "0.68rem" }}
                    >
                      {item.priority_reason.replace("_", " ")}
                    </span>

                    {/* View Details & Purchase History */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedItemId(item.canonical_item_id ?? null);
                      }}
                      title="View Purchase History & Rhythm"
                      style={{
                        background: "rgba(99, 102, 241, 0.15)",
                        border: "1px solid rgba(99, 102, 241, 0.3)",
                        borderRadius: "6px",
                        color: "#818CF8",
                        padding: "5px 9px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        fontSize: "0.72rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        transition: "all 0.2s ease"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "rgba(99, 102, 241, 0.3)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "rgba(99, 102, 241, 0.15)";
                      }}
                    >
                      <Clock size={13} />
                      <span>Details</span>
                    </button>

                    {/* Delete / Remove item button */}
                    <button
                      disabled={deletingId === item.id}
                      onClick={(e) => handleDeleteItem(e, item.id)}
                      title="Remove from grocery list"
                      style={{
                        background: "rgba(239, 68, 68, 0.15)",
                        border: "1px solid rgba(239, 68, 68, 0.3)",
                        borderRadius: "6px",
                        color: "#F87171",
                        padding: "6px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                        transition: "all 0.2s ease"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "rgba(239, 68, 68, 0.3)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)";
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}

      {/* Add Item Modal with Live Auto-Suggestions */}
      {showModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px"
          }}
          onClick={() => setShowModal(false)}
        >
          <div
            className="glass-panel"
            style={{
              width: "100%",
              maxWidth: "500px",
              background: "#111827",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
              position: "relative"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Plus size={20} color="#10B981" />
                <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#F3F4F6", margin: 0 }}>
                  Add Item to Grocery List
                </h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
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

            <p style={{ fontSize: "0.82rem", color: "#9CA3AF", marginBottom: "16px", lineHeight: 1.4 }}>
              Type an item name to see live suggestions from your grocery catalog and purchase history.
            </p>

            <form onSubmit={handleAddSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {/* Item Name with Auto-suggestions */}
              <div style={{ position: "relative" }} ref={suggestionsRef}>
                <label style={{ fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "4px", display: "block" }}>
                  Item Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Whole Milk, Avocados, Basmati Rice..."
                  value={itemName}
                  onChange={handleItemNameChange}
                  autoFocus
                  required
                  style={{
                    width: "100%",
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "8px",
                    padding: "10px 12px",
                    color: "#F3F4F6",
                    fontSize: "0.9rem",
                    outline: "none"
                  }}
                />

                {/* Suggestions Dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                  <div
                    style={{
                      position: "absolute",
                      top: "100%",
                      left: 0,
                      right: 0,
                      marginTop: "4px",
                      background: "#1F2937",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "8px",
                      overflow: "hidden",
                      zIndex: 1010,
                      boxShadow: "0 10px 25px rgba(0, 0, 0, 0.5)"
                    }}
                  >
                    <div style={{ padding: "6px 10px", fontSize: "0.72rem", color: "#9CA3AF", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", display: "flex", alignItems: "center", gap: "4px" }}>
                      <Sparkles size={12} color="#10B981" />
                      <span>Suggested from Catalog & History:</span>
                    </div>
                    {suggestions.map((sug) => (
                      <div
                        key={sug.id}
                        onClick={() => selectSuggestion(sug)}
                        style={{
                          padding: "8px 12px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          cursor: "pointer",
                          borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                          transition: "background 0.15s ease"
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "rgba(16, 185, 129, 0.15)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "transparent";
                        }}
                      >
                        <span style={{ fontSize: "0.88rem", fontWeight: 500, color: "#F3F4F6" }}>
                          {sug.canonical_name}
                        </span>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ fontSize: "0.72rem", color: "#9CA3AF" }}>
                            {sug.category}
                          </span>
                          {sug.preferred_store && (
                            <span style={{ fontSize: "0.72rem", color: "#10B981" }}>
                              • {sug.preferred_store}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Quantity and Unit row */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "4px", display: "block" }}>
                    Quantity
                  </label>
                  <input
                    type="number"
                    step="any"
                    min="0.1"
                    placeholder="1"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      background: "rgba(255, 255, 255, 0.05)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "8px",
                      padding: "10px 12px",
                      color: "#F3F4F6",
                      fontSize: "0.9rem",
                      outline: "none"
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "4px", display: "block" }}>
                    Unit
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. count, lb, oz, gallon"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    required
                    style={{
                      width: "100%",
                      background: "rgba(255, 255, 255, 0.05)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "8px",
                      padding: "10px 12px",
                      color: "#F3F4F6",
                      fontSize: "0.9rem",
                      outline: "none"
                    }}
                  />
                </div>
              </div>

              {/* Category & Store row */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "4px", display: "block" }}>
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#1F2937",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "8px",
                      padding: "10px 12px",
                      color: "#F3F4F6",
                      fontSize: "0.85rem",
                      outline: "none"
                    }}
                  >
                    <option value="Produce">Produce</option>
                    <option value="Dairy">Dairy</option>
                    <option value="Bakery">Bakery</option>
                    <option value="Grains / Flours">Grains / Flours</option>
                    <option value="Meat & Seafood">Meat & Seafood</option>
                    <option value="Pantry">Pantry</option>
                    <option value="Snacks">Snacks</option>
                    <option value="General">General</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "4px", display: "block" }}>
                    Target Store
                  </label>
                  <select
                    value={targetStore}
                    onChange={(e) => setTargetStore(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#1F2937",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "8px",
                      padding: "10px 12px",
                      color: "#F3F4F6",
                      fontSize: "0.85rem",
                      outline: "none"
                    }}
                  >
                    <option value="Any Store">Any Store</option>
                    <option value="Costco Wholesale">Costco Wholesale</option>
                    <option value="Trader Joe's">Trader Joe's</option>
                    <option value="New India Bazar">New India Bazar</option>
                    <option value="Whole Foods">Whole Foods</option>
                    <option value="Grocery Store">Grocery Store</option>
                  </select>
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    background: "rgba(255, 255, 255, 0.06)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "8px",
                    padding: "8px 16px",
                    color: "#9CA3AF",
                    fontSize: "0.85rem",
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-success"
                  style={{
                    padding: "8px 20px",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px"
                  }}
                >
                  <Plus size={16} />
                  <span>{submitting ? "Adding..." : "Add to List"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Item Details & Purchase History Modal */}
      {selectedItemId !== null && (
        <ItemDetailsModal
          itemId={selectedItemId}
          householdId={householdId}
          onClose={() => setSelectedItemId(null)}
          onItemUpdated={onRefresh}
        />
      )}
    </div>
  );
};
