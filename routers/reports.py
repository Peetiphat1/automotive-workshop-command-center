"""
Router: Comprehensive Reports Module
Provides aggregated data for the 7 standard workshop reports:
1. Sales Report (รายวัน แยกอะไหล่/งานซ่อม + Daily Trend)
2. Top Selling Parts (อะไหล่ขายดี)
3. Stock Valuation Report (รายงานสต็อก)
4. Mechanic Performance Report (ผลงานช่างและค่าคอมมิชชั่น)
5. Top Spending Customers Report (รายงานลูกค้า)
6. Profit & Loss Statement (กำไร-ขาดทุน)
7. Sales Tax Report (รายงานภาษีขาย สำหรับยื่น ภ.พ.30)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, date, timedelta, timezone
from models.db_models import get_local_now
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from core.dependencies import get_db
from models.db_models import (
    StockItem, ServiceTicket, WorkOrder, FinanceBill,
    LedgerEntry, Expense, Customer, Vehicle, PurchaseBill, TicketStatus
)

router = APIRouter()


def _parse_date(d_str: Optional[str], default: datetime) -> datetime:
    if not d_str:
        return default
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(d_str.strip(), fmt)
        except ValueError:
            continue
    return default


def _date_range_defaults(start_date: Optional[str], end_date: Optional[str]):
    today = get_local_now()
    # Default start to 1st of current month
    first_of_month = datetime(today.year, today.month, 1, 0, 0, 0)
    end_of_today = datetime(today.year, today.month, today.day, 23, 59, 59)

    start_dt = _parse_date(start_date, first_of_month)
    end_dt = _parse_date(end_date, end_of_today)
    if end_dt.hour == 0 and end_dt.minute == 0:
        end_dt = datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59)

    # If start is after end, swap them
    if start_dt > end_dt:
        start_dt, end_dt = end_dt.replace(hour=0, minute=0, second=0), start_dt.replace(hour=23, minute=59, second=59)

    # Cap max span to 366 days
    if (end_dt - start_dt).days > 366:
        start_dt = end_dt - timedelta(days=365)
        start_dt = start_dt.replace(hour=0, minute=0, second=0)

    return start_dt, end_dt


# ──────────────────────────────────────────────────────────────────────────────
# 1. รายงานยอดขาย (Sales Report)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/sales")
def get_sales_report(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or DD/MM/YYYY)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or DD/MM/YYYY)"),
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _date_range_defaults(start_date, end_date)

    # 1. POS Parts Sales from Ledger
    ledger_parts = db.query(LedgerEntry).filter(
        LedgerEntry.entry_type == "income",
        LedgerEntry.category == "parts_sale",
        LedgerEntry.entry_date >= start_dt,
        LedgerEntry.entry_date <= end_dt,
    ).all()
    pos_parts_total = sum(e.amount for e in ledger_parts)

    # 2. Repair Labor Sales from Ledger
    ledger_repairs = db.query(LedgerEntry).filter(
        LedgerEntry.entry_type == "income",
        LedgerEntry.category == "repair_service",
        LedgerEntry.entry_date >= start_dt,
        LedgerEntry.entry_date <= end_dt,
    ).all()
    repair_total = sum(e.amount for e in ledger_repairs)

    # 3. Also include WorkOrders within date range
    work_orders = db.query(WorkOrder).filter(
        WorkOrder.created_at >= start_dt,
        WorkOrder.created_at <= end_dt,
    ).all()
    for wo in work_orders:
        pos_parts_total += (wo.parts_cost or 0.0)
        repair_total += (wo.labor_cost or 0.0)

    # 4. Also check approved/completed ServiceTickets in date range (avoid double-counting with ledger)
    ticket_ids_in_ledger = {
        int(match.group(1))
        for e in ledger_repairs
        if (match := re.search(r"Ticket #(\d+)", e.description or ""))
    }
    tickets = db.query(ServiceTicket).filter(
        ServiceTicket.status.in_([TicketStatus.APPROVED, TicketStatus.COMPLETED]),
        ServiceTicket.created_at >= start_dt,
        ServiceTicket.created_at <= end_dt,
    ).all()
    for t in tickets:
        if t.id in ticket_ids_in_ledger:
            continue
        cost = t.final_cost or t.total_estimated_cost or 0.0
        parts_c = t.estimated_parts_cost or (cost * 0.4)
        labor_c = t.estimated_labor_cost or (cost * 0.6)
        pos_parts_total += parts_c
        repair_total += labor_c

    grand_total = pos_parts_total + repair_total

    # Build daily aggregation between start_dt and end_dt
    days_span = max(1, (end_dt.date() - start_dt.date()).days + 1)
    daily_map: Dict[str, Dict[str, float]] = {}
    cur = start_dt.date()
    while cur <= end_dt.date():
        ds = cur.strftime("%Y-%m-%d")
        daily_map[ds] = {
            "date": ds,
            "day_label": cur.strftime("%d/%m"),
            "pos_sales": 0.0,
            "repair_sales": 0.0,
            "total": 0.0,
        }
        cur += timedelta(days=1)

    # Populate daily from ledger
    for e in ledger_parts:
        ds = e.entry_date.strftime("%Y-%m-%d")
        if ds in daily_map:
            daily_map[ds]["pos_sales"] += e.amount
            daily_map[ds]["total"] += e.amount

    for e in ledger_repairs:
        ds = e.entry_date.strftime("%Y-%m-%d")
        if ds in daily_map:
            daily_map[ds]["repair_sales"] += e.amount
            daily_map[ds]["total"] += e.amount

    for wo in work_orders:
        ds = (wo.work_date or wo.created_at).strftime("%Y-%m-%d")
        if ds in daily_map:
            daily_map[ds]["pos_sales"] += (wo.parts_cost or 0.0)
            daily_map[ds]["repair_sales"] += (wo.labor_cost or 0.0)
            daily_map[ds]["total"] += (wo.total_cost or 0.0)

    for t in tickets:
        ds = t.created_at.strftime("%Y-%m-%d")
        if ds in daily_map:
            cost = t.final_cost or t.total_estimated_cost or 0.0
            parts_c = t.estimated_parts_cost or (cost * 0.4)
            labor_c = t.estimated_labor_cost or (cost * 0.6)
            daily_map[ds]["pos_sales"] += parts_c
            daily_map[ds]["repair_sales"] += labor_c
            daily_map[ds]["total"] += cost

    # Build transaction items list for table
    items: List[Dict[str, Any]] = []
    # From tickets
    for t in tickets:
        cost = t.final_cost or t.total_estimated_cost or 0.0
        c_name = t.customer.name if t.customer else "ลูกค้าทั่วไป"
        v_plate = t.vehicle.plate if t.vehicle else "-"
        items.append({
            "id": f"TK-{t.id}",
            "doc_no": f"TKT-{t.id:04d}",
            "date": t.created_at.strftime("%d/%m/%Y"),
            "customer": c_name,
            "vehicle": v_plate,
            "type": "งานซ่อม",
            "amount": cost,
            "status": t.status,
        })
    # From work orders
    for wo in work_orders:
        items.append({
            "id": f"WO-{wo.id}",
            "doc_no": f"WO-{wo.id:04d}",
            "date": (wo.work_date or wo.created_at).strftime("%d/%m/%Y"),
            "customer": wo.customer_name or "ลูกค้าทั่วไป",
            "vehicle": wo.vehicle_plate or "-",
            "type": "งานซ่อม/อะไหล่",
            "amount": wo.total_cost or 0.0,
            "status": "COMPLETED",
        })
    # From ledger entries
    for e in ledger_parts + ledger_repairs:
        items.append({
            "id": f"LED-{e.id}",
            "doc_no": f"TX-{e.id:04d}",
            "date": e.entry_date.strftime("%d/%m/%Y"),
            "customer": "รายการทั่วไป",
            "vehicle": "-",
            "type": "ขายอะไหล่ (POS)" if e.category == "parts_sale" else "งานซ่อม",
            "amount": e.amount,
            "status": "RECORDED",
        })

    items.sort(key=lambda x: x["date"], reverse=True)

    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "pos_parts_total": round(pos_parts_total, 2),
        "repair_total": round(repair_total, 2),
        "grand_total": round(grand_total, 2),
        "daily_sales": list(daily_map.values()),
        "items": items,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. อะไหล่ขายดี (Top Selling Parts)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/top-parts")
def get_top_parts_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _date_range_defaults(start_date, end_date)

    parts_agg: Dict[str, Dict[str, Any]] = {}

    # Check work order line items
    work_orders = db.query(WorkOrder).filter(
        WorkOrder.created_at >= start_dt,
        WorkOrder.created_at <= end_dt,
    ).all()

    for wo in work_orders:
        if not wo.line_items:
            continue
        try:
            items = json.loads(wo.line_items)
            for it in items:
                name = it.get("name") or "อะไหล่"
                qty = float(it.get("qty", 1))
                tot = float(it.get("total", it.get("unit_price", 0) * qty))
                key = name.strip()
                if key not in parts_agg:
                    parts_agg[key] = {"sku": "-", "name": key, "quantity": 0, "total_amount": 0.0}
                parts_agg[key]["quantity"] += int(qty)
                parts_agg[key]["total_amount"] += tot
        except Exception:
            pass

    # Check ServiceTickets line items
    tickets = db.query(ServiceTicket).filter(
        ServiceTicket.status.in_([TicketStatus.APPROVED, TicketStatus.COMPLETED]),
        ServiceTicket.created_at >= start_dt,
        ServiceTicket.created_at <= end_dt,
    ).all()

    for t in tickets:
        for it in t.get_line_items():
            if it.get("type") == "part" or "ค่าแรง" not in it.get("name_th", ""):
                name = it.get("name_th") or it.get("name") or "อะไหล่"
                qty = float(it.get("qty", 1))
                tot = float(it.get("total", it.get("unit_price", 0) * qty))
                key = name.strip()
                if key not in parts_agg:
                    parts_agg[key] = {"sku": "-", "name": key, "quantity": 0, "total_amount": 0.0}
                parts_agg[key]["quantity"] += int(qty)
                parts_agg[key]["total_amount"] += tot

    # Match SKU from StockItem if possible
    all_stock = db.query(StockItem).all()
    for item in parts_agg.values():
        for s in all_stock:
            if s.name_th.strip() == item["name"] or (s.name_en and s.name_en.strip() == item["name"]):
                item["sku"] = s.sku or "-"
                break

    sorted_parts = sorted(parts_agg.values(), key=lambda x: (x["quantity"], x["total_amount"]), reverse=True)
    ranked_list = []
    for idx, p in enumerate(sorted_parts, start=1):
        ranked_list.append({
            "rank": idx,
            "sku": p["sku"],
            "name": p["name"],
            "quantity_sold": p["quantity"],
            "total_revenue": round(p["total_amount"], 2),
        })

    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "items": ranked_list,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 3. รายงานสต็อก (Stock Report)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/stock")
def get_stock_report(db: Session = Depends(get_db)):
    stock_items = db.query(StockItem).order_by(StockItem.category, StockItem.name_th).all()

    items = []
    total_cost_valuation = 0.0

    for it in stock_items:
        qty = it.quantity or 0
        cost = it.unit_cost or 0.0
        val = qty * cost
        total_cost_valuation += val
        items.append({
            "id": it.id,
            "sku": it.sku or f"SKU-{it.id:04d}",
            "name": it.name_th,
            "category": it.category,
            "quantity": qty,
            "unit_cost": round(cost, 2),
            "total_value": round(val, 2),
        })

    return {
        "total_cost_valuation": round(total_cost_valuation, 2),
        "total_items_count": len(items),
        "items": items,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 4. รายงานช่าง (Mechanics Report)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/mechanics")
def get_mechanics_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    commission_pct: Optional[float] = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
):
    """Jobs, revenue and labour per mechanic (from the name on each job), with commission on labour."""
    from services import job_costing, shop_settings
    start_dt, end_dt = _date_range_defaults(start_date, end_date)
    rate = commission_pct if commission_pct is not None else shop_settings.get_float(db, "commission_pct")

    per: Dict[str, Dict[str, Any]] = {}
    for r in job_costing.job_rows(db, start_dt, end_dt):
        if r["kind"] == "pos":
            continue
        name = r["mechanic"] or "ไม่ระบุช่าง"
        m = per.setdefault(name, {"jobs": 0, "completed": 0, "revenue": 0.0, "labor": 0.0})
        m["jobs"] += 1
        m["completed"] += 1 if r["status"] == "COMPLETED" else 0
        m["revenue"] += r["revenue"]
        m["labor"] += r["labor_revenue"]

    # Jobs still open show the current workload
    open_jobs: Dict[str, int] = {}
    for t in db.query(ServiceTicket).filter(ServiceTicket.status.in_([
        TicketStatus.PENDING_MECHANIC_APPROVAL, TicketStatus.DRAFT_ESTIMATE,
        TicketStatus.APPROVED, TicketStatus.IN_PROGRESS,
    ])).all():
        name = job_costing.ticket_mechanic(t) or "ไม่ระบุช่าง"
        open_jobs[name] = open_jobs.get(name, 0) + 1

    results = []
    for name in set(per) | set(open_jobs):
        m = per.get(name, {"jobs": 0, "completed": 0, "revenue": 0.0, "labor": 0.0})
        results.append({
            "mechanic_name": name,
            "jobs_count": m["jobs"],
            "completed_count": m["completed"],
            "open_jobs": open_jobs.get(name, 0),
            "total_revenue": round(m["revenue"], 2),
            "total_labor": round(m["labor"], 2),
            "commission_rate": rate,
            "commission_amount": round(m["labor"] * rate / 100.0, 2),
        })
    results.sort(key=lambda r: r["total_labor"], reverse=True)

    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "commission_rate": rate,
        "items": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5. รายงานลูกค้า (Top Customers Report)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/customers")
def get_customers_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _date_range_defaults(start_date, end_date)

    all_customers = db.query(Customer).all()
    cust_agg: Dict[int, Dict[str, Any]] = {}

    for c in all_customers:
        cust_agg[c.id] = {
            "id": c.id,
            "name": c.name,
            "phone": c.phone or "-",
            "visits_count": 0,
            "points": 0,
            "total_spent": 0.0,
        }

    # Sum spend from ServiceTickets
    tickets = db.query(ServiceTicket).filter(
        ServiceTicket.status.in_([TicketStatus.APPROVED, TicketStatus.COMPLETED]),
        ServiceTicket.created_at >= start_dt,
        ServiceTicket.created_at <= end_dt,
    ).all()

    for t in tickets:
        if t.customer_id and t.customer_id in cust_agg:
            cost = t.final_cost or t.total_estimated_cost or 0.0
            cust_agg[t.customer_id]["visits_count"] += 1
            cust_agg[t.customer_id]["total_spent"] += cost
            cust_agg[t.customer_id]["points"] += int(cost // 100)

    # Sum spend from WorkOrders
    work_orders = db.query(WorkOrder).filter(
        WorkOrder.created_at >= start_dt,
        WorkOrder.created_at <= end_dt,
    ).all()

    for wo in work_orders:
        if wo.customer_id and wo.customer_id in cust_agg:
            cust_agg[wo.customer_id]["visits_count"] += 1
            cust_agg[wo.customer_id]["total_spent"] += (wo.total_cost or 0.0)
            cust_agg[wo.customer_id]["points"] += int((wo.total_cost or 0.0) // 100)

    sorted_cust = sorted(cust_agg.values(), key=lambda x: x["total_spent"], reverse=True)
    # Filter active in range or keep all if spending > 0
    active_cust = [c for c in sorted_cust if c["total_spent"] > 0 or c["visits_count"] > 0]
    if not active_cust and len(sorted_cust) > 0:
        # If no transactions in strict period, show empty state or list as in screenshot
        active_cust = []

    ranked = []
    for idx, c in enumerate(active_cust, start=1):
        ranked.append({
            "rank": idx,
            "name": c["name"],
            "phone": c["phone"],
            "visits_count": c["visits_count"],
            "points": c["points"],
            "total_spent": round(c["total_spent"], 2),
        })

    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "items": ranked,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 6. รายงานกำไร-ขาดทุน (Profit & Loss Statement)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/profit")
def get_profit_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """P&L: revenue of jobs in the period, cost of the parts those jobs used, then expenses.
    Buying stock is not a cost until the part is sold (shown separately as stock_purchases)."""
    from services import job_costing
    start_dt, end_dt = _date_range_defaults(start_date, end_date)
    jobs = job_costing.job_rows(db, start_dt, end_dt)

    parts_revenue = sum(j["parts_revenue"] for j in jobs)
    repair_revenue = sum(j["labor_revenue"] for j in jobs)
    cogs = sum(j["parts_cost"] for j in jobs)

    # Income booked by hand / from scanned income bills (not created by a job)
    job_entry = re.compile(r"Ticket #\d+|Work Order #\d+|POS")
    other_income = db.query(LedgerEntry).filter(
        LedgerEntry.entry_type == "income",
        LedgerEntry.entry_date >= start_dt,
        LedgerEntry.entry_date <= end_dt,
    ).all()
    other_revenue = sum(e.amount for e in other_income if not job_entry.search(e.description or ""))

    total_revenue = parts_revenue + repair_revenue + other_revenue
    gross_profit = total_revenue - cogs

    exp_ledger = db.query(LedgerEntry).filter(
        LedgerEntry.entry_type == "expense",
        LedgerEntry.category != "parts_purchase",
        LedgerEntry.entry_date >= start_dt,
        LedgerEntry.entry_date <= end_dt,
    ).all()
    expenses = db.query(Expense).filter(
        Expense.expense_date >= start_dt,
        Expense.expense_date <= end_dt,
    ).all()
    operating_expenses = sum(e.amount for e in exp_ledger) + sum(ex.amount for ex in expenses)
    net_profit = gross_profit - operating_expenses

    purchases = db.query(PurchaseBill).filter(
        PurchaseBill.bill_date >= start_dt,
        PurchaseBill.bill_date <= end_dt,
    ).all()

    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "parts_revenue": round(parts_revenue, 2),
        "repair_revenue": round(repair_revenue, 2),
        "other_revenue": round(other_revenue, 2),
        "total_revenue": round(total_revenue, 2),
        "cogs": round(cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "operating_expenses": round(operating_expenses, 2),
        "net_profit": round(net_profit, 2),
        "stock_purchases": round(sum(pb.total_amount or 0 for pb in purchases), 2),
        "jobs_missing_cost": sum(1 for j in jobs if j["missing_cost"]),
        "jobs_count": len(jobs),
    }


@router.get("/job-profit")
def get_job_profit_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Profit of every job: price minus the cost of the parts it used."""
    from services import job_costing
    start_dt, end_dt = _date_range_defaults(start_date, end_date)
    jobs = job_costing.job_rows(db, start_dt, end_dt)
    kind_th = {"repair": "งานซ่อม", "pos": "ขายหน้าร้าน", "work_order": "ใบสั่งงาน"}
    items = [{**j, "date": j["date"].strftime("%d/%m/%Y"), "kind_th": kind_th.get(j["kind"], j["kind"])} for j in jobs]
    revenue = sum(j["revenue"] for j in jobs)
    cost = sum(j["parts_cost"] for j in jobs)
    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "total_revenue": round(revenue, 2),
        "total_parts_cost": round(cost, 2),
        "total_profit": round(revenue - cost, 2),
        "margin_pct": round((revenue - cost) / revenue * 100, 1) if revenue else 0.0,
        "jobs_missing_cost": sum(1 for j in jobs if j["missing_cost"]),
        "items": items,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 7. รายงานภาษีขาย (Sales Tax / ภ.พ.30)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/tax")
