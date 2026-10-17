"""
Ticket Service — Module 1 business logic
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agents.diagnosis_agent import DiagnosisState, diagnosis_graph
from agents.router_graph import RouterState, router_graph
from services import payment_service
from models.db_models import (
    Customer, LedgerEntry, PartsCatalog, ServiceTicket, TicketStatus, Vehicle,
)
from models.schemas import (
    DiagnosedIssueSchema, LineItemSchema, TicketApproveRequest,
    TicketCompleteRequest, TicketIngestRequest, TicketResponse,
    TicketUpdateRequest,
)

logger = logging.getLogger(__name__)

BANGKOK_TZ = timezone(timedelta(hours=7))

def get_local_now() -> datetime:
    """Return local naive datetime in workshop timezone (Asia/Bangkok, UTC+7)."""
    return datetime.now(BANGKOK_TZ).replace(tzinfo=None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ticket_ledger_entries(db: Session, ticket_id: int):
    """Ledger rows of exactly this ticket. Descriptions look like '... Ticket #12 (plate)',
    so match '#12 (' / a trailing '#12' — a plain LIKE '%#1%' would also hit #10-#19."""
    from sqlalchemy import or_
    return db.query(LedgerEntry).filter(or_(
        LedgerEntry.description.like(f"%Ticket #{ticket_id} (%"),
        LedgerEntry.description.like(f"%Ticket #{ticket_id}"),
    ))


def ticket_plate(ticket: ServiceTicket) -> str:
    return ticket.vehicle.plate if ticket.vehicle else "ไม่ระบุ"


def _deduct_ticket_stock(db: Session, ticket: ServiceTicket, changed_by: str) -> List[str]:
    """Take parts linked to stock (line items with stock_item_id) out of stock once, when the job is done.
    Never blocks closing the job: a shortage is clamped at 0 and returned as a warning."""
    from models.db_models import StockItem, StockHistory
    items = ticket.get_line_items()
    warnings = []
    changed = False
    for it in items:
        sid = it.get("stock_item_id")
        if not sid or it.get("stock_deducted"):
            continue
        stock = db.query(StockItem).filter(StockItem.id == sid).first()
        if not stock:
            continue
        qty = max(1, int(round(it.get("qty") or 1)))
        before = stock.quantity
        stock.quantity = max(0, before - qty)
        if before < qty:
            warnings.append(f"{stock.name_th}: สต็อกมี {before} แต่ใช้ {qty}")
        db.add(StockHistory(
            stock_item_id=stock.id, change_type="sale", delta=stock.quantity - before,
            quantity_before=before, quantity_after=stock.quantity,
            reason=f"ใช้ในงานซ่อม Ticket #{ticket.id} ({ticket_plate(ticket)})", changed_by=changed_by,
        ))
        it["stock_deducted"] = True
        it["stock_deducted_qty"] = before - stock.quantity
        it["unit_cost"] = stock.unit_cost or 0.0  # cost at the time it was used, for profit per job
        changed = True
    if changed:
        ticket.line_items = json.dumps(items, ensure_ascii=False)
    return warnings


def _restore_ticket_stock(db: Session, ticket: ServiceTicket) -> None:
    from models.db_models import StockItem, StockHistory
    for it in ticket.get_line_items():
        if not it.get("stock_deducted"):
            continue
        stock = db.query(StockItem).filter(StockItem.id == it.get("stock_item_id")).first()
        qty = int(it.get("stock_deducted_qty") or 0)
        if not stock or qty <= 0:
            continue
        before = stock.quantity
        stock.quantity = before + qty
        db.add(StockHistory(
            stock_item_id=stock.id, change_type="return", delta=qty,
            quantity_before=before, quantity_after=stock.quantity,
            reason=f"ลบงานซ่อม Ticket #{ticket.id} (คืนสต็อก)", changed_by="ระบบ",
        ))


def _link_stock_items(line_items: list, links: list) -> list:
    """Attach stock_item_id from the intake form to the parsed line items (matched by name)."""
    def norm(s):
        return re.sub(r"\s+", "", (s or "")).lower()
    used = set()
    for link in links or []:
        target = norm(link.get("name"))
        if not target:
            continue
        for idx, it in enumerate(line_items):
            if idx in used:
                continue
            n = norm(it.get("name_th") or it.get("name"))
            if n and (n == target or target in n or n in target):
                it["stock_item_id"] = link.get("stock_item_id")
                qty = link.get("qty")
                if qty and qty != it.get("qty"):
                    # The parsed line carries the line total; spread it over the real quantity
                    total = it.get("total") or (it.get("unit_price", 0) * it.get("qty", 1))
                    it["qty"] = qty
                    it["unit_price"] = round(total / qty, 2)
                    it["total"] = round(total, 2)
                used.add(idx)
                break
    return line_items


