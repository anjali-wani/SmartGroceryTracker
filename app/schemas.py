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
    matched_via: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryOut(BaseModel):
    id: int
    canonical_item_id: int
    item_name: Optional[str] = None
    category: Optional[str] = None
    current_quantity: float
    unit: str
    purchase_date: date
    expiration_date: Optional[date]
    status: InventoryStatus

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


class ExpiringItemOut(BaseModel):
    inventory_id: int
    canonical_item_id: int
    item_name: str
    category: str
    current_quantity: float
    unit: str
    purchase_date: date
    expiration_date: date
    days_until_expiration: int


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
    estimated_days_remaining: Optional[float]  # stock / daily_velocity
    lookback_days: int  # 30 for standard, 180 for bulk
    purchase_count: int
    confidence: str  # "high", "moderate", "cold_start"
    last_purchased: Optional[date]


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


class GroceryListResponse(BaseModel):
    household_id: int
    forecast_days: int
    generated_date: date
    total_items: int
    total_estimated_cost: float
    items: List[GroceryListItemOut]
    items_by_store: dict
    items_by_category: dict
