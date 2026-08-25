"""
Router: Module 1 — Service & Repair Tickets
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import TicketApproveRequest, TicketIngestRequest, TicketListResponse, TicketResponse
from services import ticket_service

router = APIRouter()


@router.post(
    "/ingest",
    response_model=TicketResponse,
    status_code=201,
    summary="Ingest new repair ticket",
    description=(
        "Receives raw Thai text describing symptoms and car info. "
        "Runs the **RouterGraph** (intent + entity extraction) then the **DiagnosisGraph** "
        "(symptom → diagnosis → cost estimate → HITL guardrail). "
        "\n\n**Guardrail**: if total estimated cost > 3,000 THB or heavy repair, "
        "status is set to `PENDING_MECHANIC_APPROVAL` and the ticket is blocked until "
        "a mechanic approves it via `POST /tickets/{id}/approve`."
    ),
)
def ingest_ticket(req: TicketIngestRequest, db: Session = Depends(get_db)):
    return ticket_service.create_ticket(db, req)


@router.get(
    "/",
    response_model=TicketListResponse,
    summary="List all tickets",
)
def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status, e.g. PENDING_MECHANIC_APPROVAL"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    result = ticket_service.list_tickets(db, status_filter=status, limit=limit, offset=offset)
    return result


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket by ID",
)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    return ticket_service.get_ticket(db, ticket_id)


@router.post(
    "/{ticket_id}/approve",
    response_model=TicketResponse,
    summary="Approve / adjust a ticket (HITL gate)",
    description=(
        "**Human-in-the-Loop** approval endpoint. Mechanic or admin reviews the AI estimate, "
        "optionally adjusts `final_cost` or `adjusted_line_items`, adds `mechanic_notes`, "
        "and approves. Transitions status from `PENDING_MECHANIC_APPROVAL` → `APPROVED`. "
        "Also works on `DRAFT_ESTIMATE` tickets for manual review."
    ),
)
def approve_ticket(
    ticket_id: int,
    req: TicketApproveRequest,
    db: Session = Depends(get_db),
):
    return ticket_service.approve_ticket(db, ticket_id, req)