def _ticket_to_response(ticket: ServiceTicket, db: Session) -> TicketResponse:
    """Convert ORM ServiceTicket → TicketResponse Pydantic model."""
    vehicle: Optional[Vehicle] = ticket.vehicle
    customer: Optional[Customer] = ticket.customer

    # Fallback extraction from raw_input if vehicle wasn't linked
    fallback_plate = None
    fallback_model = None
    if not vehicle and ticket.raw_input:
        import re
        pm = re.search(r"(?:ทะเบียน|plate|เลขทะเบียน)\s*[:=]?\s*([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4}(?:\s*[ก-๙]+)?)", ticket.raw_input, re.IGNORECASE)
        if not pm:
            pm = re.search(r"\b([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4})\b", ticket.raw_input)
        if pm:
            fallback_plate = pm.group(1).strip()
        for b in ["Toyota", "Honda", "Isuzu", "Mazda", "Ford", "Nissan", "Mitsubishi", "โตโยต้า", "ฮอนด้า", "มาสด้า", "อีซูซุ"]:
            if b.lower() in ticket.raw_input.lower():
                fallback_model = b
                break

    symptoms = ticket.get_symptoms()
    raw_issues = ticket.get_diagnosed_issues()
    raw_items = ticket.get_line_items()

    diagnosed = [DiagnosedIssueSchema(**i) for i in raw_issues]
    items = [LineItemSchema(**i) for i in raw_items]

    guardrail_reason = None
    if ticket.status == TicketStatus.PENDING_MECHANIC_APPROVAL:
        reasons = []
        if ticket.total_estimated_cost > 3000:
            guardrail_reason = f"ราคาประเมิน {ticket.total_estimated_cost:,.0f} บาท เกินเกณฑ์"
        if ticket.requires_heavy_repair:
            guardrail_reason = (guardrail_reason or "") + " | งานซ่อมหนัก"

    mechanic_name = None
    if ticket.mechanic_notes:
        import re
        mn = re.search(r"ช่างผู้รับงาน:\s*([^\n\r]+)", ticket.mechanic_notes)
        if mn:
            mechanic_name = mn.group(1).strip()

    return TicketResponse(
        id=ticket.id,
        vehicle_plate=vehicle.plate if vehicle else fallback_plate,
        customer_id=customer.id if customer else None,
        customer_name=customer.name if customer else "ลูกค้าทั่วไป",
        customer_phone=customer.phone if customer else None,
        customer_line_id=customer.line_id if customer else None,
        car_model=f"{vehicle.brand} {vehicle.model}".strip() if vehicle else fallback_model,
        mileage=vehicle.current_mileage if vehicle else None,
        mechanic_name=mechanic_name,
        raw_input=ticket.raw_input,
        extracted_symptoms=symptoms,
        diagnosed_issues=diagnosed,
        line_items=items,
        estimated_labor_cost=ticket.estimated_labor_cost,
        estimated_parts_cost=ticket.estimated_parts_cost,
        total_estimated_cost=ticket.total_estimated_cost,
        requires_heavy_repair=ticket.requires_heavy_repair,
        status=ticket.status,  # type: ignore[arg-type]
        guardrail_reason=guardrail_reason,
        mechanic_notes=ticket.mechanic_notes,
        approved_by=ticket.approved_by,
        approved_at=ticket.approved_at,
        final_cost=ticket.final_cost,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        completed_at=ticket.completed_at,
        **payment_service.ticket_summary(db, ticket),
        customer_decision=ticket.customer_decision,
        customer_decision_at=ticket.customer_decision_at,
        customer_decision_note=ticket.customer_decision_note,
        approval_link_sent=bool(ticket.approval_token),
        warranty_months=ticket.warranty_months,
        warranty_note=ticket.warranty_note,
        warranty_until=warranty_until(ticket),
        photos=[{"id": p.id, "path": p.path, "kind": p.kind} for p in ticket.photos],
    )


def warranty_until(ticket: ServiceTicket) -> Optional[datetime]:
    if not ticket.warranty_months or not ticket.completed_at:
        return None
    from dateutil.relativedelta import relativedelta
    return ticket.completed_at + relativedelta(months=ticket.warranty_months)


def reserved_stock(db: Session, exclude_ticket_id: Optional[int] = None) -> dict:
    """Parts held for open repair jobs: {stock_item_id: qty}. A part picked on a job stays
    reserved until the job is completed (then it leaves stock) or cancelled."""
    open_tickets = db.query(ServiceTicket).filter(
        ServiceTicket.status.notin_([TicketStatus.COMPLETED, TicketStatus.CANCELLED])
    ).all()
    held: dict = {}
    for t in open_tickets:
        if t.id == exclude_ticket_id:
            continue
        for it in t.get_line_items():
            sid = it.get("stock_item_id")
            if sid and not it.get("stock_deducted"):
                held[sid] = held.get(sid, 0) + max(1, int(round(it.get("qty") or 1)))
    return held


