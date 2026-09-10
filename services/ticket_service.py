"""
Ticket Service — Module 1 business logic
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agents.diagnosis_agent import DiagnosisState, diagnosis_graph
from agents.router_graph import RouterState, router_graph
from models.db_models import (
    Customer, LedgerEntry, PartsCatalog, ServiceTicket, TicketStatus, Vehicle,
)
from models.schemas import (
    DiagnosedIssueSchema, LineItemSchema, TicketApproveRequest,
    TicketIngestRequest, TicketResponse,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ticket_to_response(ticket: ServiceTicket, db: Session) -> TicketResponse:
    """Convert ORM ServiceTicket → TicketResponse Pydantic model."""
    vehicle: Optional[Vehicle] = ticket.vehicle
    customer: Optional[Customer] = ticket.customer

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

    return TicketResponse(
        id=ticket.id,
        vehicle_plate=vehicle.plate if vehicle else None,
        customer_name=customer.name if customer else None,
        car_model=f"{vehicle.brand} {vehicle.model}" if vehicle else None,
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
    )


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
            w.notes = f"แก้ไขผ่านการอนุมัติใบสั่งซ่อม Ticket #{ticket.id} เมื่อ {datetime.utcnow().strftime('%Y-%m-%d')}"
            
            # Update vehicle status dates/mileage
            if w.component == "น้ำมันเครื่อง" and vehicle:
                vehicle.last_oil_change_mileage = vehicle.current_mileage
                vehicle.last_oil_change_date = datetime.utcnow()
            elif w.component == "แบตเตอรี่" and vehicle:
                vehicle.last_battery_date = datetime.utcnow()
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
        clean_plate = re.sub(r"[^\w\dก-ฮ]", "", plate)
        for v in db.query(Vehicle).all():
            v_clean = re.sub(r"[^\w\dก-ฮ]", "", v.plate)
            if clean_plate and (clean_plate in v_clean or v_clean in clean_plate):
                vehicle = v
                break
    if phone:
        customer = db.query(Customer).filter(Customer.phone == phone).first()
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
        line_items=json.dumps(diag_result["line_items"], ensure_ascii=False),
        estimated_labor_cost=diag_result["estimated_labor_cost"],
        estimated_parts_cost=diag_result["estimated_parts_cost"],
        total_estimated_cost=diag_result["total_estimated_cost"],
        requires_heavy_repair=diag_result["requires_heavy_repair"],
        status=diag_result["status"],
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
            entry_date=datetime.utcnow()
        )
        db.add(ledger)
        _resolve_watchlist_for_ticket(db, ticket)
        db.commit()

    # Update vehicle last_service_date
    if vehicle and req.mileage:
        vehicle.current_mileage = req.mileage
        vehicle.last_service_date = datetime.utcnow()
        db.commit()

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
    if ticket.status == TicketStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot approve a cancelled ticket.")

    ticket.status = TicketStatus.APPROVED
    ticket.approved_by = req.approved_by
    ticket.approved_at = datetime.utcnow()
    ticket.mechanic_notes = req.mechanic_notes

    if req.final_cost is not None:
        ticket.final_cost = req.final_cost
    else:
        ticket.final_cost = ticket.total_estimated_cost

    if req.adjusted_line_items:
        ticket.line_items = json.dumps(
            [i.model_dump() for i in req.adjusted_line_items], ensure_ascii=False
        )

    # Write to general ledger upon approval
    ledger = LedgerEntry(
        bill_id=None,
        entry_type="income",
        category="repair_service",
        amount=ticket.final_cost,
        description=f"รายรับค่าซ่อมรถ (อนุมัติ) — Ticket #{ticket.id} ({ticket.vehicle.plate if ticket.vehicle else 'ไม่ระบุ'})",
        entry_date=datetime.utcnow()
    )
    db.add(ledger)
    _resolve_watchlist_for_ticket(db, ticket)

    ticket.updated_at = datetime.utcnow()
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

