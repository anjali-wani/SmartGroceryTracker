from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Enum as SQLEnum,
    Text
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class InventoryStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    SPOILED = "SPOILED"
    ADJUSTED = "ADJUSTED"


class Item(Base):
    """Canonical grocery items with standard attributes."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    standard_unit = Column(String(50), nullable=False, default="count")
    default_shelf_life_days = Column(Integer, nullable=False, default=7)
    is_bulk = Column(Boolean, default=False)
    
    # Phase 3 Fields
    is_active = Column(Boolean, default=True, index=True)  # Soft-archiving
    reorder_cadence_days = Column(Integer, nullable=True)   # Periodic modulo scheduler (e.g. 7, 14, 30)
    preferred_store = Column(String(100), nullable=True)     # Store routing
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    aliases = relationship("ItemAlias", back_populates="item", cascade="all, delete-orphan")
    purchases = relationship("PurchaseLog", back_populates="item")
    inventory_entries = relationship("Inventory", back_populates="item", cascade="all, delete-orphan")
    list_entries = relationship("GroceryListEntry", back_populates="item")


class ItemAlias(Base):
    """Known aliases and store-specific product names mapped to canonical items."""
    __tablename__ = "item_aliases"

    id = Column(Integer, primary_key=True, index=True)
    canonical_item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    raw_alias = Column(String(255), unique=True, nullable=False, index=True)
    match_confidence = Column(Float, default=1.0)
    source = Column(String(100), default="system_seed")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    item = relationship("Item", back_populates="aliases")


class Household(Base):
    """Household profile for velocity modeling and DRI targets."""
    __tablename__ = "household"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, default="My Household")
    member_count = Column(Integer, default=2)
    postal_code = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    purchases = relationship("PurchaseLog", back_populates="household")
    inventory_items = relationship("Inventory", back_populates="household")
    guest_events = relationship("GuestEvent", back_populates="household")
    grocery_list_entries = relationship("GroceryListEntry", back_populates="household")


class PurchaseLog(Base):
    """Historical transaction line items parsed from receipts/bills."""
    __tablename__ = "purchase_logs"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("household.id"), nullable=False, default=1)
    purchase_date = Column(Date, nullable=False, index=True)
    store_name = Column(String(100), default="Grocery Store")
    raw_text = Column(String(500), nullable=False)
    canonical_item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    quantity = Column(Float, default=1.0)
    unit = Column(String(50), default="count")
    price = Column(Float, nullable=True)
    matched_via = Column(String(50), default="exact")
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="purchases")
    item = relationship("Item", back_populates="purchases")


class Inventory(Base):
    """Current active stock in pantry, fridge, or freezer."""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("household.id"), nullable=False, default=1)
    canonical_item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    purchase_log_id = Column(Integer, ForeignKey("purchase_logs.id", ondelete="SET NULL"), nullable=True)
    current_quantity = Column(Float, default=1.0)
    unit = Column(String(50), default="count")
    purchase_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=True)
    status = Column(SQLEnum(InventoryStatus), default=InventoryStatus.ACTIVE, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="inventory_items")
    item = relationship("Item", back_populates="inventory_entries")


class GuestEvent(Base):
    """Guest events to adjust consumption baseline."""
    __tablename__ = "guest_events"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("household.id"), nullable=False, default=1)
    event_date = Column(Date, nullable=False)
    guest_count = Column(Integer, default=1)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="guest_events")


class GroceryListEntry(Base):
    """Generated and custom shopping list items."""
    __tablename__ = "grocery_list_entries"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("household.id"), nullable=False, default=1)
    canonical_item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    custom_item_name = Column(String(255), nullable=True)
    category = Column(String(100), default="General")
    target_store = Column(String(100), default="Any Store")
    recommended_quantity = Column(Float, default=1.0)
    unit = Column(String(50), default="count")
    estimated_cost = Column(Float, nullable=True)
    priority_reason = Column(String(50), default="RUNNING_LOW")  # CRITICAL_DEPLETION, RUNNING_LOW, EXPIRING_SOON, SCHEDULED_CADENCE, MANUAL
    is_checked = Column(Boolean, default=False)
    estimated_runout_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="grocery_list_entries")
    item = relationship("Item", back_populates="list_entries")
