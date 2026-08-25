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
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)
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
