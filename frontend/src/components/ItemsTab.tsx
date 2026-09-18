import React, { useState, useEffect, useMemo } from "react";
import {
  Search,
  Package,
  Activity,
  Tags,
  Plus,
  RefreshCw,
  ShoppingBag,
  Filter,
  AlertTriangle,
  ChevronRight,
  Store,
  X,
  DollarSign,
  Clock
} from "lucide-react";
import type { CanonicalItem, InventoryItem, ItemVelocity } from "../types";
import {
  fetchCanonicalItems,
  fetchActiveInventory,
  fetchVelocityReport,
  createCanonicalItem
} from "../api/client";
import { ItemDetailsModal } from "./ItemDetailsModal";

interface ItemsTabProps {
  householdId: number;
}

export const ItemsTab: React.FC<ItemsTabProps> = ({ householdId }) => {
  const [items, setItems] = useState<CanonicalItem[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [velocities, setVelocities] = useState<ItemVelocity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [itemTypeFilter, setItemTypeFilter] = useState<"ALL" | "GROCERY" | "NON_GROCERY">("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("All");

  // Selection for details modal
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);

  // New Item Modal
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const [newItemCategory, setNewItemCategory] = useState("Pantry");
  const [newItemUnit, setNewItemUnit] = useState("count");
  const [newItemShelfLife, setNewItemShelfLife] = useState(14);
  const [newItemStore, setNewItemStore] = useState("");
  const [newItemPrice, setNewItemPrice] = useState<string>("");
  const [newItemIsGrocery, setNewItemIsGrocery] = useState(true);
  const [addingItem, setAddingItem] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [itemsData, invData, velData] = await Promise.all([
        fetchCanonicalItems(),
        fetchActiveInventory(householdId).catch(() => []),
        fetchVelocityReport(householdId).catch(() => ({ household_id: householdId, items: [] }))
      ]);

      setItems(itemsData);
      setInventory(invData);
      setVelocities(velData.items || []);
    } catch (err) {
      console.error("Error loading items tab data:", err);
      setError("Failed to load items. Please try refreshing.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [householdId]);

  // Inventory Map by canonical_item_id
  const inventoryMap = useMemo(() => {
    const map = new Map<number, InventoryItem>();
    inventory.forEach((inv) => {
      map.set(inv.canonical_item_id, inv);
    });
    return map;
  }, [inventory]);

  // Velocity Map by canonical_item_id
  const velocityMap = useMemo(() => {
    const map = new Map<number, ItemVelocity>();
    velocities.forEach((vel) => {
      map.set(vel.canonical_item_id, vel);
    });
    return map;
  }, [velocities]);

  // Extract unique categories
  const categories = useMemo(() => {
    const set = new Set<string>();
    items.forEach((item) => {
      if (item.category) set.add(item.category);
    });
    return ["All", ...Array.from(set).sort()];
  }, [items]);

  // Metrics (clean catalog metrics with no active/pantry stock counters)
  const metrics = useMemo(() => {
    const total = items.length;
    const withVelocity = items.filter((it) => {
      const vel = velocityMap.get(it.id);
      return vel && vel.daily_velocity > 0;
    }).length;
    const nonGrocery = items.filter(
      (it) => it.is_grocery === false || it.category.toLowerCase() === "non-grocery"
    ).length;
    const grocery = total - nonGrocery;

    return { total, withVelocity, nonGrocery, grocery };
  }, [items, velocityMap]);

  // Filtered Items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Search matching
      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !query ||
        item.canonical_name.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query) ||
        (item.preferred_store && item.preferred_store.toLowerCase().includes(query)) ||
        (item.aliases && item.aliases.some((a) => a.raw_alias.toLowerCase().includes(query)));

      if (!matchesSearch) return false;

      // Item type filter (All / Grocery / Non-Grocery)
      const isNonGrocery = item.is_grocery === false || item.category.toLowerCase() === "non-grocery";
      if (itemTypeFilter === "GROCERY" && isNonGrocery) return false;
      if (itemTypeFilter === "NON_GROCERY" && !isNonGrocery) return false;

      // Category filter
      if (selectedCategory !== "All" && item.category !== selectedCategory) {
        return false;
      }

      return true;
    });
  }, [items, searchQuery, itemTypeFilter, selectedCategory]);

  const handleCreateItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim()) return;

    try {
      setAddingItem(true);
      await createCanonicalItem({
        canonical_name: newItemName.trim(),
        category: newItemCategory,
        standard_unit: newItemUnit.trim() || "count",
        default_shelf_life_days: Number(newItemShelfLife) || 14,
        preferred_store: newItemStore.trim() || undefined,
        default_unit_price: newItemPrice ? parseFloat(newItemPrice) : undefined,
        is_grocery: newItemIsGrocery
      });

      setIsAddModalOpen(false);
      setNewItemName("");
      setNewItemStore("");
      setNewItemPrice("");
      setNewItemIsGrocery(true);
      await loadData();
    } catch (err) {
      console.error("Failed to create item:", err);
      alert("Failed to create new item. Please check the inputs.");
    } finally {
      setAddingItem(false);
    }
  };

  // Helper to compute item price for cards
  const getItemPrice = (item: CanonicalItem): number | null => {
    if (item.default_unit_price != null && item.default_unit_price > 0) {
      return item.default_unit_price;
    }
    const inv = inventoryMap.get(item.id);
    if (inv && inv.price != null && inv.price > 0) {
      return inv.price;
    }
    return null;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Header Banner */}
      <div className="glass-panel" style={{ padding: "20px 24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(16, 185, 129, 0.2) 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "1px solid rgba(99, 102, 241, 0.4)",
                boxShadow: "0 0 16px rgba(99, 102, 241, 0.2)"
              }}
            >
              <Package size={22} color="#818CF8" />
            </div>
            <div>
              <h2 style={{ fontSize: "1.35rem", fontWeight: 700, color: "#F3F4F6", letterSpacing: "-0.02em", margin: 0 }}>
                Items & Pantry Intelligence
              </h2>
              <p style={{ fontSize: "0.82rem", color: "#9CA3AF", marginTop: "4px", margin: 0 }}>
                Unified catalog tracking grocery items, consumption velocity, pricing, and store aliases.
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              onClick={loadData}
              disabled={loading}
              className="btn-secondary"
              style={{ padding: "8px 12px", borderRadius: "10px" }}
              title="Refresh item data"
            >
              <RefreshCw size={16} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
              <span style={{ fontSize: "0.82rem" }}>Refresh</span>
            </button>
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="btn-primary"
            >
              <Plus size={16} />
              <span>Add New Item</span>
            </button>
          </div>
        </div>
      </div>

      {/* Overview Stat Cards (3 Clean Cards - In Pantry Now section removed) */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "14px" }}>
        {/* Card 1: Total Catalog */}
        <div
          onClick={() => { setItemTypeFilter("ALL"); setSelectedCategory("All"); }}
          className="glass-panel"
          style={{
            padding: "18px 20px",
            cursor: "pointer",
            borderRadius: "14px",
            border: itemTypeFilter === "ALL" && selectedCategory === "All"
              ? "1px solid #6366F1"
              : "1px solid var(--border-subtle)",
            boxShadow: itemTypeFilter === "ALL" && selectedCategory === "All"
              ? "0 0 18px rgba(99, 102, 241, 0.25)"
              : "none",
            transition: "all 0.2s ease"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Total Catalog
            </span>
            <div
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "10px",
                background: "rgba(99, 102, 241, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#818CF8"
              }}
            >
              <Tags size={18} />
            </div>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#F3F4F6", marginTop: "8px" }}>
            {metrics.total}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#9CA3AF", marginTop: "2px" }}>
            Unique tracked items
          </div>
        </div>

        {/* Card 2: Consumption Rhythm */}
        <div
          onClick={() => { setItemTypeFilter("ALL"); setSelectedCategory("All"); }}
          className="glass-panel"
          style={{
            padding: "18px 20px",
            borderRadius: "14px",
            border: "1px solid var(--border-subtle)"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Consumption Rhythm
            </span>
            <div
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "10px",
                background: "rgba(168, 85, 247, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#C084FC"
              }}
            >
              <Activity size={18} />
            </div>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#C084FC", marginTop: "8px" }}>
            {metrics.withVelocity}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#9CA3AF", marginTop: "2px" }}>
            Learned burn velocity
          </div>
        </div>

        {/* Card 3: Non-Grocery */}
        <div
          onClick={() => setItemTypeFilter("NON_GROCERY")}
          className="glass-panel"
          style={{
            padding: "18px 20px",
            cursor: "pointer",
            borderRadius: "14px",
            border: itemTypeFilter === "NON_GROCERY"
              ? "1px solid #F59E0B"
              : "1px solid var(--border-subtle)",
            boxShadow: itemTypeFilter === "NON_GROCERY"
              ? "0 0 18px rgba(245, 158, 11, 0.25)"
              : "none",
            transition: "all 0.2s ease"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Non-Grocery
            </span>
            <div
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "10px",
                background: "rgba(245, 158, 11, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#F59E0B"
              }}
            >
              <ShoppingBag size={18} />
            </div>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#FCD34D", marginTop: "8px" }}>
            {metrics.nonGrocery}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#9CA3AF", marginTop: "2px" }}>
            Excluded from Sunday list
          </div>
        </div>
      </div>

      {/* Search & Filter Controls Bar */}
      <div className="glass-panel" style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: "14px" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center", justifyContent: "space-between" }}>
          {/* Search Box */}
          <div style={{ position: "relative", flex: "1 1 300px", minWidth: "240px" }}>
            <Search
              size={18}
              color="#9CA3AF"
              style={{ position: "absolute", left: "14px", top: "50%", transform: "translateY(-50%)" }}
            />
            <input
              type="text"
              placeholder="Search items by name, store, alias, or category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field"
              style={{ width: "100%", paddingLeft: "42px", paddingRight: searchQuery ? "38px" : "14px" }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  right: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#9CA3AF",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Type Filters (All / Grocery / Non-Grocery) */}
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              onClick={() => setItemTypeFilter("ALL")}
              style={{
                background: itemTypeFilter === "ALL" ? "linear-gradient(135deg, #6366F1, #4F46E5)" : "rgba(255, 255, 255, 0.05)",
                color: itemTypeFilter === "ALL" ? "#FFFFFF" : "#9CA3AF",
                border: itemTypeFilter === "ALL" ? "1px solid rgba(99, 102, 241, 0.6)" : "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "6px 12px",
                fontSize: "0.78rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              All Items ({items.length})
            </button>
            <button
              onClick={() => setItemTypeFilter("GROCERY")}
              style={{
                background: itemTypeFilter === "GROCERY" ? "linear-gradient(135deg, #10B981, #059669)" : "rgba(255, 255, 255, 0.05)",
                color: itemTypeFilter === "GROCERY" ? "#FFFFFF" : "#9CA3AF",
                border: itemTypeFilter === "GROCERY" ? "1px solid rgba(16, 185, 129, 0.6)" : "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "6px 12px",
                fontSize: "0.78rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              Grocery ({metrics.grocery})
            </button>
            <button
              onClick={() => setItemTypeFilter("NON_GROCERY")}
              style={{
                background: itemTypeFilter === "NON_GROCERY" ? "linear-gradient(135deg, #F59E0B, #D97706)" : "rgba(255, 255, 255, 0.05)",
                color: itemTypeFilter === "NON_GROCERY" ? "#FFFFFF" : "#9CA3AF",
                border: itemTypeFilter === "NON_GROCERY" ? "1px solid rgba(245, 158, 11, 0.6)" : "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "6px 12px",
                fontSize: "0.78rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              Non-Grocery ({metrics.nonGrocery})
            </button>
          </div>
        </div>

        {/* Category Pills */}
        <div
          style={{
            display: "flex",
            gap: "8px",
            overflowX: "auto",
            paddingBottom: "4px",
            alignItems: "center",
            borderTop: "1px solid rgba(255, 255, 255, 0.06)",
            paddingTop: "12px"
          }}
        >
          <span style={{ fontSize: "0.78rem", color: "#9CA3AF", fontWeight: 600, display: "flex", alignItems: "center", gap: "4px", marginRight: "4px", whiteSpace: "nowrap" }}>
            <Filter size={14} /> Category:
          </span>
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  padding: "5px 12px",
                  borderRadius: "20px",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  border: isSelected ? "1px solid rgba(99, 102, 241, 0.6)" : "1px solid rgba(255, 255, 255, 0.08)",
                  transition: "all 0.2s ease",
                  whiteSpace: "nowrap",
                  background: isSelected
                    ? "linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)"
                    : "rgba(255, 255, 255, 0.04)",
                  color: isSelected ? "#FFFFFF" : "#9CA3AF",
                  boxShadow: isSelected ? "0 0 12px rgba(99, 102, 241, 0.4)" : "none"
                }}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div
          className="glass-panel"
          style={{
            padding: "14px 18px",
            borderLeft: "4px solid #EF4444",
            background: "rgba(239, 68, 68, 0.12)",
            color: "#F87171",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "0.85rem"
          }}
        >
          <AlertTriangle size={18} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Items List */}
      {loading ? (
        <div className="glass-panel" style={{ padding: "60px 20px", textAlign: "center" }}>
          <RefreshCw
            size={32}
            color="#818CF8"
            style={{ animation: "spin 1s linear infinite", margin: "0 auto 14px" }}
          />
          <p style={{ color: "#F3F4F6", fontSize: "0.95rem", fontWeight: 600, margin: 0 }}>
            Loading items & catalog...
          </p>
          <p style={{ color: "#9CA3AF", fontSize: "0.8rem", marginTop: "4px" }}>
            Synchronizing catalog items, prices, and learned rhythms
          </p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="glass-panel" style={{ padding: "60px 20px", textAlign: "center" }}>
          <Package size={40} color="#9CA3AF" style={{ margin: "0 auto 12px" }} />
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#F3F4F6", margin: 0 }}>
            No items match your criteria
          </h3>
          <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "6px", maxWidth: "400px", margin: "6px auto 0" }}>
            Try adjusting your search query or switching the category filter.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "16px"
          }}
        >
          {filteredItems.map((item) => {
            const vel = velocityMap.get(item.id);
            const isNonGrocery = item.is_grocery === false || item.category.toLowerCase() === "non-grocery";
            const price = getItemPrice(item);

            return (
              <div
                key={item.id}
                onClick={() => setSelectedItemId(item.id)}
                className="glass-panel"
                style={{
                  padding: "18px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  gap: "12px",
                  cursor: "pointer",
                  borderRadius: "14px",
                  transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.5)";
                  e.currentTarget.style.transform = "translateY(-2px)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border-subtle)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                <div>
                  {/* Top Badges (Category + Standard Unit / Shelf life, NO active/pantry stock) */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", marginBottom: "10px" }}>
                    <span
                      className={isNonGrocery ? "badge badge-amber" : "badge badge-indigo"}
                      style={{ fontSize: "0.7rem", padding: "2px 8px" }}
                    >
                      {item.category}
                    </span>

                    <span
                      style={{
                        fontSize: "0.72rem",
                        color: "#9CA3AF",
                        background: "rgba(255, 255, 255, 0.04)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        padding: "2px 8px",
                        borderRadius: "9999px",
                        display: "flex",
                        alignItems: "center",
                        gap: "4px"
                      }}
                    >
                      <Clock size={11} color="#9CA3AF" />
                      {item.default_shelf_life_days}d shelf life
                    </span>
                  </div>

                  {/* Title & Chevron */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "6px" }}>
                    <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#F3F4F6", margin: 0 }}>
                      {item.canonical_name}
                    </h3>
                    <ChevronRight size={16} color="#818CF8" style={{ flexShrink: 0 }} />
                  </div>

                  {/* Store & PROMINENT PRICE DISPLAY */}
                  <div style={{ marginTop: "8px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", fontSize: "0.82rem" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#9CA3AF" }}>
                      <Store size={14} color="#9CA3AF" />
                      {item.preferred_store || "Any store"}
                    </span>

                    {/* Price */}
                    <span
                      style={{
                        color: price != null ? "#34D399" : "#6B7280",
                        fontWeight: 600,
                        display: "flex",
                        alignItems: "center",
                        gap: "3px"
                      }}
                    >
                      <DollarSign size={13} color={price != null ? "#10B981" : "#6B7280"} />
                      {price != null
                        ? `$${Number(price).toFixed(2)} / ${item.standard_unit || "count"}`
                        : "No price"}
                    </span>
                  </div>

                  {/* Consumption Rhythm / Velocity */}
                  <div
                    style={{
                      marginTop: "12px",
                      paddingTop: "10px",
                      borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: "0.78rem"
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#9CA3AF" }}>
                      <Activity size={14} color="#A78BFA" />
                      <span>Rhythm:</span>
                      {vel && vel.daily_velocity > 0 ? (
                        <strong style={{ color: "#D8B4FE", fontWeight: 600 }}>
                          {vel.daily_velocity.toFixed(2)} {item.standard_unit || "count"}/day
                        </strong>
                      ) : (
                        <span style={{ color: "#6B7280", fontStyle: "italic" }}>No rhythm yet</span>
                      )}
                    </div>

                    <span style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>
                      Unit: <strong style={{ color: "#E5E7EB" }}>{item.standard_unit || "count"}</strong>
                    </span>
                  </div>
                </div>

                {/* Bottom Aliases & Action CTA */}
                <div
                  style={{
                    borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                    paddingTop: "10px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "0.75rem"
                  }}
                >
                  <span style={{ color: "#9CA3AF", display: "flex", alignItems: "center", gap: "4px" }}>
                    <Tags size={14} color="#9CA3AF" />
                    {item.aliases && item.aliases.length > 0
                      ? `${item.aliases.length} alias${item.aliases.length > 1 ? "es" : ""}`
                      : "No aliases"}
                  </span>
                  <span style={{ color: "#818CF8", fontWeight: 600, display: "flex", alignItems: "center", gap: "2px" }}>
                    Details & Price →
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Item Details Modal */}
      {selectedItemId !== null && (
        <ItemDetailsModal
          itemId={selectedItemId}
          householdId={householdId}
          onClose={() => setSelectedItemId(null)}
          onItemUpdated={loadData}
        />
      )}

      {/* Add New Item Modal */}
      {isAddModalOpen && (
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
          onClick={() => setIsAddModalOpen(false)}
        >
          <div
            className="glass-panel"
            style={{
              width: "100%",
              maxWidth: "480px",
              background: "#111827",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
              position: "relative"
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "#F3F4F6", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                <Plus size={20} color="#818CF8" />
                Add New Catalog Item
              </h2>
              <button
                onClick={() => setIsAddModalOpen(false)}
                style={{ background: "transparent", border: "none", color: "#9CA3AF", cursor: "pointer", padding: "4px" }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateItem} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                  Item Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Organic Almond Milk"
                  value={newItemName}
                  onChange={(e) => setNewItemName(e.target.value)}
                  className="input-field"
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                    Category *
                  </label>
                  <select
                    value={newItemCategory}
                    onChange={(e) => setNewItemCategory(e.target.value)}
                    style={{
                      width: "100%",
                      background: "#1F2937",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "10px",
                      color: "#F3F4F6",
                      padding: "8px 12px",
                      fontSize: "0.85rem",
                      outline: "none"
                    }}
                  >
                    <option value="Produce">Produce</option>
                    <option value="Dairy">Dairy</option>
                    <option value="Pantry">Pantry</option>
                    <option value="Bakery">Bakery</option>
                    <option value="Snacks">Snacks</option>
                    <option value="Beverages">Beverages</option>
                    <option value="Frozen">Frozen</option>
                    <option value="Non-Grocery">Non-Grocery</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                    Standard Unit *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="count, carton, kg"
                    value={newItemUnit}
                    onChange={(e) => setNewItemUnit(e.target.value)}
                    className="input-field"
                    style={{ width: "100%" }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                  Est. Shelf Life (Days)
                </label>
                <input
                  type="number"
                  value={newItemShelfLife}
                  onChange={(e) => setNewItemShelfLife(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                    Preferred Store
                  </label>
                  <input
                    type="text"
                    placeholder="Trader Joe's, Costco..."
                    value={newItemStore}
                    onChange={(e) => setNewItemStore(e.target.value)}
                    className="input-field"
                    style={{ width: "100%" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.72rem", fontWeight: 600, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
                    Unit Price ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="3.99"
                    value={newItemPrice}
                    onChange={(e) => setNewItemPrice(e.target.value)}
                    className="input-field"
                    style={{ width: "100%" }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px", paddingTop: "4px" }}>
                <input
                  type="checkbox"
                  id="is_grocery_check"
                  checked={newItemIsGrocery}
                  onChange={(e) => setNewItemIsGrocery(e.target.checked)}
                  style={{ width: "16px", height: "16px", accentColor: "#6366F1", cursor: "pointer" }}
                />
                <label htmlFor="is_grocery_check" style={{ fontSize: "0.8rem", color: "#D1D5DB", cursor: "pointer" }}>
                  This is a grocery item (eligible for Sunday grocery list)
                </label>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "10px", marginTop: "8px", paddingTop: "12px", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="btn-secondary"
                  style={{ padding: "8px 16px" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingItem || !newItemName.trim()}
                  className="btn-primary"
                  style={{ padding: "8px 18px" }}
                >
                  {addingItem ? "Creating..." : "Create Item"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
