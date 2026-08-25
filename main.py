"""
Automotive Workshop Command Center — Main Entry Point
═══════════════════════════════════════════════════════
R.O.S.E. Framework: Router · Orchestrator · Shared State · Execution & Guardrails
Built with FastAPI + LangGraph + Pydantic + SQLite

Run:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, SessionLocal, engine
from models.db_models import (
    BillStatus, Customer, FinanceBill, LedgerEntry,
    MarketingTask, PartsCatalog, ServiceTicket, TicketStatus,
    Vehicle, VehicleHealthWatchlist,
)
from routers import customers, finance, marketing, tickets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workshop")


# ─── Seed Data ────────────────────────────────────────────────────────────────

def _seed(db):
    """Idempotent seed — skips if data already exists."""
    if db.query(Customer).count() > 0:
        logger.info("Database already seeded — skipping.")
        return

    logger.info("Seeding database with demo data…")
    now = datetime.utcnow()

    # ── Customers ─────────────────────────────────────────────────────────────
    c1 = Customer(name="สมชาย มีสุข",   phone="0812345678", line_id="somchai_m",   email="somchai@email.com")
    c2 = Customer(name="นภาพร จันทร์ดี", phone="0898765432", line_id="naphaporn_j", email="naphaporn@email.com")
    c3 = Customer(name="วิชัย ทองคำ",   phone="0856781234", line_id="wichai_t",     email="wichai@email.com")
    db.add_all([c1, c2, c3])
    db.commit()
    for c in [c1, c2, c3]:
        db.refresh(c)

    # ── Vehicles ──────────────────────────────────────────────────────────────
    v1 = Vehicle(
        plate="กข 1234 กรุงเทพ", brand="Toyota", model="Camry",    year=2020, color="ขาว",
        current_mileage=52000, customer_id=c1.id,
        last_service_date=now - timedelta(days=200),
        last_oil_change_date=now - timedelta(days=210),   # >6 months → oil_overdue
        last_oil_change_mileage=42000,                    # 10k delta → oil_overdue
        last_battery_date=now - timedelta(days=800),      # >2 years  → battery_overdue
        last_tire_change_mileage=10000,                   # 42k delta → tire_overdue
    )
    v2 = Vehicle(
        plate="คง 5678 เชียงใหม่", brand="Honda",  model="PCX 150",  year=2022, color="แดง",
        current_mileage=8500, customer_id=c2.id,
        last_service_date=now - timedelta(days=30),
        last_oil_change_date=now - timedelta(days=45),
        last_oil_change_mileage=5500,
        last_battery_date=now - timedelta(days=300),
        last_tire_change_mileage=5000,
    )
    v3 = Vehicle(
        plate="จฉ 9012 ขอนแก่น", brand="Isuzu",  model="D-Max",    year=2019, color="เทา",
        current_mileage=87000, customer_id=c3.id,
        last_service_date=now - timedelta(days=195),      # ~6.5 months → churn_risk candidate
        last_oil_change_date=now - timedelta(days=185),
        last_oil_change_mileage=77000,                    # 10k delta → oil_overdue
        last_battery_date=now - timedelta(days=550),
        last_tire_change_mileage=45000,                   # 42k delta → tire_overdue
    )
    v4 = Vehicle(
        plate="ชซ 3456 กรุงเทพ",  brand="Mazda",  model="2",        year=2021, color="น้ำเงิน",
        current_mileage=25000, customer_id=c1.id,
        last_service_date=now - timedelta(days=90),
        last_oil_change_date=now - timedelta(days=95),
        last_oil_change_mileage=18000,
        last_battery_date=now - timedelta(days=400),
        last_tire_change_mileage=20000,
    )
    db.add_all([v1, v2, v3, v4])
    db.commit()
    for v in [v1, v2, v3, v4]:
        db.refresh(v)

    # ── Parts Catalog ─────────────────────────────────────────────────────────
    parts = [
        PartsCatalog(name="Engine Oil 5W-30 (4L)",  name_th="น้ำมันเครื่อง 5W-30",       unit_price=850.0,  category="consumable", is_heavy_repair=False),
        PartsCatalog(name="Oil Filter",              name_th="กรองน้ำมันเครื่อง",         unit_price=150.0,  category="filter",     is_heavy_repair=False),
        PartsCatalog(name="Air Filter",              name_th="กรองอากาศ",                 unit_price=350.0,  category="filter",     is_heavy_repair=False),
        PartsCatalog(name="Spark Plug (4 pcs)",      name_th="หัวเทียน (4 ชิ้น)",         unit_price=480.0,  category="ignition",   is_heavy_repair=False),
        PartsCatalog(name="Brake Pad (Front)",       name_th="ผ้าเบรคหน้า",              unit_price=1200.0, category="brake",      is_heavy_repair=False),
        PartsCatalog(name="Brake Pad (Rear)",        name_th="ผ้าเบรคหลัง",              unit_price=950.0,  category="brake",      is_heavy_repair=False),
        PartsCatalog(name="Brake Fluid",             name_th="น้ำมันเบรค",               unit_price=120.0,  category="fluid",      is_heavy_repair=False),
        PartsCatalog(name="Car Battery 75Ah",        name_th="แบตเตอรี่รถยนต์ 75Ah",    unit_price=3200.0, category="electrical", is_heavy_repair=False),
        PartsCatalog(name="Tire (195/65R15)",        name_th="ยางรถยนต์ 195/65R15",      unit_price=2800.0, category="tire",       is_heavy_repair=False),
        PartsCatalog(name="Transmission Fluid",      name_th="น้ำมันเกียร์",             unit_price=620.0,  category="fluid",      is_heavy_repair=True),
        PartsCatalog(name="Timing Belt",             name_th="สายพานราวลิ้น",           unit_price=1800.0, category="engine",     is_heavy_repair=True),
        PartsCatalog(name="Radiator",                name_th="หม้อน้ำรถยนต์",           unit_price=5500.0, category="cooling",    is_heavy_repair=True),
        PartsCatalog(name="Alternator",              name_th="ไดชาร์จ",                 unit_price=4200.0, category="electrical", is_heavy_repair=True),
        PartsCatalog(name="Coolant (1L)",            name_th="น้ำยาหม้อน้ำ",            unit_price=180.0,  category="fluid",      is_heavy_repair=False),
        PartsCatalog(name="Wiper Blade (pair)",      name_th="ใบปัดน้ำฝน (คู่)",        unit_price=280.0,  category="exterior",   is_heavy_repair=False),
    ]
    db.add_all(parts)
    db.commit()

    # ── Vehicle Health Watchlist ───────────────────────────────────────────────
    watchlist = [
        VehicleHealthWatchlist(
            vehicle_id=v1.id, component="น้ำมันเครื่อง",
            condition="เกินกำหนด (>10,000 กม. และ >6 เดือน)",
            next_due_mileage=52000, next_due_date=now - timedelta(days=30),
            is_overdue=True, notes="เปลี่ยนครั้งล่าสุดที่ 42,000 กม. ปัจจุบัน 52,000 กม.",
        ),
        VehicleHealthWatchlist(
            vehicle_id=v1.id, component="แบตเตอรี่",
            condition="เกินกำหนด (ใช้งานมาแล้ว >2 ปี)",
            next_due_mileage=None, next_due_date=now - timedelta(days=70),
            is_overdue=True, notes="ติดตั้งแบตเตอรี่มา 800 วัน",
        ),
        VehicleHealthWatchlist(
            vehicle_id=v1.id, component="ยางรถยนต์",
            condition="เกินกำหนด (>40,000 กม.)",
            next_due_mileage=50000, next_due_date=None,
            is_overdue=True, notes="เปลี่ยนยางที่ 10,000 กม. ปัจจุบัน 52,000 กม.",
        ),
        VehicleHealthWatchlist(
            vehicle_id=v3.id, component="น้ำมันเครื่อง",
            condition="เกินกำหนด (>10,000 กม.)",
            next_due_mileage=87000, next_due_date=now + timedelta(days=14),
            is_overdue=True, notes="เปลี่ยนครั้งล่าสุดที่ 77,000 กม. ปัจจุบัน 87,000 กม.",
        ),
        VehicleHealthWatchlist(
            vehicle_id=v3.id, component="ยางรถยนต์",
            condition="เกินกำหนด (>40,000 กม.)",
            next_due_mileage=85000, next_due_date=None,
            is_overdue=True, notes="เปลี่ยนยางที่ 45,000 กม. ปัจจุบัน 87,000 กม.",
        ),
    ]
    db.add_all(watchlist)
    db.commit()

    # ── Service Tickets ───────────────────────────────────────────────────────
    # Ticket 1: approved (cost within threshold, brake job)
    t1 = ServiceTicket(
        vehicle_id=v1.id, customer_id=c1.id,
        raw_input="รถ Toyota Camry ทะเบียน กข 1234 กรุงเทพ เสียงดังจากเบรคหน้า ผ้าเบรคสึกมาก",
        extracted_symptoms=json.dumps(["เสียงดังจากเบรค", "ผ้าเบรคสึก"], ensure_ascii=False),
        diagnosed_issues=json.dumps([
            {"symptom": "เสียงดังจากเบรค", "issue": "ผ้าเบรคหน้าสึกหรอ", "severity": "high"},
            {"symptom": "ผ้าเบรคสึก",       "issue": "ผ้าเบรคหน้าและหลังสึกหรอ จำเป็นต้องเปลี่ยน", "severity": "high"},
        ], ensure_ascii=False),
        line_items=json.dumps([
            {"name": "Brake Pad (Front)", "name_th": "ผ้าเบรคหน้า",        "qty": 1, "unit_price": 1200.0, "total": 1200.0, "type": "part"},
            {"name": "Brake Pad (Rear)",  "name_th": "ผ้าเบรคหลัง",        "qty": 1, "unit_price": 950.0,  "total": 950.0,  "type": "part"},
            {"name": "Labor - เสียงดังจากเบรค", "name_th": "ค่าแรง (เสียงดังจากเบรค)", "qty": 1, "unit_price": 500.0, "total": 500.0, "type": "labor"},
            {"name": "Labor - ผ้าเบรคสึก",     "name_th": "ค่าแรง (ผ้าเบรคสึก)",     "qty": 1, "unit_price": 800.0, "total": 800.0, "type": "labor"},
        ], ensure_ascii=False),
        estimated_labor_cost=1300.0,
        estimated_parts_cost=2150.0,
        total_estimated_cost=3450.0,
        requires_heavy_repair=False,
        status=TicketStatus.APPROVED,
        mechanic_notes="ตรวจสอบแล้ว ผ้าเบรคสึกจริง อนุมัติดำเนินการได้",
        approved_by="ช่างสมศักดิ์",
        approved_at=now - timedelta(days=5),
        final_cost=3450.0,
    )

    # Ticket 2: pending approval (heavy repair + cost > 3,000 THB)
    t2 = ServiceTicket(
        vehicle_id=v3.id, customer_id=c3.id,
        raw_input="Isuzu D-Max เกียร์สะดุด เกียร์ไม่เข้า ต้องการเปลี่ยนถ่ายน้ำมันเกียร์และตรวจชุดเกียร์",
        extracted_symptoms=json.dumps(["เกียร์สะดุด", "เกียร์ไม่เข้า"], ensure_ascii=False),
        diagnosed_issues=json.dumps([
            {"symptom": "เกียร์สะดุด",  "issue": "น้ำมันเกียร์เสื่อมสภาพ หรือชุดเกียร์มีปัญหา", "severity": "high"},
            {"symptom": "เกียร์ไม่เข้า", "issue": "ชุดเกียร์ต้องตรวจเช็คเชิงลึก",               "severity": "high"},
        ], ensure_ascii=False),
        line_items=json.dumps([
            {"name": "Transmission Fluid", "name_th": "น้ำมันเกียร์",                "qty": 2, "unit_price": 620.0,  "total": 1240.0, "type": "part"},
            {"name": "Labor - เกียร์สะดุด",  "name_th": "ค่าแรง (เกียร์สะดุด)",    "qty": 1, "unit_price": 2500.0, "total": 2500.0, "type": "labor"},
            {"name": "Labor - เกียร์ไม่เข้า","name_th": "ค่าแรง (เกียร์ไม่เข้า)", "qty": 1, "unit_price": 2500.0, "total": 2500.0, "type": "labor"},
        ], ensure_ascii=False),
        estimated_labor_cost=5000.0,
        estimated_parts_cost=1240.0,
        total_estimated_cost=6240.0,
        requires_heavy_repair=True,
        status=TicketStatus.PENDING_MECHANIC_APPROVAL,
    )
    db.add_all([t1, t2])
    db.commit()

    # ── Finance Bills & Ledger ────────────────────────────────────────────────
    b1 = FinanceBill(
        source_type="text",
        raw_input=(
            "ร้านอะไหล่มีสุข\n"
            "น้ำมันเครื่อง 5W-30 10 ลิตร ราคา 850 บาท/ลิตร รวม 8,500 บาท\n"
            "กรองน้ำมัน 5 ชิ้น ราคา 150 บาท/ชิ้น รวม 750 บาท\n"
            "ยอดรวมทั้งหมด 9,250 บาท"
        ),
        extracted_items=json.dumps([
            {"name": "น้ำมันเครื่อง 5W-30", "qty": 10.0, "unit_price": 850.0, "total": 8500.0},
            {"name": "กรองน้ำมัน",          "qty": 5.0,  "unit_price": 150.0, "total": 750.0},
        ], ensure_ascii=False),
        extracted_total=9250.0, calculated_total=9250.0,
        math_verified=True, math_discrepancy=0.0,
        status=BillStatus.CONFIRMED, bill_type="expense",
        vendor_name="ร้านอะไหล่มีสุข",
        bill_date=now - timedelta(days=30),
        confirmed_by="ผู้จัดการ", confirmed_at=now - timedelta(days=29),
    )
    b2 = FinanceBill(
        source_type="text",
        raw_input="รายรับค่าซ่อมรถลูกค้าประจำเดือนกรกฎาคม 2026",
        extracted_items=json.dumps([
            {"name": "ค่าซ่อมรถ Toyota Camry",      "qty": 1.0, "unit_price": 3450.0, "total": 3450.0},
            {"name": "ค่าซ่อมรถ Honda PCX",         "qty": 1.0, "unit_price": 850.0,  "total": 850.0},
            {"name": "ค่าเปลี่ยนน้ำมันเครื่อง x3", "qty": 3.0, "unit_price": 950.0,  "total": 2850.0},
        ], ensure_ascii=False),
        extracted_total=7150.0, calculated_total=7150.0,
        math_verified=True, math_discrepancy=0.0,
        status=BillStatus.CONFIRMED, bill_type="income",
        vendor_name="อู่ซ่อมรถ (รายรับ)",
        bill_date=now - timedelta(days=25),
        confirmed_by="ผู้จัดการ", confirmed_at=now - timedelta(days=24),
    )
    db.add_all([b1, b2])
    db.commit()
    db.refresh(b1)
    db.refresh(b2)

    # ── Ledger Entries — 3 months for P&L demo ────────────────────────────────
    ledger = [
        # June 2026
        LedgerEntry(entry_type="income",  category="repair_service",  amount=52000.0, description="รายรับค่าซ่อมรถเดือนมิถุนายน",    entry_date=datetime(2026, 6, 30)),
        LedgerEntry(entry_type="income",  category="parts_sale",       amount=15000.0, description="รายรับขายอะไหล่เดือนมิถุนายน",    entry_date=datetime(2026, 6, 30)),
        LedgerEntry(entry_type="expense", category="parts_purchase",    amount=22000.0, description="ซื้ออะไหล่เดือนมิถุนายน",          entry_date=datetime(2026, 6, 15)),
        LedgerEntry(entry_type="expense", category="utilities",         amount=4000.0,  description="ค่าไฟฟ้าและน้ำเดือนมิถุนายน",      entry_date=datetime(2026, 6, 5)),
        LedgerEntry(entry_type="expense", category="salary",            amount=25000.0, description="เงินเดือนช่างเดือนมิถุนายน",       entry_date=datetime(2026, 6, 30)),
        # July 2026
        LedgerEntry(entry_type="income",  category="repair_service",  amount=45000.0, description="รายรับค่าซ่อมรถเดือนกรกฎาคม",    entry_date=datetime(2026, 7, 31), bill_id=b2.id),
        LedgerEntry(entry_type="income",  category="parts_sale",       amount=12000.0, description="รายรับขายอะไหล่เดือนกรกฎาคม",    entry_date=datetime(2026, 7, 31)),
        LedgerEntry(entry_type="expense", category="parts_purchase",    amount=18000.0, description="ซื้ออะไหล่เดือนกรกฎาคม",          entry_date=datetime(2026, 7, 15), bill_id=b1.id),
        LedgerEntry(entry_type="expense", category="utilities",         amount=3500.0,  description="ค่าไฟฟ้าและน้ำเดือนกรกฎาคม",      entry_date=datetime(2026, 7, 5)),
        LedgerEntry(entry_type="expense", category="salary",            amount=25000.0, description="เงินเดือนช่างเดือนกรกฎาคม",       entry_date=datetime(2026, 7, 31)),
        # August 2026
        LedgerEntry(entry_type="income",  category="repair_service",  amount=38000.0, description="รายรับค่าซ่อมรถเดือนสิงหาคม",    entry_date=datetime(2026, 8, 20)),
        LedgerEntry(entry_type="income",  category="parts_sale",       amount=9500.0,  description="รายรับขายอะไหล่เดือนสิงหาคม",    entry_date=datetime(2026, 8, 20)),
        LedgerEntry(entry_type="expense", category="parts_purchase",    amount=15000.0, description="ซื้ออะไหล่เดือนสิงหาคม",          entry_date=datetime(2026, 8, 10)),
        LedgerEntry(entry_type="expense", category="utilities",         amount=3200.0,  description="ค่าไฟฟ้าและน้ำเดือนสิงหาคม",      entry_date=datetime(2026, 8, 5)),
        LedgerEntry(entry_type="expense", category="salary",            amount=25000.0, description="เงินเดือนช่างเดือนสิงหาคม",       entry_date=datetime(2026, 8, 25)),
    ]
    db.add_all(ledger)
    db.commit()
    logger.info("✅ Seed complete — 3 customers, 4 vehicles, 15 parts, 2 tickets, 3 months P&L data.")


# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()
    yield
    logger.info("Workshop Command Center shutting down.")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="🔧 Automotive Workshop Command Center",
    description=(
        "**ระบบหลังบ้านอัจฉริยะสำหรับอู่ซ่อมรถ** — R.O.S.E. Framework\n\n"
        "| Module | Prefix | Description |\n"
        "|--------|--------|-------------|\n"
        "| 1 | `/api/v1/tickets` | Repair Intake + HITL Quotation |\n"
        "| 2 | `/api/v1/finance` | Bill Pre-filling + Zero-Hallucination Math + P&L |\n"
        "| 3 | `/api/v1/customers` | Customer & Vehicle 360° Hub |\n"
        "| 4 | `/api/v1/marketing` | Autonomous Retention & Marketing Engine |\n\n"
        "**Default API Key** (header `X-API-Key`): `workshop-secret-2026`\n\n"
        "*No external LLM API key required — all AI is deterministic mock for demo.*"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(
    tickets.router,
    prefix="/api/v1/tickets",
    tags=["📋 Module 1 — Tickets & Repair Intake"],
)
app.include_router(
    finance.router,
    prefix="/api/v1/finance",
    tags=["💰 Module 2 — Finance & Billing"],
)
app.include_router(
    customers.router,
    prefix="/api/v1",
    tags=["👥 Module 3 — Customer & Vehicle 360°"],
)
app.include_router(
    marketing.router,
    prefix="/api/v1/marketing",
    tags=["📣 Module 4 — Marketing & Retention"],
)


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", tags=["🏠 Health"])
def root():
    return {
        "system": "Automotive Workshop Command Center",
        "framework": "R.O.S.E.",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "tickets": "/api/v1/tickets",
            "finance": "/api/v1/finance",
            "customers": "/api/v1/customers",
            "vehicles": "/api/v1/vehicles",
            "marketing": "/api/v1/marketing",
        },
    }


@app.get("/health", tags=["🏠 Health"])
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
