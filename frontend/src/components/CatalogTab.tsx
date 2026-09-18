import React, { useState, useEffect } from "react";
import {
  Tags,
  Search,
  Plus,
  Sparkles,
  PackageCheck,
  Check,
  X,
  Layers,
  HelpCircle
} from "lucide-react";
import type { CanonicalItem } from "../types";
import { fetchCanonicalItems, addAliasToItem, createCanonicalItem } from "../api/client";

export const CatalogTab: React.FC = () => {
  const [items, setItems] = useState<CanonicalItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("All");

  // Adding alias inline
  const [activeAddAliasId, setActiveAddAliasId] = useState<number | null>(null);
  const [newAliasText, setNewAliasText] = useState<string>("");
  const [submittingAlias, setSubmittingAlias] = useState<boolean>(false);

  // New item modal
  const [showNewItemModal, setShowNewItemModal] = useState<boolean>(false);
  const [newItemName, setNewItemName] = useState<string>("");
  const [newItemCategory, setNewItemCategory] = useState<string>("Produce");
  const [newItemUnit, setNewItemUnit] = useState<string>("count");
  const [newItemShelfLife, setNewItemShelfLife] = useState<number>(7);
  const [newItemIsBulk, setNewItemIsBulk] = useState<boolean>(false);
  const [creatingItem, setCreatingItem] = useState<boolean>(false);

  const loadItems = async () => {
    try {
      setLoading(true);
      const data = await fetchCanonicalItems();
      const normalized = data.map((it) => {
        if (it.is_grocery === false || (it.category && it.category.toLowerCase().includes("non-grocery"))) {
          return { ...it, category: "Non-Grocery" };
        }
        return it;
      });
      setItems(normalized);
    } catch (err) {
      console.error("Failed to load catalog items", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);

  const categories = ["All", ...Array.from(new Set(items.map((it) => it.category))).sort()];

  const filteredItems = items.filter((item) => {
    const matchesCat = selectedCategory === "All" || item.category.toLowerCase() === selectedCategory.toLowerCase();
    if (!matchesCat) return false;

    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    const matchesName = item.canonical_name.toLowerCase().includes(q);
    const matchesAlias = item.aliases?.some((a) => a.raw_alias.toLowerCase().includes(q));
    const matchesCategory = item.category.toLowerCase().includes(q);

    return matchesName || matchesAlias || matchesCategory;
  });

  const totalAliases = items.reduce((acc, it) => acc + (it.aliases?.length || 0), 0);

  const handleAddAlias = async (itemId: number) => {
    if (!newAliasText.trim()) return;
    try {
      setSubmittingAlias(true);
      const added = await addAliasToItem(itemId, newAliasText.trim());
      setItems((prev) =>
        prev.map((it) => {
          if (it.id === itemId) {
            return {
              ...it,
              aliases: [...(it.aliases || []), added]
            };
          }
          return it;
        })
      );
      setNewAliasText("");
      setActiveAddAliasId(null);
    } catch (err: any) {
      alert(err.message || "Failed to add alias");
    } finally {
      setSubmittingAlias(false);
    }
  };

  const handleCreateItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim()) return;
    try {
      setCreatingItem(true);
      const created = await createCanonicalItem({
        canonical_name: newItemName.trim(),
        category: newItemCategory,
        standard_unit: newItemUnit.trim() || "count",
        default_shelf_life_days: Number(newItemShelfLife) || 7,
        is_bulk: newItemIsBulk
      });
      setItems((prev) => [...prev, created].sort((a, b) => a.canonical_name.localeCompare(b.canonical_name)));
      setShowNewItemModal(false);
      setNewItemName("");
      setNewItemShelfLife(7);
      setNewItemIsBulk(false);
    } catch (err: any) {
      alert(err.message || "Failed to create item");
    } finally {
      setCreatingItem(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Header Banner */}
      <div className="glass-panel" style={{ padding: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div>
            <h3 style={{ fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px", color: "#F3F4F6" }}>
              <Tags size={24} color="#6366F1" />
              <span>Canonical Food Catalog & Known Aliases</span>
            </h3>
            <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "6px", maxWidth: "780px", lineHeight: 1.5 }}>
              The Entity Resolution engine automatically cleans and resolves raw store receipt line items
              (e.g., <em>"KIRKLAND WHOLE MILK 1 GAL"</em> or <em>"ROMA TOM"</em>) into these canonical items.
              Every registered alias provides instant 100% confidence matching.
            </p>
          </div>

          <button
            onClick={() => setShowNewItemModal(true)}
            className="btn-primary"
            style={{ display: "flex", alignItems: "center", gap: "8px" }}
          >
            <Plus size={18} />
            <span>Add Canonical Item</span>
          </button>
        </div>

        {/* Stats Row */}
        <div style={{ display: "flex", gap: "24px", marginTop: "20px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "rgba(99, 102, 241, 0.15)",
              color: "#818CF8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}>
              <PackageCheck size={20} />
            </div>
            <div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F3F4F6" }}>{items.length}</div>
              <div style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>Tracked Canonical Items</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "rgba(16, 185, 129, 0.15)",
              color: "#10B981",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}>
              <Sparkles size={20} />
            </div>
            <div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F3F4F6" }}>{totalAliases}</div>
              <div style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>Mapped Store Aliases</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "rgba(245, 158, 11, 0.15)",
              color: "#F59E0B",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}>
              <Layers size={20} />
            </div>
            <div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F3F4F6" }}>{categories.length - 1}</div>
              <div style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>Food Categories</div>
            </div>
          </div>
        </div>
      </div>

      {/* Controls Bar: Search & Category Pills */}
      <div className="glass-panel" style={{ padding: "16px 20px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          {/* Search Box */}
          <div style={{ position: "relative" }}>
            <Search
              size={18}
              color="#9CA3AF"
              style={{ position: "absolute", left: "14px", top: "50%", transform: "translateY(-50%)" }}
            />
            <input
              type="text"
              placeholder="Search by canonical food name, category, or any store alias (e.g. 'milk', 'trader', 'kirkland')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field"
              style={{ paddingLeft: "42px", width: "100%" }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  right: "14px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#9CA3AF",
                  cursor: "pointer"
                }}
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Category Pills */}
          <div style={{ display: "flex", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "20px",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  border: "none",
                  transition: "all 0.2s ease",
                  whiteSpace: "nowrap",
                  background:
                    selectedCategory === cat
                      ? "linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)"
                      : "rgba(255, 255, 255, 0.05)",
                  color: selectedCategory === cat ? "#FFFFFF" : "#9CA3AF",
                  boxShadow: selectedCategory === cat ? "0 0 12px rgba(99, 102, 241, 0.4)" : "none"
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Item List Grid */}
      {loading ? (
        <div className="glass-panel" style={{ padding: "60px 20px", textAlign: "center" }}>
          <div style={{ color: "#818CF8", fontSize: "1rem" }}>Loading canonical catalog...</div>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="glass-panel" style={{ padding: "60px 20px", textAlign: "center" }}>
          <HelpCircle size={36} color="#9CA3AF" style={{ margin: "0 auto 12px" }} />
          <h4 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#F3F4F6" }}>No Items Found</h4>
          <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "4px" }}>
            No canonical items or aliases match "{searchQuery}" in {selectedCategory}.
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "16px" }}>
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="glass-panel"
              style={{
                padding: "20px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: "14px",
                borderRadius: "16px",
                border: "1px solid rgba(255, 255, 255, 0.08)"
              }}
            >
              {/* Item Header */}
              <div>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px" }}>
                  <div>
                    <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#F3F4F6" }}>
                      {item.canonical_name}
                    </h4>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "6px" }}>
                      <span className="badge badge-blue" style={{ fontSize: "0.7rem" }}>
                        {item.category}
                      </span>
                      {item.is_bulk && (
                        <span className="badge badge-purple" style={{ fontSize: "0.7rem" }}>
                          Bulk Storage
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ textAlign: "right", fontSize: "0.75rem", color: "#9CA3AF" }}>
                    <div>Unit: <strong style={{ color: "#E5E7EB" }}>{item.standard_unit}</strong></div>
                    <div style={{ marginTop: "2px" }}>Life: <strong style={{ color: "#E5E7EB" }}>{item.default_shelf_life_days}d</strong></div>
                  </div>
                </div>

                {/* Aliases Section */}
                <div style={{ marginTop: "14px" }}>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
                    Recognized Aliases ({item.aliases?.length || 0}):
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    {item.aliases && item.aliases.length > 0 ? (
                      item.aliases.map((alias) => (
                        <span
                          key={alias.id}
                          style={{
                            background: "rgba(255, 255, 255, 0.06)",
                            border: "1px solid rgba(255, 255, 255, 0.12)",
                            borderRadius: "6px",
                            padding: "3px 8px",
                            fontSize: "0.75rem",
                            color: "#D1D5DB",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px"
                          }}
                          title={`Source: ${alias.source} | Confidence: ${alias.match_confidence}`}
                        >
                          <span>{alias.raw_alias}</span>
                        </span>
                      ))
                    ) : (
                      <span style={{ fontSize: "0.75rem", color: "#6B7280", fontStyle: "italic" }}>
                        No aliases registered yet
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Add Alias Inline Form */}
              <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "12px" }}>
                {activeAddAliasId === item.id ? (
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <input
                      type="text"
                      placeholder="e.g. organic whole milk"
                      value={newAliasText}
                      onChange={(e) => setNewAliasText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleAddAlias(item.id);
                        if (e.key === "Escape") setActiveAddAliasId(null);
                      }}
                      className="input-field"
                      style={{ flex: 1, padding: "6px 10px", fontSize: "0.8rem" }}
                      autoFocus
                    />
                    <button
                      disabled={submittingAlias}
                      onClick={() => handleAddAlias(item.id)}
                      className="btn-success"
                      style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => {
                        setActiveAddAliasId(null);
                        setNewAliasText("");
                      }}
                      style={{
                        background: "rgba(255, 255, 255, 0.1)",
                        border: "none",
                        color: "#9CA3AF",
                        borderRadius: "8px",
                        padding: "6px 10px",
                        cursor: "pointer"
                      }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setActiveAddAliasId(item.id);
                      setNewAliasText("");
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "#818CF8",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                      padding: 0
                    }}
                  >
                    <Plus size={14} />
                    <span>Map New Store Alias</span>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Add New Canonical Item */}
      {showNewItemModal && (
        <div style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0, 0, 0, 0.75)",
          backdropFilter: "blur(6px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          padding: "20px"
        }}>
          <div className="glass-panel" style={{ width: "100%", maxWidth: "480px", padding: "28px", borderRadius: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F3F4F6", display: "flex", alignItems: "center", gap: "8px" }}>
                <Plus size={20} color="#6366F1" />
                <span>Create Canonical Item</span>
              </h3>
              <button
                onClick={() => setShowNewItemModal(false)}
                style={{ background: "transparent", border: "none", color: "#9CA3AF", cursor: "pointer" }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateItem} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "6px" }}>
                  Canonical Item Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Organic Rolled Oats"
                  value={newItemName}
                  onChange={(e) => setNewItemName(e.target.value)}
                  className="input-field"
                  style={{ width: "100%" }}
                  required
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "6px" }}>
                    Category
                  </label>
                  <select
                    value={newItemCategory}
                    onChange={(e) => setNewItemCategory(e.target.value)}
                    className="input-field"
                    style={{ width: "100%" }}
                  >
                    {categories.filter((c) => c !== "All").map((cat) => (
                      <option key={cat} value={cat} style={{ background: "#1F2937", color: "#F3F4F6" }}>
                        {cat}
                      </option>
                    ))}
                    <option value="Snacks" style={{ background: "#1F2937", color: "#F3F4F6" }}>Snacks</option>
                    <option value="Beverages" style={{ background: "#1F2937", color: "#F3F4F6" }}>Beverages</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "6px" }}>
                    Standard Unit
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. lb, count, oz"
                    value={newItemUnit}
                    onChange={(e) => setNewItemUnit(e.target.value)}
                    className="input-field"
                    style={{ width: "100%" }}
                    required
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", alignItems: "center" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#9CA3AF", marginBottom: "6px" }}>
                    Default Shelf Life (Days)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={newItemShelfLife}
                    onChange={(e) => setNewItemShelfLife(Number(e.target.value))}
                    className="input-field"
                    style={{ width: "100%" }}
                  />
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "18px" }}>
                  <input
                    type="checkbox"
                    id="bulkCheck"
                    checked={newItemIsBulk}
                    onChange={(e) => setNewItemIsBulk(e.target.checked)}
                    style={{ width: "18px", height: "18px", accentColor: "#6366F1", cursor: "pointer" }}
                  />
                  <label htmlFor="bulkCheck" style={{ fontSize: "0.85rem", color: "#D1D5DB", cursor: "pointer" }}>
                    Bulk Storage (180d lookback)
                  </label>
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setShowNewItemModal(false)}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: "10px",
                    background: "rgba(255, 255, 255, 0.08)",
                    border: "none",
                    color: "#D1D5DB",
                    fontWeight: 600,
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingItem}
                  className="btn-primary"
                  style={{ flex: 1, justifyContent: "center" }}
                >
                  {creatingItem ? "Creating..." : "Create Item"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
