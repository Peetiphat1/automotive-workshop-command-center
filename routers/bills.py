"""
Bill Scanner Router
────────────────────
POST /api/v1/bills/scan-photo  — upload a bill image → Gemini extracts customer/parts/totals
POST /api/v1/bills/confirm     — human-reviewed data → saves to work_orders, stock, ledger
GET  /api/v1/bills/pending     — list unconfirmed scanned bills
DELETE /api/v1/bills/{id}      — reject/delete a pending bill
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from models.db_models import get_local_now
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import verify_api_key, get_db
from models.db_models import (
    Customer, FinanceBill, LedgerEntry, StockItem,
    Vehicle, VehicleHealthWatchlist, WorkOrder
)

log = logging.getLogger("workshop")
router = APIRouter(dependencies=[Depends(verify_api_key)])

UPLOAD_DIR = "static/images/bills"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ScannedLineItem(BaseModel):
    name: str
    qty: float = 1.0
    unit_price: float = 0.0
    total: float = 0.0
    stock_item_id: Optional[int] = None
    confidence: Optional[str] = "ok"  # ok | low | missing

class BillConfirmRequest(BaseModel):
    image_filename: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_submodel: Optional[str] = None      # e.g. 2.5 Hybrid
    vehicle_year: Optional[int] = None
    vehicle_color: Optional[str] = None
    engine_size: Optional[str] = None           # e.g. 2.5L
    fuel_type: Optional[str] = None             # เบนซิน | ดีเซล | ไฮบริด | EV
    transmission: Optional[str] = None          # อัตโนมัติ | ธรรมดา | CVT
    mileage: Optional[int] = None
    bill_date: Optional[str] = None
    mechanic_name: Optional[str] = None
    description: Optional[str] = None
    line_items: List[ScannedLineItem] = []
    labor_cost: float = 0.0
    total: float = 0.0
    notes: Optional[str] = None


# ── Gemini vision extraction ──────────────────────────────────────────────────

def _extract_with_gemini(image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """Call Gemini 1.5 Flash vision REST API to extract bill data. Falls back gracefully on error."""
    try:
        from services import ai_service
        api_key = ai_service.get_configured_key("GEMINI_API_KEY") or ai_service.get_configured_key("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("No Gemini API key found")

        import httpx
        models_to_try = ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-flash-latest", "gemini-2.5-flash"]
        prompt = """You are reading a Thai automotive workshop bill/receipt.
Extract ALL information and return ONLY valid JSON (no markdown, no explanation):

{
  "customer_name": "string or null",
  "customer_phone": "string or null",
  "vehicle_plate": "Thai license plate or null",
  "vehicle_model": "car model e.g. Toyota Camry or null",
  "vehicle_brand": "brand e.g. Toyota or null",
  "mileage": integer or null,
  "bill_date": "DD/MM/YYYY or null",
  "mechanic_name": "string or null",
  "line_items": [
    {"name": "item name in Thai or English", "qty": number, "unit_price": number, "total": number}
  ],
  "labor_cost": number or 0,
  "total": number or 0,
  "notes": "any other relevant info or null"
}

