import type {
  InventoryItem,
  GroceryListResponse,
  HouseholdVelocityReport,
  CSVUploadSummary,
  ReceiptUpload,
  BillItem,
  ItemDetails,
  ItemAlias,
  CanonicalItem
} from "../types";

const API_BASE = "http://127.0.0.1:8001";

export type DatabaseMode = "production" | "test";

let currentDatabaseMode: DatabaseMode =
  (localStorage.getItem("grocery_tracker_db_mode") as DatabaseMode) || "production";

export function getDatabaseMode(): DatabaseMode {
  return currentDatabaseMode;
}

export function setDatabaseMode(mode: DatabaseMode) {
  currentDatabaseMode = mode;
  localStorage.setItem("grocery_tracker_db_mode", mode);
}

export async function customFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("X-Database-Mode")) {
    headers.set("X-Database-Mode", currentDatabaseMode);
  }
  return fetch(url, { ...init, headers });
}

export interface DatabaseModeStatus {
  current_mode: DatabaseMode;
  active_file: string;
  databases: {
    production: {
      name: string;
      file: string;
      path: string;
      is_active: boolean;
      description: string;
      items_count: number;
      inventory_count: number;
      active_inventory_count: number;
      purchase_logs_count: number;
      receipts_count: number;
    };
    test: {
      name: string;
      file: string;
      path: string;
      is_active: boolean;
      description: string;
      items_count: number;
      inventory_count: number;
      active_inventory_count: number;
      purchase_logs_count: number;
      receipts_count: number;
    };
  };
}

export async function fetchDatabaseStatus(): Promise<DatabaseModeStatus> {
  const res = await customFetch(`${API_BASE}/system/database-mode`);
  if (!res.ok) throw new Error("Failed to fetch database status");
  return res.json();
}

export async function switchServerDatabaseMode(mode: DatabaseMode): Promise<any> {
  const res = await customFetch(`${API_BASE}/system/database-mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode })
  });
  if (!res.ok) throw new Error("Failed to switch database mode");
  return res.json();
}

export async function fetchActiveInventory(householdId: number): Promise<InventoryItem[]> {
  const res = await customFetch(`${API_BASE}/inventory/active?household_id=${householdId}`);
  if (!res.ok) throw new Error("Failed to fetch active inventory");
  return res.json();
}

export async function fetchCurrentInventory(householdId: number, status?: string): Promise<InventoryItem[]> {
  const url = status
    ? `${API_BASE}/items/inventory/current?household_id=${householdId}&status_filter=${status}`
    : `${API_BASE}/items/inventory/current?household_id=${householdId}`;
  const res = await customFetch(url);
  if (!res.ok) throw new Error("Failed to fetch inventory");
  return res.json();
}

export async function adjustInventoryStock(inventoryId: number, newQuantity: number): Promise<any> {
  const res = await customFetch(`${API_BASE}/inventory/adjust`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inventory_id: inventoryId, new_quantity: newQuantity })
  });
  if (!res.ok) throw new Error("Failed to adjust inventory");
  return res.json();
}

export async function confirmAvailability(
  canonicalItemId: number,
  isAvailable: boolean,
  householdId: number
): Promise<any> {
  const res = await customFetch(
    `${API_BASE}/inventory/${canonicalItemId}/confirm-availability?is_available=${isAvailable}&household_id=${householdId}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error("Failed to confirm availability");
  return res.json();
}

export async function fetchVelocityReport(householdId: number): Promise<HouseholdVelocityReport> {
  const res = await customFetch(`${API_BASE}/analytics/velocity?household_id=${householdId}`);
  if (!res.ok) throw new Error("Failed to fetch velocity analytics");
  return res.json();
}

export async function fetchGroceryList(householdId: number, daysAhead: number = 7): Promise<GroceryListResponse> {
  const res = await customFetch(`${API_BASE}/grocery-list/generate?household_id=${householdId}&days_ahead=${daysAhead}`);
  if (!res.ok) throw new Error("Failed to generate smart grocery list");
  return res.json();
}

export async function deleteGroceryListItem(itemId: number): Promise<void> {
  const res = await customFetch(`${API_BASE}/grocery-list/items/${itemId}`, {
    method: "DELETE"
  });
  if (!res.ok) throw new Error("Failed to delete grocery item");
}

export async function toggleGroceryListItem(itemId: number, isChecked: boolean): Promise<any> {
  const res = await customFetch(`${API_BASE}/grocery-list/items/${itemId}/toggle?is_checked=${isChecked}`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to toggle grocery item");
  return res.json();
}

export async function dismissGroceryListItem(entryId: number): Promise<any> {
  const res = await customFetch(`${API_BASE}/grocery-list/items/${entryId}/dismiss`, {
    method: "PATCH"
  });
  if (!res.ok) throw new Error("Failed to dismiss item");
  return res.json();
}

export async function addManualGroceryItem(
  householdId: number,
  data: { item_name: string; quantity: number; unit: string; category: string; target_store: string }
): Promise<any> {
  const res = await customFetch(`${API_BASE}/grocery-list/items?household_id=${householdId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to add manual grocery item");
  return res.json();
}

export async function exportGroceryListText(householdId: number): Promise<string> {
  const res = await customFetch(`${API_BASE}/grocery-list/export?household_id=${householdId}&format=text`);
  if (!res.ok) throw new Error("Failed to export list");
  return res.text();
}

export async function uploadReceiptCsv(file: File, householdId: number = 1): Promise<CSVUploadSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await customFetch(`${API_BASE}/bills/upload-csv?household_id=${householdId}`, {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Failed to process receipt CSV");
  }
  return res.json();
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await customFetch(`${API_BASE}/`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function resetDatabase(householdId: number = 1): Promise<any> {
  const res = await customFetch(`${API_BASE}/bills/reset-data?household_id=${householdId}`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to reset database data");
  return res.json();
}

export async function resetDatabaseData(householdId: number = 1): Promise<any> {
  return resetDatabase(householdId);
}

export async function fetchCanonicalItems(category?: string, search?: string): Promise<any[]> {
  let url = `${API_BASE}/items`;
  const params = new URLSearchParams();
  if (category && category !== "All") params.append("category", category);
  if (search) params.append("search", search);
  if (params.toString()) url += `?${params.toString()}`;
  const res = await customFetch(url);
  if (!res.ok) throw new Error("Failed to fetch canonical items");
  return res.json();
}

export async function addAliasToItem(itemId: number, rawAlias: string): Promise<any> {
  const res = await customFetch(`${API_BASE}/items/${itemId}/aliases?raw_alias=${encodeURIComponent(rawAlias)}`, {
    method: "POST"
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to add alias" }));
    throw new Error(err.detail || "Failed to add alias");
  }
  return res.json();
}

export async function addStoreAlias(
  itemId: number,
  rawAlias: string,
  storeName?: string
): Promise<ItemAlias> {
  const res = await customFetch(`${API_BASE}/items/${itemId}/aliases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_alias: rawAlias, store_name: storeName })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to add alias" }));
    throw new Error(err.detail || "Failed to add alias");
  }
  return res.json();
}

