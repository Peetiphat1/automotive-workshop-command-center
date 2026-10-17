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
from datetime import datetime, timedelta, timezone

import hmac

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import Base, SessionLocal, engine
from models.db_models import (
    BillStatus, Customer, FinanceBill, LedgerEntry,
    MarketingTask, PartsCatalog, ServiceTicket, TicketStatus,
    Vehicle, VehicleHealthWatchlist, StockItem, WorkOrder,
    Supplier, PurchaseBill, StockHistory, Appointment, Expense
)
from routers import customers, finance, marketing, tickets, stock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workshop")


# ─── Seed Data ────────────────────────────────────────────────────────────────

def _seed(db):
    """Idempotent seed — skips if data already exists or .no_seed marker is present."""
    import os as _os
    _no_seed_flag = _os.path.join(_os.path.dirname(__file__), ".no_seed")
    if _os.path.exists(_no_seed_flag):
        logger.info("Found .no_seed marker — skipping demo seed (clean system mode).")
        return
    if db.query(Customer).count() > 0:
        logger.info("Database already seeded — skipping.")
        return

    logger.info("Seeding database with demo data…")
    now = datetime.now(timezone.utc)

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

    # ── Stock Items ───────────────────────────────────────────────────────────
    if db.query(StockItem).count() == 0:
        stock_seeds = [
            StockItem(name_th="น้ำมันเครื่อง 5W-30", name_en="Engine Oil 5W-30", sku="OIL-5W30", category="น้ำมันเครื่อง", quantity=24, unit_cost=200, sell_price=350, reorder_level=10),
            StockItem(name_th="น้ำมันเครื่อง 10W-40", name_en="Engine Oil 10W-40", sku="OIL-10W40", category="น้ำมันเครื่อง", quantity=18, unit_cost=180, sell_price=300, reorder_level=10),
            StockItem(name_th="กรองน้ำมันเครื่อง", name_en="Oil Filter", sku="FILTER-OIL", category="กรอง", quantity=30, unit_cost=80, sell_price=150, reorder_level=10),
            StockItem(name_th="กรองอากาศ", name_en="Air Filter", sku="FILTER-AIR", category="กรอง", quantity=15, unit_cost=120, sell_price=220, reorder_level=5),
            StockItem(name_th="ผ้าเบรคหน้า", name_en="Front Brake Pad", sku="BRAKE-FRONT", category="เบรค", quantity=8, unit_cost=600, sell_price=1200, reorder_level=4),
            StockItem(name_th="ผ้าเบรคหลัง", name_en="Rear Brake Pad", sku="BRAKE-REAR", category="เบรค", quantity=6, unit_cost=500, sell_price=950, reorder_level=4),
            StockItem(name_th="น้ำมันเบรค", name_en="Brake Fluid DOT3", sku="FLUID-BRAKE", category="เบรค", quantity=12, unit_cost=60, sell_price=120, reorder_level=5),
            StockItem(name_th="แบตเตอรี่ 60Ah", name_en="Battery 60Ah", sku="BAT-60AH", category="ไฟฟ้า", quantity=4, unit_cost=1800, sell_price=2800, reorder_level=2),
            StockItem(name_th="แบตเตอรี่ 75Ah", name_en="Battery 75Ah", sku="BAT-75AH", category="ไฟฟ้า", quantity=3, unit_cost=2200, sell_price=3500, reorder_level=2),
            StockItem(name_th="หัวเทียน NGK", name_en="Spark Plug NGK", sku="SPARK-NGK", category="ไฟฟ้า", quantity=40, unit_cost=80, sell_price=160, reorder_level=10),
            StockItem(name_th="น้ำมันเกียร์อัตโนมัติ ATF", name_en="ATF Transmission Oil", sku="OIL-ATF", category="น้ำมันเครื่อง", quantity=10, unit_cost=250, sell_price=450, reorder_level=5),
            StockItem(name_th="สายพาน V-Belt", name_en="V-Belt", sku="BELT-V", category="อะไหล่", quantity=7, unit_cost=180, sell_price=350, reorder_level=3),
            StockItem(name_th="ลูกปืนล้อหน้า", name_en="Front Wheel Bearing", sku="BEAR-FRONT", category="อะไหล่", quantity=4, unit_cost=450, sell_price=900, reorder_level=2),
            StockItem(name_th="น้ำยาล้างหม้อน้ำ", name_en="Radiator Coolant", sku="COOL-RAD", category="สารเคมี", quantity=20, unit_cost=90, sell_price=180, reorder_level=8),
            StockItem(name_th="กาวซิลิโคน", name_en="Silicone Gasket", sku="SEAL-SIL", category="สารเคมี", quantity=15, unit_cost=45, sell_price=90, reorder_level=5),
        ]
        db.add_all(stock_seeds)
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
    # ── Suppliers ──────────────────────────────────────────────────────────
    if db.query(Supplier).count() == 0:
        sup1 = Supplier(name="ร้านอะไหล่มีสุข", phone="0812223333", email="meesuk@email.com", line_id="meesuk_parts", address="123 ถ.พระราม 4 กรุงเทพ")
        sup2 = Supplier(name="YS อะไหล่ยนต์", phone="0899887766", email="ys_parts@email.com", line_id="ys_autoparts", address="456 ถ.สุขุมวิท กรุงเทพ")
        sup3 = Supplier(name="บริษัท ไทยออยล์ จำกัด", phone="0855667788", email="thaioil@email.com", address="789 ถ.เพชรบุรี กรุงเทพ")
        db.add_all([sup1, sup2, sup3])
        db.commit()
        for s in [sup1, sup2, sup3]:
            db.refresh(s)

        # Purchase bills
        pb1 = PurchaseBill(supplier_id=sup1.id, bill_number="INV-2026-001", bill_date=now - timedelta(days=30),
            items=json.dumps([{"name": "น้ำมันเครื่อง 5W-30", "qty": 10, "unit_price": 200, "total": 2000}, {"name": "กรองน้ำมัน", "qty": 5, "unit_price": 80, "total": 400}], ensure_ascii=False),
            total_amount=2400, notes="สั่งซื้อรอบเดือน ส.ค.")
        pb2 = PurchaseBill(supplier_id=sup2.id, bill_number="INV-2026-002", bill_date=now - timedelta(days=15),
            items=json.dumps([{"name": "ผ้าเบรคหน้า", "qty": 4, "unit_price": 600, "total": 2400}, {"name": "ผ้าเบรคหลัง", "qty": 4, "unit_price": 500, "total": 2000}], ensure_ascii=False),
            total_amount=4400, notes="สั่งซื้อเบรค")
        db.add_all([pb1, pb2])
        db.commit()

    # ── Appointments ──────────────────────────────────────────────────────
    if db.query(Appointment).count() == 0:
        appt_seeds = [
            Appointment(customer_name="สมชาย มีสุข", customer_phone="0812345678", vehicle_plate="กข 1234 กรุงเทพ",
                vehicle_info="Toyota Camry", appointment_date=now + timedelta(days=1), time_slot="09:00",
                service_type="เปลี่ยนน้ำมันเครื่อง + ตรวจเช็คช่วงล่าง", status="confirmed"),
            Appointment(customer_name="นภาพร จันทร์ดี", customer_phone="0898765432", vehicle_plate="คง 5678 เชียงใหม่",
                vehicle_info="Honda PCX 150", appointment_date=now + timedelta(days=1), time_slot="13:30",
                service_type="เปลี่ยนยางรถยนต์หน้า-หลัง", status="pending"),
            Appointment(customer_name="วิชัย ทองคำ", customer_phone="0856781234", vehicle_plate="จฉ 9012 ขอนแก่น",
                vehicle_info="Isuzu D-Max", appointment_date=now + timedelta(days=3), time_slot="10:00",
                service_type="ตรวจเช็คเกียร์", status="confirmed"),
            Appointment(customer_name="สมชาย มีสุข", customer_phone="0812345678", vehicle_plate="ชซ 3456 กรุงเทพ",
                vehicle_info="Mazda 2", appointment_date=now + timedelta(days=7), time_slot="14:00",
                service_type="เปลี่ยนแบตเตอรี่", status="confirmed"),
            Appointment(customer_name="นภาพร จันทร์ดี", customer_phone="0898765432", vehicle_plate="คง 5678 เชียงใหม่",
                vehicle_info="Honda PCX 150", appointment_date=now - timedelta(days=2), time_slot="11:00",
                service_type="เปลี่ยนน้ำมันเครื่อง", status="completed"),
        ]
        db.add_all(appt_seeds)
        db.commit()

    # ── Expenses ──────────────────────────────────────────────────────────
    if db.query(Expense).count() == 0:
        expense_seeds = [
            Expense(category="ค่าไฟฟ้า", description="ค่าไฟฟ้าเดือนสิงหาคม 2026", amount=2800, expense_date=now - timedelta(days=10), added_by="ผู้จัดการ"),
            Expense(category="ค่าน้ำประปา", description="ค่าน้ำประปาเดือนสิงหาคม 2026", amount=450, expense_date=now - timedelta(days=10), added_by="ผู้จัดการ"),
            Expense(category="ค่าเช่า", description="ค่าเช่าอู่ซ่อมรถเดือนกันยายน 2026", amount=15000, expense_date=now - timedelta(days=5), added_by="ผู้จัดการ"),
            Expense(category="ค่าอินเทอร์เน็ต", description="ค่าอินเทอร์เน็ตเดือนสิงหาคม 2026", amount=890, expense_date=now - timedelta(days=8), added_by="ผู้จัดการ"),
            Expense(category="อื่นๆ", description="ค่าอุปกรณ์ทำความสะอาด", amount=350, expense_date=now - timedelta(days=3), added_by="ช่างสมศักดิ์"),
        ]
        db.add_all(expense_seeds)
        db.commit()

    logger.info("✅ Seed complete — 3 customers, 4 vehicles, 15 parts, 2 tickets, 3 months P&L data, suppliers, appointments, expenses.")


