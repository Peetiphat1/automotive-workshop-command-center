from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import json
import os
import shutil

from core.dependencies import get_db
from models.db_models import (
    StockItem, WorkOrder, Vehicle, Customer, FinanceBill, LedgerEntry, StockHistory,
    PurchaseBill, Supplier, get_local_now, to_local_naive,
)
from services import payment_service
from services.ticket_service import reserved_stock

router = APIRouter()

class StockItemCreate(BaseModel):
    name_th: str = Field(..., min_length=1)
    name_en: Optional[str] = None
    sku: Optional[str] = None
    category: str
    quantity: int = Field(0, ge=0)
    unit_cost: float = Field(0.0, ge=0)
    sell_price: float = Field(0.0, ge=0)
    reorder_level: int = Field(5, ge=0)
    notes: Optional[str] = None
    bill_path: Optional[str] = None

class StockAdjust(BaseModel):
    delta: int
    reason: str = ""
    changed_by: str = "ผู้จัดการ"

class BarcodeScanRequest(BaseModel):
    sku: str
    action: str = "add"  # "add", "deduct", "lookup"
    delta: Optional[int] = None
    reason: Optional[str] = None
    changed_by: Optional[str] = "สแกนเนอร์ห้องสต๊อก"

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


class PosSaleItem(BaseModel):
    stock_item_id: Optional[int] = None
    name: str
    qty: float = Field(1.0, gt=0)
    unit_price: float = Field(0.0, ge=0)
    total: float = 0.0


class PosSaleCreate(BaseModel):
    customer_name: Optional[str] = "ลูกค้าทั่วไป (Walk-in)"
    customer_phone: Optional[str] = None
    sale_date: Optional[datetime] = None
    payment_method: Optional[str] = "เงินสด"
    items: List[PosSaleItem] = []
    notes: Optional[str] = None


# ── Stock movement helpers (shared by work orders and POS sales) ──────────────

def _resolve_stock_item(db: Session, stock_item_id: Optional[int], name: Optional[str]) -> Optional[StockItem]:
    item = None
    if stock_item_id:
        item = db.query(StockItem).filter(StockItem.id == stock_item_id).first()
    if not item and name:
        item = db.query(StockItem).filter(StockItem.name_th == name.strip()).first()
    return item


def _whole_qty(qty: float, name: str) -> int:
    if qty <= 0:
        raise HTTPException(status_code=400, detail=f"จำนวนของ \"{name}\" ต้องมากกว่า 0")
    if qty != int(qty):
        raise HTTPException(status_code=400, detail=f"จำนวนของ \"{name}\" ต้องเป็นจำนวนเต็ม (สต็อกนับเป็นหน่วย)")
    return int(qty)


def _deduct_stock(db: Session, lines: list, reason: str, changed_by: str) -> None:
    """Check every line first, then deduct. Raises 400 (nothing changed) if any item is short.
    Each line is a dict with name, qty and optional stock_item_id; stock_item_id is filled in when matched."""
    need = {}
    for line in lines:
        item = _resolve_stock_item(db, line.get("stock_item_id"), line.get("name"))
        if item:
            line["stock_item_id"] = item.id
            need[item.id] = need.get(item.id, 0) + int(line["qty"])
    held = reserved_stock(db) if need else {}
    for item_id, qty in need.items():
        item = db.query(StockItem).filter(StockItem.id == item_id).first()
        reserved = held.get(item_id, 0)
        available = item.quantity - reserved
        if available < qty:
            extra = f" (จองไว้สำหรับงานซ่อม {reserved} ชิ้น)" if reserved else ""
            raise HTTPException(
                status_code=400,
                detail=f"สต็อกไม่พอ: \"{item.name_th}\" ขายได้ {max(available, 0)} ชิ้น แต่ต้องการ {qty}{extra}",
            )
    costs = {}
    for item_id, qty in need.items():
        item = db.query(StockItem).filter(StockItem.id == item_id).first()
        costs[item_id] = item.unit_cost or 0.0
        before = item.quantity
        item.quantity = before - qty
        db.add(StockHistory(
            stock_item_id=item.id, change_type="sale", delta=-qty,
            quantity_before=before, quantity_after=item.quantity,
            reason=reason, changed_by=changed_by,
        ))
    for line in lines:  # cost at the time of sale, for profit per job
        if line.get("stock_item_id") in costs:
            line["unit_cost"] = costs[line["stock_item_id"]]


