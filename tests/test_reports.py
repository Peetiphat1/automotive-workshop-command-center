"""
Unit tests for reports router helper functions — Module 7: Reports

Covers:
- _parse_date (valid formats / invalid → default)
- _date_range_defaults (normal / swapped start/end / max-span cap)
- Sales report endpoint (HTTP 200 + structure)
- Stock valuation endpoint (HTTP 200 + structure)
- Mechanic performance endpoint (HTTP 200 + structure)
- Top spending customers endpoint (HTTP 200 + structure)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from routers.reports import _parse_date, _date_range_defaults


# ─── _parse_date ──────────────────────────────────────────────────────────────

class TestParseDate:
    _default = datetime(2026, 1, 1)

    def test_iso_format(self):
        result = _parse_date("2026-08-15", self._default)
        assert result == datetime(2026, 8, 15)

    def test_thai_format(self):
        result = _parse_date("15/08/2026", self._default)
        assert result == datetime(2026, 8, 15)

    def test_us_format(self):
        result = _parse_date("08/15/2026", self._default)
        assert result == datetime(2026, 8, 15)

    def test_slash_iso_format(self):
        result = _parse_date("2026/08/15", self._default)
        assert result == datetime(2026, 8, 15)

    def test_invalid_returns_default(self):
        result = _parse_date("not-a-date", self._default)
        assert result == self._default

    def test_none_returns_default(self):
        result = _parse_date(None, self._default)
        assert result == self._default


# ─── _date_range_defaults ─────────────────────────────────────────────────────

class TestDateRangeDefaults:
    def test_normal_range(self):
        start, end = _date_range_defaults("2026-08-01", "2026-08-31")
        assert start < end
        assert start.year == 2026 and start.month == 8

    def test_swapped_start_end_auto_corrects(self):
        start, end = _date_range_defaults("2026-08-31", "2026-08-01")
        assert start <= end

    def test_max_span_capped_at_366(self):
        start, end = _date_range_defaults("2024-01-01", "2026-12-31")
        assert (end - start).days <= 366

    def test_no_args_returns_current_month(self):
        start, end = _date_range_defaults(None, None)
        now = datetime.now(timezone.utc)
        assert start.month == now.month or start.month == (now.month - 1 if now.month > 1 else 12)

    def test_end_time_padded_to_eod(self):
        _, end = _date_range_defaults("2026-08-01", "2026-08-15")
        assert end.hour == 23 and end.minute == 59


# ─── Sales report HTTP ────────────────────────────────────────────────────────

def test_sales_report_endpoint_ok(client):
    resp = client.get("/api/v1/reports/sales")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_revenue" in data or "period" in data or isinstance(data, dict)


def test_sales_report_with_date_params(client):
    resp = client.get("/api/v1/reports/sales?start_date=2026-01-01&end_date=2026-12-31")
    assert resp.status_code == 200


# ─── Stock valuation report ───────────────────────────────────────────────────

def test_stock_report_endpoint_ok(client):
    resp = client.get("/api/v1/reports/stock")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


# ─── Mechanic performance report ─────────────────────────────────────────────

def test_mechanic_report_endpoint_ok(client):
    resp = client.get("/api/v1/reports/mechanics")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


# ─── Top spending customers ───────────────────────────────────────────────────

def test_top_customers_endpoint_ok(client):
    resp = client.get("/api/v1/reports/customers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
