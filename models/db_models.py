"""
SQLAlchemy ORM models for the Automotive Workshop Command Center.
All JSON fields are stored as TEXT and serialised/deserialised in the service layer.
"""
import json
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import relationship

from core.database import Base


# ─── Status string constants (used across services/routers) ──────────────────

class TicketStatus:
    DRAFT_ESTIMATE = "DRAFT_ESTIMATE"
    PENDING_MECHANIC_APPROVAL = "PENDING_MECHANIC_APPROVAL"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BillStatus:
    DRAFT_AI = "DRAFT_AI"
    MATH_ERROR = "MATH_ERROR"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class MarketingTaskStatus:
    PENDING_ADMIN_APPROVAL = "PENDING_ADMIN_APPROVAL"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    REJECTED = "REJECTED"


# ─── Module 3: Customer & Vehicle 360° ───────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    line_id = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicles = relationship("Vehicle", back_populates="customer", lazy="select")
    marketing_tasks = relationship("MarketingTask", back_populates="customer", lazy="select")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate = Column(String(50), unique=True, nullable=False, index=True)
    brand = Column(String(100), nullable=False)           # e.g. Toyota
    model = Column(String(100), nullable=False)           # e.g. Camry
    submodel = Column(String(100), nullable=True)         # e.g. 2.5 Hybrid, 1.6 Turbo
    year = Column(Integer, nullable=True)                 # e.g. 2020
    color = Column(String(50), nullable=True)             # e.g. ขาว
    engine_size = Column(String(30), nullable=True)       # e.g. 2.5L, 1600cc
    fuel_type = Column(String(30), nullable=True)         # เบนซิน | ดีเซล | ไฮบริด | EV | LPG
    transmission = Column(String(30), nullable=True)      # อัตโนมัติ | ธรรมดา | CVT
    current_mileage = Column(Integer, default=0)
    last_service_date = Column(DateTime, nullable=True)

    # Maintenance tracking fields
    last_oil_change_date = Column(DateTime, nullable=True)
    last_oil_change_mileage = Column(Integer, nullable=True)
    last_battery_date = Column(DateTime, nullable=True)
    last_tire_change_mileage = Column(Integer, nullable=True)

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    customer = relationship("Customer", back_populates="vehicles")
    health_watchlist = relationship(
        "VehicleHealthWatchlist", back_populates="vehicle", lazy="select",
        cascade="all, delete-orphan",
    )
    tickets = relationship("ServiceTicket", back_populates="vehicle", lazy="select")
    marketing_tasks = relationship("MarketingTask", back_populates="vehicle", lazy="select")


class VehicleHealthWatchlist(Base):
    __tablename__ = "vehicle_health_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    component = Column(String(100), nullable=False)
    condition = Column(String(255), nullable=False)
    next_due_mileage = Column(Integer, nullable=True)
    next_due_date = Column(DateTime, nullable=True)
    is_overdue = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="health_watchlist")


# ─── Parts catalog ────────────────────────────────────────────────────────────

class PartsCatalog(Base):
    __tablename__ = "parts_catalog"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    name_th = Column(String(200), nullable=True)
    unit_price = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    is_heavy_repair = Column(Boolean, default=False)


class StockItem(Base):
    __tablename__ = "stock_items"
    id = Column(Integer, primary_key=True, index=True)
    name_th = Column(String(200), nullable=False)        # Thai name
    name_en = Column(String(200), nullable=True)         # English name
    sku = Column(String(100), nullable=True, unique=True) # Part code
    category = Column(String(100), nullable=False)        # e.g. 'น้ำมันเครื่อง'
    quantity = Column(Integer, default=0)
    unit_cost = Column(Float, default=0.0)               # What shop pays
    sell_price = Column(Float, default=0.0)              # What customer pays
    reorder_level = Column(Integer, default=5)           # Alert when below this
    image_filename = Column(String(255), nullable=True)  # File in static/images/parts/
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True, index=True)
    vehicle_plate = Column(String(50), nullable=True)
    vehicle_brand = Column(String(100), nullable=True)
    vehicle_model = Column(String(100), nullable=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    mechanic_name = Column(String(200), nullable=False)
    work_date = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)            # Free text of what was done
    line_items = Column(Text, nullable=True)             # JSON: [{name, qty, unit_price, total, stock_item_id}]
    labor_cost = Column(Float, default=0.0)
    parts_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    mileage = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)


# ─── Module 1: Service Tickets ────────────────────────────────────────────────

