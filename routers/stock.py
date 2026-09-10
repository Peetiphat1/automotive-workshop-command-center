from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import json
import os
import shutil

from core.dependencies import get_db
from models.db_models import StockItem, WorkOrder, Vehicle, Customer, FinanceBill, LedgerEntry, StockHistory

router = APIRouter()

class StockItemCreate(BaseModel):
    name_th: str
    name_en: Optional[str] = None
    sku: Optional[str] = None
    category: str
    quantity: int = 0
    unit_cost: float = 0.0
    sell_price: float = 0.0
    reorder_level: int = 5
    notes: Optional[str] = None

class StockAdjust(BaseModel):
    delta: int
    reason: str = ""

class WorkOrderLineItem(BaseModel):
    name: str
    qty: float
    unit_price: float
    total: float
    stock_item_id: Optional[int] = None

class WorkOrderCreate(BaseModel):
    vehicle_plate: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    mechanic_name: str
    description: Optional[str] = None
    line_items: List[WorkOrderLineItem] = []
    labor_cost: float = 0.0
    mileage: Optional[int] = None
    notes: Optional[str] = None


@router.get("/")
def list_stock(category: Optional[str] = None, search: Optional[str] = None, low_stock: Optional[bool] = False, db: Session = Depends(get_db)):
    query = db.query(StockItem)
    if category and category != 'All':
        query = query.filter(StockItem.category == category)
    if search:
        query = query.filter(StockItem.name_th.contains(search) | StockItem.name_en.contains(search) | StockItem.sku.contains(search))
    if low_stock:
        query = query.filter(StockItem.quantity <= StockItem.reorder_level)
    
    items = query.order_by(StockItem.category, StockItem.name_th).all()
    return items

@router.post("/")
def create_stock_item(item: StockItemCreate, db: Session = Depends(get_db)):
    db_item = StockItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.put("/{id}")
def update_stock_item(id: int, item: StockItemCreate, db: Session = Depends(get_db)):
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    for k, v in item.model_dump().items():
        setattr(db_item, k, v)
    
    db.commit()
    db.refresh(db_item)
    return db_item

@router.delete("/{id}")
def delete_stock_item(id: int, db: Session = Depends(get_db)):
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()
    return {"status": "success"}

@router.put("/{id}/adjust")
def adjust_stock(id: int, adjust: StockAdjust, db: Session = Depends(get_db)):
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    qty_before = db_item.quantity
    db_item.quantity += adjust.delta
    if db_item.quantity < 0:
        db_item.quantity = 0
    qty_after = db_item.quantity

    # Log to stock history
    history = StockHistory(
        stock_item_id=id,
        change_type="adjust",
        delta=adjust.delta,
        quantity_before=qty_before,
        quantity_after=qty_after,
        reason=adjust.reason,
        changed_by=adjust.changed_by,
    )
    db.add(history)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/{id}/history")
def get_stock_history(id: int, db: Session = Depends(get_db)):
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    history = db.query(StockHistory).filter(StockHistory.stock_item_id == id).order_by(StockHistory.created_at.desc()).limit(50).all()
    return [{
        "id": h.id, "change_type": h.change_type, "delta": h.delta,
        "quantity_before": h.quantity_before, "quantity_after": h.quantity_after,
        "reason": h.reason, "changed_by": h.changed_by,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    } for h in history]

@router.get("/history/all")
def get_all_stock_history(limit: int = 100, db: Session = Depends(get_db)):
    history = db.query(StockHistory).order_by(StockHistory.created_at.desc()).limit(limit).all()
    result = []
    for h in history:
        item = db.query(StockItem).filter(StockItem.id == h.stock_item_id).first()
        result.append({
            "id": h.id,
            "item_name": item.name_th if item else "ไม่ระบุ",
            "item_sku": item.sku if item else None,
            "change_type": h.change_type, "delta": h.delta,
            "quantity_before": h.quantity_before, "quantity_after": h.quantity_after,
            "reason": h.reason, "changed_by": h.changed_by,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        })
    return result

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    items = db.query(StockItem.category).distinct().all()
    categories = [item[0] for item in items if item[0]]
    return categories

@router.post("/upload-image/{id}")
def upload_image(id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    os.makedirs("static/images/parts", exist_ok=True)
    file_path = f"static/images/parts/{id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    db_item.image_filename = f"{id}_{file.filename}"
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/workorders/")
def list_work_orders(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    return db.query(WorkOrder).order_by(WorkOrder.created_at.desc()).offset(offset).limit(limit).all()

@router.post("/workorders/")
def create_work_order(order: WorkOrderCreate, db: Session = Depends(get_db)):
    parts_cost = 0.0
    for item in order.line_items:
        if item.stock_item_id:
            db_item = db.query(StockItem).filter(StockItem.id == item.stock_item_id).first()
            if db_item:
                db_item.quantity -= int(item.qty)
                if db_item.quantity < 0:
                    db_item.quantity = 0
        parts_cost += item.qty * item.unit_price
        
    total_cost = order.labor_cost + parts_cost
    
    vehicle_id = None
    customer_id = None
    if order.vehicle_plate:
        vehicle = db.query(Vehicle).filter(Vehicle.plate == order.vehicle_plate).first()
        if vehicle:
            vehicle_id = vehicle.id
            customer_id = vehicle.customer_id
            
    if not customer_id and order.customer_phone:
        customer = db.query(Customer).filter(Customer.phone == order.customer_phone).first()
        if customer:
            customer_id = customer.id
            
    wo = WorkOrder(
        vehicle_plate=order.vehicle_plate,
        vehicle_brand=order.vehicle_brand,
        vehicle_model=order.vehicle_model,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        mechanic_name=order.mechanic_name,
        description=order.description,
        line_items=json.dumps([item.model_dump() for item in order.line_items], ensure_ascii=False),
        labor_cost=order.labor_cost,
        parts_cost=parts_cost,
        total_cost=total_cost,
        mileage=order.mileage,
        notes=order.notes,
        vehicle_id=vehicle_id,
        customer_id=customer_id
    )
    
    db.add(wo)
    db.commit()
    db.refresh(wo)
    
    # Create FinanceBill + LedgerEntry
    now = datetime.utcnow()
    extracted_items = [
        {"name": item.name, "qty": float(item.qty), "unit_price": float(item.unit_price), "total": float(item.total)}
        for item in order.line_items
    ]
    if order.labor_cost > 0:
        extracted_items.append({"name": "ค่าแรง (Labor)", "qty": 1.0, "unit_price": float(order.labor_cost), "total": float(order.labor_cost)})
        
    bill = FinanceBill(
        source_type="text",
        raw_input=f"Work Order #{wo.id} - {order.vehicle_plate or 'No Plate'} by {order.mechanic_name}",
        extracted_items=json.dumps(extracted_items, ensure_ascii=False),
        extracted_total=total_cost,
        calculated_total=total_cost,
        math_verified=True,
        status="CONFIRMED",
        bill_date=now,
        vendor_name="อู่ซ่อมรถ (Work Order)",
        bill_type="income",
        confirmed_by=order.mechanic_name,
        confirmed_at=now,
        notes=f"Auto-generated from Work Order #{wo.id}"
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    
    ledger_entry = LedgerEntry(
        bill_id=bill.id,
        entry_type="income",
        category="repair_service",
        amount=total_cost,
        description=f"รายรับซ่อมรถ Work Order #{wo.id}",
        entry_date=now
    )
    db.add(ledger_entry)
    db.commit()
    
    return wo