def get_tax_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _date_range_defaults(start_date, end_date)

    # Taxable sales from approved tickets & confirmed income bills
    items = []
    pre_tax_total = 0.0
    vat_total = 0.0
    grand_total = 0.0

    tickets = db.query(ServiceTicket).filter(
        ServiceTicket.status.in_([TicketStatus.APPROVED, TicketStatus.COMPLETED]),
        ServiceTicket.created_at >= start_dt,
        ServiceTicket.created_at <= end_dt,
    ).all()

    for t in tickets:
        total = t.final_cost or t.total_estimated_cost or 0.0
        # Tax included: pre_tax = total / 1.07, vat = total - pre_tax
        pre_tax = round(total / 1.07, 2)
        vat = round(total - pre_tax, 2)
        pre_tax_total += pre_tax
        vat_total += vat
        grand_total += total
        items.append({
            "doc_no": f"TAX-TK-{t.id:04d}",
            "date": t.created_at.strftime("%d/%m/%Y"),
            "customer_name": t.customer.name if t.customer else "ลูกค้าทั่วไป",
            "pre_tax": pre_tax,
            "vat": vat,
            "total": total,
        })

    bills = db.query(FinanceBill).filter(
        FinanceBill.bill_type == "income",
        FinanceBill.bill_date >= start_dt,
        FinanceBill.bill_date <= end_dt,
    ).all()

    for b in bills:
        total = b.calculated_total or b.extracted_total or 0.0
        pre_tax = round(total / 1.07, 2)
        vat = round(total - pre_tax, 2)
        pre_tax_total += pre_tax
        vat_total += vat
        grand_total += total
        items.append({
            "doc_no": f"TAX-IV-{b.id:04d}",
            "date": (b.bill_date or b.created_at).strftime("%d/%m/%Y"),
            "customer_name": b.vendor_name or "ลูกค้าทั่วไป",
            "pre_tax": pre_tax,
            "vat": vat,
            "total": total,
        })

    return {
        "start_date": start_dt.strftime("%d/%m/%Y"),
        "end_date": end_dt.strftime("%d/%m/%Y"),
        "pre_tax_total": round(pre_tax_total, 2),
        "vat_total": round(vat_total, 2),
        "grand_total": round(grand_total, 2),
        "items": items,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 8. ปิดยอดประจำวัน (Daily closing)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/daily-close")
def get_daily_close(
    date_str: Optional[str] = Query(None, alias="date", description="YYYY-MM-DD (default today)"),
    db: Session = Depends(get_db),
):
    """Everything needed to close the shop for one day: money in by method, jobs, expenses, parts used."""
    from models.db_models import Payment, StockHistory
    from services import job_costing, payment_service

    day = _parse_date(date_str, get_local_now()) if date_str else get_local_now()
    start = datetime(day.year, day.month, day.day, 0, 0, 0)
    end = datetime(day.year, day.month, day.day, 23, 59, 59)

    # 1. Money received
    pays = db.query(Payment).filter(Payment.paid_at >= start, Payment.paid_at <= end).order_by(Payment.paid_at).all()
    by_method: Dict[str, float] = {}
    pay_rows = []
    for p in pays:
        method = p.method or "เงินสด"
        by_method[method] = by_method.get(method, 0.0) + p.amount
        if p.ticket_id:
            t = db.query(ServiceTicket).filter(ServiceTicket.id == p.ticket_id).first()
            ref = f"งานซ่อม #{p.ticket_id}" + (f" ({t.vehicle.plate})" if t and t.vehicle else "")
        else:
            ref = f"บิลขายหน้าร้าน #{p.work_order_id}"
        pay_rows.append({"time": p.paid_at.strftime("%H:%M"), "ref": ref, "method": method,
                         "amount": p.amount, "note": p.note, "received_by": p.received_by})
    total_received = sum(by_method.values())

    # 2. Jobs
    opened = db.query(ServiceTicket).filter(ServiceTicket.created_at >= start, ServiceTicket.created_at <= end).count()
    completed_rows = []
    for t in db.query(ServiceTicket).filter(ServiceTicket.status == TicketStatus.COMPLETED,
                                            ServiceTicket.completed_at >= start,
                                            ServiceTicket.completed_at <= end).all():
        completed_rows.append({"ticket_id": t.id, "plate": t.vehicle.plate if t.vehicle else None,
                               "customer": t.customer.name if t.customer else None,
                               "mechanic": job_costing.ticket_mechanic(t),
                               **payment_service.ticket_summary(db, t)})
    jobs_today = job_costing.job_rows(db, start, end)
    pos_sales = [j for j in jobs_today if j["kind"] == "pos"]

    # 3. Money out
    expenses = db.query(Expense).filter(Expense.expense_date >= start, Expense.expense_date <= end).all()
    purchases = db.query(PurchaseBill).filter(PurchaseBill.bill_date >= start, PurchaseBill.bill_date <= end).all()
    expense_rows = [{"category": e.category, "description": e.description, "amount": e.amount} for e in expenses]
    expense_rows += [{"category": "ซื้ออะไหล่เข้าสต็อก", "description": pb.bill_number or f"บิล #{pb.id}",
                      "amount": pb.total_amount or 0} for pb in purchases]
    total_expenses = sum(r["amount"] for r in expense_rows)

    # 4. Parts that left stock (returns from cancelled / edited sales count back)
    used: Dict[int, Dict[str, Any]] = {}
    history = db.query(StockHistory).filter(
        StockHistory.created_at >= start, StockHistory.created_at <= end,
        StockHistory.change_type.in_(["sale", "return"]),
    ).all()
    for h in history:
        item = db.query(StockItem).filter(StockItem.id == h.stock_item_id).first()
        u = used.setdefault(h.stock_item_id, {"name": item.name_th if item else "?",
                                              "sku": item.sku if item else None,
                                              "qty": 0, "left": item.quantity if item else None})
        u["qty"] -= h.delta  # sale delta is negative, return delta positive
    parts_used = sorted((u for u in used.values() if u["qty"] > 0), key=lambda u: -u["qty"])

    outstanding = payment_service.outstanding_tickets(db)
    cash_in = by_method.get("เงินสด", 0.0)

    return {
        "date": start.strftime("%Y-%m-%d"),
        "date_th": f"{start.day:02d}/{start.month:02d}/{start.year + 543}",
        "received_by_method": {k: round(v, 2) for k, v in by_method.items()},
        "total_received": round(total_received, 2),
        "payments": pay_rows,
        "tickets_opened": opened,
        "tickets_completed": completed_rows,
        "pos_sales_count": len(pos_sales),
        "pos_sales_total": round(sum(j["revenue"] for j in pos_sales), 2),
        "revenue_booked": round(sum(j["revenue"] for j in jobs_today), 2),
        "profit_on_jobs": round(sum(j["profit"] for j in jobs_today), 2),
        "expenses": expense_rows,
        "total_expenses": round(total_expenses, 2),
        "cash_net": round(cash_in - total_expenses, 2),
        "parts_used": parts_used,
        "outstanding_count": outstanding["count"],
        "outstanding_total": outstanding["total_outstanding"],
    }
