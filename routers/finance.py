"""
Router: Module 2 — Finance & Billing
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import (
    BillConfirmRequest, BillListResponse, BillParseTextRequest,
    BillResponse, FinanceSummaryResponse,
)
from services import finance_service

router = APIRouter()


# ── Bill ingestion ────────────────────────────────────────────────────────────

@router.post(
    "/expenses/parse-text",
    response_model=BillResponse,
    status_code=201,
    summary="Parse bill/receipt from raw text",
    description=(
        "Runs the **BillGraph**: extracts line items from Thai/English receipt text, "
        "then performs a **Zero-Hallucination Math Check** (Python Decimal arithmetic). "
        "\n\n- `math_verified: true` → status `DRAFT_AI` (ready for staff confirmation)"
        "\n- `math_verified: false` → status `MATH_ERROR` (blocked until corrected)"
        "\n\nSee `PUT /finance/bills/{id}/confirm` to write to the ledger."
    ),
)
def parse_text_bill(req: BillParseTextRequest, db: Session = Depends(get_db)):
    return finance_service.parse_text_bill(db, req)


@router.post(
    "/bills/upload",
    response_model=BillResponse,
    status_code=201,
    summary="Upload bill image (PNG/JPG) for OCR extraction",
    description=(
        "Accepts a PNG or JPG image file. Runs **Mock OCR** (simulating a Vision LLM), "
        "then feeds the extracted text into the **BillGraph** pipeline with math validation. "
        "\n\n*In production: replace `mock_ocr_image()` with Google Cloud Vision / GPT-4o.*"
    ),
)
async def upload_bill_image(
    file: UploadFile = File(..., description="PNG or JPG receipt/bill image."),
    bill_type: str = Form(default="expense", description="'income' or 'expense'"),
    db: Session = Depends(get_db),
):
    allowed = {"image/png", "image/jpeg", "image/jpg"}
    if file.content_type not in allowed:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Only PNG and JPG are accepted.",
        )
    contents = await file.read()
    return finance_service.parse_image_bill(db, file.filename or "upload.jpg", contents, bill_type)


# ── Bill management ───────────────────────────────────────────────────────────

@router.get(
    "/bills/",
    response_model=BillListResponse,
    summary="List all bills",
)
def list_bills(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    result = finance_service.list_bills(db, limit=limit, offset=offset)
    return result


@router.get(
    "/bills/{bill_id}",
    response_model=BillResponse,
    summary="Get bill by ID",
)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    return finance_service.get_bill(db, bill_id)


@router.put(
    "/bills/{bill_id}/confirm",
    response_model=BillResponse,
    summary="Confirm bill and write to ledger (HITL gate)",
    description=(
        "**Human-in-the-Loop** confirmation endpoint. "
        "Staff reviews the AI-extracted line items, optionally corrects them via "
        "`corrected_items` / `corrected_total`, then confirms. "
        "On confirmation, an entry is written to the **General Ledger**. "
        "Status transitions: `DRAFT_AI` / `MATH_ERROR` → `CONFIRMED`."
    ),
)
def confirm_bill(
    bill_id: int,
    req: BillConfirmRequest,
    db: Session = Depends(get_db),
):
    return finance_service.confirm_bill(db, bill_id, req)


# ── P&L Summary ───────────────────────────────────────────────────────────────

@router.get(
    "/summary/{year}/{month}",
    response_model=FinanceSummaryResponse,
    summary="Monthly P&L summary with AI insights",
    description=(
        "Returns a **deterministic Profit & Loss statement** calculated entirely from the "
        "General Ledger using SQL aggregation (no LLM math). "
        "Includes income/expense breakdown by category and a **rule-based AI narrative** "
        "with actionable business insights. "
        "\n\nExample: `GET /api/v1/finance/summary/2026/8` for August 2026."
    ),
)
def get_finance_summary(
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    return finance_service.get_finance_summary(db, year, month)
