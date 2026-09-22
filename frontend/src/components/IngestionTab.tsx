import React, { useState, useEffect } from "react";
import {
  Upload,
  FileText,
  Receipt,
  Trash2,
  ChevronDown,
  ChevronUp,
  Calendar,
  Package,
  CheckCircle2
} from "lucide-react";
import type { CSVUploadSummary, ReceiptUpload, BillItem } from "../types";
import {
  uploadReceiptCsv,
  fetchUploadedBills,
  fetchBillItems,
  deleteBill,
  deletePurchaseItem
} from "../api/client";

interface IngestionTabProps {
  householdId: number;
  onRefresh: () => void;
}

export const IngestionTab: React.FC<IngestionTabProps> = ({
  householdId,
  onRefresh,
}) => {
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary] = useState<CSVUploadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Bills list & detail state
  const [bills, setBills] = useState<ReceiptUpload[]>([]);
  const [loadingBills, setLoadingBills] = useState(false);
  const [expandedBillId, setExpandedBillId] = useState<number | null>(null);
  const [billItems, setBillItems] = useState<Record<number, BillItem[]>>({});
  const [loadingItemsFor, setLoadingItemsFor] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadBills = async () => {
    try {
      setLoadingBills(true);
      const data = await fetchUploadedBills(householdId);
      setBills(data);
    } catch (err) {
      console.error("Failed to load bills", err);
    } finally {
      setLoadingBills(false);
    }
  };

  useEffect(() => {
    loadBills();
  }, [householdId]);

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const res = await uploadReceiptCsv(file, householdId);
      setSummary(res);
      setActionMessage(`Receipt "${file.name}" uploaded and processed successfully.`);
      await loadBills();
      onRefresh();
    } catch (err: any) {
      setError(err.message || "Failed to process receipt");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const toggleBillDetails = async (billId: number) => {
    if (expandedBillId === billId) {
      setExpandedBillId(null);
      return;
    }

    setExpandedBillId(billId);
    if (!billItems[billId]) {
      try {
        setLoadingItemsFor(billId);
        const items = await fetchBillItems(billId);
        setBillItems((prev) => ({ ...prev, [billId]: items }));
      } catch (err: any) {
        alert(err.message || "Failed to load bill items");
      } finally {
        setLoadingItemsFor(null);
      }
    }
  };

  const handleDeleteBill = async (bill: ReceiptUpload) => {
    const confirmMsg = `Are you sure you want to delete the bill "${bill.filename}"?\n\nThis will remove all ${bill.total_items} items from purchase history and automatically roll back active pantry inventory.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await deleteBill(bill.id);
      setBills((prev) => prev.filter((b) => b.id !== bill.id));
      if (expandedBillId === bill.id) {
        setExpandedBillId(null);
      }
      setActionMessage(`Bill "${bill.filename}" and its purchase history were successfully deleted.`);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to delete bill");
    }
  };

  const handleDeleteItem = async (billId: number, item: BillItem) => {
    const confirmMsg = `Delete "${item.item_name}" (${item.quantity} ${item.unit}) from purchase history?\n\nThis will roll back corresponding active stock in your pantry.`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await deletePurchaseItem(item.id);
      // Remove from bill items state
      setBillItems((prev) => ({
        ...prev,
        [billId]: (prev[billId] || []).filter((it) => it.id !== item.id)
      }));
      // Update bill count in list
      setBills((prev) =>
        prev.map((b) => {
          if (b.id === billId) {
            return {
              ...b,
              total_items: Math.max(0, b.total_items - 1),
              total_amount: Math.max(0, b.total_amount - (item.price || 0))
            };
          }
          return b;
        })
      );
      setActionMessage(`Item "${item.item_name}" deleted and inventory adjusted.`);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to delete item");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Action Notification */}
      {actionMessage && (
        <div
          className="glass-panel"
          style={{
            padding: "12px 18px",
            borderLeft: "4px solid #10B981",
            background: "rgba(16, 185, 129, 0.12)",
            color: "#34D399",
            fontWeight: 600,
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <CheckCircle2 size={18} />
            <span>{actionMessage}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            style={{ background: "transparent", border: "none", color: "#9CA3AF", cursor: "pointer", fontSize: "0.85rem" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Upload Dropzone */}
      <div
        className="glass-panel"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        style={{
          padding: "36px 24px",
          textAlign: "center",
          border: "2px dashed rgba(99, 102, 241, 0.4)",
          background: "rgba(18, 24, 38, 0.6)",
          cursor: "pointer",
          borderRadius: "18px",
          transition: "border-color 0.2s ease"
        }}
        onClick={() => document.getElementById("receipt-file-input")?.click()}
      >
        <input
          id="receipt-file-input"
          type="file"
          accept=".csv,.txt"
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileUpload(e.target.files[0]);
            }
          }}
        />

        <div style={{
          width: "56px",
          height: "56px",
          borderRadius: "50%",
          background: "rgba(99, 102, 241, 0.15)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 16px"
        }}>
          <Upload size={28} color="#818CF8" />
        </div>

        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#F3F4F6" }}>
          {uploading ? "Parsing bill & populating inventory..." : "Drag & Drop Grocery Bill / Receipt CSV"}
        </h3>
        <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "6px", maxWidth: "600px", margin: "6px auto 0" }}>
          Upload itemized receipts (New India Bazar, Costco, Trader Joe's) to track purchase history,
          calibrate consumption rhythms, and maintain pantry stock.
        </p>

        <div style={{ marginTop: "18px" }}>
          <button className="btn-primary" disabled={uploading}>
            <FileText size={16} />
            <span>{uploading ? "Processing..." : "Select Receipt File"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-panel" style={{ padding: "16px", borderLeft: "4px solid #EF4444", color: "#F87171" }}>
          {error}
        </div>
      )}

      {/* Instant Upload Summary */}
      {summary && (
        <div className="glass-panel" style={{ padding: "24px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px", marginBottom: "18px" }}>
            <div>
              <span className="badge badge-emerald" style={{ marginBottom: "8px" }}>Upload Successful</span>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                {summary.store_name} • {summary.purchase_date}
              </h3>
            </div>
            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#34D399" }}>
              ${summary.total_amount.toFixed(2)}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "12px", marginBottom: "20px" }}>
            <div style={{ padding: "12px", background: "rgba(255, 255, 255, 0.04)", borderRadius: "10px" }}>
              <div style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>Total Line Items</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700 }}>{summary.total_rows}</div>
            </div>
            <div style={{ padding: "12px", background: "rgba(16, 185, 129, 0.1)", borderRadius: "10px" }}>
              <div style={{ fontSize: "0.75rem", color: "#34D399" }}>Matched / Created</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#34D399" }}>{summary.matched_rows}</div>
            </div>
            <div style={{ padding: "12px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "10px" }}>
              <div style={{ fontSize: "0.75rem", color: "#FCD34D" }}>Unresolved</div>
              <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "#FCD34D" }}>{summary.unresolved_rows}</div>
            </div>
          </div>
        </div>
      )}

      {/* Uploaded Bills History Section */}
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div className="glass-panel" style={{ padding: "20px 24px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px", color: "#F3F4F6" }}>
                <Receipt size={22} color="#6366F1" />
                <span>Uploaded Receipts & Bill History</span>
              </h3>
              <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "4px" }}>
                Browse all uploaded receipt batches. Click on any bill to inspect its items or delete specific entries from history.
              </p>
            </div>
            <div className="badge badge-purple" style={{ fontSize: "0.8rem", padding: "6px 12px" }}>
              {bills.length} {bills.length === 1 ? "Bill Uploaded" : "Bills Uploaded"}
            </div>
          </div>
        </div>

        {loadingBills ? (
          <div className="glass-panel" style={{ padding: "40px", textAlign: "center", color: "#818CF8" }}>
            Loading bill history...
          </div>
        ) : bills.length === 0 ? (
          <div className="glass-panel" style={{ padding: "60px 20px", textAlign: "center" }}>
            <div style={{
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              background: "rgba(99, 102, 241, 0.15)",
              color: "#818CF8",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px"
            }}>
              <Receipt size={28} />
            </div>
            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#F3F4F6" }}>No Bills Uploaded Yet</h4>
            <p style={{ fontSize: "0.85rem", color: "#9CA3AF", marginTop: "4px" }}>
              Upload your grocery store receipt CSV above to view and manage bills here.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {bills.map((bill) => {
              const isExpanded = expandedBillId === bill.id;
              const items = billItems[bill.id] || [];
              const isLoadingItems = loadingItemsFor === bill.id;

              return (
                <div
                  key={bill.id}
                  className="glass-panel"
                  style={{
                    borderRadius: "16px",
                    overflow: "hidden",
                    border: isExpanded ? "1px solid rgba(99, 102, 241, 0.4)" : "1px solid rgba(255, 255, 255, 0.08)",
                    transition: "border-color 0.2s ease"
                  }}
                >
                  {/* Bill Card Header */}
                  <div
                    style={{
                      padding: "20px 24px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "16px",
                      background: isExpanded ? "rgba(255, 255, 255, 0.03)" : "transparent"
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
                      <div
                        style={{
                          width: "44px",
                          height: "44px",
                          borderRadius: "12px",
                          background: "rgba(99, 102, 241, 0.15)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#818CF8"
                        }}
                      >
                        <FileText size={22} />
                      </div>

                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                          <h4 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#F3F4F6" }}>
                            {bill.store_name}
                          </h4>
                          <span className="badge badge-indigo" style={{ fontSize: "0.72rem" }}>
                            {bill.filename}
                          </span>
                        </div>

                        <div style={{ display: "flex", gap: "14px", marginTop: "4px", fontSize: "0.8rem", color: "#9CA3AF" }}>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Calendar size={13} />
                            <span>Bill Date: {bill.bill_date}</span>
                          </span>
                          <span>•</span>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <Package size={13} />
                            <span>{bill.total_items} Items</span>
                          </span>
                          <span>•</span>
                          <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#34D399", fontWeight: 600 }}>
                            <span>${bill.total_amount.toFixed(2)}</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Bill Actions */}
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <button
                        onClick={() => toggleBillDetails(bill.id)}
                        className="btn-primary"
                        style={{
                          padding: "8px 16px",
                          fontSize: "0.82rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px"
                        }}
                      >
                        <span>{isExpanded ? "Hide Items" : "View Items"}</span>
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>

                      <button
                        onClick={() => handleDeleteBill(bill)}
                        style={{
                          background: "rgba(239, 68, 68, 0.15)",
                          border: "1px solid rgba(239, 68, 68, 0.3)",
                          color: "#F87171",
                          borderRadius: "10px",
                          padding: "8px 14px",
                          fontSize: "0.82rem",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          transition: "all 0.2s ease"
                        }}
                        title="Delete entire bill and roll back inventory"
                      >
                        <Trash2 size={16} />
                        <span>Delete Bill</span>
                      </button>
                    </div>
                  </div>

                  {/* Expanded Bill Line Items Table */}
                  {isExpanded && (
                    <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", padding: "20px 24px", background: "rgba(10, 14, 23, 0.5)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                        <h5 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#D1D5DB" }}>
                          Line Items in this Bill ({items.length})
                        </h5>
                        <span style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>
                          Deleting an item updates purchase history and adjusts inventory stock
                        </span>
                      </div>

                      {isLoadingItems ? (
                        <div style={{ padding: "20px", textAlign: "center", color: "#818CF8", fontSize: "0.85rem" }}>
                          Loading bill line items...
                        </div>
                      ) : items.length === 0 ? (
                        <div style={{ padding: "20px", textAlign: "center", color: "#9CA3AF", fontSize: "0.85rem" }}>
                          No line items found for this bill.
                        </div>
                      ) : (
                        <div style={{ overflowX: "auto" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                            <thead>
                              <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#9CA3AF", textAlign: "left" }}>
                                <th style={{ padding: "8px 12px" }}>Resolved Item</th>
                                <th style={{ padding: "8px 12px" }}>Raw Text</th>
                                <th style={{ padding: "8px 12px" }}>Category</th>
                                <th style={{ padding: "8px 12px" }}>Quantity</th>
                                <th style={{ padding: "8px 12px" }}>Price</th>
                                <th style={{ padding: "8px 12px" }}>Match</th>
                                <th style={{ padding: "8px 12px", textAlign: "right" }}>Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {items.map((it) => (
                                <tr key={it.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                  <td style={{ padding: "10px 12px", fontWeight: 600, color: "#F3F4F6" }}>
                                    {it.item_name}
                                  </td>
                                  <td style={{ padding: "10px 12px", color: "#9CA3AF", fontFamily: "monospace", fontSize: "0.78rem" }}>
                                    {it.raw_text}
                                  </td>
                                  <td style={{ padding: "10px 12px" }}>
                                    <span className="badge badge-blue" style={{ fontSize: "0.68rem" }}>
                                      {it.category}
                                    </span>
                                  </td>
                                  <td style={{ padding: "10px 12px" }}>
                                    {it.quantity} {it.unit}
                                  </td>
                                  <td style={{ padding: "10px 12px", color: "#34D399", fontWeight: 600 }}>
                                    {it.price !== null && it.price !== undefined ? `$${it.price.toFixed(2)}` : "—"}
                                  </td>
                                  <td style={{ padding: "10px 12px" }}>
                                    <span
                                      className={`badge ${it.matched_via.includes("llm") ? "badge-indigo" : "badge-emerald"}`}
                                      style={{ fontSize: "0.68rem" }}
                                    >
                                      {it.matched_via}
                                    </span>
                                  </td>
                                  <td style={{ padding: "10px 12px", textAlign: "right" }}>
                                    <button
                                      onClick={() => handleDeleteItem(bill.id, it)}
                                      style={{
                                        background: "rgba(239, 68, 68, 0.12)",
                                        border: "1px solid rgba(239, 68, 68, 0.25)",
                                        color: "#F87171",
                                        borderRadius: "6px",
                                        padding: "4px 8px",
                                        fontSize: "0.75rem",
                                        cursor: "pointer",
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: "4px"
                                      }}
                                      title="Delete line item and rollback inventory"
                                    >
                                      <Trash2 size={13} />
                                      <span>Delete</span>
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