class ServiceTicket(Base):
    __tablename__ = "service_tickets"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    raw_input = Column(Text, nullable=False)
    # JSON-encoded lists stored as text
    extracted_symptoms = Column(Text, nullable=True)   # List[str]
    diagnosed_issues = Column(Text, nullable=True)     # List[{symptom, issue, severity}]
    line_items = Column(Text, nullable=True)           # List[{name, name_th, qty, unit_price, total, type}]

    estimated_labor_cost = Column(Float, default=0.0)
    estimated_parts_cost = Column(Float, default=0.0)
    total_estimated_cost = Column(Float, default=0.0)
    requires_heavy_repair = Column(Boolean, default=False)

    status = Column(String(50), default=TicketStatus.DRAFT_ESTIMATE)
    mechanic_notes = Column(Text, nullable=True)
    approved_by = Column(String(200), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    final_cost = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="tickets")
    customer = relationship("Customer")

    # ── JSON helpers ──────────────────────────────────────────────────────────
    def get_symptoms(self) -> list:
        return json.loads(self.extracted_symptoms) if self.extracted_symptoms else []

    def get_diagnosed_issues(self) -> list:
        return json.loads(self.diagnosed_issues) if self.diagnosed_issues else []

    def get_line_items(self) -> list:
        return json.loads(self.line_items) if self.line_items else []


# ─── Module 2: Finance & Billing ─────────────────────────────────────────────

class FinanceBill(Base):
    __tablename__ = "finance_bills"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(20), nullable=False)   # 'text' | 'image_png' | 'image_jpg'
    raw_input = Column(Text, nullable=True)
    extracted_items = Column(Text, nullable=True)      # List[{name, qty, unit_price, total}]

    extracted_total = Column(Float, nullable=True)
    calculated_total = Column(Float, nullable=True)
    math_verified = Column(Boolean, default=False)
    math_discrepancy = Column(Float, default=0.0)

    status = Column(String(30), default=BillStatus.DRAFT_AI)
    bill_date = Column(DateTime, nullable=True)
    vendor_name = Column(String(200), nullable=True)
    bill_type = Column(String(20), default="expense")  # 'income' | 'expense'

    confirmed_by = Column(String(200), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ledger_entries = relationship("LedgerEntry", back_populates="bill", lazy="select")

    def get_items(self) -> list:
        return json.loads(self.extracted_items) if self.extracted_items else []


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("finance_bills.id"), nullable=True)
    entry_type = Column(String(20), nullable=False)    # 'income' | 'expense'
    category = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    entry_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    bill = relationship("FinanceBill", back_populates="ledger_entries")


# ─── Module 4: Marketing & Retention ─────────────────────────────────────────

class MarketingTask(Base):
    __tablename__ = "marketing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    trigger_type = Column(String(50), nullable=False)
    # 'oil_overdue' | 'battery_overdue' | 'tire_overdue' | 'churn_risk'

    draft_message = Column(Text, nullable=False)
    voucher_code = Column(String(50), nullable=True)
    discount_amount = Column(Float, nullable=True)

    status = Column(String(50), default=MarketingTaskStatus.PENDING_ADMIN_APPROVAL)
    approved_by = Column(String(200), nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    line_message_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="marketing_tasks")
    vehicle = relationship("Vehicle", back_populates="marketing_tasks")


# ─── Module 5: Supplier Directory ─────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    line_id = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    purchase_bills = relationship("PurchaseBill", back_populates="supplier", lazy="select")


class PurchaseBill(Base):
    __tablename__ = "purchase_bills"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    bill_number = Column(String(100), nullable=True)
    bill_date = Column(DateTime, default=datetime.utcnow)
    items = Column(Text, nullable=True)          # JSON: [{name, qty, unit_price, total}]
    total_amount = Column(Float, default=0.0)
    image_path = Column(String(500), nullable=True)  # Scanned bill image
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="purchase_bills")

    def get_items(self) -> list:
        return json.loads(self.items) if self.items else []


# ─── Stock Change History ─────────────────────────────────────────────────────

class StockHistory(Base):
    __tablename__ = "stock_history"

    id = Column(Integer, primary_key=True, index=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"), nullable=False)
    change_type = Column(String(50), nullable=False)  # 'adjust', 'repair_use', 'purchase', 'sale'
    delta = Column(Integer, nullable=False)            # +/- quantity change
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    changed_by = Column(String(200), default="ระบบ")
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Appointments (Calendar) ─────────────────────────────────────────────────

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    vehicle_plate = Column(String(50), nullable=True)
    vehicle_info = Column(String(200), nullable=True)     # e.g. "Toyota Camry"
    appointment_date = Column(DateTime, nullable=False)
    time_slot = Column(String(20), nullable=True)          # e.g. "09:00"
    service_type = Column(String(200), nullable=True)      # e.g. "เปลี่ยนน้ำมันเครื่อง"
    notes = Column(Text, nullable=True)
    status = Column(String(30), default="confirmed")       # confirmed / pending / cancelled / completed
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Expenses (Utility bills etc.) ────────────────────────────────────────────

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)         # ค่าไฟ, ค่าน้ำ, ค่าเช่า, อื่นๆ
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)
    expense_date = Column(DateTime, default=datetime.utcnow)
    image_path = Column(String(500), nullable=True)        # Bill image
    added_by = Column(String(200), default="ระบบ")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