# ─── App lifecycle ────────────────────────────────────────────────────────────

# Columns added after the first release — created on start-up for existing databases
_ADDED_COLUMNS = [
    ("stock_items", "bill_path", "VARCHAR(500)"),
    ("service_tickets", "completed_at", "DATETIME"),
    ("service_tickets", "approval_token", "VARCHAR(64)"),
    ("service_tickets", "customer_decision", "VARCHAR(20)"),
    ("service_tickets", "customer_decision_at", "DATETIME"),
    ("service_tickets", "customer_decision_note", "TEXT"),
    ("service_tickets", "warranty_months", "INTEGER"),
    ("service_tickets", "warranty_note", "VARCHAR(300)"),
]


def _migrate_columns():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.connect() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.info(f"Added column {table}.{column}")
        conn.commit()


async def _daily_backup_loop():
    """Make one backup per day while the program is running (checks every 30 minutes)."""
    import asyncio
    from services import backup_service, shop_settings
    while True:
        try:
            db = SessionLocal()
            try:
                extra = shop_settings.get_setting(db, "backup_extra_dir") or None
            finally:
                db.close()
            await asyncio.to_thread(backup_service.run_daily_backup, extra)
        except Exception as e:
            logger.error(f"Daily backup loop error: {e}")
        await asyncio.sleep(30 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import os
    Base.metadata.create_all(bind=engine)
    try:
        _migrate_columns()
    except Exception as e:
        logger.error(f"Column migration failed: {e}")
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()
    backup_task = None
    if os.getenv("AUTO_BACKUP", "1") != "0":
        backup_task = asyncio.create_task(_daily_backup_loop())
    yield
    if backup_task:
        backup_task.cancel()
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
        "With `REQUIRE_PASSWORD=true` in `.env`, `/api/` routes require header `X-API-Key` (the shop password `MOCK_API_KEY`).\n\n"
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

# ── Shop password guard for every /api/ route ─────────────────────────────────
# Public exceptions: customer repair tracking page and the LINE webhook (verified by signature).
_PUBLIC_API_PREFIXES = (
    "/api/v1/tickets/track/",
    "/api/v1/line/webhook",
    "/api/v1/public/",          # customer quote approval page (random token per job)
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    path = request.url.path
    if (
        settings.REQUIRE_PASSWORD
        and path.startswith("/api/")
        and request.method != "OPTIONS"
        and not path.startswith(_PUBLIC_API_PREFIXES)
    ):
        key = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(key.encode(), settings.MOCK_API_KEY.encode()):
            return JSONResponse(status_code=401, content={"detail": "รหัสผ่านร้านไม่ถูกต้อง หรือยังไม่ได้เข้าสู่ระบบ"})
    return await call_next(request)

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

from routers import chat as chat_router
app.include_router(
    chat_router.router,
    prefix="/api/v1/chat",
    tags=["💬 Chat Command Center"],
)
app.include_router(
    stock.router,
    prefix="/api/v1/stock",
    tags=["📦 Stock & Work Orders"],
)

from routers import bills as bills_router
app.include_router(
    bills_router.router,
    prefix="/api/v1/bills",
    tags=["🧾 Bill Scanner"],
)

# New routers for PDF fixes
try:
    from routers import suppliers as suppliers_router
    app.include_router(
        suppliers_router.router,
        prefix="/api/v1/suppliers",
        tags=["🏭 Suppliers"],
    )
except ImportError:
    pass

try:
    from routers import appointments as appointments_router
    app.include_router(
        appointments_router.router,
        prefix="/api/v1/appointments",
        tags=["📅 Appointments"],
    )
except ImportError:
    pass

try:
    from routers import expenses as expenses_router
    app.include_router(
        expenses_router.router,
        prefix="/api/v1/expenses",
        tags=["💸 Expenses"],
    )
except ImportError:
    pass

try:
    from routers import reports as reports_router
    app.include_router(
        reports_router.router,
        prefix="/api/v1/reports",
        tags=["📊 Reports"],
    )
except ImportError:
    pass

try:
    from routers import settings as settings_router
    app.include_router(
        settings_router.router,
        prefix="/api/v1/settings",
        tags=["⚙️ Settings & AI Integrations"],
    )
except ImportError:
    pass

try:
    from routers import backup as backup_router
    app.include_router(
        backup_router.router,
        prefix="/api/v1/backup",
        tags=["💾 Backup & Data Transfer"],
    )
except ImportError as e:
    logger.warning(f"Could not import backup_router: {e}")

try:
    from routers import line_webhook as line_webhook_router
    app.include_router(
        line_webhook_router.router,
        prefix="/api/v1/line",
        tags=["📱 LINE OA Webhook & Bot"],
    )
except ImportError as e:
    logger.warning(f"Could not import line_webhook_router: {e}")



from routers import payments as payments_router
from routers import public_quote as public_quote_router
app.include_router(payments_router.router, prefix="/api/v1/payments", tags=["💵 Payments"])
app.include_router(public_quote_router.router, prefix="/api/v1/public", tags=["🌐 Public quote"])

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/dashboard", tags=["🏠 Dashboard"])
def dashboard():
    return FileResponse("static/index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/stock", tags=["🏠 Dashboard"])
def stock_page():
    return FileResponse("static/stock.html")

@app.get("/scan", tags=["🏠 Dashboard"])
def scan_page():
    return FileResponse("static/scan.html")

@app.get("/track", tags=["🏠 Dashboard"])
def track_page():
    return FileResponse("static/track.html")

@app.get("/quote/{token}", tags=["🏠 Dashboard"])
def quote_page(token: str):
    return FileResponse("static/quote.html", headers={"Cache-Control": "no-store"})

@app.get("/manual", tags=["🏠 Dashboard"])
def manual_page(lang: str | None = None):
    if lang and lang.lower() == "en":
        return FileResponse("static/manual_en.html")
    return FileResponse("static/manual.html")

@app.get("/manual_en", tags=["🏠 Dashboard"])
def manual_en_page():
    return FileResponse("static/manual_en.html")



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


@app.get("/api/v1/auth/check", tags=["🏠 Health"])
def auth_check():
    """Login check — the middleware already rejected a wrong password."""
    return {"ok": True}


@app.get("/health", tags=["🏠 Health"])
def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
