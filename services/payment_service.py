"""
Payments — money actually received for repair tickets and POS sales.
Income in the ledger is booked when a job is approved; payments track the cash side
(deposit, rest, outstanding balance, how it was paid).
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.db_models import Payment, ServiceTicket, TicketStatus, get_local_now, to_local_naive

PAYMENT_METHODS = ["เงินสด", "โอน", "บัตร"]


def ticket_amount_due(ticket: ServiceTicket) -> float:
    return round(float(ticket.final_cost or ticket.total_estimated_cost or 0.0), 2)


def ticket_paid(db: Session, ticket_id: int) -> float:
    total = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(Payment.ticket_id == ticket_id).scalar()
    return round(float(total or 0.0), 2)


def ticket_summary(db: Session, ticket: ServiceTicket) -> dict:
    due = ticket_amount_due(ticket)
    paid = ticket_paid(db, ticket.id)
    balance = round(max(due - paid, 0.0), 2)
    if ticket.status == TicketStatus.CANCELLED or due <= 0:
        status = "none" if paid <= 0 else "paid"
    elif paid <= 0:
        status = "unpaid"
    elif balance > 0.009:
        status = "partial"
    else:
        status = "paid"
    return {"amount_due": due, "amount_paid": paid, "balance_due": balance, "payment_status": status}


def _payment_dict(p: Payment) -> dict:
    return {
        "id": p.id, "ticket_id": p.ticket_id, "work_order_id": p.work_order_id,
        "amount": p.amount, "method": p.method, "note": p.note, "received_by": p.received_by,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
    }


def list_ticket_payments(db: Session, ticket_id: int) -> dict:
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="ไม่พบงานซ่อม")
    rows = db.query(Payment).filter(Payment.ticket_id == ticket_id).order_by(Payment.paid_at).all()
    return {**ticket_summary(db, ticket), "ticket_id": ticket_id, "payments": [_payment_dict(p) for p in rows]}


def add_ticket_payment(db: Session, ticket_id: int, amount: float, method: str, note: Optional[str] = None,
                       received_by: Optional[str] = None, paid_at=None) -> dict:
    ticket = db.query(ServiceTicket).filter(ServiceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="ไม่พบงานซ่อม")
    if ticket.status == TicketStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="งานนี้ถูกยกเลิกแล้ว รับเงินไม่ได้")
    summary = ticket_summary(db, ticket)
    if summary["amount_due"] > 0 and amount > summary["balance_due"] + 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"ยอดที่รับ ฿{amount:,.2f} มากกว่ายอดค้าง ฿{summary['balance_due']:,.2f}",
        )
    db.add(Payment(
        ticket_id=ticket_id, amount=round(amount, 2), method=method or "เงินสด",
        note=note, received_by=received_by,
        paid_at=to_local_naive(paid_at) if paid_at else get_local_now(),
    ))
    db.commit()
    return list_ticket_payments(db, ticket_id)


def delete_payment(db: Session, payment_id: int) -> dict:
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="ไม่พบรายการรับเงิน")
    if p.work_order_id and not p.ticket_id:
        raise HTTPException(status_code=400, detail="การชำระของบิลขายหน้าร้าน แก้ไขผ่านบิลขายเท่านั้น")
    ticket_id = p.ticket_id
    db.delete(p)
    db.commit()
    return list_ticket_payments(db, ticket_id)


def outstanding_tickets(db: Session) -> dict:
    """Jobs that were agreed (approved / in progress / done) and still have money owing."""
    tickets = db.query(ServiceTicket).filter(ServiceTicket.status.in_([
        TicketStatus.APPROVED, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED,
    ])).order_by(ServiceTicket.created_at).all()
    items = []
    for t in tickets:
        s = ticket_summary(db, t)
        if s["balance_due"] > 0.009:
            items.append({
                "ticket_id": t.id,
                "status": t.status,
                "plate": t.vehicle.plate if t.vehicle else None,
                "customer_name": t.customer.name if t.customer else None,
                "customer_phone": t.customer.phone if t.customer else None,
                "date": (t.completed_at or t.created_at).isoformat() if (t.completed_at or t.created_at) else None,
                **s,
            })
    return {"count": len(items), "total_outstanding": round(sum(i["balance_due"] for i in items), 2), "items": items}


# ── POS sales are paid in full at the counter ────────────────────────────────

def record_work_order_payment(db: Session, wo_id: int, amount: float, method: str, paid_at) -> None:
    db.query(Payment).filter(Payment.work_order_id == wo_id).delete(synchronize_session=False)
    if amount > 0:
        db.add(Payment(work_order_id=wo_id, amount=round(amount, 2), method=method or "เงินสด",
                       paid_at=paid_at or get_local_now(), received_by="หน้าร้าน (POS)"))


def delete_work_order_payments(db: Session, wo_id: int) -> None:
    db.query(Payment).filter(Payment.work_order_id == wo_id).delete(synchronize_session=False)