def _restore_stock(db: Session, lines: list, reason: str, changed_by: str) -> None:
    """Put the stock of previously deducted lines back."""
    for line in lines:
        item_id = line.get("stock_item_id")
        if not item_id:
            continue
        item = db.query(StockItem).filter(StockItem.id == item_id).first()
        if not item:
            continue
        qty = int(line.get("qty") or 0)
        if qty <= 0:
            continue
        before = item.quantity
        item.quantity = before + qty
        db.add(StockHistory(
            stock_item_id=item.id, change_type="return", delta=qty,
            quantity_before=before, quantity_after=item.quantity,
            reason=reason, changed_by=changed_by,
        ))


def _work_order_bills(db: Session, wo_id: int) -> list:
    """Finance bills created for exactly this work order / POS sale (not #12 when wo_id is 1)."""
    return db.query(FinanceBill).filter(or_(
        FinanceBill.raw_input.like(f"Work Order #{wo_id} -%"),
        FinanceBill.raw_input.like(f"POS Sale #{wo_id} -%"),
    )).all()


def _wo_lines(wo: WorkOrder) -> list:
    try:
        return json.loads(wo.line_items) if wo.line_items else []
    except (ValueError, TypeError):
        return []


def _check_sku_free(db: Session, sku: Optional[str], exclude_id: Optional[int] = None) -> None:
    if not sku or not sku.strip():
        return
    q = db.query(StockItem).filter(StockItem.sku == sku.strip())
    if exclude_id:
        q = q.filter(StockItem.id != exclude_id)
    other = q.first()
    if other:
        raise HTTPException(status_code=409, detail=f"รหัส SKU \"{sku}\" ซ้ำกับสินค้า \"{other.name_th}\" (ID #{other.id})")


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
    held = reserved_stock(db)
    return [_stock_dict(i, held.get(i.id, 0)) for i in items]


def _stock_dict(item: StockItem, reserved: int = 0) -> dict:
    d = {c.name: getattr(item, c.name) for c in StockItem.__table__.columns}
    d["reserved"] = reserved
    d["available"] = item.quantity - reserved
    return d


@router.get("/reorder/suggestions", summary="Parts at or below the reorder level, grouped by last supplier")
def reorder_suggestions(db: Session = Depends(get_db)):
    held = reserved_stock(db)
    low = []
    for item in db.query(StockItem).order_by(StockItem.name_th).all():
        available = item.quantity - held.get(item.id, 0)
        if available <= (item.reorder_level or 0):
            low.append((item, available))
    if not low:
        return {"count": 0, "groups": []}

    # Last supplier each part was bought from (newest purchase bill wins)
    last_supplier = {}
    for bill in db.query(PurchaseBill).order_by(PurchaseBill.bill_date.desc()).all():
        for it in bill.get_items():
            key = it.get("stock_item_id") or (it.get("name") or "").strip()
            if key and key not in last_supplier:
                last_supplier[key] = (bill.supplier_id, it.get("unit_price"))

    groups = {}
    for item, available in low:
        sup_id, last_price = last_supplier.get(item.id) or last_supplier.get(item.name_th.strip()) or (None, None)
        target = max((item.reorder_level or 0) * 2, 1)
        g = groups.setdefault(sup_id, [])
        g.append({
            "stock_item_id": item.id, "name": item.name_th, "sku": item.sku,
            "quantity": item.quantity, "reserved": held.get(item.id, 0), "available": available,
            "reorder_level": item.reorder_level, "suggested_qty": max(target - available, 1),
            "unit_cost": last_price if last_price is not None else item.unit_cost,
        })

    result = []
    for sup_id, items in groups.items():
        sup = db.query(Supplier).filter(Supplier.id == sup_id).first() if sup_id else None
        result.append({
            "supplier_id": sup.id if sup else None,
            "supplier_name": sup.name if sup else "ยังไม่ทราบผู้จำหน่าย",
            "supplier_phone": sup.phone if sup else None,
            "supplier_line_id": sup.line_id if sup else None,
            "items": items,
        })
    result.sort(key=lambda g: (g["supplier_id"] is None, g["supplier_name"]))
    return {"count": len(low), "groups": result}

@router.post("/")
def create_stock_item(item: StockItemCreate, db: Session = Depends(get_db)):
    _check_sku_free(db, item.sku)
    data = item.model_dump()
    data["sku"] = (item.sku or "").strip() or None
    db_item = StockItem(**data)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.put("/{id}")
