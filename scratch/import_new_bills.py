import json
import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
from core.database import SessionLocal
from models.db_models import Supplier, PurchaseBill, StockItem, StockHistory, LedgerEntry, Expense

def run_import():
    db = SessionLocal()
    
    # ── 1. Copy bill images ──
    for folder in ["static/uploads/bills", "static/uploads/stock/bills", "static/images/bills"]:
        os.makedirs(folder, exist_ok=True)
    
    file_mapping = {
        "26248.jpg": ["D2_0684_2026.jpg", "26248.jpg"],
        "26249.jpg": ["SUWAN_ORCM6908000203_1.jpg", "26249.jpg"],
        "26250.jpg": ["SUWAN_ORCM6908000203_2.jpg", "26250.jpg"],
        "S__170254341.jpg": ["FAFO_SO691547_1.jpg", "S__170254341.jpg"],
        "S__170254342.jpg": ["FAFO_SO691547_2.jpg", "S__170254342.jpg"],
        "S__170254343.jpg": ["FAFO_SO691547_3.jpg", "S__170254343.jpg"],
        "S__170254344.jpg": ["FAFO_SO691547_4.jpg", "S__170254344.jpg"],
        "S__170254345.jpg": ["FAFO_SO691547_5.jpg", "S__170254345.jpg"],
    }
    
    for src_name, targets in file_mapping.items():
        src_path = os.path.join("bill", "new", src_name)
        if os.path.exists(src_path):
            for tgt in targets:
                shutil.copy2(src_path, os.path.join("static/uploads/bills", tgt))
                shutil.copy2(src_path, os.path.join("static/uploads/stock/bills", tgt))
                shutil.copy2(src_path, os.path.join("static/images/bills", tgt))
            print(f"Copied {src_name} -> {targets}")
        else:
            print(f"Warning: {src_path} not found")

    # ── 2. Suppliers ──
    sup_d2 = db.query(Supplier).filter(Supplier.id == 4).first()
    if not sup_d2:
        sup_d2 = Supplier(
            id=4,
            name="D2 moter sport wheels & tire (thailand) co.,ltd",
            phone="092-819-8203",
            address="101/305 หมู่ที่ 1 ต.ศีรษะจรเข้น้อย อ.บางเสาธง จ.สมุทรปราการ 10540",
            notes="ผู้จำหน่ายล้อแม็ก D2 และยางรถยนต์ชั้นนำ"
        )
        db.add(sup_d2)
        db.commit()

    sup_suwan = db.query(Supplier).filter(Supplier.id == 5).first()
    if not sup_suwan:
        sup_suwan = Supplier(
            id=5,
            name="หจก. สุวรรณการช่าง ทีทีเจ ( HPD special parts )",
            phone="081-888-7766",
            notes="อะไหล่แต่งซิ่ง HPD Special Parts ฝาวาล์ว เกจวัดบูส เรกกูเลเตอร์"
        )
        db.add(sup_suwan)
        db.commit()

    sup_fafo = db.query(Supplier).filter(Supplier.id == 7).first()
    if not sup_fafo:
        sup_fafo = Supplier(
            id=7,
            name="บริษัท ฟอร์ฟ อินเตอร์เนชั่นแนล จำกัด",
            phone="02-961-3717",
            address="69/37 หมู่1 ต.บ้านใหม่ อ.ปากเกร็ด จ.นนทบุรี",
            notes="ผู้ผลิตและนำเข้าล้อแม็ก AM, GREAT, TC105, ชุดปั๊มเบรค, และอุปกรณ์ช่วงล่าง"
        )
        db.add(sup_fafo)
        db.commit()

    # ── 3. Data for Bills ──
    from scratch.transcribe_new_bills import bill1_d2, bill2_suwan, bill3_fafo
    
    bills_to_import = [bill1_d2, bill2_suwan, bill3_fafo]
    
    created_bills = []
    total_parts_added = 0
    total_parts_updated = 0
    
    for b_data in bills_to_import:
        bill_num = b_data["bill_number"]
        existing_bill = db.query(PurchaseBill).filter(PurchaseBill.bill_number == bill_num).first()
        if existing_bill:
            print(f"Bill {bill_num} already exists (ID {existing_bill.id}). Updating...")
            pb = existing_bill
            pb.supplier_id = b_data["supplier_id"]
            pb.bill_date = datetime.strptime(b_data["bill_date"], "%Y-%m-%d %H:%M:%S")
            pb.items = json.dumps(b_data["items"], ensure_ascii=False)
            pb.total_amount = b_data["total_amount"]
            pb.image_path = b_data["image_paths"][0]
            pb.notes = b_data["notes"]
            db.commit()
        else:
            pb = PurchaseBill(
                supplier_id=b_data["supplier_id"],
                bill_number=bill_num,
                bill_date=datetime.strptime(b_data["bill_date"], "%Y-%m-%d %H:%M:%S"),
                items=json.dumps(b_data["items"], ensure_ascii=False),
                total_amount=b_data["total_amount"],
                image_path=b_data["image_paths"][0],
                notes=b_data["notes"]
            )
            db.add(pb)
            db.commit()
            db.refresh(pb)
            print(f"Created PurchaseBill {bill_num} with ID {pb.id}")
        
        created_bills.append(pb)
        
        # ── Ledger entry ──
        existing_ledger = db.query(LedgerEntry).filter(
            LedgerEntry.description.like(f"%บิล {bill_num}%")
        ).first()
        if not existing_ledger:
            ledger = LedgerEntry(
                entry_type="expense",
                category="parts_purchase",
                amount=b_data["total_amount"],
                description=f"จัดซื้ออะไหล่ {b_data['supplier_name']} (บิล {bill_num})",
                entry_date=pb.bill_date
            )
            db.add(ledger)
            db.commit()
            print(f"Created LedgerEntry for {bill_num}")

        # ── Expense entry ──
        existing_exp = db.query(Expense).filter(
            Expense.notes.like(f"%บิล {bill_num}%")
        ).first()
        if not existing_exp:
            exp = Expense(
                category="ซื้ออะไหล่",
                description=f"จัดซื้อสต็อกสินค้า {b_data['supplier_name']} (บิล {bill_num})",
                amount=b_data["total_amount"],
                expense_date=pb.bill_date,
                image_path=b_data["image_paths"][0],
                added_by="Antigravity AI (บิลจัดซื้อ)",
                notes=f"บิลจัดซื้อ {bill_num} รวม {len(b_data['items'])} รายการ"
            )
            db.add(exp)
            db.commit()
            print(f"Created Expense for {bill_num}")

        # ── Stock Items ──
        for it in b_data["items"]:
            sku = it.get("sku")
            name = it["name"]
            qty = int(it.get("qty", 1))
            cost = float(it.get("unit_price", 0.0))
            category = it.get("category", "อะไหล่และอุปกรณ์แต่ง")
            
            # Markup: 25% - 35%
            if cost > 5000:
                sell_price = round((cost * 1.25) / 50) * 50
            elif cost > 1000:
                sell_price = round((cost * 1.30) / 10) * 10
            else:
                sell_price = round((cost * 1.35) / 10) * 10
            
            # Find existing
            existing_item = None
            if sku:
                existing_item = db.query(StockItem).filter(StockItem.sku == sku).first()
            if not existing_item:
                existing_item = db.query(StockItem).filter(StockItem.name_th == name).first()
                
            if existing_item:
                q_before = existing_item.quantity
                existing_item.quantity += qty
                existing_item.unit_cost = cost
                if not existing_item.bill_path:
                    existing_item.bill_path = b_data["image_paths"][0]
                db.commit()
                
                hist = StockHistory(
                    stock_item_id=existing_item.id,
                    change_type="purchase",
                    delta=qty,
                    quantity_before=q_before,
                    quantity_after=existing_item.quantity,
                    reason=f"จัดซื้อเพิ่มเข้าสต็อก บิล {bill_num}",
                    changed_by="Antigravity AI"
                )
                db.add(hist)
                db.commit()
                total_parts_updated += 1
            else:
                new_item = StockItem(
                    name_th=name,
                    sku=sku or f"PRT-{datetime.now().strftime('%m%d%H%M%S')}",
                    category=category,
                    quantity=qty,
                    unit_cost=cost,
                    sell_price=sell_price,
                    reorder_level=max(1, qty // 3),
                    bill_path=b_data["image_paths"][0],
                    notes=f"นำเข้าจากบิล {bill_num} ({b_data['supplier_name']})"
                )
                db.add(new_item)
                db.commit()
                db.refresh(new_item)
                
                hist = StockHistory(
                    stock_item_id=new_item.id,
                    change_type="purchase",
                    delta=qty,
                    quantity_before=0,
                    quantity_after=qty,
                    reason=f"นำเข้าสต็อกใหม่ บิล {bill_num}",
                    changed_by="Antigravity AI"
                )
                db.add(hist)
                db.commit()
                total_parts_added += 1

    print("═════════════════════════════════════════════════════")
    print(f"✅ IMPORT SUCCESSFUL!")
    print(f"Bills processed: {len(created_bills)}")
    print(f"New stock items created: {total_parts_added}")
    print(f"Existing stock items updated: {total_parts_updated}")
    
    # Check total stock items count
    total_stock = db.query(StockItem).count()
    print(f"Total items in warehouse inventory now: {total_stock}")
    print("═════════════════════════════════════════════════════")
    db.close()

if __name__ == "__main__":
    run_import()
