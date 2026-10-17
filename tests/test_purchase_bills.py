"""
Unit tests for Supplier and PurchaseBill router operations.
Ensures parts purchase bills are correctly stored and retrieved in purchase history,
separate from operating expenses.
"""
from __future__ import annotations

import json
from datetime import datetime
from models.db_models import Supplier, PurchaseBill, Expense
from routers.suppliers import list_purchases, create_purchase, PurchaseBillCreate
from routers.expenses import list_expenses

def test_create_and_list_purchases(db):
    # 1. Create a supplier
    supplier = Supplier(name="หจก. สุวรรณการช่าง ทีทีเจ", phone="02-894-1234")
    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    # 2. Create a purchase bill
    items = [
        {"name": "เกจวัดบูส PPRC Pressure 45Psi", "qty": 5, "unit_price": 1750.0, "total": 8750.0},
        {"name": "ขาวัดบูท ดำ+แหวนกด", "qty": 5, "unit_price": 350.0, "total": 1750.0}
    ]
    req = PurchaseBillCreate(
        supplier_id=supplier.id,
        bill_number="ORCM6908000203",
        bill_date=datetime(2026, 8, 27, 10, 0),
        items=json.dumps(items),
        total_amount=10500.0,
        notes="บิลซื้ออะไหล่เครื่องยนต์"
    )
    bill = create_purchase(req, db)
    assert bill.id is not None
    assert bill.total_amount == 10500.0

    # 3. List purchases and verify
    purchases = list_purchases(db)
    matching = [p for p in purchases if p["bill_number"] == "ORCM6908000203"]
    assert len(matching) == 1
    assert matching[0]["supplier_name"] == "หจก. สุวรรณการช่าง ทีทีเจ"
    assert matching[0]["total_amount"] == 10500.0
    assert len(matching[0]["items"]) == 2

    # 4. Verify that expenses list does not contain this purchase bill
    exp_res = list_expenses(None, db)
    exp_items = exp_res["items"]
    for e in exp_items:
        assert e["category"] != "ซื้ออะไหล่/วัสดุ"


def test_create_manual_purchase_with_stock_update_and_delete(db):
    from models.db_models import StockItem, StockHistory
    from routers.suppliers import delete_purchase

    items = [
        {"name": "หัวเทียน NGK Laser Iridium", "qty": 4, "unit_price": 450.0, "total": 1800.0}
    ]
    req = PurchaseBillCreate(
        supplier_name="ร้านอะไหล่ด่วนพิเศษ",
        bill_number="INV-MANUAL-001",
        bill_date=datetime(2026, 9, 1, 14, 0),
        items=json.dumps(items),
        total_amount=1800.0,
        notes="ซื้ออะไหล่ Manual หน้าร้าน",
        update_stock=True
    )
    bill = create_purchase(req, db)
    assert bill.id is not None
    assert bill.supplier_id is not None

    # Verify supplier was created
    sup = db.query(Supplier).filter(Supplier.id == bill.supplier_id).first()
    assert sup is not None
    assert "ร้านอะไหล่ด่วนพิเศษ" in sup.name

    # Verify stock item was created/updated
    part = db.query(StockItem).filter(StockItem.name_th == "หัวเทียน NGK Laser Iridium").first()
    assert part is not None
    assert part.quantity >= 4

    # Verify stock history logged
    history = db.query(StockHistory).filter(StockHistory.stock_item_id == part.id).first()
    assert history is not None
    assert history.change_type == "purchase"

    # Delete purchase bill
    del_res = delete_purchase(bill.id, db)
    assert del_res["status"] == "success"
    assert db.query(PurchaseBill).filter(PurchaseBill.id == bill.id).first() is None


def test_update_purchase(db):
    from routers.suppliers import update_purchase, PurchaseBillUpdate

    # Create bill
    req = PurchaseBillCreate(
        supplier_name="ร้านนำโชค อะไหล่ยนต์",
        bill_number="INV-UPDATE-001",
        bill_date=datetime(2026, 9, 2, 10, 0),
        total_amount=5000.0,
        notes="ก่อนแก้ไข"
    )
    bill = create_purchase(req, db)
    assert bill.id is not None

    # Update bill
    update_req = PurchaseBillUpdate(
        bill_number="INV-UPDATE-EDITED",
        total_amount=6200.0,
        notes="แก้ไขข้อมูลเรียบร้อยแล้ว"
    )
    res = update_purchase(bill.id, update_req, db)
    assert res["status"] == "success"
    assert res["bill"]["bill_number"] == "INV-UPDATE-EDITED"
    assert res["bill"]["total_amount"] == 6200.0
    assert res["bill"]["notes"] == "แก้ไขข้อมูลเรียบร้อยแล้ว"
