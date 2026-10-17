"""
Unit tests for stock router functions — Module 5: Stock & Inventory

Covers:
- list_stock (all / category / search / low_stock filters)
- create_stock_item
- update_stock_item / 404
- delete_stock_item / 404
- adjust_stock (positive / negative / floor-at-zero) / 404
- get_stock_history / 404
- get_all_stock_history
- get_categories
- lookup_by_barcode / 404
- barcode_scan_action (add / deduct / lookup / unknown SKU)
- create_work_order (creates WorkOrder + FinanceBill + LedgerEntry)
"""
from __future__ import annotations

from models.db_models import Customer, StockHistory, StockItem, Vehicle
from routers.stock import (
    BarcodeScanRequest,
    StockAdjust,
    StockItemCreate,
    WorkOrderCreate,
    WorkOrderLineItem,
    adjust_stock,
    barcode_scan_action,
    create_stock_item,
    create_work_order,
    delete_stock_item,
    get_all_stock_history,
    get_categories,
    get_stock_history,
    list_stock,
    list_work_orders,
    lookup_by_barcode,
    update_stock_item,
)

import pytest
from fastapi import HTTPException


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_item(db, name_th="น้ำมันเครื่อง", sku="OIL001", category="น้ำมัน", qty=10) -> StockItem:
    item = StockItemCreate(
        name_th=name_th, sku=sku, category=category,
        quantity=qty, unit_cost=150.0, sell_price=200.0,
    )
    return create_stock_item(item, db)


# ─── list_stock ───────────────────────────────────────────────────────────────

def test_list_stock_returns_items(db):
    _make_item(db)
    items = list_stock(db=db)
    assert len(items) >= 1


def test_list_stock_filter_category(db):
    _make_item(db, category="น้ำมัน")
    _make_item(db, name_th="กรองอากาศ", sku="AIR001", category="ฟิลเตอร์")
    oil = list_stock(category="น้ำมัน", db=db)
    assert all(i["category"] == "น้ำมัน" for i in oil)


def test_list_stock_filter_low_stock(db):
    _make_item(db, qty=1)
    low = list_stock(low_stock=True, db=db)
    assert all(i["quantity"] <= i["reorder_level"] for i in low)


def test_list_stock_search(db):
    _make_item(db, name_th="น้ำมันเครื่อง")
    results = list_stock(search="น้ำมัน", db=db)
    assert any("น้ำมัน" in i["name_th"] for i in results)


# ─── create / update / delete ─────────────────────────────────────────────────

def test_create_stock_item_success(db):
    item = create_stock_item(
        StockItemCreate(name_th="ผ้าเบรค", category="เบรค", quantity=5, unit_cost=500.0, sell_price=700.0),
        db,
    )
    assert item.id is not None
    assert item.name_th == "ผ้าเบรค"


def test_update_stock_item_success(db):
    item = _make_item(db)
    updated = update_stock_item(
        item.id,
        StockItemCreate(name_th="น้ำมันเครื่องใหม่", category="น้ำมัน", quantity=20, unit_cost=160.0, sell_price=210.0),
        db,
    )
    assert updated.quantity == 20


def test_update_stock_item_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        update_stock_item(
            99999,
            StockItemCreate(name_th="X", category="X", quantity=1, unit_cost=1.0, sell_price=2.0),
            db,
        )
    assert exc.value.status_code == 404


def test_delete_stock_item_success(db):
    item = _make_item(db)
    result = delete_stock_item(item.id, db)
    assert result["status"] == "success"


def test_delete_stock_item_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        delete_stock_item(99999, db)
    assert exc.value.status_code == 404


# ─── adjust_stock ─────────────────────────────────────────────────────────────

def test_adjust_stock_add(db):
    item = _make_item(db, qty=10)
    result = adjust_stock(item.id, StockAdjust(delta=5, reason="รับของ"), db)
    assert result.quantity == 15


def test_adjust_stock_deduct(db):
    item = _make_item(db, qty=10)
    result = adjust_stock(item.id, StockAdjust(delta=-3, reason="ใช้ไป"), db)
    assert result.quantity == 7


