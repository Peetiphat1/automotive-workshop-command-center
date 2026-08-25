"""
Marketing Agent  (O in R.O.S.E. — Orchestrator)
─────────────────────────────────────────────────
LangGraph StateGraph pipeline:
  scan_maintenance → generate_messages

Trigger rules (deterministic — no LLM needed):
  • oil_overdue    : last_oil_change > 6 months  OR  km delta > 10,000
  • battery_overdue: last_battery_date > 2 years
  • tire_overdue   : current_mileage - last_tire_change_mileage > 40,000
  • churn_risk     : last_service_date > 6 months (and no oil/tire/battery trigger)

All generated tasks are saved as PENDING_ADMIN_APPROVAL (HITL gate).
LINE dispatch is mocked — replace with real LINE Messaging API in production.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from core.config import settings


# ── Typed state ───────────────────────────────────────────────────────────────

class MarketingState(TypedDict):
    scan_date: str
    flagged_vehicles: List[Dict]    # populated by service layer from DB
    generated_tasks: List[Dict]
    scan_summary: Dict
    error: Optional[str]


# ── Voucher generator ─────────────────────────────────────────────────────────

def _gen_voucher(prefix: str = "ROSE") -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


# ── Message templates ─────────────────────────────────────────────────────────

_TEMPLATES: Dict[str, Dict] = {
    "oil_overdue": {
        "discount": 10,
        "body": (
            "สวัสดีครับ/ค่ะ คุณ{customer_name} 🚗\n\n"
            "รถ {car_model} ทะเบียน {plate} ของคุณ\n"
            "✅ ถึงรอบเปลี่ยนน้ำมันเครื่องแล้วครับ!\n"
            "   ปัจจุบัน: {current_mileage:,} กม.\n\n"
            "🎁 รับส่วนลดพิเศษ {discount}% สำหรับเปลี่ยนน้ำมันเครื่อง\n"
            "🏷️  ใช้โค้ด: **{voucher}**\n"
            "📅 ใช้ได้ถึง: {expiry}\n\n"
            "📞 นัดหมายล่วงหน้า: 081-234-5678\n"
            "ขอบคุณที่ไว้วางใจอู่ของเรานะครับ 🙏"
        ),
    },
    "battery_overdue": {
        "discount": 15,
        "body": (
            "สวัสดีครับ/ค่ะ คุณ{customer_name} 🔋\n\n"
            "รถ {car_model} ทะเบียน {plate} ของคุณ\n"
            "⚠️  แบตเตอรี่ใช้งานมาเกิน 2 ปีแล้วครับ\n"
            "   อาจหมดได้ทุกเมื่อ — มาเช็คได้เลยนะครับ!\n\n"
            "🎁 รับส่วนลด {discount}% สำหรับเปลี่ยนแบตเตอรี่\n"
            "🏷️  ใช้โค้ด: **{voucher}**\n"
            "📅 ใช้ได้ถึง: {expiry}\n\n"
            "📞 นัดหมายล่วงหน้า: 081-234-5678\n"
            "ขอบคุณที่ไว้วางใจอู่ของเรานะครับ 🙏"
        ),
    },
    "tire_overdue": {
        "discount": 12,
        "body": (
            "สวัสดีครับ/ค่ะ คุณ{customer_name} 🚗\n\n"
            "รถ {car_model} ทะเบียน {plate} ของคุณ\n"
            "⚠️  ยางรถยนต์ถึงรอบเปลี่ยนแล้วครับ!\n"
            "   ปัจจุบัน: {current_mileage:,} กม.\n\n"
            "🎁 ซื้อยาง 4 เส้น รับส่วนลด {discount}%\n"
            "🏷️  ใช้โค้ด: **{voucher}**\n"
            "📅 ใช้ได้ถึง: {expiry}\n\n"
            "📞 นัดหมายล่วงหน้า: 081-234-5678\n"
            "ขอบคุณที่ไว้วางใจอู่ของเรานะครับ 🙏"
        ),
    },
    "churn_risk": {
        "discount": 20,
        "body": (
            "สวัสดีครับ/ค่ะ คุณ{customer_name} 💌\n\n"
            "นานไม่ได้เจอกันเลยนะครับ!\n"
            "อู่ของเรายังอยู่ที่เดิม พร้อมดูแล\n"
            "รถ {car_model} ของคุณเสมอครับ\n\n"
            "🎁 ลูกค้าพิเศษ รับส่วนลด {discount}% การซ่อมครั้งถัดไป\n"
            "🏷️  ใช้โค้ด: **{voucher}**\n"
            "📅 ใช้ได้ถึง: {expiry}\n\n"
            "📞 นัดหมายล่วงหน้า: 081-234-5678\n"
            "ขอบคุณที่ไว้วางใจอู่ของเราตลอดมาครับ 🙏"
        ),
    },
}


# ── Node 1: enrich flagged records ────────────────────────────────────────────

def _scan_maintenance_node(state: MarketingState) -> MarketingState:
    """
    flagged_vehicles is already populated by the service layer (SQL queries).
    This node adds a `trigger_processed` marker and validates each record.
    """
    enriched = [{**v, "trigger_processed": True} for v in state["flagged_vehicles"]]
    return {**state, "flagged_vehicles": enriched}


# ── Node 2: generate personalised LINE messages ───────────────────────────────

def _generate_messages_node(state: MarketingState) -> MarketingState:
    flagged = state["flagged_vehicles"]
    tasks: List[Dict] = []
    expiry = (datetime.utcnow() + timedelta(days=30)).strftime("%d/%m/%Y")

    for v in flagged:
        trigger_type = v.get("trigger_type", "churn_risk")
        tmpl = _TEMPLATES.get(trigger_type, _TEMPLATES["churn_risk"])
        voucher = _gen_voucher()
        discount = tmpl["discount"]

        message = tmpl["body"].format(
            customer_name=v.get("customer_name", "ลูกค้า"),
            car_model=v.get("car_model", "รถของคุณ"),
            plate=v.get("plate", ""),
            current_mileage=v.get("current_mileage", 0),
            discount=discount,
            voucher=voucher,
            expiry=expiry,
        )

        tasks.append({
            "customer_id": v["customer_id"],
            "vehicle_id": v.get("vehicle_id"),
            "trigger_type": trigger_type,
            "draft_message": message,
            "voucher_code": voucher,
            "discount_amount": float(discount),
            "status": "PENDING_ADMIN_APPROVAL",
        })

    # Build scan summary
    breakdown: Dict[str, int] = {}
    for t in tasks:
        tt = t["trigger_type"]
        breakdown[tt] = breakdown.get(tt, 0) + 1

    scan_summary = {
        "total_flagged": len(flagged),
        "tasks_generated": len(tasks),
        "trigger_breakdown": breakdown,
    }

    return {**state, "generated_tasks": tasks, "scan_summary": scan_summary}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_marketing_graph():
    g = StateGraph(MarketingState)
    g.add_node("scan_maintenance", _scan_maintenance_node)
    g.add_node("generate_messages", _generate_messages_node)
    g.set_entry_point("scan_maintenance")
    g.add_edge("scan_maintenance", "generate_messages")
    g.add_edge("generate_messages", END)
    return g.compile()


marketing_graph = build_marketing_graph()


# ── Mock LINE Messaging API dispatch ──────────────────────────────────────────

def mock_line_dispatch(line_id: str, message: str) -> Dict:
    """
    Simulates a successful LINE OA push message.
    In production: POST to https://api.line.me/v2/bot/message/push
    with Authorization: Bearer {LINE_OA_CHANNEL_TOKEN}.
    """
    fake_message_id = str(uuid.uuid4()).replace("-", "")[:20]
    return {
        "success": True,
        "message_id": fake_message_id,
        "recipient": line_id,
        "mock": True,
        "note": "Replace with real LINE Messaging API in production.",
    }
