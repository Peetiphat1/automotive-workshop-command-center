"""
Per-job money: revenue, parts cost, labour and profit for repair tickets and work orders / POS sales.
Used by the profit, job-profit, mechanics and daily-close reports so they all agree.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import ServiceTicket, StockItem, TicketStatus, WorkOrder

POS_MECHANIC = "หน้าร้าน (POS)"
_LABOR_WORDS = ("ค่าแรง", "ค่าบริการ", "labor", "labour")
_MECH_RE = re.compile(r"ช่างผู้รับงาน:\s*([^\n\r|]+)")
BOOKED_STATUSES = (TicketStatus.APPROVED, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED)


def is_labor(line: dict) -> bool:
    if (line.get("type") or "").lower() == "labor":
        return True
    name = f"{line.get('name_th') or ''} {line.get('name') or ''}".lower()
    return any(w in name for w in _LABOR_WORDS)


def ticket_mechanic(ticket: ServiceTicket) -> Optional[str]:
    m = _MECH_RE.search(ticket.mechanic_notes or "")
    return m.group(1).strip() if m else None


def ticket_date(ticket: ServiceTicket) -> datetime:
    return ticket.completed_at or ticket.approved_at or ticket.created_at


def _line_total(line: dict) -> float:
    if line.get("total") is not None:
        return float(line.get("total") or 0)
    return float(line.get("qty") or 1) * float(line.get("unit_price") or 0)


def _cost_lines(lines: List[dict], stock_cost: Dict[int, float]) -> dict:
    """Split lines into parts / labour and work out the parts cost."""
    parts_rev = labor_rev = parts_cost = 0.0
    missing = 0
    for line in lines:
        total = _line_total(line)
        if is_labor(line):
            labor_rev += total
            continue
        parts_rev += total
        qty = float(line.get("qty") or 1)
        if line.get("unit_cost") is not None:
            parts_cost += qty * float(line["unit_cost"] or 0)
        elif line.get("stock_item_id") and line["stock_item_id"] in stock_cost:
            parts_cost += qty * stock_cost[line["stock_item_id"]]
        else:
            missing += 1  # part typed by hand — its cost is not known
    return {"parts_revenue": parts_rev, "labor_revenue": labor_rev, "parts_cost": parts_cost, "missing_cost": missing}


def _stock_costs(db: Session) -> Dict[int, float]:
    return {sid: (cost or 0.0) for sid, cost in db.query(StockItem.id, StockItem.unit_cost).all()}


def job_rows(db: Session, start: datetime, end: datetime) -> List[dict]:
    """One row per job (booked repair ticket or work order / POS sale) dated inside [start, end]."""
    stock_cost = _stock_costs(db)
    rows = []

    for t in db.query(ServiceTicket).filter(ServiceTicket.status.in_(BOOKED_STATUSES)).all():
        when = ticket_date(t)
        if not when or not (start <= when <= end):
            continue
        revenue = float(t.final_cost or t.total_estimated_cost or 0)
        c = _cost_lines(t.get_line_items(), stock_cost)
        # Price agreed with the customer can differ from the line total (discount / extra work)
        diff = revenue - (c["parts_revenue"] + c["labor_revenue"])
        labor = c["labor_revenue"] + diff
        rows.append({
            "kind": "repair", "ref": f"TK-{t.id:04d}", "id": t.id, "date": when,
            "customer": t.customer.name if t.customer else "ลูกค้าทั่วไป",
            "plate": t.vehicle.plate if t.vehicle else None,
            "mechanic": ticket_mechanic(t), "status": t.status,
            "revenue": revenue, "parts_revenue": c["parts_revenue"], "labor_revenue": labor,
            "parts_cost": c["parts_cost"], "missing_cost": c["missing_cost"],
        })

    for wo in db.query(WorkOrder).all():
        when = wo.work_date or wo.created_at
        if not when or not (start <= when <= end):
            continue
        try:
            lines = json.loads(wo.line_items) if wo.line_items else []
        except (ValueError, TypeError):
            lines = []
        c = _cost_lines(lines, stock_cost)
        is_pos = wo.mechanic_name == POS_MECHANIC
        revenue = float(wo.total_cost or 0)
        rows.append({
            "kind": "pos" if is_pos else "work_order",
            "ref": f"{'POS' if is_pos else 'WO'}-{wo.id:04d}", "id": wo.id, "date": when,
            "customer": wo.customer_name or "ลูกค้าทั่วไป", "plate": wo.vehicle_plate,
            "mechanic": None if is_pos else wo.mechanic_name, "status": "COMPLETED",
            "revenue": revenue, "parts_revenue": c["parts_revenue"],
            "labor_revenue": c["labor_revenue"] + float(wo.labor_cost or 0),
            "parts_cost": c["parts_cost"], "missing_cost": c["missing_cost"],
        })

    for r in rows:
        r["profit"] = round(r["revenue"] - r["parts_cost"], 2)
        r["margin_pct"] = round(r["profit"] / r["revenue"] * 100, 1) if r["revenue"] else 0.0
        for k in ("revenue", "parts_revenue", "labor_revenue", "parts_cost"):
            r[k] = round(r[k], 2)
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows
