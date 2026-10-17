"""
Pydantic v2 schemas — request/response contracts for all 4 modules.
All schemas include OpenAPI examples for immediate Swagger UI testing.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import re as _re


def _check_thai_phone(v):
    """Accept Thai numbers like 081-234-5678, 02 894 1234, +66812345678 (9-10 digits)."""
    if v is None:
        return v
    v = v.strip()
    digits = _re.sub(r"[\s\-().]", "", v)
    if digits.startswith("+66"):
        digits = "0" + digits[3:]
    if not _re.fullmatch(r"0\d{8,9}", digits):
        raise ValueError("เบอร์โทรไม่ถูกต้อง (ต้องเป็นตัวเลข 9-10 หลัก เช่น 0812345678)")
    return v


# ─── Status enums (mirrors db_models string constants) ───────────────────────

class TicketStatusEnum(str, Enum):
    DRAFT_ESTIMATE = "DRAFT_ESTIMATE"
    PENDING_MECHANIC_APPROVAL = "PENDING_MECHANIC_APPROVAL"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BillStatusEnum(str, Enum):
    DRAFT_AI = "DRAFT_AI"
    MATH_ERROR = "MATH_ERROR"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class MarketingTaskStatusEnum(str, Enum):
    PENDING_ADMIN_APPROVAL = "PENDING_ADMIN_APPROVAL"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    REJECTED = "REJECTED"


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1: Service & Repair Tickets
# ─────────────────────────────────────────────────────────────────────────────

class TicketIngestRequest(BaseModel):
    raw_input: str = Field(
        ...,
        min_length=5,
        description="Thai text describing symptoms and car info.",
    )
    customer_name: Optional[str] = Field(None, description="Customer name.")
    customer_phone: Optional[str] = Field(None, description="Customer phone for profile lookup.")
    customer_line_id: Optional[str] = Field(None, description="Customer LINE ID.")
    vehicle_plate: Optional[str] = Field(None, description="Vehicle plate for profile lookup.")
    car_model: Optional[str] = Field(None, description="Car make and model.")
    mechanic_name: Optional[str] = Field(None, description="Mechanic assigned to work order.")
    mileage: Optional[int] = Field(None, ge=0, description="Current odometer reading (km).")
    stock_links: Optional[List["StockLinkSchema"]] = Field(
        None, description="Lines picked from stock on the intake form (deducted when the job is completed)."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "raw_input": "รถ Toyota Camry ทะเบียน กข 1234 กรุงเทพ เสียงดังจากเบรคหน้า ผ้าเบรคสึกมาก วิ่งมา 52,000 กม.",
                "customer_name": "สมเกียรติ สว่างวงศ์",
                "customer_phone": "0812345678",
                "vehicle_plate": "กข 1234 กรุงเทพ",
                "car_model": "Toyota Camry 2020",
                "mechanic_name": "ช่างสมชาย",
                "mileage": 52000,
            }
        }
    }


class StockLinkSchema(BaseModel):
    name: str
    stock_item_id: int
    qty: Optional[float] = Field(None, gt=0)


class LineItemSchema(BaseModel):
    name: str
    name_th: Optional[str] = None
    qty: float = 1.0
    unit_price: float
    total: float
    type: Optional[str] = None  # 'part' | 'labor'
    stock_item_id: Optional[int] = None
    stock_deducted: Optional[bool] = None


TicketIngestRequest.model_rebuild()


class DiagnosedIssueSchema(BaseModel):
    symptom: str
    issue: str
    severity: str


class TicketResponse(BaseModel):
    id: int
    vehicle_plate: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_line_id: Optional[str] = None
    car_model: Optional[str] = None
    mileage: Optional[int] = None
    mechanic_name: Optional[str] = None
    raw_input: str
    extracted_symptoms: List[str] = []
    diagnosed_issues: List[DiagnosedIssueSchema] = []
    line_items: List[LineItemSchema] = []
    estimated_labor_cost: float
    estimated_parts_cost: float
    total_estimated_cost: float
    requires_heavy_repair: bool
    status: TicketStatusEnum
    guardrail_reason: Optional[str] = None
    mechanic_notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    final_cost: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Payments
    amount_due: float = 0.0
    amount_paid: float = 0.0
    balance_due: float = 0.0
    payment_status: str = "unpaid"   # 'unpaid' | 'partial' | 'paid' | 'none'

    # Customer approval through LINE link
    customer_decision: Optional[str] = None
    customer_decision_at: Optional[datetime] = None
    customer_decision_note: Optional[str] = None
    approval_link_sent: bool = False

    # Warranty
    warranty_months: Optional[int] = None
    warranty_note: Optional[str] = None
    warranty_until: Optional[datetime] = None

    photos: List[dict] = []

    model_config = {"from_attributes": True}


class TicketApproveRequest(BaseModel):
    approved_by: str = Field(..., min_length=2, description="Name/ID of the mechanic or admin approving.")
    mechanic_notes: Optional[str] = Field(None, description="Mechanic's remarks after physical inspection.")
    final_cost: Optional[float] = Field(None, ge=0, description="Adjusted final cost (leave None to keep estimate).")
    adjusted_line_items: Optional[List[LineItemSchema]] = Field(
        None, description="Override line items if prices were adjusted."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "approved_by": "ช่างสมศักดิ์",
                "mechanic_notes": "ตรวจแล้ว ผ้าเบรคสึกจริง ราคาตามประเมิน อนุมัติดำเนินการได้",
                "final_cost": 3740.0,
            }
        }
    }


class TicketCompleteRequest(BaseModel):
    completed_by: Optional[str] = Field("ช่างประจำ", description="Name of mechanic or cashier closing work.")
    final_cost: Optional[float] = Field(None, ge=0, description="Final confirmed cost.")
    completion_notes: Optional[str] = Field(None, description="Remarks on completed work.")
    warranty_months: Optional[int] = Field(None, ge=0, le=120, description="Warranty given on this job (months).")
    warranty_note: Optional[str] = Field(None, max_length=300, description="What the warranty covers.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "completed_by": "ช่างสมชาย",
                "final_cost": 3740.0,
                "completion_notes": "ซ่อมบำรุงและทดสอบระบบเรียบร้อย พร้อมส่งมอบรถ",
            }
        }
    }


class TicketUpdateRequest(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_line_id: Optional[str] = None
    vehicle_plate: Optional[str] = None
    car_model: Optional[str] = None
    mileage: Optional[int] = None
    mechanic_name: Optional[str] = None
    status: Optional[TicketStatusEnum] = None
    raw_input: Optional[str] = None
    extracted_symptoms: Optional[List[str]] = None
    line_items: Optional[List[LineItemSchema]] = None
    estimated_labor_cost: Optional[float] = None
    estimated_parts_cost: Optional[float] = None
    total_estimated_cost: Optional[float] = None
    final_cost: Optional[float] = None
    mechanic_notes: Optional[str] = None
    warranty_months: Optional[int] = Field(None, ge=0, le=120)
    warranty_note: Optional[str] = Field(None, max_length=300)


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    method: str = Field("เงินสด", max_length=30)
    note: Optional[str] = Field(None, max_length=300)
    received_by: Optional[str] = Field(None, max_length=200)
    paid_at: Optional[datetime] = None


class QuoteDecision(BaseModel):
    decision: str = Field(..., pattern="^(approve|decline)$")
    note: Optional[str] = Field(None, max_length=500)


class TicketListResponse(BaseModel):
    total: int
    items: List[TicketResponse]


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2: Finance & Billing
# ─────────────────────────────────────────────────────────────────────────────

class BillLineItemSchema(BaseModel):
    name: str
    qty: float = 1.0
    unit_price: float
    total: float


class BillParseTextRequest(BaseModel):
    raw_text: str = Field(..., min_length=10, description="Raw bill/receipt text in Thai or English.")
    bill_type: str = Field(default="expense", pattern="^(income|expense)$")
    vendor_name: Optional[str] = Field(None, description="Override vendor name if known.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "raw_text": (
                    "ร้านอะไหล่มีสุข\n"
                    "น้ำมันเครื่อง 5W-30 10 ลิตร ราคา 850 บาท/ลิตร รวม 8,500 บาท\n"
                    "กรองน้ำมัน 5 ชิ้น ราคา 150 บาท/ชิ้น รวม 750 บาท\n"
                    "ยอดรวมทั้งหมด 9,250 บาท"
                ),
                "bill_type": "expense",
                "vendor_name": "ร้านอะไหล่มีสุข",
            }
        }
    }


class BillResponse(BaseModel):
    id: int
    source_type: str
    vendor_name: Optional[str] = None
    bill_type: str
    line_items: List[BillLineItemSchema] = []
    extracted_total: Optional[float] = None
    calculated_total: Optional[float] = None
    math_verified: bool
    math_discrepancy: float
    status: BillStatusEnum
    math_check_detail: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BillConfirmRequest(BaseModel):
    confirmed_by: str = Field(..., min_length=2)
    notes: Optional[str] = None
    corrected_items: Optional[List[BillLineItemSchema]] = Field(
        None, description="Staff-corrected line items. If None, original AI-extracted items are used."
    )
    corrected_total: Optional[float] = Field(
        None, ge=0, description="Staff-corrected total. If None, calculated_total is used."
    )
    entry_date: Optional[datetime] = Field(None, description="Ledger entry date. Defaults to today.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "confirmed_by": "ผู้จัดการสาขา",
                "notes": "ตรวจสอบใบเสร็จต้นฉบับแล้ว ตัวเลขถูกต้อง",
            }
        }
    }


class LedgerEntrySchema(BaseModel):
    id: int
    entry_type: str
    category: str
    amount: float
    description: Optional[str] = None
    entry_date: datetime

    model_config = {"from_attributes": True}


class PLInsight(BaseModel):
    period: str
    total_income: float
    total_expense: float
    net_profit: float
    profit_margin_pct: float
    income_breakdown: Dict[str, float]
    expense_breakdown: Dict[str, float]
    top_income_source: str
    top_expense_source: str
    ai_insights: str
    mom_comparison: Optional[str] = None


class FinanceSummaryResponse(BaseModel):
    year: int
    month: int
    period_label: str
    summary: PLInsight
    ledger_entry_count: int


class BillListResponse(BaseModel):
    total: int
    items: List[BillResponse]


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3: Customer & Vehicle 360°
# ─────────────────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, description="ชื่อลูกค้า")
    phone: str = Field(..., min_length=3, description="เบอร์โทรศัพท์")
    line_id: Optional[str] = Field(None, description="LINE ID เช่น sommai_j, @garage")
    email: Optional[str] = Field(None, description="อีเมล")
    plate: Optional[str] = Field(None, description="ทะเบียนรถเริ่มต้น (ถ้ามี)")
    brand: Optional[str] = Field(None, description="ยี่ห้อรถ เช่น Toyota, Honda")
    model: Optional[str] = Field(None, description="รุ่นรถ เช่น Camry, Civic")
    year: Optional[int] = Field(None, description="ปี ค.ศ.")
    mileage: Optional[int] = Field(None, ge=0, description="เลขไมล์ปัจจุบัน (กม.)")

    _phone_ok = field_validator("phone")(_check_thai_phone)

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "สมหมาย ใจดี",
                "phone": "0891234567",
                "line_id": "sommai_j",
                "email": "sommai@email.com",
            }
        }
    }


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    line_id: Optional[str] = None
    email: Optional[str] = None

    _phone_ok = field_validator("phone")(_check_thai_phone)


class CustomerResponse(BaseModel):
    id: int
    name: str
    phone: str
    line_id: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthWatchlistItemSchema(BaseModel):
    id: int
    component: str
    condition: str
    next_due_mileage: Optional[int] = None
    next_due_date: Optional[datetime] = None
    is_overdue: bool
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class VehicleCreate(BaseModel):
    plate: str = Field(..., min_length=2, description="Thai vehicle plate number.")
    brand: Optional[str] = "Toyota"
    model: Optional[str] = "รถยนต์"
    year: Optional[int] = Field(None, ge=1980, le=2035)
    color: Optional[str] = None
    current_mileage: int = Field(default=0, ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "plate": "ดต 7890 กรุงเทพ",
                "brand": "Toyota",
                "model": "Yaris Cross",
                "year": 2023,
                "color": "ขาว",
                "current_mileage": 5000,
            }
        }
    }


class VehicleMileageUpdate(BaseModel):
    current_mileage: int = Field(..., ge=0)
    last_service_date: Optional[datetime] = None
    last_oil_change_date: Optional[datetime] = None
    last_oil_change_mileage: Optional[int] = None
    last_battery_date: Optional[datetime] = None
    last_tire_change_mileage: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "current_mileage": 55000,
                "last_oil_change_date": "2026-08-25T10:00:00",
                "last_oil_change_mileage": 55000,
            }
        }
    }


class VehicleResponse(BaseModel):
    id: int
    plate: str
    brand: str
    model: str
    year: Optional[int] = None
    color: Optional[str] = None
    current_mileage: int
    last_service_date: Optional[datetime] = None
    last_oil_change_date: Optional[datetime] = None
    last_oil_change_mileage: Optional[int] = None
    last_battery_date: Optional[datetime] = None
    last_tire_change_mileage: Optional[int] = None
    customer_id: int
    health_watchlist: List[HealthWatchlistItemSchema] = []

    model_config = {"from_attributes": True}


class Customer360Profile(BaseModel):
    customer: CustomerResponse
    vehicles: List[VehicleResponse]
    ticket_history: List[TicketResponse]
    total_spent: float
    total_visits: int
    last_visit_date: Optional[datetime]
    customer_segment: str   # 'VIP' | 'Regular' | 'At Risk' | 'Churned'
    health_alerts: List[HealthWatchlistItemSchema]


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4: Marketing & Retention Engine
# ─────────────────────────────────────────────────────────────────────────────

class MarketingTriggerResponse(BaseModel):
    run_id: str
    scan_date: str
    total_flagged: int
    tasks_generated: int
    trigger_breakdown: Dict[str, int]
    task_ids: List[int]


class MarketingTaskResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    vehicle_plate: Optional[str] = None
    trigger_type: str
    draft_message: str
    voucher_code: Optional[str] = None
    discount_amount: Optional[float] = None
    status: MarketingTaskStatusEnum
    approved_by: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    line_message_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MarketingApproveRequest(BaseModel):
    approved_by: str = Field(..., min_length=2)
    edited_message: Optional[str] = Field(
        None, description="Staff-edited message. If None, draft_message is dispatched as-is."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "approved_by": "ผู้จัดการ",
                "edited_message": None,
            }
        }
    }


class MarketingRejectRequest(BaseModel):
    rejected_by: str = Field(..., min_length=2)
    reason: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "rejected_by": "ผู้จัดการ",
                "reason": "ลูกค้าติดต่อมาแล้ว ไม่ต้องส่งข้อความ",
            }
        }
    }


class MarketingTaskListResponse(BaseModel):
    total: int
    pending: int
    items: List[MarketingTaskResponse]
