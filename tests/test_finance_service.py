"""
Unit tests for finance_service.py — Module 2: Finance & Billing

Covers:
- _bill_to_response helper (math_verified True/False detail strings)
- _generate_ai_insights (profit / loss / margin branches)
- get_bill / 404
- list_bills pagination
- confirm_bill / duplicate confirm guard / corrected items / corrected total
- get_finance_summary month validation
- parse_text_bill (mocked bill_graph)
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from models.db_models import BillStatus, FinanceBill, LedgerEntry
from models.schemas import BillConfirmRequest, BillLineItemSchema, BillParseTextRequest
from services import finance_service


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _persist_raw_bill(db, *, math_verified=True, status=BillStatus.DRAFT_AI, bill_type="expense") -> FinanceBill:
    items = [{"name": "น้ำมันเครื่อง", "qty": 1.0, "unit_price": 200.0, "total": 200.0}]
    bill = FinanceBill(
        source_type="text",
        raw_input="ทดสอบ",
        extracted_items=json.dumps(items),
        extracted_total=200.0,
        calculated_total=200.0,
        math_verified=math_verified,
        math_discrepancy=0.0,
        status=status,
        bill_type=bill_type,
        vendor_name="ร้านทดสอบ",
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def _persist_ledger(db, bill_id: int, entry_type="expense", amount=200.0, month=8, year=2026):
    ledger = LedgerEntry(
        bill_id=bill_id,
        entry_type=entry_type,
        category="parts_purchase" if entry_type == "expense" else "repair_service",
        amount=amount,
        description="test entry",
        entry_date=datetime(year, month, 15),
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


# ─── _bill_to_response ────────────────────────────────────────────────────────

def test_bill_to_response_math_ok_detail(db):
    bill = _persist_raw_bill(db, math_verified=True)
    resp = finance_service._bill_to_response(bill)
    assert "✅" in resp.math_check_detail


def test_bill_to_response_math_fail_detail(db):
    bill = FinanceBill(
        source_type="text",
        raw_input="test",
        extracted_items=json.dumps([{"name": "x", "qty": 1.0, "unit_price": 100.0, "total": 100.0}]),
        extracted_total=200.0,
        calculated_total=100.0,
        math_verified=False,
        math_discrepancy=100.0,
        status="MATH_ERROR",
        bill_type="expense",
    )
    db.add(bill)
    db.commit()
    resp = finance_service._bill_to_response(bill)
    assert "❌" in resp.math_check_detail


# ─── get_bill ─────────────────────────────────────────────────────────────────

def test_get_bill_success(db):
    bill = _persist_raw_bill(db)
    resp = finance_service.get_bill(db, bill.id)
    assert resp.id == bill.id


def test_get_bill_not_found_raises_404(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        finance_service.get_bill(db, 99999)
    assert exc.value.status_code == 404


# ─── list_bills ───────────────────────────────────────────────────────────────

def test_list_bills_returns_total(db):
    _persist_raw_bill(db)
    _persist_raw_bill(db)
    result = finance_service.list_bills(db)
    assert result["total"] >= 2


def test_list_bills_limit(db):
    for _ in range(5):
        _persist_raw_bill(db)
    result = finance_service.list_bills(db, limit=2)
    assert len(result["items"]) <= 2


# ─── confirm_bill ─────────────────────────────────────────────────────────────

def test_confirm_bill_success(db):
    bill = _persist_raw_bill(db)
    req = BillConfirmRequest(confirmed_by="ผู้จัดการ")
    resp = finance_service.confirm_bill(db, bill.id, req)
    assert resp.status.value == "CONFIRMED"
    assert resp.confirmed_by == "ผู้จัดการ"


def test_confirm_bill_already_confirmed_raises_409(db):
    from fastapi import HTTPException
    bill = _persist_raw_bill(db, status=BillStatus.CONFIRMED)
    req = BillConfirmRequest(confirmed_by="ผู้จัดการ")
    with pytest.raises(HTTPException) as exc:
        finance_service.confirm_bill(db, bill.id, req)
    assert exc.value.status_code == 409


def test_confirm_bill_not_found_raises_404(db):
    from fastapi import HTTPException
    req = BillConfirmRequest(confirmed_by="ผู้จัดการ")
    with pytest.raises(HTTPException) as exc:
        finance_service.confirm_bill(db, 99999, req)
    assert exc.value.status_code == 404


def test_confirm_bill_with_corrected_items(db):
    bill = _persist_raw_bill(db)
    corrected = [BillLineItemSchema(name="อะไหล่ใหม่", qty=2.0, unit_price=500.0, total=1000.0)]
    req = BillConfirmRequest(confirmed_by="ผู้จัดการ", corrected_items=corrected)
    resp = finance_service.confirm_bill(db, bill.id, req)
    assert resp.calculated_total == 1000.0


def test_confirm_bill_with_corrected_total(db):
    bill = _persist_raw_bill(db)
    req = BillConfirmRequest(confirmed_by="ผู้จัดการ", corrected_total=999.0)
    resp = finance_service.confirm_bill(db, bill.id, req)
    assert resp.extracted_total == 999.0


# ─── get_finance_summary ──────────────────────────────────────────────────────

def test_get_finance_summary_invalid_month_raises_400(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        finance_service.get_finance_summary(db, 2026, 13)
    assert exc.value.status_code == 400


def test_get_finance_summary_invalid_year_raises_400(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        finance_service.get_finance_summary(db, 1990, 1)
    assert exc.value.status_code == 400


def test_get_finance_summary_empty_period(db):
    result = finance_service.get_finance_summary(db, 2025, 1)
    assert result.summary.total_income == 0.0
    assert result.summary.total_expense == 0.0
    assert result.summary.net_profit == 0.0


def test_get_finance_summary_with_ledger_entries(db):
    bill = _persist_raw_bill(db, bill_type="income", status=BillStatus.CONFIRMED)
    _persist_ledger(db, bill.id, entry_type="income", amount=5000.0, month=6, year=2026)
    result = finance_service.get_finance_summary(db, 2026, 6)
    assert result.summary.total_income == 5000.0
    assert result.summary.net_profit == 5000.0


# ─── _generate_ai_insights ────────────────────────────────────────────────────

def test_generate_ai_insights_profit():
    text = finance_service._generate_ai_insights(
        total_income=10000, total_expense=5000, net_profit=5000,
        margin=50.0, income_bd={"repair_service": 10000},
        expense_bd={"parts_purchase": 5000}, period="สิงหาคม 2569",
    )
    assert "กำไร" in text


def test_generate_ai_insights_loss():
    text = finance_service._generate_ai_insights(
        total_income=3000, total_expense=8000, net_profit=-5000,
        margin=-166.0, income_bd={"repair_service": 3000},
        expense_bd={"parts_purchase": 8000}, period="สิงหาคม 2569",
    )
    assert "ขาดทุน" in text


def test_generate_ai_insights_high_salary_ratio():
    text = finance_service._generate_ai_insights(
        total_income=10000, total_expense=5000, net_profit=5000,
        margin=50.0, income_bd={"repair_service": 10000},
        expense_bd={"salary": 4500}, period="สิงหาคม 2569",
    )
    assert "ค่าแรง" in text


# ─── parse_text_bill (integration — mocks bill_graph) ────────────────────────

def test_parse_text_bill_persists_and_returns(db):
    """Mock the LangGraph invocation to avoid network calls."""
    mock_state = {
        "raw_text": "ใบเสร็จทดสอบ",
        "source_type": "text",
        "bill_type": "expense",
        "vendor_name": "ร้านทดสอบ",
        "bill_date": None,
        "line_items": [{"name": "น้ำมันเครื่อง", "qty": 1.0, "unit_price": 200.0, "total": 200.0}],
        "extracted_total": 200.0,
        "calculated_total": 200.0,
        "math_verified": True,
        "math_discrepancy": 0.0,
        "status": "DRAFT_AI",
        "error": None,
    }
    with patch("services.finance_service.bill_graph") as mock_graph:
        mock_graph.invoke.return_value = mock_state
        req = BillParseTextRequest(raw_text="ใบเสร็จทดสอบ" * 3, bill_type="expense")
        resp = finance_service.parse_text_bill(db, req)
    assert resp.id is not None
    assert resp.math_verified is True
    assert resp.calculated_total == 200.0