def test_adjust_stock_floor_at_zero(db):
    item = _make_item(db, qty=2)
    result = adjust_stock(item.id, StockAdjust(delta=-100, reason="ทดสอบ"), db)
    assert result.quantity == 0


def test_adjust_stock_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        adjust_stock(99999, StockAdjust(delta=1, reason="x"), db)
    assert exc.value.status_code == 404


def test_adjust_stock_writes_history(db):
    item = _make_item(db, qty=10)
    adjust_stock(item.id, StockAdjust(delta=5, reason="test history"), db)
    history = db.query(StockHistory).filter(StockHistory.stock_item_id == item.id).all()
    assert len(history) >= 1
    assert history[-1].delta == 5


# ─── get_stock_history ────────────────────────────────────────────────────────

def test_get_stock_history_success(db):
    item = _make_item(db, qty=10)
    adjust_stock(item.id, StockAdjust(delta=1, reason="test"), db)
    history = get_stock_history(item.id, db)
    assert isinstance(history, list)
    assert len(history) >= 1


def test_get_stock_history_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        get_stock_history(99999, db)
    assert exc.value.status_code == 404


# ─── get_all_stock_history ────────────────────────────────────────────────────

def test_get_all_stock_history(db):
    item = _make_item(db, qty=5)
    adjust_stock(item.id, StockAdjust(delta=2, reason="all-history test"), db)
    result = get_all_stock_history(db=db)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "item_name" in result[0]


# ─── get_categories ───────────────────────────────────────────────────────────

def test_get_categories_returns_unique(db):
    _make_item(db, category="น้ำมัน")
    _make_item(db, name_th="กรองอากาศ", sku="AIR002", category="ฟิลเตอร์")
    cats = get_categories(db=db)
    assert "น้ำมัน" in cats
    assert "ฟิลเตอร์" in cats
    assert len(cats) == len(set(cats))  # all unique


# ─── lookup_by_barcode ────────────────────────────────────────────────────────

def test_lookup_by_barcode_success(db):
    _make_item(db, sku="TESTSKU123")
    result = lookup_by_barcode("TESTSKU123", db)
    assert result.sku == "TESTSKU123"


def test_lookup_by_barcode_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        lookup_by_barcode("NOTEXIST", db)
    assert exc.value.status_code == 404


# ─── barcode_scan_action ──────────────────────────────────────────────────────

def test_barcode_scan_add(db):
    item = _make_item(db, qty=5, sku="SCAN001")
    result = barcode_scan_action(BarcodeScanRequest(sku="SCAN001", action="add"), db)
    assert result["quantity_after"] == 6


def test_barcode_scan_deduct(db):
    item = _make_item(db, qty=5, sku="SCAN002")
    result = barcode_scan_action(BarcodeScanRequest(sku="SCAN002", action="deduct"), db)
    assert result["quantity_after"] == 4


def test_barcode_scan_lookup(db):
    item = _make_item(db, qty=5, sku="SCAN003")
    result = barcode_scan_action(BarcodeScanRequest(sku="SCAN003", action="lookup"), db)
    # lookup (delta=0) should not change qty
    assert result["quantity_after"] == result["quantity_before"]


def test_barcode_scan_unknown_sku_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        barcode_scan_action(BarcodeScanRequest(sku="DOESNOTEXIST", action="add"), db)
    assert exc.value.status_code == 404


def test_barcode_scan_empty_sku_raises_400(db):
    with pytest.raises(HTTPException) as exc:
        barcode_scan_action(BarcodeScanRequest(sku="", action="add"), db)
    assert exc.value.status_code == 400


# ─── create_work_order ────────────────────────────────────────────────────────

def test_create_work_order_creates_records(db):
    item = _make_item(db, qty=10, sku="WO001")
    order = WorkOrderCreate(
        mechanic_name="ช่างทดสอบ",
        line_items=[WorkOrderLineItem(
            name="น้ำมันเครื่อง", qty=2.0, unit_price=200.0, total=400.0, stock_item_id=item.id,
        )],
        labor_cost=500.0,
    )
    wo = create_work_order(order, db)
    assert wo.id is not None
    assert wo.total_cost == 900.0  # 400 parts + 500 labor
    # Stock should have been deducted
    db.refresh(item)
    assert item.quantity == 8


