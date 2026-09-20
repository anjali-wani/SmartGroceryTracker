export type InventoryStatus = "ACTIVE" | "CONSUMED" | "SPOILED" | "ADJUSTED";

export interface InventoryItem {
  id: number;
  household_id: number;
  canonical_item_id: number;
  item_name: string;
  category: string;
  current_quantity: number;
  unit: string;
  purchase_date: string;
  status: InventoryStatus;
  store_name?: string;
  price?: number;
  unit_price?: number;
}

export interface AvailabilityPrompt {
  canonical_item_id: number;
  item_name: string;
  category: string;
  last_purchased: string;
  last_quantity: number;
  unit: string;
  message: string;
}

export interface GroceryListItem {
  id: number;
  canonical_item_id?: number | null;
  item_name: string;
  category: string;
  target_store: string;
  recommended_quantity: number;
  unit: string;
  estimated_cost?: number | null;
  priority_reason: "CRITICAL_DEPLETION" | "RUNNING_LOW" | "SCHEDULED_PERIODIC" | "MANUAL" | "CONFIRMED_DEPLETED";
  is_checked: boolean;
  estimated_runout_date?: string | null;
}

export interface GroceryListResponse {
  household_id: number;
  forecast_days: number;
  generated_date: string;
  total_items: number;
  total_estimated_cost: number;
  items: GroceryListItem[];
  items_by_store: Record<string, GroceryListItem[]>;
  items_by_category: Record<string, GroceryListItem[]>;
  availability_prompts: AvailabilityPrompt[];
}

export interface ItemVelocity {
  canonical_item_id: number;
  item_name: string;
  category: string;
  is_bulk: boolean;
  daily_velocity: number;
  per_capita_velocity: number;
  current_stock: number;
  unit: string;
  estimated_days_remaining?: number | null;
  lookback_days: number;
  purchase_count: number;
  confidence: "high" | "moderate" | "cold_start";
  last_purchased?: string | null;
  avg_purchase_interval_days?: number | null;
  days_per_unit?: number | null;
  modal_quantity?: number | null;
  projected_runout_date?: string | null;
  needs_availability_check: boolean;
  prompt_message?: string | null;
}

export interface HouseholdVelocityReport {
  household_id: number;
  total_tracked_items: number;
  household_members: number;
  report_date: string;
  items: ItemVelocity[];
}

export interface ProcessedLineItem {
  raw_line: string;
  clean_name: string;
  canonical_name?: string | null;
  category?: string | null;
  quantity: number;
  unit: string;
  price?: number | null;
  matched_via: string;
  confidence: number;
  status: string;
}

export interface CSVUploadSummary {
  store_name: string;
  purchase_date: string;
  total_rows: number;
  matched_rows: number;
  unresolved_rows: number;
  total_amount: number;
  bill_id?: number | null;
  processed_items: ProcessedLineItem[];
}

export interface ItemAlias {
  id: number;
  raw_alias: string;
  match_confidence: number;
  source: string;
}

export interface CanonicalItem {
  id: number;
  canonical_name: string;
  category: string;
  standard_unit: string;
  unit?: string;
  shelf_life_days?: number;
  default_shelf_life_days: number;
  is_bulk: boolean;
  is_grocery?: boolean;
  preferred_store?: string;
  default_unit_price?: number;
  created_at: string;
  aliases: ItemAlias[];
}


export interface ReceiptUpload {
  id: number;
  household_id: number;
  filename: string;
  store_name: string;
  bill_date: string;
  total_items: number;
  total_amount: number;
  bill_id?: number | null;
  uploaded_at: string;
}

export interface BillItem {
  id: number;
  raw_text: string;
  canonical_item_id?: number | null;
  item_name: string;
  category: string;
  quantity: number;
  unit: string;
  price?: number | null;
  matched_via: string;
  confidence: number;
  purchase_date: string;
  store_name: string;
}


export interface ItemPurchaseHistoryEntry {
  id: number;
  store_name: string;
  purchase_date: string;
  quantity: number;
  unit: string;
  price?: number;
  unit_price?: number;
  raw_text?: string;
}

export interface ItemConsumptionRhythm {
  daily_rate: number;
  avg_purchase_interval_days?: number;
  days_left?: number;
  runout_date?: string;
  burn_rate_weekly: number;
}

export interface ItemDetails {
  item: CanonicalItem;
  active_inventory?: InventoryItem;
  consumption_rhythm: ItemConsumptionRhythm;
  purchase_history: ItemPurchaseHistoryEntry[];
  aliases: ItemAlias[];
}