Rules:
- line_items should include parts AND labor separately if listed
- All prices in THB (numbers only, no ฿ or บาท)
- If mileage written as e.g. "52,000 กม." return 52000
- If something is not found, use null
- Return ONLY the JSON object, nothing else"""

        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data,
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
        }

        with httpx.Client(timeout=25.0) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                    return json.loads(raw)
                elif res.status_code == 404:
                    continue
                else:
                    raise RuntimeError(f"Gemini API ({model_name}) returned status {res.status_code}: {res.text[:150]}")
            raise RuntimeError("None of the Gemini models were available.")

    except Exception as e:
        log.warning(f"Gemini extraction failed: {e} — using fallback")
        return _mock_extraction()


def _mock_extraction() -> Dict[str, Any]:
    """Demo data when Gemini is not configured."""
    return {
        "customer_name": "สมชาย มั่งมี",
        "customer_phone": "081-234-5678",
        "vehicle_plate": "กข 1234 กรุงเทพ",
        "vehicle_model": "Camry",
        "vehicle_brand": "Toyota",
        "mileage": 52000,
        "bill_date": get_local_now().strftime("%d/%m/%Y"),
        "mechanic_name": "ช่างสมชาย",
        "line_items": [
            {"name": "เปลี่ยนผ้าเบรคหน้า", "qty": 1, "unit_price": 1200, "total": 1200},
            {"name": "น้ำมันเบรค DOT3", "qty": 1, "unit_price": 120, "total": 120},
            {"name": "ค่าแรง", "qty": 1, "unit_price": 500, "total": 500},
        ],
        "labor_cost": 500,
        "total": 1820,
        "notes": "⚠️ Demo mode — upload a real bill photo with Gemini API key for live extraction",
    }


# ── Match line items to stock ─────────────────────────────────────────────────

def _match_stock(db: Session, line_items: List[Dict]) -> List[Dict]:
    """Try to match each line item to a StockItem by name similarity."""
    stock_items = db.query(StockItem).all()

    def similarity(a: str, b: str) -> bool:
        a, b = a.lower().strip(), b.lower().strip()
        return a in b or b in a or (len(a) > 3 and a[:4] in b)

    enriched = []
    for item in line_items:
        name = item.get("name", "")
        matched_id = None
        for si in stock_items:
            if similarity(name, si.name_th) or similarity(name, si.name_en or ""):
                matched_id = si.id
                break
        enriched.append({**item, "stock_item_id": matched_id,
                         "confidence": "ok" if matched_id else "low"})
    return enriched


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan-photo")
async def scan_bill_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a bill photo → AI extracts data → returns structured JSON for review."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "File must be an image (jpg, png, heic, webp)")

    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    # Save image to disk
    ext = os.path.splitext(file.filename or "bill.jpg")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    # Extract with Gemini
    extracted = _extract_with_gemini(image_bytes, mime_type)

    # Enrich line items with stock matches
    raw_items = extracted.get("line_items") or []
    enriched_items = _match_stock(db, raw_items)

    # Math check
    calc_total = sum(
        float(i.get("qty", 1)) * float(i.get("unit_price", 0))
        for i in enriched_items
    )
    stated_total = float(extracted.get("total") or 0)
    labor_cost = float(extracted.get("labor_cost") or 0)
    math_ok = abs(calc_total - stated_total) <= 2.0 or stated_total == 0

    return {
        "image_filename": filename,
        "image_url": f"/static/images/bills/{filename}",
        "customer_name": extracted.get("customer_name"),
        "customer_phone": extracted.get("customer_phone"),
        "vehicle_plate": extracted.get("vehicle_plate"),
        "vehicle_model": extracted.get("vehicle_model"),
        "vehicle_brand": extracted.get("vehicle_brand"),
        "mileage": extracted.get("mileage"),
        "bill_date": extracted.get("bill_date") or get_local_now().strftime("%d/%m/%Y"),
        "mechanic_name": extracted.get("mechanic_name"),
        "line_items": enriched_items,
        "labor_cost": labor_cost,
        "total": stated_total or calc_total,
        "math_ok": math_ok,
        "notes": extracted.get("notes"),
    }


@router.post("/confirm")
def confirm_bill(req: BillConfirmRequest, db: Session = Depends(get_db)):
    """Human-reviewed bill → save to all systems."""

    # ── 1. Upsert customer ────────────────────────────────────────────────────
    customer = None
    if req.customer_phone:
        customer = db.query(Customer).filter(
            Customer.phone == req.customer_phone
        ).first()
    if not customer and req.customer_name:
        customer = db.query(Customer).filter(
            Customer.name == req.customer_name
        ).first()
    if not customer and (req.customer_name or req.customer_phone):
        customer = Customer(
            name=req.customer_name or "ลูกค้าใหม่",
            phone=req.customer_phone or f"unknown-{uuid.uuid4().hex[:6]}",
        )
        db.add(customer)
        db.flush()

    # ── 2. Upsert vehicle ─────────────────────────────────────────────────────
    vehicle = None
    if req.vehicle_plate:
        vehicle = db.query(Vehicle).filter(
            Vehicle.plate == req.vehicle_plate
        ).first()
    if not vehicle and req.vehicle_plate and customer:
        vehicle = Vehicle(
            plate=req.vehicle_plate,
            brand=req.vehicle_brand or "Unknown",
            model=req.vehicle_model or "Unknown",
            submodel=req.vehicle_submodel,
            year=req.vehicle_year,
            color=req.vehicle_color,
            engine_size=req.engine_size,
            fuel_type=req.fuel_type,
            transmission=req.transmission,
            customer_id=customer.id,
            current_mileage=req.mileage or 0,
        )
        db.add(vehicle)
        db.flush()
    elif vehicle:
        # Update spec fields if provided
        if req.vehicle_brand:  vehicle.brand = req.vehicle_brand
        if req.vehicle_model:  vehicle.model = req.vehicle_model
        if req.vehicle_submodel: vehicle.submodel = req.vehicle_submodel
        if req.vehicle_year:   vehicle.year = req.vehicle_year
        if req.vehicle_color:  vehicle.color = req.vehicle_color
        if req.engine_size:    vehicle.engine_size = req.engine_size
        if req.fuel_type:      vehicle.fuel_type = req.fuel_type
        if req.transmission:   vehicle.transmission = req.transmission
        if req.mileage:        vehicle.current_mileage = req.mileage
        vehicle.last_service_date = get_local_now()
        # Update oil change tracking if oil change in line items
        names = " ".join(i.name.lower() for i in req.line_items)
        if any(k in names for k in ["น้ำมันเครื่อง", "oil", "engine oil"]):
            vehicle.last_oil_change_date = get_local_now()
            vehicle.last_oil_change_mileage = req.mileage or vehicle.current_mileage
        if any(k in names for k in ["แบต", "battery"]):
            vehicle.last_battery_date = get_local_now()

    # ── 3. Deduct stock ───────────────────────────────────────────────────────
    for item in req.line_items:
        if item.stock_item_id:
            si = db.query(StockItem).filter(StockItem.id == item.stock_item_id).first()
            if si:
                si.quantity = max(0, si.quantity - int(item.qty))

    # ── 4. Create WorkOrder ───────────────────────────────────────────────────
    parts_cost = sum(i.total for i in req.line_items)
    wo = WorkOrder(
        vehicle_plate=req.vehicle_plate,
        vehicle_brand=req.vehicle_brand,
        vehicle_model=req.vehicle_model,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
        mechanic_name=req.mechanic_name or "ช่างประจำร้าน",
        description=req.description or ", ".join(i.name for i in req.line_items),
        line_items=json.dumps([i.model_dump() for i in req.line_items], ensure_ascii=False),
        labor_cost=req.labor_cost,
        parts_cost=parts_cost,
        total_cost=req.total or parts_cost + req.labor_cost,
        mileage=req.mileage,
        notes=req.notes,
        vehicle_id=vehicle.id if vehicle else None,
        customer_id=customer.id if customer else None,
    )
    db.add(wo)
    db.flush()

    # ── 5. Create income ledger entry ─────────────────────────────────────────
    bill = FinanceBill(
        source_type="image_jpg",
        raw_input=f"Scanned bill — {req.vehicle_plate} — {req.bill_date}",
        extracted_items=wo.line_items,
        extracted_total=req.total,
        calculated_total=req.total,
        math_verified=True,
        bill_type="income",
        vendor_name=req.customer_name or "ลูกค้า",
        confirmed_by="admin",
        confirmed_at=get_local_now(),
        notes=req.notes,
        status="CONFIRMED",
    )
    db.add(bill)
    db.flush()

    ledger = LedgerEntry(
        bill_id=bill.id,
        entry_type="income",
        category="repair_service",
        amount=req.total,
        description=f"{req.vehicle_plate} — {', '.join(i.name for i in req.line_items[:3])}",
        entry_date=get_local_now(),
    )
    db.add(ledger)

    db.commit()

    return {
        "ok": True,
        "work_order_id": wo.id,
        "bill_id": bill.id,
        "customer_id": customer.id if customer else None,
        "vehicle_id": vehicle.id if vehicle else None,
        "total_saved": req.total,
        "stock_deducted": sum(
            int(i.qty) for i in req.line_items if i.stock_item_id
        ),
    }
