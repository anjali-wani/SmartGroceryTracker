import React from "react";
import {
  Package,
  ShoppingCart,
  Receipt,
  Home,
  Sparkles,
  RotateCcw,
  Database
} from "lucide-react";
import type { DatabaseMode } from "../api/client";

interface NavbarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  householdId: number;
  setHouseholdId: (id: number) => void;
  groceryCount: number;
  inventoryCount: number;
  backendOnline: boolean;
  onResetData: () => void;
  dbMode: DatabaseMode;
  onDbModeChange: (mode: DatabaseMode) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  setCurrentTab,
  householdId,
  setHouseholdId,
  groceryCount,
  inventoryCount: _inventoryCount,
  backendOnline,
  onResetData,
  dbMode,
  onDbModeChange,
}) => {
  const tabs = [
    {
      id: "items",
      label: "Items",
      icon: Package
    },
    {
      id: "grocery",
      label: "Sunday Grocery List",
      icon: ShoppingCart,
      badge: groceryCount > 0 ? `${groceryCount} needed` : undefined,
      badgeColor: "badge-indigo"
    },
    {
      id: "bills",
      label: "Receipts & Bills",
      icon: Receipt
    },
  ];

  return (
    <header className="glass-panel" style={{ margin: "16px 24px 24px", padding: "14px 24px", borderRadius: "18px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
        
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            width: "42px",
            height: "42px",
            borderRadius: "12px",
            background: "linear-gradient(135deg, #10B981 0%, #6366F1 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 20px rgba(99, 102, 241, 0.4)"
          }}>
            <Sparkles size={22} color="#fff" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.02em", color: "#F3F4F6", lineHeight: 1.2 }}>
                Smart Grocery Tracker
              </h1>
              <span className="badge badge-amber" style={{ fontSize: "0.65rem", padding: "2px 8px" }}>
                AI ENGINE
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", color: "#9CA3AF" }}>
              <span style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: backendOnline ? "#10B981" : "#EF4444",
                boxShadow: backendOnline ? "0 0 8px #10B981" : "0 0 8px #EF4444",
                display: "inline-block"
              }} />
              <span>{backendOnline ? "API Online (Port 8001)" : "Backend Offline"}</span>
            </div>
          </div>
        </div>

        {/* Controls: Database Switcher, Household Switcher & Reset Button */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>

          {/* Database Mode Switcher (Production vs Test) */}
          <div style={{
            background: dbMode === "production" ? "rgba(16, 185, 129, 0.12)" : "rgba(245, 158, 11, 0.14)",
            border: dbMode === "production" ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid rgba(245, 158, 11, 0.45)",
            borderRadius: "10px",
            padding: "4px 10px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            boxShadow: dbMode === "production" ? "0 0 12px rgba(16, 185, 129, 0.15)" : "0 0 12px rgba(245, 158, 11, 0.15)",
            transition: "all 0.2s ease"
          }}>
            <Database size={15} color={dbMode === "production" ? "#34D399" : "#FBBF24"} />
            <span style={{
              fontSize: "0.78rem",
              color: dbMode === "production" ? "#34D399" : "#FBBF24",
              fontWeight: 700,
              letterSpacing: "0.02em"
            }}>
              DB:
            </span>
            <select
              value={dbMode}
              onChange={(e) => onDbModeChange(e.target.value as DatabaseMode)}
              title="Switch between Production (live) and Test (sandbox) databases"
              style={{
                background: "transparent",
                border: "none",
                color: "#F3F4F6",
                fontWeight: 600,
                fontSize: "0.82rem",
                cursor: "pointer",
                outline: "none"
              }}
            >
              <option value="production" style={{ background: "#111827", color: "#34D399" }}>
                🟢 Production DB (Live)
              </option>
              <option value="test" style={{ background: "#111827", color: "#FBBF24" }}>
                🟡 Test DB (Sandbox)
              </option>
            </select>
          </div>

          <div style={{
            background: "rgba(255, 255, 255, 0.05)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "10px",
            padding: "4px 12px",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}>
            <Home size={16} color="#9CA3AF" />
            <span style={{ fontSize: "0.8rem", color: "#9CA3AF", fontWeight: 500 }}>Household:</span>
            <select
              value={householdId}
              onChange={(e) => setHouseholdId(Number(e.target.value))}
              style={{
                background: "transparent",
                border: "none",
                color: "#F3F4F6",
                fontWeight: 600,
                fontSize: "0.85rem",
                cursor: "pointer",
                outline: "none"
              }}
            >
              <option value={1} style={{ background: "#111827", color: "#fff" }}>Household 1 (Family)</option>
              <option value={2} style={{ background: "#111827", color: "#fff" }}>Household 2 (Personal)</option>
              <option value={3} style={{ background: "#111827", color: "#fff" }}>Household 3 (Guest)</option>
            </select>
          </div>

          {/* Reset Data Button (only for Test mode) */}
          {dbMode === "test" && (
            <button
              onClick={onResetData}
              className="btn-danger"
              style={{ padding: "6px 12px", fontSize: "0.8rem", borderRadius: "10px" }}
              title="Reset transactional data in Test DB"
            >
              <RotateCcw size={14} />
              <span>Reset Test Data</span>
            </button>
          )}

        </div>

      </div>

      {/* Exactly 3 Tabs */}
      <nav style={{ display: "flex", gap: "10px", marginTop: "16px", overflowX: "auto", paddingBottom: "4px" }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setCurrentTab(tab.id)}
              style={{
                background: isActive ? "linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(16, 185, 129, 0.15) 100%)" : "rgba(255, 255, 255, 0.02)",
                border: isActive ? "1px solid rgba(99, 102, 241, 0.5)" : "1px solid rgba(255, 255, 255, 0.06)",
                borderRadius: "12px",
                padding: "10px 18px",
                color: isActive ? "#F3F4F6" : "#9CA3AF",
                fontSize: "0.9rem",
                fontWeight: isActive ? 600 : 500,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "10px",
                whiteSpace: "nowrap",
                transition: "all 0.2s ease"
              }}
            >
              <Icon size={18} color={isActive ? "#818CF8" : "#9CA3AF"} />
              <span>{tab.label}</span>
              {tab.badge && (
                <span className={`badge ${tab.badgeColor || "badge-indigo"}`} style={{ padding: "2px 8px", fontSize: "0.72rem" }}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </header>
  );
};
