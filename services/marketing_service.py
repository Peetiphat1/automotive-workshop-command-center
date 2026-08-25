"""
Marketing Service — Module 4 business logic (Retention Engine)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from agents.marketing_agent import MarketingState, marketing_graph, mock_line_dispatch
from core.config import settings
from models.db_models import Customer, MarketingTask, MarketingTaskStatus, Vehicle
from models.schemas import (
    MarketingApproveRequest, MarketingRejectRequest, MarketingTaskResponse,
    MarketingTriggerResponse,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _task_to_response(task: MarketingTask) -> MarketingTaskResponse:
    customer_name = task.customer.name if task.customer else None
    vehicle_plate = task.vehicle.plate if task.vehicle else None
    return MarketingTaskResponse(
        id=task.id,
        customer_id=task.customer_id,
        customer_name=customer_name,
        vehicle_plate=vehicle_plate,
        trigger_type=task.trigger_type,
        draft_message=task.draft_message,
        voucher_code=task.voucher_code,
        discount_amount=task.discount_amount,
        status=task.status,  # type: ignore[arg-type]
        approved_by=task.approved_by,
        dispatched_at=task.dispatched_at,
        line_message_id=task.line_message_id,
        created_at=task.created_at,
    )


# ── Maintenance scan (deterministic date/mileage math) ────────────────────────

def _scan_vehicles_for_triggers(db: Session) -> List[Dict]:
    """
    Query all vehicles and flag those matching maintenance thresholds.
    Multiple triggers per vehicle produce separate tasks.
    """
    now = datetime.utcnow()
    oil_km_limit = settings.OIL_CHANGE_KM
    oil_month_limit = timedelta(days=settings.OIL_CHANGE_MONTHS * 30)
    battery_limit = timedelta(days=settings.BATTERY_CHANGE_YEARS * 365)
    tire_km_limit = settings.TIRE_CHANGE_KM
    churn_limit = timedelta(days=settings.CUSTOMER_INACTIVE_MONTHS * 30)

    flagged: List[Dict] = []
    vehicles = db.query(Vehicle).all()

    for v in vehicles:
        customer: Customer = v.customer
        base = {
            "customer_id": customer.id,
            "customer_name": customer.name,
            "vehicle_id": v.id,
            "car_model": f"{v.brand} {v.model}",
            "plate": v.plate,
            "current_mileage": v.current_mileage,
        }

        triggered = False

        # ── Oil overdue ───────────────────────────────────────────────────────
        oil_km_overdue = (
            v.last_oil_change_mileage is not None
            and (v.current_mileage - v.last_oil_change_mileage) >= oil_km_limit
        )
        oil_date_overdue = (
            v.last_oil_change_date is not None
            and (now - v.last_oil_change_date) >= oil_month_limit
        )
        if oil_km_overdue or oil_date_overdue:
            flagged.append({**base, "trigger_type": "oil_overdue"})
            triggered = True

        # ── Battery overdue ───────────────────────────────────────────────────
        battery_overdue = (
            v.last_battery_date is not None
            and (now - v.last_battery_date) >= battery_limit
        )
        if battery_overdue:
            flagged.append({**base, "trigger_type": "battery_overdue"})
            triggered = True

        # ── Tire overdue ──────────────────────────────────────────────────────
        tire_overdue = (
            v.last_tire_change_mileage is not None
            and (v.current_mileage - v.last_tire_change_mileage) >= tire_km_limit
        )
        if tire_overdue:
            flagged.append({**base, "trigger_type": "tire_overdue"})
            triggered = True

        # ── Churn risk (only if no other trigger already flagged) ─────────────
        if not triggered:
            churn = (
                v.last_service_date is not None
                and (now - v.last_service_date) >= churn_limit
            )
            if churn:
                flagged.append({**base, "trigger_type": "churn_risk"})

    return flagged


# ── Service functions ─────────────────────────────────────────────────────────

def run_marketing_cron(db: Session) -> MarketingTriggerResponse:
    """
    Full pipeline:
      1. Scan DB for maintenance/churn triggers (deterministic math)
      2. Run MarketingGraph (message generation with vouchers)
      3. Persist as PENDING_ADMIN_APPROVAL tasks
    """
    run_id = str(uuid.uuid4())[:8].upper()
    flagged = _scan_vehicles_for_triggers(db)

    if not flagged:
        return MarketingTriggerResponse(
            run_id=run_id,
            scan_date=datetime.utcnow().isoformat(),
            total_flagged=0,
            tasks_generated=0,
            trigger_breakdown={},
            task_ids=[],
        )

    # Run MarketingGraph
    result: MarketingState = marketing_graph.invoke({
        "scan_date": datetime.utcnow().isoformat(),
        "flagged_vehicles": flagged,
        "generated_tasks": [],
        "scan_summary": {},
        "error": None,
    })

    # Persist tasks
    task_ids: List[int] = []
    for t in result["generated_tasks"]:
        task = MarketingTask(
            customer_id=t["customer_id"],
            vehicle_id=t.get("vehicle_id"),
            trigger_type=t["trigger_type"],
            draft_message=t["draft_message"],
            voucher_code=t["voucher_code"],
            discount_amount=t["discount_amount"],
            status=MarketingTaskStatus.PENDING_ADMIN_APPROVAL,
        )
        db.add(task)
        db.flush()
        task_ids.append(task.id)

    db.commit()
    summary = result["scan_summary"]

    return MarketingTriggerResponse(
        run_id=run_id,
        scan_date=result["scan_date"],
        total_flagged=summary.get("total_flagged", 0),
        tasks_generated=summary.get("tasks_generated", 0),
        trigger_breakdown=summary.get("trigger_breakdown", {}),
        task_ids=task_ids,
    )


def list_tasks(
    db: Session,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    q = db.query(MarketingTask)
    if status_filter:
        q = q.filter(MarketingTask.status == status_filter)
    total = q.count()
    pending = db.query(MarketingTask).filter(
        MarketingTask.status == MarketingTaskStatus.PENDING_ADMIN_APPROVAL
    ).count()
    tasks = q.order_by(MarketingTask.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "pending": pending,
        "items": [_task_to_response(t) for t in tasks],
    }


def get_task(db: Session, task_id: int) -> MarketingTaskResponse:
    task = db.query(MarketingTask).filter(MarketingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Marketing task #{task_id} not found.")
    return _task_to_response(task)


def approve_task(db: Session, task_id: int, req: MarketingApproveRequest) -> MarketingTaskResponse:
    """
    HITL gate: admin reviews draft, optionally edits, then dispatches to LINE OA (mock).
    """
    task = db.query(MarketingTask).filter(MarketingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Marketing task #{task_id} not found.")
    if task.status == MarketingTaskStatus.DISPATCHED:
        raise HTTPException(status_code=409, detail="Task is already dispatched.")
    if task.status == MarketingTaskStatus.REJECTED:
        raise HTTPException(status_code=409, detail="Cannot approve a rejected task.")

    # Apply edited message if provided
    if req.edited_message:
        task.draft_message = req.edited_message

    # Mock LINE dispatch
    customer: Customer = task.customer
    line_id = customer.line_id or customer.phone
    dispatch_result = mock_line_dispatch(line_id, task.draft_message)

    task.status = MarketingTaskStatus.DISPATCHED
    task.approved_by = req.approved_by
    task.dispatched_at = datetime.utcnow()
    task.line_message_id = dispatch_result.get("message_id", "MOCK_ID")

    db.commit()
    db.refresh(task)
    return _task_to_response(task)


def reject_task(db: Session, task_id: int, req: MarketingRejectRequest) -> MarketingTaskResponse:
    task = db.query(MarketingTask).filter(MarketingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Marketing task #{task_id} not found.")
    if task.status in (MarketingTaskStatus.DISPATCHED, MarketingTaskStatus.REJECTED):
        raise HTTPException(status_code=409, detail=f"Task is already {task.status}.")

    task.status = MarketingTaskStatus.REJECTED
    task.approved_by = req.rejected_by  # reuse field for audit trail
    if req.reason:
        # Prepend rejection reason to draft_message for audit visibility
        task.draft_message = f"[REJECTED: {req.reason}]\n\n" + task.draft_message

    db.commit()
    db.refresh(task)
    return _task_to_response(task)