def active_warranties(db: Session, plate: str) -> List[dict]:
    """Jobs on this car whose warranty has not run out yet."""
    clean = re.sub(r"[^\w\dก-ฮ]", "", plate or "")
    if not clean:
        return []
    now = get_local_now()
    result = []
    for v in db.query(Vehicle).all():
        if re.sub(r"[^\w\dก-ฮ]", "", v.plate) != clean:
            continue
        for t in v.tickets:
            until = warranty_until(t)
            if until and until >= now and t.status == TicketStatus.COMPLETED:
                result.append({
                    "ticket_id": t.id,
                    "completed_at": t.completed_at.isoformat(),
                    "warranty_until": until.isoformat(),
                    "warranty_months": t.warranty_months,
                    "warranty_note": t.warranty_note,
                    "items": [i.get("name_th") or i.get("name") for i in t.get_line_items()],
                    "days_left": (until - now).days,
                })
    return sorted(result, key=lambda r: r["warranty_until"])


def _resolve_watchlist_for_ticket(db: Session, ticket: ServiceTicket):
    if not ticket.vehicle_id:
        return
    from models.db_models import VehicleHealthWatchlist
    vehicle = ticket.vehicle
    watchlist_items = db.query(VehicleHealthWatchlist).filter(
        VehicleHealthWatchlist.vehicle_id == ticket.vehicle_id,
        VehicleHealthWatchlist.is_overdue == True
    ).all()
    if not watchlist_items:
        return

    repaired_components = set()
    try:
        line_items = json.loads(ticket.line_items) if ticket.line_items else []
        for item in line_items:
            name_th = item.get("name_th", "")
            if "น้ำมันเครื่อง" in name_th or "กรองเครื่อง" in name_th:
                repaired_components.add("น้ำมันเครื่อง")
            if "แบตเตอรี่" in name_th:
                repaired_components.add("แบตเตอรี่")
            if "ยาง" in name_th:
                repaired_components.add("ยางรถยนต์")
            if "น้ำมันเกียร์" in name_th:
                repaired_components.add("น้ำมันเกียร์")
    except Exception:
        pass

    raw_text = ticket.raw_input or ""
    if "น้ำมันเครื่อง" in raw_text or "เปลี่ยนน้ำมัน" in raw_text:
        repaired_components.add("น้ำมันเครื่อง")
    if "แบตเตอรี่" in raw_text or "เปลี่ยนแบต" in raw_text:
        repaired_components.add("แบตเตอรี่")
    if "ยาง" in raw_text:
        repaired_components.add("ยางรถยนต์")

    for w in watchlist_items:
        if w.component in repaired_components:
            w.is_overdue = False
            w.condition = "ได้รับการแก้ไขแล้ว"
            w.notes = f"แก้ไขผ่านการอนุมัติใบสั่งซ่อม Ticket #{ticket.id} เมื่อ {get_local_now().strftime('%Y-%m-%d')}"
            
            # Update vehicle status dates/mileage
            if w.component == "น้ำมันเครื่อง" and vehicle:
                vehicle.last_oil_change_mileage = vehicle.current_mileage
                vehicle.last_oil_change_date = get_local_now()
            elif w.component == "แบตเตอรี่" and vehicle:
                vehicle.last_battery_date = get_local_now()
            elif w.component == "ยางรถยนต์" and vehicle:
                vehicle.last_tire_change_mileage = vehicle.current_mileage


# ── Service functions ─────────────────────────────────────────────────────────

def create_ticket(db: Session, req: TicketIngestRequest) -> TicketResponse:
    """
    Full pipeline:
      1. RouterGraph  → intent + entity extraction
      2. DiagnosisGraph → symptoms → estimate → guardrail
      3. Persist to DB
    """
    # Step 1: Router
    router_result: RouterState = router_graph.invoke({
        "raw_input": req.raw_input,
        "intent": "",
        "entities": {},
        "confidence": 0.0,
        "routing_path": "",
        "error": None,
    })

    entities = router_result.get("entities", {})

    # Resolve vehicle & customer from DB
    vehicle: Optional[Vehicle] = None
    customer: Optional[Customer] = None
    plate = req.vehicle_plate or entities.get("plate")
    phone = req.customer_phone or entities.get("phone")

    if plate:
        import re
        clean_plate = re.sub(r"[^\w\dก-ฮ]", "", plate).strip()
        # 1. Exact cleaned match first
        for v in db.query(Vehicle).all():
            v_clean = re.sub(r"[^\w\dก-ฮ]", "", v.plate).strip()
            if clean_plate == v_clean:
                vehicle = v
                break
        # 2. If no exact match, prefix match ONLY if plate has Thai characters
        if not vehicle:
            thai_chars = re.findall(r"[ก-ฮ]", clean_plate)
            if len(thai_chars) >= 2:
                for v in db.query(Vehicle).all():
                    v_clean = re.sub(r"[^\w\dก-ฮ]", "", v.plate).strip()
                    if clean_plate.startswith(v_clean) or v_clean.startswith(clean_plate):
                        vehicle = v
                        break

    if phone:
        customer = db.query(Customer).filter(Customer.phone == phone).first()
    if not customer and req.customer_name:
        customer = db.query(Customer).filter(Customer.name == req.customer_name).first()
    line_id = getattr(req, "customer_line_id", None)
    if not customer and (req.customer_name or phone):
        import time
        customer = Customer(
            name=req.customer_name or "ลูกค้าทั่วไป",
            phone=phone or f"080-{int(time.time()) % 10000000:07d}",
            line_id=line_id.strip() if line_id else None,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    elif customer and line_id and line_id.strip():
        # Update LINE ID if provided and customer doesn't have one or it changed
        customer.line_id = line_id.strip()
        db.commit()
    if not customer:
        customer = db.query(Customer).first()

    # 3. If plate was provided but vehicle does NOT exist in DB, AUTO-CREATE VEHICLE!
    if plate and not vehicle:
        raw_text = ((req.car_model or "") + " " + req.raw_input).lower()
        detected_brand = "Toyota"
        detected_model = entities.get("car_model") or "Sedan"
        if req.car_model:
            parts = req.car_model.strip().split(maxsplit=1)
            detected_brand = parts[0]
            detected_model = parts[1] if len(parts) > 1 else "ทั่วไป"
        else:
            brands_map = {
                "honda": ("Honda", "Civic"),
                "ฮอนด้า": ("Honda", "Civic"),
                "toyota": ("Toyota", "Corolla"),
                "โตโยต้า": ("Toyota", "Corolla"),
                "isuzu": ("Isuzu", "D-Max"),
                "อีซูซุ": ("Isuzu", "D-Max"),
                "mazda": ("Mazda", "2"),
                "มาสด้า": ("Mazda", "2"),
                "ford": ("Ford", "Ranger"),
                "ฟอร์ด": ("Ford", "Ranger"),
                "nissan": ("Nissan", "Almera"),
                "นิสสัน": ("Nissan", "Almera"),
                "mitsubishi": ("Mitsubishi", "Triton"),
                "มิตซู": ("Mitsubishi", "Triton"),
                "byd": ("BYD", "Atto 3"),
                "bmw": ("BMW", "Series 3"),
                "benz": ("Mercedes-Benz", "C-Class"),
            }
            for kw, (b, m) in brands_map.items():
                if kw in raw_text:
                    detected_brand = b
                    detected_model = m
                    break
        
        vehicle = Vehicle(
            plate=plate,
            brand=detected_brand,
            model=detected_model,
            customer_id=customer.id if customer else 1,
            current_mileage=req.mileage or 50000,
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)

    if vehicle and not customer:
        customer = vehicle.customer

    # Load parts catalog for cost estimation
    parts_db = [
        {"name": p.name, "name_th": p.name_th, "unit_price": p.unit_price,
         "category": p.category, "is_heavy_repair": p.is_heavy_repair}
        for p in db.query(PartsCatalog).all()
    ]

    # Step 2: Diagnosis
    diag_result: DiagnosisState = diagnosis_graph.invoke({
        "raw_input": req.raw_input,
        "customer_id": customer.id if customer else None,
        "vehicle_plate": plate,
        "car_model": entities.get("car_model", "Unknown"),
        "mileage": req.mileage or entities.get("mileage", 0),
        "symptoms": [],
        "diagnosed_issues": [],
        "recommended_parts": [],
        "line_items": [],
        "estimated_labor_cost": 0.0,
        "estimated_parts_cost": 0.0,
        "total_estimated_cost": 0.0,
        "requires_heavy_repair": False,
        "status": "",
        "guardrail_reason": "",
        "error": None,
        "parts_db": parts_db,
    })

    # Step 3: Persist
    ticket = ServiceTicket(
        vehicle_id=vehicle.id if vehicle else None,
        customer_id=customer.id if customer else None,
        raw_input=req.raw_input,
        extracted_symptoms=json.dumps(diag_result["symptoms"], ensure_ascii=False),
        diagnosed_issues=json.dumps(diag_result["diagnosed_issues"], ensure_ascii=False),
        line_items=json.dumps(
            _link_stock_items(diag_result["line_items"], [l.model_dump() for l in (req.stock_links or [])]),
            ensure_ascii=False,
        ),
        estimated_labor_cost=diag_result["estimated_labor_cost"],
        estimated_parts_cost=diag_result["estimated_parts_cost"],
        total_estimated_cost=diag_result["total_estimated_cost"],
        requires_heavy_repair=diag_result["requires_heavy_repair"],
        status=diag_result["status"],
        mechanic_notes=f"ช่างผู้รับงาน: {req.mechanic_name}" if req.mechanic_name else None,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # If the ticket was auto-approved, write it to the general ledger
    if ticket.status == TicketStatus.APPROVED:
        ticket.final_cost = ticket.total_estimated_cost
        ledger = LedgerEntry(
            bill_id=None,
            entry_type="income",
            category="repair_service",
            amount=ticket.final_cost,
            description=f"รายรับค่าซ่อมรถ — Ticket #{ticket.id} ({vehicle.plate if vehicle else 'ไม่ระบุ'})",
            entry_date=get_local_now()
        )
        db.add(ledger)
        _resolve_watchlist_for_ticket(db, ticket)
        db.commit()

    # Update vehicle last_service_date
    if vehicle and req.mileage:
        vehicle.current_mileage = req.mileage
        vehicle.last_service_date = get_local_now()
        db.commit()

    # ── Auto-dispatch LINE OA Intake Notification ─────────────────────────────
    if customer and customer.line_id:
        try:
            from agents.marketing_agent import mock_line_dispatch
            plate_str = vehicle.plate if vehicle else (plate or "รถของท่าน")
            car_str = f"{vehicle.brand} {vehicle.model}" if vehicle else (entities.get("car_model") or "รถของท่าน")
            symptom_str = ticket.raw_input or "ตรวจเช็คสภาพทั่วไป"
            symptom_str = re.sub(r"\[แนบภาพถ่าย[^\]]*\]", "", symptom_str)
            symptom_str = re.sub(r"/static/\S+", "", symptom_str)
            symptom_str = re.sub(r"https?://\S+", "", symptom_str).strip()
            symptom_str = symptom_str[:100] if symptom_str else "ตรวจเช็คสภาพทั่วไป"

            line_msg = (
                f"🚗 [Zero Garage — เปิดใบรับรถเข้าศูนย์บริการ]\n"
                f"เรียนคุณ {customer.name}\n\n"
                f"อู่ได้รับรถ {car_str} (ทะเบียน {plate_str}) เรียบร้อยแล้วครับ\n"
                f"📋 หมายเลข Ticket: #{ticket.id}\n"
                f"🔧 รายการแจ้งเบื้องต้น: {symptom_str}\n"
                f"⏳ สถานะ: ช่างกำลังเริ่มตรวจเช็คสภาพจริงหน้างาน\n\n"
                f"เมื่อช่างตรวจเช็คและซ่อมเสร็จ ระบบจะแจ้งเตือนให้ท่านทราบทันทีครับ 🙏"
            )
            mock_line_dispatch(customer.line_id, line_msg)
        except Exception as e:
            logger.warning(f"Failed to auto-send intake LINE notification: {e}")

    return _ticket_to_response(ticket, db)


def get_ticket(db: Session, ticket_id: int) -> TicketResponse:
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticket #{ticket_id} not found.")
    return _ticket_to_response(ticket, db)


def list_tickets(
    db: Session,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    q = db.query(ServiceTicket)
    if status_filter:
        q = q.filter(ServiceTicket.status == status_filter)
    total = q.count()
    tickets = q.order_by(ServiceTicket.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_ticket_to_response(t, db) for t in tickets]}


def approve_ticket(db: Session, ticket_id: int, req: TicketApproveRequest) -> TicketResponse:
    """HITL gate: mechanic/admin reviews, adjusts, and approves."""
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticket #{ticket_id} not found.")

    if ticket.status == TicketStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ticket is already approved.")
    if ticket.status == TicketStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ticket is already completed.")
    if ticket.status == TicketStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot approve a cancelled ticket.")

    ticket.status = TicketStatus.APPROVED
    ticket.approved_by = req.approved_by
    ticket.approved_at = get_local_now()
    if req.mechanic_notes:
        ticket.mechanic_notes = req.mechanic_notes

    if req.final_cost is not None and req.final_cost > 0:
        ticket.final_cost = req.final_cost
    else:
        ticket.final_cost = ticket.total_estimated_cost

    if req.adjusted_line_items:
        ticket.line_items = json.dumps(
            [i.model_dump() for i in req.adjusted_line_items], ensure_ascii=False
        )

    # Write to general ledger upon approval (one row per ticket)
    existing_ledger = ticket_ledger_entries(db, ticket.id).first()
    if existing_ledger:
        existing_ledger.amount = ticket.final_cost
    else:
        db.add(LedgerEntry(
            bill_id=None,
            entry_type="income",
            category="repair_service",
            amount=ticket.final_cost,
            description=f"รายรับค่าซ่อมรถ (อนุมัติเริ่มงาน) — Ticket #{ticket.id} ({ticket_plate(ticket)})",
            entry_date=get_local_now()
        ))
    _resolve_watchlist_for_ticket(db, ticket)

    ticket.updated_at = get_local_now()
    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket, db)


def complete_ticket(db: Session, ticket_id: int, req: TicketCompleteRequest) -> TicketResponse:
    """Mark ticket as COMPLETED (work finished). Finalizes cost and notifies customer."""
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticket #{ticket_id} not found.")

    if ticket.status == TicketStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ticket is already completed.")

    ticket.status = TicketStatus.COMPLETED
    now_local = get_local_now()
    ticket.completed_at = now_local
    if req.warranty_months is not None:
        ticket.warranty_months = req.warranty_months or None
    if req.warranty_note is not None:
        ticket.warranty_note = req.warranty_note.strip() or None

    if req.final_cost is not None and req.final_cost > 0:
        ticket.final_cost = req.final_cost
    elif not ticket.final_cost:
        ticket.final_cost = ticket.total_estimated_cost

    if req.completion_notes:
        existing = ticket.mechanic_notes or ""
        ticket.mechanic_notes = f"{existing} | ปิดงาน: {req.completion_notes}".strip(" |")

    ticket.updated_at = now_local

    # Update or insert ledger entry for this ticket
    existing_ledger = ticket_ledger_entries(db, ticket.id).first()
    plate_str = ticket_plate(ticket)
    if existing_ledger:
        existing_ledger.amount = ticket.final_cost
        existing_ledger.description = f"รายรับค่าซ่อมรถ (เสร็จสิ้น) — Ticket #{ticket.id} ({plate_str})"
        existing_ledger.entry_date = now_local
    else:
        ledger = LedgerEntry(
            bill_id=None,
            entry_type="income",
            category="repair_service",
            amount=ticket.final_cost,
            description=f"รายรับค่าซ่อมรถ (เสร็จสิ้น) — Ticket #{ticket.id} ({plate_str})",
            entry_date=now_local
        )
        db.add(ledger)

    _resolve_watchlist_for_ticket(db, ticket)

    # Parts chosen from stock on the intake form leave the stock now that the job is done
    stock_warnings = _deduct_ticket_stock(db, ticket, req.completed_by or "ช่างประจำ")
    if stock_warnings:
        note = "⚠️ สต็อกไม่พอ: " + "; ".join(stock_warnings)
        ticket.mechanic_notes = f"{ticket.mechanic_notes or ''} | {note}".strip(" |")

    # ── Auto-dispatch LINE OA Notification on Repair Completion ──────────────
    customer = ticket.customer
    if customer and customer.line_id:
        try:
            from agents.marketing_agent import mock_line_dispatch
            plate_str = ticket.vehicle.plate if ticket.vehicle else "รถของท่าน"
            car_str = f"{ticket.vehicle.brand} {ticket.vehicle.model}" if ticket.vehicle and ticket.vehicle.brand else "รถยนต์"
            cost_str = f"{ticket.final_cost:,.2f}" if ticket.final_cost else "0.00"
            raw_notes = req.completion_notes or ticket.mechanic_notes or "ดำเนินการตรวจเช็คและซ่อมบำรุงเรียบร้อย"
            raw_notes = re.sub(r"\[แนบภาพถ่าย[^\]]*\]", "", raw_notes)
            raw_notes = re.sub(r"/static/\S+", "", raw_notes)
            raw_notes = re.sub(r"https?://\S+", "", raw_notes).strip()
            notes_str = raw_notes[:120] if raw_notes else "ดำเนินการตรวจเช็คและซ่อมบำรุงเรียบร้อย"

            line_msg = (
                f"🎉 [Zero Garage — แจ้งซ่อมเสร็จสิ้น พร้อมส่งมอบรถ]\n"
                f"เรียนคุณ {customer.name}\n\n"
                f"รถ {car_str} (ทะเบียน {plate_str}) ดำเนินการซ่อมบำรุงเสร็จสมบูรณ์เรียบร้อยแล้วครับ ✨\n"
                f"📋 หมายเลข Ticket: #{ticket.id}\n"
                f"🔧 งานที่ดำเนินการ: {notes_str}\n"
                f"💰 ยอดชำระสุทธิ: {cost_str} บาท\n\n"
                f"📍 ท่านสามารถเข้ามารับรถได้ที่ศูนย์บริการ ขอบคุณที่ไว้วางใจให้เราดูแลครับ 🙏"
            )
            mock_line_dispatch(customer.line_id, line_msg)
        except Exception as e:
            logger.warning(f"Failed to auto-send completion LINE notification: {e}")

    ticket.updated_at = now_local
    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket, db)


