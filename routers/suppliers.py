"""
Router: Suppliers — CRUD for supplier directory
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, List, Union
from pydantic import BaseModel
from datetime import datetime
import json
import os
import shutil

from core.dependencies import get_db
from models.db_models import Supplier, PurchaseBill, StockItem, StockHistory
from models.db_models import get_local_now, to_local_naive

router = APIRouter()


class SupplierCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    line_id: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class PurchaseBillCreate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    bill_number: Optional[str] = None
    bill_date: Optional[datetime] = None
    items: Optional[str] = None  # JSON string
    total_amount: float = 0.0
    image_path: Optional[str] = None
    notes: Optional[str] = None
    update_stock: Optional[bool] = False


class PurchaseBillUpdate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    bill_number: Optional[str] = None
    bill_date: Optional[datetime] = None
    items: Optional[Union[str, list]] = None
    total_amount: Optional[float] = None
    image_path: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
def list_suppliers(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Supplier)
    if search:
        query = query.filter(Supplier.name.contains(search) | Supplier.phone.contains(search))
    suppliers = query.order_by(Supplier.name).all()
    result = []
    for s in suppliers:
        bills = db.query(PurchaseBill).filter(PurchaseBill.supplier_id == s.id).order_by(PurchaseBill.bill_date.desc()).all()
        result.append({
            "id": s.id, "name": s.name, "phone": s.phone, "email": s.email,
            "line_id": s.line_id, "address": s.address, "notes": s.notes,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "total_purchases": len(bills),
            "total_amount": sum(b.total_amount or 0 for b in bills),
            "purchase_bills": [{
                "id": b.id, "bill_number": b.bill_number,
                "bill_date": b.bill_date.isoformat() if b.bill_date else None,
                "total_amount": b.total_amount, "notes": b.notes
            } for b in bills[:5]]
        })
    return result


@router.post("/")
def create_supplier(req: SupplierCreate, db: Session = Depends(get_db)):
    supplier = Supplier(**req.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/{supplier_id}")
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    bills = db.query(PurchaseBill).filter(PurchaseBill.supplier_id == supplier.id).order_by(PurchaseBill.bill_date.desc()).all()
    return {
        "id": supplier.id, "name": supplier.name, "phone": supplier.phone,
        "email": supplier.email, "line_id": supplier.line_id, "address": supplier.address,
        "notes": supplier.notes,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None,
        "purchase_bills": [{
            "id": b.id, "bill_number": b.bill_number,
            "bill_date": b.bill_date.isoformat() if b.bill_date else None,
            "items": b.get_items(), "total_amount": b.total_amount, "notes": b.notes
        } for b in bills]
    }


# ── Purchase Bills — must come BEFORE /{supplier_id} to avoid routing conflict ─

@router.get("/purchases/all")
def list_purchases(db: Session = Depends(get_db)):
    bills = db.query(PurchaseBill).order_by(PurchaseBill.bill_date.desc()).all()
    result = []
    for b in bills:
        supplier = db.query(Supplier).filter(Supplier.id == b.supplier_id).first() if b.supplier_id else None
        result.append({
            "id": b.id, "bill_number": b.bill_number,
            "bill_date": b.bill_date.isoformat() if b.bill_date else None,
            "supplier_name": supplier.name if supplier else "ไม่ระบุ",
            "items": b.get_items(), "total_amount": b.total_amount,
            "image_path": b.image_path, "notes": b.notes,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return result


@router.post("/purchases/upload-image")
def upload_purchase_bill_image(file: UploadFile = File(...)):
    os.makedirs("static/images/bills", exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"bill_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(3).hex()}{ext}"
    file_path = f"static/images/bills/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"image_path": f"/static/images/bills/{filename}"}


@router.post("/purchases/")
def create_purchase(req: PurchaseBillCreate, db: Session = Depends(get_db)):
    sup_id = req.supplier_id
    if not sup_id and req.supplier_name and req.supplier_name.strip():
        name_clean = req.supplier_name.strip()
        sup = db.query(Supplier).filter(Supplier.name.ilike(f"%{name_clean}%")).first()
        if not sup:
            sup = Supplier(name=name_clean, notes="บันทึกจากการจัดซื้อ Manual")
            db.add(sup)
            db.commit()
            db.refresh(sup)
        sup_id = sup.id

    bill_num = req.bill_number.strip() if req.bill_number else None
    if not bill_num:
        bill_num = f"PB-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    bill_dt = to_local_naive(req.bill_date) if req.bill_date else get_local_now()

    # Parse items if passed as string or list
    parsed_items = []
    if req.items:
        if isinstance(req.items, str):
            try:
                parsed_items = json.loads(req.items)
            except Exception:
                parsed_items = []
        elif isinstance(req.items, list):
            parsed_items = req.items

    total = req.total_amount
    if (not total or total == 0.0) and parsed_items:
        total = sum(float(i.get("total", (float(i.get("qty", 1)) * float(i.get("unit_price", 0))))) for i in parsed_items)

    bill = PurchaseBill(
        supplier_id=sup_id,
        bill_number=bill_num,
        bill_date=bill_dt,
        items=json.dumps(parsed_items, ensure_ascii=False) if parsed_items else req.items,
        total_amount=round(float(total or 0.0), 2),
        image_path=req.image_path,
        notes=req.notes
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)

    # Optional auto stock update
    if req.update_stock and parsed_items:
        for it in parsed_items:
            name = (it.get("name") or it.get("name_th") or "").strip()
            if not name:
                continue
            qty = int(it.get("qty") or 1)
            cost = float(it.get("unit_price") or it.get("cost") or 0.0)
            sku = (it.get("sku") or "").strip()

            existing = None
            if sku:
                existing = db.query(StockItem).filter(StockItem.sku == sku).first()
            if not existing:
                existing = db.query(StockItem).filter(StockItem.name_th == name).first()

            if existing:
                q_before = existing.quantity
                existing.quantity += qty
                if cost > 0:
                    existing.unit_cost = cost
                db.commit()

                hist = StockHistory(
                    stock_item_id=existing.id,
                    change_type="purchase",
                    delta=qty,
                    quantity_before=q_before,
                    quantity_after=existing.quantity,
                    reason=f"จัดซื้อเข้าสต็อก บิล {bill.bill_number}",
                    changed_by="Manual (บันทึกจัดซื้อ)"
                )
                db.add(hist)
                db.commit()
            else:
                auto_sku = sku or f"PRT-{datetime.now().strftime('%m%d%H%M%S')}-{os.urandom(2).hex()}"
                sell_price = round(cost * 1.35 / 10) * 10 if cost > 0 else 0.0
                new_item = StockItem(
                    name_th=name,
                    sku=auto_sku,
                    category="ทั่วไป",
                    quantity=qty,
                    unit_cost=cost,
                    sell_price=sell_price,
                    reorder_level=2,
                    notes=f"สร้างอัตโนมัติจากบิลจัดซื้อ {bill.bill_number}"
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
                    reason=f"เพิ่มอะไหล่ใหม่ บิล {bill.bill_number}",
                    changed_by="Manual (บันทึกจัดซื้อ)"
                )
                db.add(hist)
                db.commit()

    return bill


@router.put("/purchases/{id}")
def update_purchase(id: int, req: PurchaseBillUpdate, db: Session = Depends(get_db)):
    bill = db.query(PurchaseBill).filter(PurchaseBill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    
    if req.supplier_name is not None and req.supplier_name.strip():
        name_clean = req.supplier_name.strip()
        sup = db.query(Supplier).filter(Supplier.name.ilike(f"%{name_clean}%")).first()
        if not sup:
            sup = Supplier(name=name_clean, notes="บันทึกจากการจัดซื้อ")
            db.add(sup)
            db.commit()
            db.refresh(sup)
        bill.supplier_id = sup.id
    elif req.supplier_id is not None:
        bill.supplier_id = req.supplier_id

    if req.bill_number is not None:
        bill.bill_number = req.bill_number.strip()
    if req.bill_date is not None:
        bill.bill_date = to_local_naive(req.bill_date)
    if req.total_amount is not None:
        bill.total_amount = round(float(req.total_amount), 2)
    if req.notes is not None:
        bill.notes = req.notes
    if req.image_path is not None:
        bill.image_path = req.image_path
    if req.items is not None:
        if isinstance(req.items, list):
            bill.items = json.dumps(req.items, ensure_ascii=False)
        else:
            bill.items = str(req.items)
            
    db.commit()
    db.refresh(bill)
    return {
        "status": "success",
        "bill": {
            "id": bill.id,
            "bill_number": bill.bill_number,
            "bill_date": bill.bill_date.isoformat() if bill.bill_date else None,
            "supplier_id": bill.supplier_id,
            "total_amount": bill.total_amount,
            "notes": bill.notes,
            "image_path": bill.image_path
        }
    }


@router.delete("/purchases/{id}")
def delete_purchase(id: int, db: Session = Depends(get_db)):
    bill = db.query(PurchaseBill).filter(PurchaseBill.id == id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    db.delete(bill)
    db.commit()
    return {"status": "success", "deleted_id": id}


@router.put("/{supplier_id}")
def update_supplier(supplier_id: int, req: SupplierCreate, db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(supplier, k, v)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    # Unlink any purchase bills referencing this supplier so records remain intact
    db.query(PurchaseBill).filter(PurchaseBill.supplier_id == supplier_id).update({"supplier_id": None})
    db.delete(supplier)
    db.commit()
    return {"status": "deleted", "deleted_id": supplier_id}