def test_create_work_order_deducts_stock(db):
    item = _make_item(db, qty=10, sku="WO002")
    order = WorkOrderCreate(
        mechanic_name="ช่างทดสอบ",
        line_items=[WorkOrderLineItem(
            name="น้ำมันเครื่อง", qty=3.0, unit_price=200.0, total=600.0, stock_item_id=item.id,
        )],
        labor_cost=0.0,
    )
    create_work_order(order, db)
    db.refresh(item)
    assert item.quantity == 7


def test_list_work_orders(db):
    item = _make_item(db, qty=10, sku="WO003")
    order = WorkOrderCreate(
        mechanic_name="ช่างทดสอบ",
        line_items=[],
        labor_cost=100.0,
    )
    create_work_order(order, db)
    result = list_work_orders(db=db)
    assert len(result) >= 1


def test_create_pos_sale_deducts_stock_and_logs_ledger(db):
    from routers.stock import PosSaleCreate, PosSaleItem, create_pos_sale, delete_work_order
    from models.db_models import LedgerEntry, StockHistory

    item = _make_item(db, qty=15, sku="POS-OIL", name_th="น้ำมันเครื่องสังเคราะห์")
    sale = PosSaleCreate(
        customer_name="คุณวิชัย ลูกค้าซื้อหน้าร้าน",
        customer_phone="0899998888",
        payment_method="เงินสด",
        items=[
            PosSaleItem(
                stock_item_id=item.id,
                name="น้ำมันเครื่องสังเคราะห์",
                qty=2.0,
                unit_price=350.0,
                total=700.0,
            )
        ],
        notes="ลูกค้าซื้ออะไหล่อย่างเดียวไม่ได้ทำงานซ่อม",
    )
    wo = create_pos_sale(sale, db)
    wo_id = wo["id"] if isinstance(wo, dict) else wo.id
    parts_cost = wo["parts_cost"] if isinstance(wo, dict) else wo.parts_cost
    assert wo_id is not None
    assert parts_cost == 700.0

    # Verify stock deduction
    db.refresh(item)
    assert item.quantity == 13

    # Verify stock history
    hist = db.query(StockHistory).filter(StockHistory.stock_item_id == item.id).first()
    assert hist is not None
    assert hist.change_type == "sale"

    # Verify ledger entry
    ledger = db.query(LedgerEntry).filter(LedgerEntry.category == "parts_sale").first()
    assert ledger is not None
    assert ledger.amount == 700.0

    # Verify deletion
    del_res = delete_work_order(wo_id, db)
    assert del_res["status"] == "success"


def test_delete_stock_item(db):
    from routers.stock import delete_stock_item
    item = _make_item(db, qty=5, sku="DEL-ITEM", name_th="อะไหล่ทดสอบลบ")
    res = delete_stock_item(item.id, db)
    assert res["status"] == "success"
    assert res["deleted_id"] == item.id


def test_update_stock_item_and_bill_path(db):
    from routers.stock import update_stock_item, StockItemCreate
    item = _make_item(db, qty=5, sku="MS-TEST-001", name_th="ฝาพาวเวอร์ Billet")
    update_data = StockItemCreate(
        name_th="ฝาพาวเวอร์ ISUZU Billet V2",
        name_en="Power Steering Cap Billet V2",
        sku="MS-TEST-001",
        category="อุปกรณ์แต่งห้องเครื่อง Billet",
        quantity=8,
        unit_cost=1200.0,
        sell_price=1500.0,
        reorder_level=3,
        bill_path="/static/uploads/bills/SO6908141_1.jpg",
    )
    updated = update_stock_item(item.id, update_data, db)
    assert updated.name_th == "ฝาพาวเวอร์ ISUZU Billet V2"
    assert updated.quantity == 8
    assert updated.bill_path == "/static/uploads/bills/SO6908141_1.jpg"