def search_tickets_for_tracking(db: Session, query: str) -> List[TicketResponse]:
    """Public search by license plate or ticket ID."""
    import re
    query_str = query.strip()
    
    # Try by ticket ID if integer
    if query_str.isdigit():
        t = db.query(ServiceTicket).filter(ServiceTicket.id == int(query_str)).first()
        if t:
            return [_ticket_to_response(t, db)]
            
    # Search by license plate
    clean_q = re.sub(r"[^\w\dก-ฮ]", "", query_str)
    tickets = []
    
    # Find matching vehicles first
    matching_v_ids = []
    for v in db.query(Vehicle).all():
        v_clean = re.sub(r"[^\w\dก-ฮ]", "", v.plate)
        if clean_q and (clean_q in v_clean or v_clean in clean_q):
            matching_v_ids.append(v.id)
            
    if matching_v_ids:
        db_tickets = (
            db.query(ServiceTicket)
            .filter(ServiceTicket.vehicle_id.in_(matching_v_ids))
            .order_by(ServiceTicket.created_at.desc())
            .all()
        )
        tickets.extend([_ticket_to_response(t, db) for t in db_tickets])
        
    return tickets


def update_ticket(db: Session, ticket_id: int, req: TicketUpdateRequest) -> TicketResponse:
    """Update details of an existing ticket."""
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket #{ticket_id} not found",
        )

    # 1. Update Customer information if provided
    if req.customer_name or req.customer_phone or req.customer_line_id:
        if ticket.customer:
            if req.customer_name:
                ticket.customer.name = req.customer_name
            if req.customer_phone:
                ticket.customer.phone = req.customer_phone
            if req.customer_line_id is not None:
                ticket.customer.line_id = req.customer_line_id
        else:
            # Create or find customer
            cust = None
            if req.customer_phone:
                cust = db.query(Customer).filter(Customer.phone == req.customer_phone).first()
            if not cust:
                cust = Customer(
                    name=req.customer_name or "ลูกค้าทั่วไป",
                    phone=req.customer_phone,
                    line_id=req.customer_line_id,
                )
                db.add(cust)
                db.flush()
            ticket.customer_id = cust.id

    # 2. Update Vehicle information if provided
    if req.vehicle_plate or req.car_model or req.mileage is not None:
        if ticket.vehicle:
            if req.vehicle_plate:
                ticket.vehicle.plate = req.vehicle_plate
            if req.car_model:
                parts = req.car_model.strip().split(" ", 1)
                ticket.vehicle.brand = parts[0]
                ticket.vehicle.model = parts[1] if len(parts) > 1 else ""
            if req.mileage is not None:
                ticket.vehicle.current_mileage = req.mileage
        else:
            # Create or find vehicle
            plate = req.vehicle_plate or "ไม่ระบุ"
            veh = db.query(Vehicle).filter(Vehicle.plate == plate).first()
            if not veh:
                brand = "Toyota"
                model = ""
                if req.car_model:
                    parts = req.car_model.strip().split(" ", 1)
                    brand = parts[0]
                    model = parts[1] if len(parts) > 1 else ""
                veh = Vehicle(
                    customer_id=ticket.customer_id or 1,
                    plate=plate,
                    brand=brand,
                    model=model,
                    current_mileage=req.mileage or 0,
                )
                db.add(veh)
                db.flush()
            ticket.vehicle_id = veh.id

    # 3. Update Mechanic name in notes if provided
    if req.mechanic_name:
        current_notes = ticket.mechanic_notes or ""
        if "ช่างผู้รับงาน:" in current_notes:
            ticket.mechanic_notes = re.sub(r"ช่างผู้รับงาน:\s*[^\n\r]+", f"ช่างผู้รับงาน: {req.mechanic_name}", current_notes)
        else:
            ticket.mechanic_notes = f"ช่างผู้รับงาน: {req.mechanic_name}\n" + current_notes

    if req.mechanic_notes is not None:
        ticket.mechanic_notes = req.mechanic_notes

    # 4. Update Symptoms & Line items
    if req.extracted_symptoms is not None:
        ticket.extracted_symptoms = json.dumps(req.extracted_symptoms, ensure_ascii=False)
    if req.raw_input is not None:
        ticket.raw_input = req.raw_input

    if req.line_items is not None:
        # Keep the "already taken from stock" flags of lines that are still the same part
        old_by_stock = {it.get("stock_item_id"): it for it in ticket.get_line_items() if it.get("stock_deducted")}
        new_items = []
        for it in req.line_items:
            d = it.model_dump()
            old = old_by_stock.get(d.get("stock_item_id"))
            d["stock_deducted"] = bool(old)
            if old:
                d["stock_deducted_qty"] = old.get("stock_deducted_qty")
            new_items.append(d)
        ticket.line_items = json.dumps(new_items, ensure_ascii=False)
        if req.total_estimated_cost is None:
            ticket.total_estimated_cost = round(sum(i["total"] for i in new_items), 2)

    # 5. Update Financials
    if req.estimated_labor_cost is not None:
        ticket.estimated_labor_cost = req.estimated_labor_cost
    if req.estimated_parts_cost is not None:
        ticket.estimated_parts_cost = req.estimated_parts_cost
    if req.total_estimated_cost is not None:
        ticket.total_estimated_cost = req.total_estimated_cost
    if req.final_cost is not None:
        ticket.final_cost = req.final_cost

    # 6. Update Status
    if req.status is not None:
        ticket.status = req.status
        if req.status == TicketStatus.COMPLETED and not ticket.completed_at:
            ticket.completed_at = get_local_now()

    if req.warranty_months is not None:
        ticket.warranty_months = req.warranty_months or None
    if req.warranty_note is not None:
        ticket.warranty_note = req.warranty_note.strip() or None

    # 7. Keep the booked income in line with the edited price
    entry = ticket_ledger_entries(db, ticket.id).first()
    if entry:
        if ticket.status == TicketStatus.CANCELLED:
            db.delete(entry)
        else:
            entry.amount = ticket.final_cost or ticket.total_estimated_cost or 0.0

    ticket.updated_at = get_local_now()
    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket, db)


