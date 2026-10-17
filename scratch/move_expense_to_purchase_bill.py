import json
from datetime import datetime
from core.database import SessionLocal
from models.db_models import Supplier, PurchaseBill, Expense
from scratch.import_paper_parts import parts_data

def migrate():
    db = SessionLocal()
    
    # 1. Check or create Supplier
    supplier = db.query(Supplier).filter(Supplier.name.like("%สุวรรณการช่าง%")).first()
    if not supplier:
        supplier = Supplier(
            name="หจก. สุวรรณการช่าง ทีทีเจ (SUWAN KARNCHANG TTJ)",
            phone="02-894-1234",
            email="suwan.ttj@example.com",
            address="กรุงเทพมหานคร",
            notes="ผู้ผลิตและจำหน่ายอุปกรณ์ตกแต่ง อะไหล่แต่ง และเกจวัด PPRC",
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        print(f"Created Supplier: ID {supplier.id} - {supplier.name}")
    else:
        print(f"Found existing Supplier: ID {supplier.id} - {supplier.name}")

    # 2. Get Expense record 14
    exp = db.query(Expense).filter(Expense.id == 14).first()
    image_path = exp.image_path if exp else "/static/uploads/bills/img_33006eb87453.jpg"

    # 3. Build items list
    items = []
    total_amount = 0.0
    for p in parts_data:
        qty = int(p["qty"])
        cost = float(p["cost"])
        line_total = round(qty * cost, 2)
        total_amount += line_total
        items.append({
            "name": p["name_th"],
            "qty": qty,
            "unit_price": cost,
            "total": line_total
        })

    # 4. Check or create PurchaseBill
    pb = db.query(PurchaseBill).filter(PurchaseBill.bill_number == "ORCM6908000203").first()
    if not pb:
        pb = PurchaseBill(
            supplier_id=supplier.id,
            bill_number="ORCM6908000203",
            bill_date=datetime(2026, 8, 27, 10, 30),
            items=json.dumps(items, ensure_ascii=False),
            total_amount=round(total_amount, 2),
            image_path=image_path,
            notes="บิลซื้ออะไหล่เครื่องยนต์และของแต่งรถ (หจก. สุวรรณการช่าง ทีทีเจ)"
        )
        db.add(pb)
        db.commit()
        db.refresh(pb)
        print(f"Created PurchaseBill: ID {pb.id} - {pb.bill_number} (฿{pb.total_amount:,.2f})")
    else:
        pb.items = json.dumps(items, ensure_ascii=False)
        pb.total_amount = round(total_amount, 2)
        pb.image_path = image_path
        db.commit()
        print(f"Updated existing PurchaseBill: ID {pb.id}")

    # 5. Delete Expense 14
    if exp:
        db.delete(exp)
        db.commit()
        print("Deleted Expense #14 from expenses table.")

    # 6. Also check if there are any remaining expenses with category 'ซื้ออะไหล่/วัสดุ'
    other_parts_exp = db.query(Expense).filter(Expense.category == "ซื้ออะไหล่/วัสดุ").all()
    for e in other_parts_exp:
        print(f"Removing other parts expense #{e.id}: {e.description}")
        db.delete(e)
    if other_parts_exp:
        db.commit()

    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
