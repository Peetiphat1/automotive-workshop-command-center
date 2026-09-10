"""
Router: Suppliers — CRUD for supplier directory
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import json

from core.dependencies import get_db
from models.db_models import Supplier, PurchaseBill

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
    bill_number: Optional[str] = None
    bill_date: Optional[datetime] = None
    items: Optional[str] = None  # JSON string
    total_amount: float = 0.0
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


# ── Purchase Bills ────────────────────────────────────────────────────────────

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


@router.post("/purchases/")
def create_purchase(req: PurchaseBillCreate, db: Session = Depends(get_db)):
    bill = PurchaseBill(**req.model_dump())
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill
