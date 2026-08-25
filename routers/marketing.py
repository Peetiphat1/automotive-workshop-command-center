"""
Router: Module 4 — Autonomous Retention & Marketing Engine
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import (
    MarketingApproveRequest, MarketingRejectRequest, MarketingTaskListResponse,
    MarketingTaskResponse, MarketingTriggerResponse,
)
from services import marketing_service

router = APIRouter()


@router.post(
    "/triggers/run-cron",
    response_model=MarketingTriggerResponse,
    summary="Run maintenance scan & generate marketing tasks",
    description=(
        "**Autonomous Retention Engine** — scans the entire vehicle database for: "
        "\n- 🔧 `oil_overdue`: last oil change > 6 months or > 10,000 km delta"
        "\n- 🔋 `battery_overdue`: last battery replacement > 2 years"
        "\n- 🚗 `tire_overdue`: mileage delta since last tire change > 40,000 km"
        "\n- 💌 `churn_risk`: last service visit > 6 months (with no other trigger)"
        "\n\nFor each flagged vehicle, the **MarketingGraph** generates a hyper-personalised "
        "Thai LINE message with a dynamic voucher code. All tasks are saved as "
        "`PENDING_ADMIN_APPROVAL` and must be reviewed before dispatch."
    ),
)
def run_cron(db: Session = Depends(get_db)):
    return marketing_service.run_marketing_cron(db)


@router.get(
    "/tasks/",
    response_model=MarketingTaskListResponse,
    summary="List marketing tasks",
)
def list_tasks(
    status: Optional[str] = Query(
        None,
        description="Filter by status: PENDING_ADMIN_APPROVAL | APPROVED | DISPATCHED | REJECTED",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    result = marketing_service.list_tasks(db, status_filter=status, limit=limit, offset=offset)
    return result


@router.get(
    "/tasks/{task_id}",
    response_model=MarketingTaskResponse,
    summary="Get marketing task by ID",
)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return marketing_service.get_task(db, task_id)


@router.post(
    "/tasks/{task_id}/approve",
    response_model=MarketingTaskResponse,
    summary="Approve & dispatch marketing task (HITL gate)",
    description=(
        "**Human-in-the-Loop** approval. Admin reviews the draft LINE message, "
        "optionally edits it via `edited_message`, then approves. "
        "The system **mock-dispatches** to LINE OA and transitions status to `DISPATCHED`. "
        "\n\n*In production: replace `mock_line_dispatch()` with real LINE Messaging API call.*"
    ),
)
def approve_task(
    task_id: int,
    req: MarketingApproveRequest,
    db: Session = Depends(get_db),
):
    return marketing_service.approve_task(db, task_id, req)


@router.post(
    "/tasks/{task_id}/reject",
    response_model=MarketingTaskResponse,
    summary="Reject a marketing task",
    description="Admin rejects the task. Status transitions to `REJECTED`. No LINE message is sent.",
)
def reject_task(
    task_id: int,
    req: MarketingRejectRequest,
    db: Session = Depends(get_db),
):
    return marketing_service.reject_task(db, task_id, req)
