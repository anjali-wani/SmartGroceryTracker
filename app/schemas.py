from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models import InventoryStatus


class ItemBase(BaseModel):
    canonical_name: str
    category: str
    standard_unit: str = "count"
    default_shelf_life_days: int = 7
    is_bulk: bool = False
    is_grocery: bool = True
    default_unit_price: Optional[float] = None
    preferred_store: Optional[str] = None


class ItemCreate(ItemBase):
    pass


class ItemAliasOut(BaseModel):
    id: int
    raw_alias: str
    match_confidence: float
    source: str

    model_config = ConfigDict(from_attributes=True)


class ItemOut(ItemBase):
    id: int
    created_at: datetime
    aliases: List[ItemAliasOut] = []

    model_config = ConfigDict(from_attributes=True)


class PurchaseLogOut(BaseModel):
    id: int
    household_id: int
    purchase_date: date
    store_name: str
    raw_text: str
    canonical_item_id: Optional[int]
    quantity: float
    unit: str
    price: Optional[float]
    unit_price: Optional[float] = None
    matched_via: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryOut(BaseModel):
    id: int
    household_id: int
    canonical_item_id: int
    item_name: Optional[str] = None
    category: Optional[str] = None
    current_quantity: float
    unit: str
    purchase_date: date
    status: InventoryStatus
    store_name: Optional[str] = None
    price: Optional[float] = None
    unit_price: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ProcessedLineItem(BaseModel):
    raw_line: str
    clean_name: str
    canonical_name: Optional[str]
    category: Optional[str]
    quantity: float
    unit: str
    price: Optional[float]
    matched_via: str
    confidence: float
    status: str


class CSVUploadSummary(BaseModel):
    store_name: str
    purchase_date: date
    total_rows: int
    matched_rows: int
    unresolved_rows: int
    total_amount: float
    bill_id: Optional[int] = None
    processed_items: List[ProcessedLineItem]


# --- Phase 2 Schemas ---

class InventoryAdjustRequest(BaseModel):
    inventory_id: int
    new_quantity: Optional[float] = None
    status: Optional[InventoryStatus] = None  # e.g. SPOILED, CONSUMED, ADJUSTED
    reason: Optional[str] = None  # "spoiled", "dining_out", "manual_correction"
    notes: Optional[str] = None


class InventoryAdjustResponse(BaseModel):
    id: int
    canonical_item_id: int
    item_name: str
    previous_quantity: float
    current_quantity: float
    unit: str
    status: InventoryStatus
    adjusted_at: datetime


class GuestEventCreate(BaseModel):
    event_date: date
    guest_count: int = 1
    notes: Optional[str] = None


class GuestEventOut(BaseModel):
    id: int
    household_id: int
    event_date: date
    guest_count: int
    notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemVelocityOut(BaseModel):
    canonical_item_id: int
    item_name: str
    category: str
    is_bulk: bool
    daily_velocity: float  # units consumed per day
    per_capita_velocity: float  # units per person per day
    current_stock: float
    unit: str
    estimated_days_remaining: Optional[float] = None  # days until projected runout
    lookback_days: int  # 30 for standard, 180 for bulk
    purchase_count: int
    confidence: str  # "high", "moderate", "cold_start"
    last_purchased: Optional[date] = None
    avg_purchase_interval_days: Optional[float] = None
    days_per_unit: Optional[float] = None  # empirical days 1 unit lasts (e.g. 14 days/lb)
    modal_quantity: Optional[float] = None  # most frequent purchase quantity
    projected_runout_date: Optional[date] = None
    needs_availability_check: bool = False
    prompt_message: Optional[str] = None


class HouseholdVelocityReport(BaseModel):
    household_id: int
    total_tracked_items: int
    household_members: int
    report_date: date
    items: List[ItemVelocityOut]


# --- Phase 3 Schemas ---

class ItemScheduleUpdate(BaseModel):
    reorder_cadence_days: Optional[int] = None
    preferred_store: Optional[str] = None
    default_unit_price: Optional[float] = None


class ItemArchiveResponse(BaseModel):
    id: int
    canonical_name: str
    is_active: bool
    message: str


class ManualListItemCreate(BaseModel):
    item_name: str
    quantity: float = 1.0
    unit: str = "count"
    category: Optional[str] = "General"
    target_store: Optional[str] = "Any Store"


class GroceryListItemOut(BaseModel):
    id: int
    canonical_item_id: Optional[int] = None
    item_name: str
    category: str
    target_store: str
    recommended_quantity: float
    unit: str
    estimated_cost: Optional[float] = None
    priority_reason: str
    is_checked: bool
    estimated_runout_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class AvailabilityPrompt(BaseModel):
    canonical_item_id: int
    item_name: str
    category: str
    last_purchased: date
    last_quantity: float
    unit: str
    message: str


class GroceryListResponse(BaseModel):
    household_id: int
    forecast_days: int
    generated_date: date
    total_items: int
    total_estimated_cost: float
    items: List[GroceryListItemOut]
    items_by_store: dict
    items_by_category: dict
    availability_prompts: List[AvailabilityPrompt] = []

class ReceiptUploadOut(BaseModel):
    id: int
    household_id: int
    filename: str
    store_name: str
    bill_date: date
    total_items: int
    total_amount: float
    bill_id: Optional[int] = None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillItemOut(BaseModel):
    id: int
    raw_text: str
    canonical_item_id: Optional[int]
    item_name: str
    category: str
    quantity: float
    unit: str
    price: Optional[float]
    matched_via: str
    confidence: float
    purchase_date: date
    store_name: str

    model_config = ConfigDict(from_attributes=True)


class ItemPurchaseHistoryEntry(BaseModel):
    id: int
    store_name: str
    purchase_date: date
    quantity: float
    unit: str
    price: Optional[float] = None
    unit_price: Optional[float] = None
    raw_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ItemConsumptionRhythm(BaseModel):
    daily_rate: float
    avg_purchase_interval_days: Optional[float] = None
    days_left: Optional[float] = None
    runout_date: Optional[date] = None
    burn_rate_weekly: float


class ItemDetailsOut(BaseModel):
    item: ItemOut
    active_inventory: Optional[InventoryOut] = None
    consumption_rhythm: ItemConsumptionRhythm
    purchase_history: List[ItemPurchaseHistoryEntry]
    aliases: List[ItemAliasOut]
