"""
Router: Payments — deposits, part payments and outstanding balances of repair jobs
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import PaymentCreate
from services import payment_service

router = APIRouter()


@router.get("/outstanding", summary="Jobs that still owe money")
def outstanding(db: Session = Depends(get_db)):
    return payment_service.outstanding_tickets(db)


@router.get("/methods", summary="Payment methods offered in the UI")
def methods():
    return payment_service.PAYMENT_METHODS


@router.get("/ticket/{ticket_id}", summary="Payments and balance of one job")
def ticket_payments(ticket_id: int, db: Session = Depends(get_db)):
    return payment_service.list_ticket_payments(db, ticket_id)


@router.post("/ticket/{ticket_id}", summary="Receive money for a job (deposit or rest)")
def add_payment(ticket_id: int, req: PaymentCreate, db: Session = Depends(get_db)):
    return payment_service.add_ticket_payment(
        db, ticket_id, req.amount, req.method, req.note, req.received_by, req.paid_at,
    )


@router.delete("/{payment_id}", summary="Remove a payment entered by mistake")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    return payment_service.delete_payment(db, payment_id)
