"""
Router: Module 1 — Service & Repair Tickets
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import (
    TicketApproveRequest, TicketCompleteRequest, TicketIngestRequest,
    TicketListResponse, TicketResponse, TicketUpdateRequest,
)
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


@router.post(
    "/{ticket_id}/complete",
    response_model=TicketResponse,
    summary="Mark ticket as completed / finished",
    description="Transitions ticket to COMPLETED, finalizes cost, updates ledger, and sends completion LINE notification.",
)
def complete_ticket(
    ticket_id: int,
    req: TicketCompleteRequest,
    db: Session = Depends(get_db),
):
    return ticket_service.complete_ticket(db, ticket_id, req)


@router.delete(
    "/{ticket_id}",
    summary="Delete a ticket by ID",
)
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    return ticket_service.delete_ticket(db, ticket_id)


@router.put(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update an existing ticket",
)
def update_ticket(ticket_id: int, req: TicketUpdateRequest, db: Session = Depends(get_db)):
    return ticket_service.update_ticket(db, ticket_id, req)


@router.post("/{ticket_id}/request-approval", summary="Send the quote link to the customer's LINE")
def request_approval(ticket_id: int, request: Request, db: Session = Depends(get_db)):
    return ticket_service.request_customer_approval(db, ticket_id, str(request.base_url))


@router.get("/warranty/{plate}", summary="Jobs on this car still under warranty")
def warranty_for_plate(plate: str, db: Session = Depends(get_db)):
    return ticket_service.active_warranties(db, plate)


_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}
_PHOTO_MAX_BYTES = 10 * 1024 * 1024


@router.post("/{ticket_id}/photos", summary="Add a before / after photo to a job")
async def upload_photo(
    ticket_id: int,
    file: UploadFile = File(...),
    kind: str = Form("before"),
    db: Session = Depends(get_db),
):
    from models.db_models import ServiceTicket, TicketPhoto
    if not db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบงานซ่อม")
    ext = _PHOTO_TYPES.get((file.content_type or "").lower())
    if not ext:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์รูปภาพ JPG / PNG / WEBP / HEIC")
    data = await file.read()
    if len(data) > _PHOTO_MAX_BYTES:
        raise HTTPException(status_code=400, detail="รูปใหญ่เกิน 10MB")
    os.makedirs("static/uploads/tickets", exist_ok=True)
    name = f"t{ticket_id}_{'after' if kind == 'after' else 'before'}_{uuid.uuid4().hex[:10]}{ext}"
    with open(os.path.join("static/uploads/tickets", name), "wb") as f:
        f.write(data)
    photo = TicketPhoto(ticket_id=ticket_id, path=f"/static/uploads/tickets/{name}",
                        kind="after" if kind == "after" else "before")
    db.add(photo)
    db.commit()
    return {"id": photo.id, "path": photo.path, "kind": photo.kind}


@router.delete("/photos/{photo_id}", summary="Remove a job photo")
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    from models.db_models import TicketPhoto
    photo = db.query(TicketPhoto).filter(TicketPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="ไม่พบรูป")
    local = photo.path.lstrip("/")
    db.delete(photo)
    db.commit()
    if local.startswith("static/uploads/tickets/") and os.path.exists(local):
        try:
            os.remove(local)
        except OSError:
            pass
    return {"status": "deleted", "id": photo_id}


@router.get(
    "/track/{query}",
    response_model=list[TicketResponse],
    summary="Track ticket status publicly by plate or ID",
)
def track_ticket(query: str, db: Session = Depends(get_db)):
    return ticket_service.search_tickets_for_tracking(db, query)

