"""
Finance Service — Module 2 business logic
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from agents.bill_agent import BillState, bill_graph, mock_ocr_image
from models.db_models import BillStatus, FinanceBill, LedgerEntry
from models.schemas import (
    BillConfirmRequest, BillLineItemSchema, BillParseTextRequest,
    BillResponse, FinanceSummaryResponse, LedgerEntrySchema, PLInsight,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_THAI_MONTHS = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]


def _bill_to_response(bill: FinanceBill) -> BillResponse:
    items = bill.get_items()
    line_items = [BillLineItemSchema(**i) for i in items]

    if bill.math_verified:
        math_detail = f"✅ ยืนยันแล้ว: คำนวณได้ {bill.calculated_total:,.2f} บาท ตรงกับใบเสร็จ"
    else:
        math_detail = (
            f"❌ ไม่ตรงกัน: คำนวณได้ {bill.calculated_total:,.2f} บาท "
            f"แต่ใบเสร็จระบุ {bill.extracted_total:,.2f} บาท "
            f"(ต่าง {bill.math_discrepancy:,.2f} บาท)"
        )

    return BillResponse(
        id=bill.id,
        source_type=bill.source_type,
        vendor_name=bill.vendor_name,
        bill_type=bill.bill_type,
        line_items=line_items,
        extracted_total=bill.extracted_total,
        calculated_total=bill.calculated_total,
        math_verified=bill.math_verified,
        math_discrepancy=bill.math_discrepancy,
        status=bill.status,  # type: ignore[arg-type]
        math_check_detail=math_detail,
        confirmed_by=bill.confirmed_by,
        confirmed_at=bill.confirmed_at,
        notes=bill.notes,
        created_at=bill.created_at,
    )


def _run_bill_graph(raw_text: str, source_type: str, bill_type: str, vendor_name: str) -> BillState:
    return bill_graph.invoke({
        "raw_text": raw_text,
        "source_type": source_type,
        "bill_type": bill_type,
        "vendor_name": vendor_name,
        "bill_date": None,
        "line_items": [],
        "extracted_total": 0.0,
        "calculated_total": 0.0,
        "math_verified": False,
        "math_discrepancy": 0.0,
        "status": "DRAFT_AI",
        "error": None,
    })


def _persist_bill(db: Session, result: BillState) -> FinanceBill:
    bill = FinanceBill(
        source_type=result["source_type"],
        raw_input=result["raw_text"],
        extracted_items=json.dumps(result["line_items"], ensure_ascii=False),
        extracted_total=result["extracted_total"],
        calculated_total=result["calculated_total"],
        math_verified=result["math_verified"],
        math_discrepancy=result["math_discrepancy"],
        status=result["status"],
        vendor_name=result.get("vendor_name") or None,
        bill_type=result["bill_type"],
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


# ── Mock AI insight generator ─────────────────────────────────────────────────

def _generate_ai_insights(
    total_income: float,
    total_expense: float,
    net_profit: float,
    margin: float,
    income_bd: Dict[str, float],
    expense_bd: Dict[str, float],
    period: str,
) -> str:
    """
    Deterministic rule-based insight generator (mock LLM narrative).
    In production: replace with GPT-4o / Claude API call.
    """
    lines = [f"📊 วิเคราะห์ผล P&L เดือน {period}\n"]

    if net_profit > 0:
        lines.append(f"✅ ธุรกิจมีกำไร {net_profit:,.0f} บาท (margin {margin:.1f}%)")
    else:
        lines.append(f"⚠️ ธุรกิจมีผลขาดทุน {abs(net_profit):,.0f} บาท — ต้องตรวจสอบค่าใช้จ่าย")

    top_income = max(income_bd, key=income_bd.get) if income_bd else "N/A"
    top_expense = max(expense_bd, key=expense_bd.get) if expense_bd else "N/A"

    income_labels = {
        "repair_service": "บริการซ่อม",
        "parts_sale": "ขายอะไหล่",
        "other": "อื่นๆ",
    }
    expense_labels = {
        "parts_purchase": "ซื้ออะไหล่",
        "utilities": "ค่าสาธารณูปโภค",
        "salary": "เงินเดือนช่าง",
        "other": "อื่นๆ",
    }

    lines.append(
        f"\n💰 รายรับหลัก: {income_labels.get(top_income, top_income)} ({income_bd.get(top_income, 0):,.0f} บาท)"
    )
    lines.append(
        f"💸 รายจ่ายหลัก: {expense_labels.get(top_expense, top_expense)} ({expense_bd.get(top_expense, 0):,.0f} บาท)"
    )

    salary = expense_bd.get("salary", 0)
    if salary > 0 and total_income > 0:
        salary_ratio = (salary / total_income) * 100
        lines.append(f"\n🔍 สัดส่วนค่าแรง/รายรับ: {salary_ratio:.1f}%")
        if salary_ratio > 40:
            lines.append("   ⚠️ สัดส่วนค่าแรงสูง — พิจารณาเพิ่มประสิทธิภาพหรือรับงานเพิ่ม")

    if margin >= 25:
        lines.append("\n💡 แนะนำ: margin ดี — เหมาะแก่การลงทุนซื้ออุปกรณ์เพิ่ม")
    elif margin >= 10:
        lines.append("\n💡 แนะนำ: margin ปานกลาง — ควรเพิ่มรายรับจากบริการเฉพาะทาง")
    else:
        lines.append("\n💡 แนะนำ: margin ต่ำ — ตรวจสอบค่าใช้จ่ายคงที่และราคาอะไหล่")

    return "\n".join(lines)


# ── Service functions ─────────────────────────────────────────────────────────

def parse_text_bill(db: Session, req: BillParseTextRequest) -> BillResponse:
    result = _run_bill_graph(
        raw_text=req.raw_text,
        source_type="text",
        bill_type=req.bill_type,
        vendor_name=req.vendor_name or "",
    )
    bill = _persist_bill(db, result)
    return _bill_to_response(bill)


def parse_image_bill(
    db: Session,
    filename: str,
    file_bytes: bytes,
    bill_type: str,
) -> BillResponse:
    """Mock OCR → BillGraph → persist."""
    source_type = "image_png" if filename.lower().endswith(".png") else "image_jpg"
    ocr_text = mock_ocr_image(filename, file_bytes)
    result = _run_bill_graph(
        raw_text=ocr_text,
        source_type=source_type,
        bill_type=bill_type,
        vendor_name="",
    )
    bill = _persist_bill(db, result)
    return _bill_to_response(bill)


def list_bills(db: Session, limit: int = 50, offset: int = 0) -> dict:
    total = db.query(FinanceBill).count()
    bills = (
        db.query(FinanceBill)
        .order_by(FinanceBill.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"total": total, "items": [_bill_to_response(b) for b in bills]}


def get_bill(db: Session, bill_id: int) -> BillResponse:
    bill = db.query(FinanceBill).filter(FinanceBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill #{bill_id} not found.")
    return _bill_to_response(bill)


def confirm_bill(db: Session, bill_id: int, req: BillConfirmRequest) -> BillResponse:
    """
    HITL gate: staff reviews AI-extracted data, optionally corrects, then commits to ledger.
    """
    bill = db.query(FinanceBill).filter(FinanceBill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill #{bill_id} not found.")
    if bill.status == BillStatus.CONFIRMED:
        raise HTTPException(status_code=409, detail="Bill is already confirmed.")

    # Apply staff corrections
    if req.corrected_items:
        from decimal import Decimal, ROUND_HALF_UP
        corrected = [i.model_dump() for i in req.corrected_items]
        bill.extracted_items = json.dumps(corrected, ensure_ascii=False)
        calc = sum(Decimal(str(i["qty"])) * Decimal(str(i["unit_price"])) for i in corrected)
        bill.calculated_total = float(calc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        bill.math_verified = True
        bill.math_discrepancy = 0.0

    if req.corrected_total is not None:
        bill.extracted_total = req.corrected_total

    bill.status = BillStatus.CONFIRMED
    bill.confirmed_by = req.confirmed_by
    bill.confirmed_at = datetime.utcnow()
    bill.notes = req.notes

    # Write to general ledger
    ledger_amount = bill.extracted_total or bill.calculated_total or 0.0
    entry_date = req.entry_date or datetime.utcnow()

    ledger = LedgerEntry(
        bill_id=bill.id,
        entry_type=bill.bill_type,
        category="parts_purchase" if bill.bill_type == "expense" else "repair_service",
        amount=ledger_amount,
        description=f"{'ค่าใช้จ่าย' if bill.bill_type == 'expense' else 'รายรับ'} — {bill.vendor_name or 'ไม่ระบุ'}",
        entry_date=entry_date,
    )
    db.add(ledger)
    db.commit()
    db.refresh(bill)
    return _bill_to_response(bill)


def get_finance_summary(db: Session, year: int, month: int) -> FinanceSummaryResponse:
    """
    Deterministic P&L: pure SQL aggregation + rule-based AI narrative.
    No LLM involvement in the numbers — guaranteed accuracy.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12.")
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year.")

    entries = (
        db.query(LedgerEntry)
        .filter(
            extract("year", LedgerEntry.entry_date) == year,
            extract("month", LedgerEntry.entry_date) == month,
        )
        .all()
    )

    income_bd: Dict[str, float] = {}
    expense_bd: Dict[str, float] = {}

    for e in entries:
        if e.entry_type == "income":
            income_bd[e.category] = income_bd.get(e.category, 0.0) + e.amount
        else:
            expense_bd[e.category] = expense_bd.get(e.category, 0.0) + e.amount

    total_income = round(sum(income_bd.values()), 2)
    total_expense = round(sum(expense_bd.values()), 2)
    net_profit = round(total_income - total_expense, 2)
    margin = round((net_profit / total_income * 100) if total_income > 0 else 0.0, 2)

    top_income = max(income_bd, key=income_bd.get) if income_bd else "N/A"
    top_expense = max(expense_bd, key=expense_bd.get) if expense_bd else "N/A"

    period_label = f"{_THAI_MONTHS[month]} {year + 543}"  # Buddhist Era year

    ai_insight = _generate_ai_insights(
        total_income, total_expense, net_profit, margin,
        income_bd, expense_bd, period_label,
    )

    pl = PLInsight(
        period=period_label,
        total_income=total_income,
        total_expense=total_expense,
        net_profit=net_profit,
        profit_margin_pct=margin,
        income_breakdown=income_bd,
        expense_breakdown=expense_bd,
        top_income_source=top_income,
        top_expense_source=top_expense,
        ai_insights=ai_insight,
    )

    return FinanceSummaryResponse(
        year=year,
        month=month,
        period_label=period_label,
        summary=pl,
        ledger_entry_count=len(entries),
    )