def update_stock_item(id: int, item: StockItemCreate, db: Session = Depends(get_db)):
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    _check_sku_free(db, item.sku, exclude_id=id)

    data = item.model_dump()
    data["sku"] = (item.sku or "").strip() or None
    for k, v in data.items():
        setattr(db_item, k, v)

    db.commit()
    db.refresh(db_item)
    return db_item

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

    # Log to stock history (real change, in case it was clamped at 0)
    history = StockHistory(
        stock_item_id=id,
        change_type="adjust",
        delta=qty_after - qty_before,
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

@router.get("/barcode/{sku}")
def lookup_by_barcode(sku: str, db: Session = Depends(get_db)):
    """Exact SKU lookup for barcode scanner — returns item or 404."""
    db_item = db.query(StockItem).filter(StockItem.sku == sku).first()
    if not db_item:
        raise HTTPException(status_code=404, detail=f"No item found with SKU: {sku}")
    return db_item

@router.get("/barcode/identify/{sku}")
async def identify_by_barcode(sku: str, db: Session = Depends(get_db)):
    """
    Auto-identify an unknown barcode or SKU using:
      - Local inventory check
      - Source B: Global retail product barcode databases (Open Product Facts / EAN)
      - Source C: Automotive OEM/Aftermarket parts catalogs & web sources
      - AI Synthesis (Gemini / OpenAI) with offline automotive heuristics
    """
    from services import barcode_service
    result = await barcode_service.identify_barcode(sku, db)
    return result

@router.post("/barcode/scan")
def barcode_scan_action(payload: BarcodeScanRequest, db: Session = Depends(get_db)):
    """Instant barcode scan action (e.g. +1 receive, -1 issue, or lookup) for stock room workflows."""
    sku = (payload.sku or "").strip()
    if not sku:
        raise HTTPException(status_code=400, detail="กรุณาระบุรหัสบาร์โค้ด (SKU)")

    db_item = db.query(StockItem).filter(StockItem.sku == sku).first()
    if not db_item:
        db_item = db.query(StockItem).filter(StockItem.sku.ilike(sku)).first()
    if not db_item:
        raise HTTPException(status_code=404, detail=f"ไม่พบสินค้าสำหรับ SKU: {sku}")

    qty_before = db_item.quantity
    delta = payload.delta
    if delta is None:
        if payload.action == "add":
            delta = 1
        elif payload.action == "deduct":
            delta = -1
        else:
            delta = 0

    if delta != 0:
        db_item.quantity += delta
        if db_item.quantity < 0:
            db_item.quantity = 0
        qty_after = db_item.quantity

        reason = payload.reason or (f"สแกนเนอร์ห้องสต๊อก ({'+' if delta > 0 else ''}{delta})")
        history = StockHistory(
            stock_item_id=db_item.id,
            change_type="adjust",
            delta=qty_after - qty_before,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reason=reason,
            changed_by=payload.changed_by or "สแกนเนอร์ห้องสต๊อก",
        )
        db.add(history)
        db.commit()
        db.refresh(db_item)
    else:
        qty_after = qty_before

    return {
        "status": "success",
        "action": payload.action,
        "delta": delta,
        "quantity_before": qty_before,
        "quantity_after": qty_after,
        "item": {
            "id": db_item.id,
            "name_th": db_item.name_th,
            "name_en": db_item.name_en,
            "sku": db_item.sku,
            "category": db_item.category,
            "quantity": db_item.quantity,
            "unit_cost": db_item.unit_cost,
            "sell_price": db_item.sell_price,
            "reorder_level": db_item.reorder_level,
            "image_filename": getattr(db_item, 'image_filename', None)
        }
    }

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


@router.post("/upload-bill/{id}")
@router.post("/{id}/upload-bill")
def upload_stock_bill(id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a purchase bill / receipt image for a stock item."""
    db_item = db.query(StockItem).filter(StockItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    os.makedirs("static/uploads/bills", exist_ok=True)
    ext = os.path.splitext(file.filename or "bill.jpg")[1] or ".jpg"
    import uuid as _uuid
    filename = f"stock_{id}_{_uuid.uuid4().hex[:8]}{ext}"
    file_path = f"static/uploads/bills/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_item.bill_path = f"/static/uploads/bills/{filename}"
    db.commit()
    db.refresh(db_item)
    return {
        "id": db_item.id,
        "bill_path": db_item.bill_path,
        "name_th": db_item.name_th,
    }

@router.get("/workorders/")
def list_work_orders(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    return db.query(WorkOrder).order_by(WorkOrder.created_at.desc()).offset(offset).limit(limit).all()

@router.post("/workorders/")
def create_work_order(order: WorkOrderCreate, db: Session = Depends(get_db)):
    lines = []
    parts_cost = 0.0
    for item in order.line_items:
        line = item.model_dump()
        line["qty"] = _whole_qty(item.qty, item.name)
        lines.append(line)
        parts_cost += item.qty * item.unit_price

    # Only lines explicitly linked to stock are deducted for work orders
    linked = [l for l in lines if l.get("stock_item_id")]
    _deduct_stock(db, linked, f"เบิกใช้ในงานซ่อม ({order.vehicle_plate or 'ไม่ระบุทะเบียน'})", order.mechanic_name)

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

    now = get_local_now()
    wo = WorkOrder(
        vehicle_plate=order.vehicle_plate,
        vehicle_brand=order.vehicle_brand,
        vehicle_model=order.vehicle_model,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        mechanic_name=order.mechanic_name,
        work_date=now,
        description=order.description,
        line_items=json.dumps(lines, ensure_ascii=False),
        labor_cost=order.labor_cost,
        parts_cost=parts_cost,
        total_cost=total_cost,
        mileage=order.mileage,
        notes=order.notes,
        vehicle_id=vehicle_id,
        customer_id=customer_id
    )
    db.add(wo)
    db.flush()

    # Create FinanceBill + LedgerEntry
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
    db.flush()

    db.add(LedgerEntry(
        bill_id=bill.id,
        entry_type="income",
        category="repair_service",
        amount=total_cost,
        description=f"รายรับซ่อมรถ Work Order #{wo.id}",
        entry_date=now
    ))
    db.commit()
    db.refresh(wo)
    return wo


def _prepare_pos_lines(req: PosSaleCreate) -> tuple:
    lines = []
    total = 0.0
    for item in req.items:
        qty = _whole_qty(item.qty, item.name)
        price = float(item.unit_price)
        line_total = round(qty * price, 2)
        total += line_total
        lines.append({
            "name": item.name.strip(),
            "qty": qty,
            "unit_price": price,
            "total": line_total,
            "stock_item_id": item.stock_item_id,
        })
    return lines, round(total, 2)


def _write_pos_finance(db: Session, wo: WorkOrder, lines: list, total: float, sale_dt: datetime,
                       cust_name: str, payment_method: str) -> None:
    bill = FinanceBill(
        source_type="pos_sale",
        raw_input=f"POS Sale #{wo.id} - {cust_name} ({len(lines)} รายการ)",
        extracted_items=json.dumps(lines, ensure_ascii=False),
        extracted_total=total,
        calculated_total=total,
        math_verified=True,
        status="CONFIRMED",
        bill_date=sale_dt,
        vendor_name=cust_name,
        bill_type="income",
        confirmed_by="หน้าร้าน (POS)",
        confirmed_at=sale_dt,
        notes=f"ขายอะไหล่หน้าร้าน (POS) วิธีชำระ: {payment_method}"
    )
    db.add(bill)
    db.flush()
    db.add(LedgerEntry(
        bill_id=bill.id,
        entry_type="income",
        category="parts_sale",
        amount=total,
        description=f"รายรับขายอะไหล่หน้าร้าน (POS) บิล #{wo.id} - {cust_name}",
        entry_date=sale_dt
    ))


def _delete_wo_finance(db: Session, wo_id: int) -> None:
    for b in _work_order_bills(db, wo_id):
        db.query(LedgerEntry).filter(LedgerEntry.bill_id == b.id).delete()
        db.delete(b)


def _pos_response(wo: WorkOrder, lines: list) -> dict:
    return {
        "id": wo.id,
        "customer_name": wo.customer_name,
        "customer_phone": wo.customer_phone,
        "parts_cost": wo.parts_cost,
        "total_cost": wo.total_cost,
        "description": wo.description,
        "work_date": wo.work_date.isoformat() if wo.work_date else None,
        "line_items": lines,
        "status": "success"
    }


@router.post("/pos-sale")
def create_pos_sale(req: PosSaleCreate, db: Session = Depends(get_db)):
    if not req.items:
        raise HTTPException(status_code=400, detail="กรุณาระบุรายการอะไหล่อย่างน้อย 1 รายการ")

    sale_dt = to_local_naive(req.sale_date) if req.sale_date else get_local_now()
    cust_name = req.customer_name.strip() if req.customer_name and req.customer_name.strip() else "ลูกค้าทั่วไป (Walk-in)"
    payment = req.payment_method or "เงินสด"

    lines, total = _prepare_pos_lines(req)
    # Validates every line before touching stock — an over-sale changes nothing
    _deduct_stock(db, lines, f"ขายอะไหล่หน้าร้าน (POS) ให้กับ {cust_name}", "หน้าร้าน (POS)")

    wo = WorkOrder(
        customer_name=cust_name,
        customer_phone=req.customer_phone,
        mechanic_name="หน้าร้าน (POS)",
        work_date=sale_dt,
        description=f"ขายอะไหล่หน้าร้าน (POS) [{payment}]",
        line_items=json.dumps(lines, ensure_ascii=False),
        labor_cost=0.0,
        parts_cost=total,
        total_cost=total,
        notes=req.notes,
    )
    db.add(wo)
    db.flush()
    _write_pos_finance(db, wo, lines, total, sale_dt, cust_name, payment)
    payment_service.record_work_order_payment(db, wo.id, total, payment, sale_dt)
    db.commit()
    db.refresh(wo)
    return _pos_response(wo, lines)


@router.put("/workorders/{id}")
@router.put("/pos-sale/{id}")
def update_pos_sale(id: int, req: PosSaleCreate, db: Session = Depends(get_db)):
    """Edit a POS sale: returns the old items to stock, deducts the new ones and rewrites its bill."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="ไม่พบรายการขาย")
    if wo.mechanic_name != "หน้าร้าน (POS)":
        raise HTTPException(status_code=400, detail="แก้ไขได้เฉพาะบิลขายหน้าร้าน (POS)")
    if not req.items:
        raise HTTPException(status_code=400, detail="กรุณาระบุรายการอะไหล่อย่างน้อย 1 รายการ")

    cust_name = req.customer_name.strip() if req.customer_name and req.customer_name.strip() else "ลูกค้าทั่วไป (Walk-in)"
    payment = req.payment_method or "เงินสด"
    sale_dt = to_local_naive(req.sale_date) if req.sale_date else wo.work_date

    # Savepoint: if the new items don't fit in stock, undo only the "give back old items" step
    savepoint = db.begin_nested()
    try:
        _restore_stock(db, _wo_lines(wo), f"แก้ไขบิลขาย #{wo.id} (คืนรายการเดิม)", "หน้าร้าน (POS)")
        db.flush()
        lines, total = _prepare_pos_lines(req)
        _deduct_stock(db, lines, f"แก้ไขบิลขาย #{wo.id} ให้กับ {cust_name}", "หน้าร้าน (POS)")
        db.flush()
    except HTTPException:
        savepoint.rollback()
        raise
    savepoint.commit()

    wo.customer_name = cust_name
    wo.customer_phone = req.customer_phone
    wo.work_date = sale_dt
    wo.description = f"ขายอะไหล่หน้าร้าน (POS) [{payment}]"
    wo.line_items = json.dumps(lines, ensure_ascii=False)
    wo.parts_cost = total
    wo.total_cost = total
    wo.notes = req.notes

    _delete_wo_finance(db, wo.id)
    _write_pos_finance(db, wo, lines, total, sale_dt, cust_name, payment)
    payment_service.record_work_order_payment(db, wo.id, total, payment, sale_dt)
    db.commit()
    db.refresh(wo)
    return _pos_response(wo, lines)


@router.delete("/workorders/{id}")
@router.post("/pos-sale/{id}/void")
def delete_work_order(id: int, db: Session = Depends(get_db)):
    """Cancel a work order / POS sale: parts go back to stock and its income is removed."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    _restore_stock(db, _wo_lines(wo), f"ยกเลิกบิล #{wo.id} (คืนสต็อก)", "ระบบ")
    _delete_wo_finance(db, wo.id)
    payment_service.delete_work_order_payments(db, wo.id)
    db.delete(wo)
    db.commit()
    return {"status": "success", "deleted_id": id}


@router.delete("/{item_id}")
def delete_stock_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้าในสต็อก")
    # Delete associated stock history
    db.query(StockHistory).filter(StockHistory.stock_item_id == item_id).delete()
    db.delete(item)
    db.commit()
    return {"status": "success", "deleted_id": item_id}
