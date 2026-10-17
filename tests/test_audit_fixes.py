"""
Regression tests for the audit fixes (October 2026):
- shop password on /api/ routes, signed LINE webhook
- POS: no over-selling, whole quantities, edit and cancel give stock back
- exact "Ticket #N" / "Work Order #N" matching (no #1 vs #12 mix-ups)
- tickets: edit route, complete without vehicle, stock taken on complete, delete cleans up
- duplicate SKU, negative values, phone check, appointment double booking, expense date kept
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from models.db_models import FinanceBill, LedgerEntry, ServiceTicket, StockItem, TicketStatus, to_local_naive
from routers.stock import (
    PosSaleCreate,
    PosSaleItem,
    StockItemCreate,
    WorkOrderCreate,
    WorkOrderLineItem,
    create_pos_sale,
    create_stock_item,
    create_work_order,
    delete_work_order,
    update_pos_sale,
)
from services.ticket_service import ticket_ledger_entries


def _item(db, sku="AUD-1", qty=5, name="กรองน้ำมันเครื่องทดสอบ"):
    return create_stock_item(StockItemCreate(name_th=name, sku=sku, category="ทดสอบ", quantity=qty, sell_price=100), db)


def _sale(item_id, qty, name="x"):
    return PosSaleCreate(items=[PosSaleItem(stock_item_id=item_id, name=name, qty=qty, unit_price=100)])


# ─── Security ─────────────────────────────────────────────────────────────────

def test_api_open_when_password_off(client):
    assert client.get("/api/v1/stock/", headers={"X-API-Key": ""}).status_code == 200


def test_api_rejects_missing_or_wrong_key(client, monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "REQUIRE_PASSWORD", True)
    assert client.get("/api/v1/stock/", headers={"X-API-Key": ""}).status_code == 401
    assert client.get("/api/v1/stock/", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/api/v1/backup/wipe-all-data", headers={"X-API-Key": ""}).status_code == 401
    assert client.get("/api/v1/stock/").status_code == 200  # fixture sends the right key


def test_public_routes_need_no_key(client):
    assert client.get("/api/v1/tickets/track/abc", headers={"X-API-Key": ""}).status_code == 200
    assert client.get("/health").status_code == 200


def test_line_webhook_rejects_unsigned_request(client, monkeypatch):
    from services import ai_service
    monkeypatch.setattr(ai_service, "get_configured_key",
                        lambda name: "test-secret" if name == "LINE_OA_CHANNEL_SECRET" else "MOCK_LINE_TOKEN")
    body = b'{"events": []}'
    r = client.post("/api/v1/line/webhook", content=body, headers={"X-API-Key": ""})
    assert r.status_code == 401
    r = client.post("/api/v1/line/webhook", content=body, headers={"X-Line-Signature": "bad"})
    assert r.status_code == 401

    import base64, hashlib, hmac
    sig = base64.b64encode(hmac.new(b"test-secret", body, hashlib.sha256).digest()).decode()
    r = client.post("/api/v1/line/webhook", content=body, headers={"X-Line-Signature": sig, "X-API-Key": ""})
    assert r.status_code == 200


# ─── POS ──────────────────────────────────────────────────────────────────────

def test_pos_oversell_is_rejected_and_stock_untouched(db):
    item = _item(db, qty=5)
    with pytest.raises(HTTPException) as e:
        create_pos_sale(_sale(item.id, 6), db)
    assert e.value.status_code == 400
    db.refresh(item)
    assert item.quantity == 5
    assert db.query(FinanceBill).filter(FinanceBill.source_type == "pos_sale").count() == 0


def test_pos_rejects_fractional_and_negative_qty(db):
    item = _item(db)
    with pytest.raises(HTTPException):
        create_pos_sale(_sale(item.id, 1.5), db)
    with pytest.raises(ValueError):
        PosSaleItem(stock_item_id=item.id, name="x", qty=-2, unit_price=10)


def test_pos_sale_uses_local_time(db):
    item = _item(db)
    utc = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)  # = 1 Nov 03:00 in Bangkok
    req = _sale(item.id, 1)
    req.sale_date = utc
    res = create_pos_sale(req, db)
    assert res["work_date"].startswith("2026-11-01T03:00")


def test_pos_cancel_returns_stock_and_removes_income(db):
    item = _item(db, qty=5)
    sale = create_pos_sale(_sale(item.id, 2), db)
    db.refresh(item)
    assert item.quantity == 3
    delete_work_order(sale["id"], db)
    db.refresh(item)
    assert item.quantity == 5
    assert db.query(FinanceBill).filter(FinanceBill.raw_input.like(f"POS Sale #{sale['id']} -%")).count() == 0


def test_pos_edit_rebalances_stock_and_bill(db):
    item = _item(db, qty=5)
    sale = create_pos_sale(_sale(item.id, 2), db)
    res = update_pos_sale(sale["id"], _sale(item.id, 4), db)
    db.refresh(item)
    assert item.quantity == 1
    assert res["total_cost"] == 400
    bills = db.query(FinanceBill).filter(FinanceBill.raw_input.like(f"POS Sale #{sale['id']} -%")).all()
    assert len(bills) == 1 and bills[0].extracted_total == 400
    # Editing to more than is available fails and leaves everything as it was
    with pytest.raises(HTTPException):
        update_pos_sale(sale["id"], _sale(item.id, 99), db)
    db.refresh(item)
    assert item.quantity == 1


def test_delete_work_order_only_removes_its_own_bills(db):
    other = FinanceBill(source_type="text", raw_input="Work Order #12 - X by Y", bill_type="income", status="CONFIRMED")
    db.add(other)
    db.commit()
    wo = create_work_order(WorkOrderCreate(mechanic_name="ช่าง", line_items=[], labor_cost=100), db)
    assert wo.id is not None  # response used to be empty
    delete_work_order(wo.id, db)
    assert db.query(FinanceBill).filter(FinanceBill.id == other.id).count() == 1


def test_work_order_oversell_rejected(db):
    item = _item(db, qty=1)
    with pytest.raises(HTTPException):
        create_work_order(WorkOrderCreate(
            mechanic_name="ช่าง",
            line_items=[WorkOrderLineItem(name="x", qty=3, unit_price=10, total=30, stock_item_id=item.id)],
        ), db)


# ─── Stock validation ─────────────────────────────────────────────────────────

def test_duplicate_sku_gives_409(db):
    _item(db, sku="DUP-1")
    with pytest.raises(HTTPException) as e:
        _item(db, sku="DUP-1", name="อีกชิ้น")
    assert e.value.status_code == 409


def test_negative_stock_values_rejected():
    with pytest.raises(ValueError):
        StockItemCreate(name_th="x", category="y", quantity=-1)
    with pytest.raises(ValueError):
        StockItemCreate(name_th="x", category="y", sell_price=-5)


# ─── Tickets ──────────────────────────────────────────────────────────────────

def test_ticket_ledger_match_is_exact(db):
    db.add(LedgerEntry(entry_type="income", category="repair_service", amount=1,
                       description="รายรับค่าซ่อมรถ — Ticket #12 (กข 1)"))
    db.commit()
    assert ticket_ledger_entries(db, 1).count() == 0
    assert ticket_ledger_entries(db, 12).count() == 1


def _ingest(client, **extra):
    body = {"raw_input": "ใบแจ้งงาน:\nกรองน้ำมันเครื่องทดสอบ 300\nค่าแรง 200", "vehicle_plate": "ทดสอบ 77",
            "customer_name": "ลูกค้าทดสอบ", "customer_phone": "0811112222"}
    body.update(extra)
    r = client.post("/api/v1/tickets/ingest", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_ticket_edit_route(client):
    t = _ingest(client)
    r = client.put(f"/api/v1/tickets/{t['id']}", json={
        "mechanic_name": "ช่างใหม่",
        "line_items": [{"name": "ค่าแรง", "qty": 1, "unit_price": 500, "total": 500}],
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mechanic_name"] == "ช่างใหม่"
    assert d["total_estimated_cost"] == 500


def test_complete_ticket_without_vehicle_does_not_crash(client, db):
    t = _ingest(client)
    db.query(ServiceTicket).filter(ServiceTicket.id == t["id"]).update({"vehicle_id": None})
    db.commit()
    r = client.post(f"/api/v1/tickets/{t['id']}/complete", json={"final_cost": 500})
    assert r.status_code == 200, r.text


def test_ticket_stock_taken_on_complete_and_returned_on_delete(client, db):
    item = _item(db, qty=5)
    t = _ingest(client, stock_links=[{"name": "กรองน้ำมันเครื่องทดสอบ", "stock_item_id": item.id, "qty": 2}])
    assert any(i.get("stock_item_id") == item.id for i in t["line_items"])
    db.refresh(item)
    assert item.quantity == 5  # nothing taken until the job is done

    client.post(f"/api/v1/tickets/{t['id']}/approve", json={"approved_by": "ผู้จัดการ"})
    r = client.post(f"/api/v1/tickets/{t['id']}/complete", json={})
    assert r.status_code == 200, r.text
    db.refresh(item)
    assert item.quantity == 3

    # Completing twice is refused, so stock is never taken twice
    assert client.post(f"/api/v1/tickets/{t['id']}/complete", json={}).status_code == 409

    assert ticket_ledger_entries(db, t["id"]).count() == 1
    assert client.delete(f"/api/v1/tickets/{t['id']}").status_code == 200
    db.refresh(item)
    assert item.quantity == 5
    assert ticket_ledger_entries(db, t["id"]).count() == 0


def test_cannot_approve_completed_ticket(client):
    t = _ingest(client)
    client.post(f"/api/v1/tickets/{t['id']}/complete", json={})
    r = client.post(f"/api/v1/tickets/{t['id']}/approve", json={"approved_by": "ผู้จัดการ"})
    assert r.status_code == 409


# ─── Appointments / expenses / customers ──────────────────────────────────────

def test_appointment_double_booking(client):
    base = {"customer_name": "ก", "appointment_date": "2030-01-05T10:00:00", "time_slot": "10:00"}
    assert client.post("/api/v1/appointments/", json=base).status_code == 200
    assert client.post("/api/v1/appointments/", json={**base, "customer_name": "ข"}).status_code == 409
    r = client.post("/api/v1/appointments/", json={**base, "customer_name": "ข", "allow_overlap": True})
    assert r.status_code == 200
    # Editing an appointment without moving it is not a clash with itself
    appt_id = r.json()["id"]
    r = client.put(f"/api/v1/appointments/{appt_id}", json={**base, "customer_name": "ข แก้", "allow_overlap": True})
    assert r.status_code == 200 and r.json()["customer_name"] == "ข แก้"


def test_expense_must_be_positive_and_edit_keeps_date(client):
    assert client.post("/api/v1/expenses/", json={"category": "x", "amount": -5}).status_code == 422
    r = client.post("/api/v1/expenses/", json={"category": "x", "amount": 50, "expense_date": "2026-03-02T09:00:00"})
    eid = r.json()["id"]
    r = client.put(f"/api/v1/expenses/{eid}", json={"category": "x", "amount": 60})
    assert r.status_code == 200
    assert r.json()["expense_date"].startswith("2026-03-02")


def test_customer_phone_validation(client):
    assert client.post("/api/v1/customers/", json={"name": "x", "phone": "abc"}).status_code == 422
    assert client.post("/api/v1/customers/", json={"name": "x", "phone": "081-999-1234"}).status_code == 201


def test_to_local_naive():
    assert to_local_naive(datetime(2026, 1, 1, 17, 30, tzinfo=timezone.utc)) == datetime(2026, 1, 2, 0, 30)
    naive = datetime(2026, 1, 1, 8, 0)
    assert to_local_naive(naive) == naive
