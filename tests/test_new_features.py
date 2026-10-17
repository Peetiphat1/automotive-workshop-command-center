"""
Tests for the October 2026 features:
payments & outstanding balance, daily close, profit per job, stock reservation,
automatic daily backup, reorder suggestions, customer approval link, warranty,
mechanics commission, job photos and shop settings.
"""
from __future__ import annotations

import json
import os
import sqlite3

import pytest
from fastapi import HTTPException

from models.db_models import (
    Payment, PurchaseBill, ServiceTicket, StockItem, Supplier, TicketStatus,
)
from routers.stock import PosSaleCreate, PosSaleItem, StockItemCreate, create_pos_sale, create_stock_item, delete_work_order


# ─── helpers ──────────────────────────────────────────────────────────────────

def _part(db, sku="NF-1", qty=5, cost=60.0, price=100.0, name="หัวเทียนทดสอบ", reorder=2):
    return create_stock_item(StockItemCreate(
        name_th=name, sku=sku, category="ทดสอบ", quantity=qty, unit_cost=cost, sell_price=price, reorder_level=reorder,
    ), db)


def _job(client, plate="ฟีเจอร์ 1", mechanic="ช่างเอ", lines="ค่าแรง 500", **extra):
    body = {"raw_input": f"ใบแจ้งงาน:\n{lines}", "vehicle_plate": plate, "customer_name": "ลูกค้าฟีเจอร์",
            "customer_phone": "0822223333", "mechanic_name": mechanic}
    body.update(extra)
    r = client.post("/api/v1/tickets/ingest", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _approve(client, tid):
    r = client.post(f"/api/v1/tickets/{tid}/approve", json={"approved_by": "ผู้จัดการ"})
    assert r.status_code in (200, 409), r.text


# ─── 1. Payments ──────────────────────────────────────────────────────────────

def test_deposit_then_rest_and_outstanding(client):
    t = _job(client)
    _approve(client, t["id"])
    due = client.get(f"/api/v1/payments/ticket/{t['id']}").json()["amount_due"]
    assert due > 0

    r = client.post(f"/api/v1/payments/ticket/{t['id']}", json={"amount": 200, "method": "โอน", "note": "มัดจำ"})
    assert r.status_code == 200, r.text
    assert r.json()["payment_status"] == "partial"
    assert r.json()["balance_due"] == round(due - 200, 2)

    out = client.get("/api/v1/payments/outstanding").json()
    assert any(i["ticket_id"] == t["id"] and i["balance_due"] == round(due - 200, 2) for i in out["items"])

    # Paying more than is owed is refused
    assert client.post(f"/api/v1/payments/ticket/{t['id']}", json={"amount": due}).status_code == 400

    r = client.post(f"/api/v1/payments/ticket/{t['id']}", json={"amount": due - 200, "method": "เงินสด"})
    assert r.json()["payment_status"] == "paid"
    ticket = client.get(f"/api/v1/tickets/{t['id']}").json()
    assert ticket["payment_status"] == "paid" and ticket["balance_due"] == 0

    # Removing a payment puts the balance back
    pid = r.json()["payments"][-1]["id"]
    r = client.delete(f"/api/v1/payments/{pid}")
    assert r.json()["payment_status"] == "partial"


def test_pos_sale_is_paid_and_cancel_removes_payment(db):
    item = _part(db)
    sale = create_pos_sale(PosSaleCreate(payment_method="โอน", items=[PosSaleItem(stock_item_id=item.id, name="x", qty=1, unit_price=100)]), db)
    pay = db.query(Payment).filter(Payment.work_order_id == sale["id"]).one()
    assert pay.amount == 100 and pay.method == "โอน"
    delete_work_order(sale["id"], db)
    assert db.query(Payment).filter(Payment.work_order_id == sale["id"]).count() == 0


# ─── 2. Daily close ───────────────────────────────────────────────────────────

def test_daily_close_sums_money_by_method(client, db):
    t = _job(client, plate="ปิดยอด 1")
    _approve(client, t["id"])
    client.post(f"/api/v1/payments/ticket/{t['id']}", json={"amount": 100, "method": "เงินสด"})
    item = _part(db, sku="DC-1")
    create_pos_sale(PosSaleCreate(payment_method="โอน", items=[PosSaleItem(stock_item_id=item.id, name="x", qty=2, unit_price=100)]), db)
    client.post("/api/v1/expenses/", json={"category": "ค่าน้ำ", "amount": 30})

    d = client.get("/api/v1/reports/daily-close").json()
    assert d["received_by_method"].get("เงินสด", 0) >= 100
    assert d["received_by_method"].get("โอน", 0) >= 200
    assert d["total_expenses"] >= 30
    assert d["pos_sales_count"] >= 1
    assert any(p["name"] == item.name_th and p["qty"] == 2 for p in d["parts_used"])


# ─── 3. Profit per job ────────────────────────────────────────────────────────

def test_job_profit_uses_parts_cost(client, db):
    item = _part(db, sku="JP-1", qty=5, cost=60)
    t = _job(client, plate="กำไร 1", lines="หัวเทียนทดสอบ 200\nค่าแรง 300",
             stock_links=[{"name": "หัวเทียนทดสอบ", "stock_item_id": item.id, "qty": 2}])
    _approve(client, t["id"])
    client.post(f"/api/v1/tickets/{t['id']}/complete", json={})
    rep = client.get("/api/v1/reports/job-profit").json()
    row = next(r for r in rep["items"] if r["kind"] == "repair" and r["id"] == t["id"])
    assert row["parts_cost"] == 120          # 2 × 60
    assert row["profit"] == row["revenue"] - 120

    pnl = client.get("/api/v1/reports/profit").json()
    assert pnl["cogs"] >= 120
    assert pnl["total_revenue"] >= row["revenue"]


# ─── 4. Reservation ───────────────────────────────────────────────────────────

def test_parts_on_open_job_are_reserved(client, db):
    item = _part(db, sku="RS-1", qty=3)
    t = _job(client, plate="จอง 1", lines="หัวเทียนทดสอบ 300",
             stock_links=[{"name": "หัวเทียนทดสอบ", "stock_item_id": item.id, "qty": 2}])
    row = next(s for s in client.get("/api/v1/stock/").json() if s["id"] == item.id)
    assert row["reserved"] == 2 and row["available"] == 1

    # Only 1 can be sold at the counter while 2 are held for the job
    with pytest.raises(HTTPException) as e:
        create_pos_sale(PosSaleCreate(items=[PosSaleItem(stock_item_id=item.id, name="x", qty=2, unit_price=10)]), db)
    assert "จองไว้" in e.value.detail

    _approve(client, t["id"])
    client.post(f"/api/v1/tickets/{t['id']}/complete", json={})
    row = next(s for s in client.get("/api/v1/stock/").json() if s["id"] == item.id)
    assert row["quantity"] == 1 and row["reserved"] == 0


# ─── 5. Daily backup ──────────────────────────────────────────────────────────

def test_daily_backup_and_extra_copy(tmp_path, monkeypatch):
    from services import backup_service
    src = tmp_path / "live.db"
    con = sqlite3.connect(src)
    con.execute("create table t(x)")
    con.commit()
    con.close()
    monkeypatch.setattr(backup_service, "get_db_path", lambda: str(src))
    monkeypatch.setattr(backup_service, "BACKUP_DIR", str(tmp_path / "backups"))
    extra = tmp_path / "usb"
    extra.mkdir()

    r = backup_service.run_daily_backup(str(extra))
    assert r["created"] and not r["error"]
    assert os.path.exists(tmp_path / "backups" / r["last_file"])
    assert os.path.exists(extra / r["last_file"])
    assert backup_service.run_daily_backup(str(extra))["created"] is False  # once per day

    r = backup_service.run_daily_backup(str(tmp_path / "missing"))
    assert "ไม่พบโฟลเดอร์" in r["error"]


# ─── 7. Reorder suggestions ───────────────────────────────────────────────────

def test_reorder_groups_by_last_supplier(client, db):
    sup = Supplier(name="ร้านอะไหล่ทดสอบ", phone="021234567")
    db.add(sup)
    db.commit()
    item = _part(db, sku="RO-1", qty=1, reorder=3, name="ไส้กรองทดสอบ")
    db.add(PurchaseBill(supplier_id=sup.id, items=json.dumps([{"name": "ไส้กรองทดสอบ", "qty": 5, "unit_price": 45}]), total_amount=225))
    db.commit()
    data = client.get("/api/v1/stock/reorder/suggestions").json()
    group = next(g for g in data["groups"] if g["supplier_id"] == sup.id)
    line = next(i for i in group["items"] if i["stock_item_id"] == item.id)
    assert line["suggested_qty"] == 5     # target 2 × reorder (6) − available (1)
    assert line["unit_cost"] == 45


# ─── 8. Customer approval link ────────────────────────────────────────────────

def test_customer_approves_quote_through_public_link(client):
    t = _job(client, plate="อนุมัติ 1", lines="เปลี่ยนคลัตช์ 9000")  # over the threshold → waits for approval
    assert t["status"] == "PENDING_MECHANIC_APPROVAL"
    r = client.post(f"/api/v1/tickets/{t['id']}/request-approval")
    assert r.status_code == 200, r.text
    token = r.json()["link"].rsplit("/", 1)[1]

    pub = client.get(f"/api/v1/public/quote/{token}", headers={"X-API-Key": ""})
    assert pub.status_code == 200 and pub.json()["can_decide"]
    assert client.get("/api/v1/public/quote/wrong-token", headers={"X-API-Key": ""}).status_code == 404

    r = client.post(f"/api/v1/public/quote/{token}/decision", json={"decision": "approve"}, headers={"X-API-Key": ""})
    assert r.status_code == 200, r.text
    ticket = client.get(f"/api/v1/tickets/{t['id']}").json()
    assert ticket["status"] == "APPROVED" and ticket["customer_decision"] == "approved"
    # Answering twice is refused
    r = client.post(f"/api/v1/public/quote/{token}/decision", json={"decision": "decline"}, headers={"X-API-Key": ""})
    assert r.status_code == 409


def test_customer_declines_quote(client):
    t = _job(client, plate="อนุมัติ 2", lines="เปลี่ยนเกียร์ 25000")
    token = client.post(f"/api/v1/tickets/{t['id']}/request-approval").json()["link"].rsplit("/", 1)[1]
    client.post(f"/api/v1/public/quote/{token}/decision", json={"decision": "decline", "note": "แพงไป"}, headers={"X-API-Key": ""})
    ticket = client.get(f"/api/v1/tickets/{t['id']}").json()
    assert ticket["status"] == "PENDING_MECHANIC_APPROVAL"
    assert ticket["customer_decision"] == "declined" and ticket["customer_decision_note"] == "แพงไป"


# ─── 9. Warranty ──────────────────────────────────────────────────────────────

def test_warranty_shows_for_plate(client):
    t = _job(client, plate="ประกัน 99")
    _approve(client, t["id"])
    r = client.post(f"/api/v1/tickets/{t['id']}/complete", json={"warranty_months": 6, "warranty_note": "แบตเตอรี่"})
    assert r.json()["warranty_until"] is not None
    w = client.get("/api/v1/tickets/warranty/ประกัน 99").json()
    assert w and w[0]["ticket_id"] == t["id"] and w[0]["warranty_note"] == "แบตเตอรี่" and w[0]["days_left"] > 170


# ─── 10. Mechanics & commission ───────────────────────────────────────────────

def test_mechanics_report_uses_job_mechanic_and_setting(client):
    t = _job(client, plate="ช่าง 1", mechanic="ช่างทดสอบคอม", lines="ค่าแรง 1000")
    _approve(client, t["id"])
    assert client.put("/api/v1/settings/shop", json={"commission_pct": "15"}).status_code == 200
    rep = client.get("/api/v1/reports/mechanics").json()
    row = next(r for r in rep["items"] if r["mechanic_name"] == "ช่างทดสอบคอม")
    assert row["jobs_count"] == 1 and row["total_labor"] == 1000
    assert row["commission_rate"] == 15 and row["commission_amount"] == 150
    assert not any(r["mechanic_name"] == "ช่างเอก ใจดี" for r in rep["items"])  # no more made-up names


# ─── Photos & settings ────────────────────────────────────────────────────────

def test_job_photo_upload_and_delete(client):
    t = _job(client, plate="รูป 1")
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    r = client.post(f"/api/v1/tickets/{t['id']}/photos", files={"file": ("a.png", png, "image/png")}, data={"kind": "after"})
    assert r.status_code == 200, r.text
    photo = r.json()
    assert photo["kind"] == "after"
    assert client.get(f"/api/v1/tickets/{t['id']}").json()["photos"][0]["id"] == photo["id"]
    assert client.post(f"/api/v1/tickets/{t['id']}/photos", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 400
    assert client.delete(f"/api/v1/tickets/photos/{photo['id']}").status_code == 200


def test_shop_settings_validation(client):
    assert client.put("/api/v1/settings/shop", json={"commission_pct": "150"}).status_code == 400
    assert client.put("/api/v1/settings/shop", json={"shop_tax_id": "123"}).status_code == 400
    assert client.put("/api/v1/settings/shop", json={"nope": "1"}).status_code == 400
    r = client.put("/api/v1/settings/shop", json={"shop_tax_id": "0105555555555", "vat_registered": "1"})
    assert r.status_code == 200 and r.json()["vat_registered"] == "1"
