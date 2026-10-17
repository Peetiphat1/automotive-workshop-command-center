"""
Router: public quote page for customers (no shop password) — opened from the LINE link.
The random token in the link is the only key, so it never reveals other jobs.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import QuoteDecision
from services import ticket_service

router = APIRouter()


@router.get("/quote/{token}", summary="Quote details for the customer")
def get_quote(token: str, db: Session = Depends(get_db)):
    return ticket_service.get_public_quote(db, token)


@router.post("/quote/{token}/decision", summary="Customer approves or declines the quote")
def decide(token: str, req: QuoteDecision, db: Session = Depends(get_db)):
    return ticket_service.decide_public_quote(db, token, req.decision, req.note)