def delete_ticket(db: Session, ticket_id: int) -> dict:
    """Delete a ticket together with its income rows; parts already taken from stock go back."""
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    _restore_ticket_stock(db, ticket)
    ticket_ledger_entries(db, ticket.id).delete(synchronize_session=False)
    from models.db_models import Payment
    db.query(Payment).filter(Payment.ticket_id == ticket.id).delete(synchronize_session=False)
    db.delete(ticket)
    db.commit()
    return {"status": "deleted", "deleted_id": ticket_id}




# ── Customer approves the quote through a LINE link ───────────────────────────

def _quote_ticket(db: Session, token: str) -> ServiceTicket:
    ticket = db.query(ServiceTicket).filter(ServiceTicket.approval_token == token).first() if token else None
    if not ticket:
        raise HTTPException(status_code=404, detail="ลิงก์ไม่ถูกต้องหรือหมดอายุแล้ว")
    return ticket


def request_customer_approval(db: Session, ticket_id: int, base_url: str) -> dict:
    """Create (or reuse) the quote link and send it to the customer's LINE when possible."""
    import secrets
    from services import shop_settings

    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="ไม่พบงานซ่อม")
    if ticket.status not in (TicketStatus.PENDING_MECHANIC_APPROVAL, TicketStatus.DRAFT_ESTIMATE):
        raise HTTPException(status_code=400, detail="ส่งให้ลูกค้าอนุมัติได้เฉพาะงานที่ยังรออนุมัติ")
    if not ticket.approval_token:
        ticket.approval_token = secrets.token_urlsafe(18)
    ticket.customer_decision = None
    ticket.customer_decision_at = None
    db.commit()

    public_base = (shop_settings.get_setting(db, "public_base_url") or base_url).rstrip("/")
    link = f"{public_base}/quote/{ticket.approval_token}"
    shop_name = shop_settings.get_setting(db, "shop_name") or "อู่ซ่อมรถ"
    total = ticket_amount = payment_service.ticket_amount_due(ticket)
    plate = ticket_plate(ticket)

    sent, send_error = False, None
    customer = ticket.customer
    if customer and customer.line_id:
        from agents.marketing_agent import mock_line_dispatch
        msg = (
            f"🔧 [{shop_name}] ใบเสนอราคางานซ่อม #{ticket.id}\n"
            f"รถทะเบียน {plate}\n"
            f"💰 ยอดประเมิน {total:,.2f} บาท\n\n"
            f"กรุณากดดูรายละเอียดและอนุมัติ/ไม่อนุมัติที่ลิงก์นี้:\n{link}"
        )
        res = mock_line_dispatch(customer.line_id, msg)
        sent = bool(res.get("success")) and not res.get("mock")
        if not res.get("success"):
            send_error = res.get("error")
        elif res.get("mock"):
            send_error = "ยังไม่ได้ตั้งค่า LINE OA Token — คัดลอกลิงก์ส่งให้ลูกค้าเองได้"
    else:
        send_error = "ลูกค้าไม่มี LINE ID — คัดลอกลิงก์ส่งให้ลูกค้าเองได้"

    return {"link": link, "sent_via_line": sent, "note": send_error, "amount": ticket_amount}


