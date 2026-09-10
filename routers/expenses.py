"""
Router: Expenses — Utility bills and general expenses
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from core.dependencies import get_db
from models.db_models import Expense

router = APIRouter()


class ExpenseCreate(BaseModel):
    category: str
    description: Optional[str] = None
    amount: float
    expense_date: Optional[datetime] = None
    image_path: Optional[str] = None
    added_by: str = "ระบบ"
    notes: Optional[str] = None


@router.get("/")
def list_expenses(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Expense)
    if category:
        query = query.filter(Expense.category == category)
    expenses = query.order_by(Expense.expense_date.desc()).all()
    total = sum(e.amount for e in expenses)
    return {
        "total": total,
        "count": len(expenses),
        "items": [{
            "id": e.id,
            "category": e.category,
            "description": e.description,
            "amount": e.amount,
            "expense_date": e.expense_date.isoformat() if e.expense_date else None,
            "image_path": e.image_path,
            "added_by": e.added_by,
            "notes": e.notes,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in expenses]
    }


@router.post("/")
def create_expense(req: ExpenseCreate, db: Session = Depends(get_db)):
    expense = Expense(**req.model_dump())
    if not expense.expense_date:
        expense.expense_date = datetime.utcnow()
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return {
        "id": expense.id,
        "category": expense.category,
        "amount": expense.amount,
        "description": expense.description,
    }


@router.get("/categories")
def get_expense_categories(db: Session = Depends(get_db)):
    items = db.query(Expense.category).distinct().all()
    return [item[0] for item in items if item[0]]


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"status": "deleted"}