export async function createCanonicalItem(data: {
  canonical_name: string;
  category: string;
  standard_unit: string;
  default_shelf_life_days: number;
  is_bulk?: boolean;
  preferred_store?: string;
  default_unit_price?: number;
  is_grocery?: boolean;
}): Promise<any> {
  const res = await customFetch(`${API_BASE}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to create item" }));
    throw new Error(err.detail || "Failed to create item");
  }
  return res.json();
}

export async function fetchUploadedBills(householdId: number): Promise<ReceiptUpload[]> {
  const res = await customFetch(`${API_BASE}/bills?household_id=${householdId}`);
  if (!res.ok) throw new Error("Failed to fetch uploaded bills");
  return res.json();
}

export async function fetchBillItems(billId: number): Promise<BillItem[]> {
  const res = await customFetch(`${API_BASE}/bills/${billId}/items`);
  if (!res.ok) throw new Error("Failed to fetch bill items");
  return res.json();
}

export async function deleteBill(billId: number): Promise<any> {
  const res = await customFetch(`${API_BASE}/bills/${billId}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to delete bill" }));
    throw new Error(err.detail || "Failed to delete bill");
  }
  return res.json();
}

export async function deletePurchaseItem(purchaseId: number): Promise<any> {
  const res = await customFetch(`${API_BASE}/bills/purchases/${purchaseId}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to delete purchase item" }));
    throw new Error(err.detail || "Failed to delete purchase item");
  }
  return res.json();
}

export async function fetchItemDetails(itemId: number, householdId: number = 1): Promise<ItemDetails> {
  const res = await customFetch(`${API_BASE}/items/${itemId}/details?household_id=${householdId}`);
  if (!res.ok) throw new Error("Failed to fetch item details");
  return res.json();
}

export async function deleteItemAlias(aliasId: number): Promise<void> {
  const res = await customFetch(`${API_BASE}/items/aliases/${aliasId}`, {
    method: "DELETE"
  });
  if (!res.ok) throw new Error("Failed to delete alias");
}

export async function updateItemAlias(aliasId: number, rawAlias: string): Promise<ItemAlias> {
  const res = await customFetch(`${API_BASE}/items/aliases/${aliasId}?raw_alias=${encodeURIComponent(rawAlias)}`, {
    method: "PATCH"
  });
  if (!res.ok) throw new Error("Failed to update alias");
  return res.json();
}

export async function updateItemPrice(itemId: number, price: number): Promise<CanonicalItem> {
  const res = await customFetch(`${API_BASE}/items/${itemId}/schedule`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ default_unit_price: price })
  });
  if (!res.ok) throw new Error("Failed to update item price");
  return res.json();
}
