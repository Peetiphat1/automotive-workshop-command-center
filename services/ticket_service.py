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
    Customer, PartsCatalog, ServiceTicket, TicketStatus, Vehicle,
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
        vehicle = db.query(Vehicle).filter(Vehicle.plate == plate).first()
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

    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket, db)