def get_public_quote(db: Session, token: str) -> dict:
    from services import shop_settings
    t = _quote_ticket(db, token)
    return {
        "ticket_id": t.id,
        "shop_name": shop_settings.get_setting(db, "shop_name"),
        "shop_phone": shop_settings.get_setting(db, "shop_phone"),
        "plate": ticket_plate(t),
        "car_model": f"{t.vehicle.brand} {t.vehicle.model}".strip() if t.vehicle else None,
        "customer_name": t.customer.name if t.customer else None,
        "items": [{"name": i.get("name_th") or i.get("name"), "qty": i.get("qty", 1), "total": i.get("total", 0)}
                  for i in t.get_line_items()],
        "total": payment_service.ticket_amount_due(t),
        "status": t.status,
        "decision": t.customer_decision,
        "decision_at": t.customer_decision_at.isoformat() if t.customer_decision_at else None,
        "can_decide": t.status in (TicketStatus.PENDING_MECHANIC_APPROVAL, TicketStatus.DRAFT_ESTIMATE)
                      and not t.customer_decision,
    }


def decide_public_quote(db: Session, token: str, decision: str, note: Optional[str]) -> dict:
    t = _quote_ticket(db, token)
    if t.customer_decision:
        raise HTTPException(status_code=409, detail="ใบเสนอราคานี้ได้รับคำตอบแล้ว")
    if t.status not in (TicketStatus.PENDING_MECHANIC_APPROVAL, TicketStatus.DRAFT_ESTIMATE):
        raise HTTPException(status_code=409, detail="งานนี้ดำเนินการไปแล้ว กรุณาติดต่ออู่")
    now = get_local_now()
    t.customer_decision = "approved" if decision == "approve" else "declined"
    t.customer_decision_at = now
    t.customer_decision_note = (note or "").strip() or None
    db.commit()
    if decision == "approve":
        approve_ticket(db, t.id, TicketApproveRequest(
            approved_by="ลูกค้า (อนุมัติผ่านลิงก์ LINE)",
            mechanic_notes=t.mechanic_notes,
        ))
    return get_public_quote(db, token)
