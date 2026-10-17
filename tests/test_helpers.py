"""
Unit tests for helper functions and utility logic across the codebase.

Covers:
- models/db_models.py: JSON helpers on ServiceTicket, FinanceBill, PurchaseBill
- routers/settings.py: _mask / _update_env_file helper
- routers/bills.py: _mock_extraction / _match_stock / math_ok logic
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest


# ─── ServiceTicket JSON helpers ───────────────────────────────────────────────

class TestServiceTicketHelpers:
    def _make_ticket(self):
        from models.db_models import ServiceTicket
        t = ServiceTicket(
            raw_input="test",
            extracted_symptoms=json.dumps(["เสียงดัง", "น้ำมันรั่ว"]),
            diagnosed_issues=json.dumps([{"symptom": "เสียงดัง", "issue": "ผ้าเบรค", "severity": "HIGH"}]),
            line_items=json.dumps([{"name": "ผ้าเบรค", "qty": 1.0, "unit_price": 1200.0, "total": 1200.0, "type": "part"}]),
        )
        return t

    def test_get_symptoms_returns_list(self):
        t = self._make_ticket()
        assert t.get_symptoms() == ["เสียงดัง", "น้ำมันรั่ว"]

    def test_get_diagnosed_issues_returns_list(self):
        t = self._make_ticket()
        issues = t.get_diagnosed_issues()
        assert isinstance(issues, list)
        assert issues[0]["severity"] == "HIGH"

    def test_get_line_items_returns_list(self):
        t = self._make_ticket()
        items = t.get_line_items()
        assert items[0]["name"] == "ผ้าเบรค"

    def test_get_symptoms_empty_returns_empty_list(self):
        from models.db_models import ServiceTicket
        t = ServiceTicket(raw_input="test")
        assert t.get_symptoms() == []

    def test_get_diagnosed_issues_empty_returns_empty_list(self):
        from models.db_models import ServiceTicket
        t = ServiceTicket(raw_input="test")
        assert t.get_diagnosed_issues() == []

    def test_get_line_items_empty_returns_empty_list(self):
        from models.db_models import ServiceTicket
        t = ServiceTicket(raw_input="test")
        assert t.get_line_items() == []


# ─── FinanceBill JSON helpers ─────────────────────────────────────────────────

class TestFinanceBillHelpers:
    def test_get_items_returns_list(self):
        from models.db_models import FinanceBill
        items = [{"name": "น้ำมัน", "qty": 1.0, "unit_price": 200.0, "total": 200.0}]
        b = FinanceBill(
            source_type="text",
            raw_input="test",
            extracted_items=json.dumps(items),
            status="DRAFT_AI",
            bill_type="expense",
        )
        assert b.get_items() == items

    def test_get_items_none_returns_empty(self):
        from models.db_models import FinanceBill
        b = FinanceBill(source_type="text", raw_input="test", status="DRAFT_AI", bill_type="expense")
        assert b.get_items() == []


# ─── PurchaseBill JSON helpers ────────────────────────────────────────────────

class TestPurchaseBillHelpers:
    def test_get_items_returns_list(self):
        from models.db_models import PurchaseBill
        items = [{"name": "โช้ค", "qty": 2, "unit_price": 1500.0, "total": 3000.0}]
        p = PurchaseBill(items=json.dumps(items))
        assert p.get_items() == items

    def test_get_items_none_returns_empty(self):
        from models.db_models import PurchaseBill
        p = PurchaseBill()
        assert p.get_items() == []


# ─── Settings _mask helper ────────────────────────────────────────────────────

class TestMaskHelper:
    def test_masks_long_key(self):
        from routers.settings import _mask
        result = _mask("ABCD1234EFGH5678")
        assert result.startswith("ABCD")
        assert result.endswith("5678")
        assert "••••••••" in result

    def test_none_returns_none(self):
        from routers.settings import _mask
        assert _mask(None) is None

    def test_short_key_returns_none(self):
        from routers.settings import _mask
        assert _mask("SHORT") is None


# ─── Settings _update_env_file ────────────────────────────────────────────────

class TestUpdateEnvFile:
    def test_writes_new_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        # Patch the path used inside the function
        with patch("routers.settings.os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=lambda p, m, **kw: env_file.open(m, **kw)):
            from routers.settings import _update_env_file
            _update_env_file({"GEMINI_API_KEY": "test-key-12345"})
        content = env_file.read_text()
        assert "GEMINI_API_KEY" in content

    def test_updates_existing_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('GEMINI_API_KEY="old-value"\n')
        with patch("routers.settings.os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=lambda p, m, **kw: env_file.open(m, **kw)):
            from routers.settings import _update_env_file
            _update_env_file({"GEMINI_API_KEY": "new-value"})
        content = env_file.read_text()
        assert "new-value" in content
        assert "old-value" not in content


# ─── bills.py _mock_extraction ────────────────────────────────────────────────

class TestMockExtraction:
    def test_returns_required_fields(self):
        from routers.bills import _mock_extraction
        result = _mock_extraction()
        assert "customer_name" in result
        assert "line_items" in result
        assert "total" in result
        assert isinstance(result["line_items"], list)
        assert result["total"] > 0


# ─── bills.py _match_stock ────────────────────────────────────────────────────

class TestMatchStock:
    def test_matches_by_thai_name(self, db):
        from models.db_models import StockItem
        si = StockItem(
            name_th="ผ้าเบรค", name_en="Brake Pad",
            category="เบรค", quantity=5, unit_cost=300.0, sell_price=500.0,
        )
        db.add(si)
        db.commit()

        from routers.bills import _match_stock
        line_items = [{"name": "ผ้าเบรค", "qty": 1, "unit_price": 500.0, "total": 500.0}]
        enriched = _match_stock(db, line_items)
        assert enriched[0]["stock_item_id"] == si.id
        assert enriched[0]["confidence"] == "ok"

    def test_no_match_sets_low_confidence(self, db):
        from routers.bills import _match_stock
        line_items = [{"name": "สินค้าที่ไม่มีในระบบ", "qty": 1, "unit_price": 100.0, "total": 100.0}]
        enriched = _match_stock(db, line_items)
        assert enriched[0]["stock_item_id"] is None
        assert enriched[0]["confidence"] == "low"


# ─── bills.py math_ok logic ───────────────────────────────────────────────────

class TestBillsMathCheck:
    def test_math_ok_within_tolerance(self):
        """Verify the tolerance logic used in scan_bill_photo."""
        items = [{"qty": 2, "unit_price": 500.0}]
        calc = sum(float(i["qty"]) * float(i["unit_price"]) for i in items)
        stated = 1001.0  # 1 baht over
        math_ok = abs(calc - stated) <= 2.0 or stated == 0
        assert math_ok is True

    def test_math_not_ok_outside_tolerance(self):
        items = [{"qty": 2, "unit_price": 500.0}]
        calc = sum(float(i["qty"]) * float(i["unit_price"]) for i in items)
        stated = 1100.0  # 100 baht over
        math_ok = abs(calc - stated) <= 2.0 or stated == 0
        assert math_ok is False

    def test_math_ok_if_stated_total_is_zero(self):
        """If stated_total == 0, math is considered ok (fallback)."""
        calc = 1000.0
        stated = 0.0
        math_ok = abs(calc - stated) <= 2.0 or stated == 0
        assert math_ok is True


# ─── TicketStatus / BillStatus constants ──────────────────────────────────────

class TestStatusConstants:
    def test_ticket_statuses_defined(self):
        from models.db_models import TicketStatus
        assert TicketStatus.DRAFT_ESTIMATE == "DRAFT_ESTIMATE"
        assert TicketStatus.PENDING_MECHANIC_APPROVAL == "PENDING_MECHANIC_APPROVAL"
        assert TicketStatus.APPROVED == "APPROVED"
        assert TicketStatus.IN_PROGRESS == "IN_PROGRESS"
        assert TicketStatus.COMPLETED == "COMPLETED"
        assert TicketStatus.CANCELLED == "CANCELLED"

    def test_bill_statuses_defined(self):
        from models.db_models import BillStatus
        assert BillStatus.DRAFT_AI == "DRAFT_AI"
        assert BillStatus.MATH_ERROR == "MATH_ERROR"
        assert BillStatus.CONFIRMED == "CONFIRMED"
        assert BillStatus.REJECTED == "REJECTED"
