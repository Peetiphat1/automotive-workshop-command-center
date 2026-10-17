"""
Router: LINE OA Webhook & 2-Way Interactive Bot
═══════════════════════════════════════════════
Handles incoming webhook events from LINE Messaging API.
When customers message the workshop LINE Official Account, this router:
  1. Identifies the customer / vehicle via LINE User ID or plate
  2. Inquires live repair status from DB (ServiceTicket)
  3. Formats rich response with live status, cost, mechanic notes & tracking link
  4. Automatically replies via LINE Reply API
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
import httpx
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_db
from models.db_models import Customer, ServiceTicket, TicketStatus, Vehicle
from services import ai_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_signature(body_bytes: bytes, signature: str, secret: str) -> bool:
    """Verify X-Line-Signature header."""
    if not secret:
        return True
    hash_val = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(hash_val).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _reply_line(reply_token: str, user_id: str, messages: List[Dict[str, Any]], token: str) -> bool:
    """Send reply message via LINE Reply API, with fallback to Push API."""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": messages,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            if reply_token and not reply_token.startswith("dummy"):
                res = client.post(url, headers=headers, json=payload)
                print(f"--> [LINE REPLY API] Status: {res.status_code}, Body: {res.text}")
                if res.status_code == 200:
                    return True

            # If reply API failed or reply_token invalid/expired, fallback to push directly
            if user_id:
                print(f"--> Falling back to Push API for user: {user_id}")
                push_url = "https://api.line.me/v2/bot/message/push"
                push_payload = {"to": user_id, "messages": messages}
                push_res = client.post(push_url, headers=headers, json=push_payload)
                print(f"--> [LINE PUSH FALLBACK] Status: {push_res.status_code}, Body: {push_res.text}")
                return push_res.status_code == 200
    except Exception as e:
        print(f"--> Error in _reply_line: {e}")
        return False
    return False


def handle_customer_line_text(db: Session, user_id: str, text: str) -> str:
    """
    Process incoming customer text message and formulate workshop reply.
    """
    clean = text.strip()
    m_lower = clean.lower()

    # 1. Identify customer by LINE user_id
    customer = db.query(Customer).filter(Customer.line_id == user_id).first()

    # If customer not found by LINE ID, check if they provided a license plate in the message
    plate_m = re.search(r"(\d?[ก-ฮ]{1,3}\s*\d{1,4}|[a-zA-Z0-9]{2,4}\s*[-]?\s*[0-9]{1,4})", clean)
    extracted_plate = plate_m.group(1).replace(" ", "").strip() if plate_m else None

    # Find tickets
    ticket: Optional[ServiceTicket] = None

    # Priority A: Look up ticket by extracted plate
    if extracted_plate:
        for v in db.query(Vehicle).all():
            if v.plate and (extracted_plate.lower() in v.plate.replace(" ", "").lower()):
                t = (
                    db.query(ServiceTicket)
                    .filter(ServiceTicket.vehicle_id == v.id)
                    .order_by(ServiceTicket.created_at.desc())
                    .first()
                )
                if t:
                    ticket = t
                    if not customer and v.customer:
                        customer = v.customer
                    break

    # Priority B: Look up ticket by customer's vehicles
    if not ticket and customer:
        v_ids = [v.id for v in customer.vehicles]
        if v_ids:
            ticket = (
                db.query(ServiceTicket)
                .filter(ServiceTicket.vehicle_id.in_(v_ids))
                .order_by(ServiceTicket.created_at.desc())
                .first()
            )

    # ── CASE: Repair Status Inquiry (สถานะงานซ่อม) ────────────────────────────
    status_keywords = ["สถานะ", "ซ่อม", "เสร็จยัง", "เสร็จหรือยัง", "เช็ค", "ตรวจ", "รถ", "ticket", "ตั๋ว", "งานซ่อม", "รับรถ"]
    is_asking_status = any(k in m_lower for k in status_keywords) or bool(extracted_plate)

    if is_asking_status:
        if ticket:
            cust_name = customer.name if customer else "ท่าน"
            v = ticket.vehicle
            plate_str = v.plate if v else (ticket.vehicle_plate or "รถของคุณ")
            car_str = f"{v.brand} {v.model}" if v and v.brand else (ticket.car_model or "รถยนต์")
            # Clean symptom text from any file/picture tags
            raw_sym = ticket.mechanic_notes or ticket.raw_input or "ตรวจเช็คทั่วไป"
            raw_sym = re.sub(r"\[แนบภาพถ่าย[^\]]*\]", "", raw_sym)
            raw_sym = re.sub(r"/static/\S+", "", raw_sym)
            raw_sym = re.sub(r"https?://\S+", "", raw_sym).strip()
            symptom = raw_sym[:100] if raw_sym else "ตรวจเช็คทั่วไป"

            status_val = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
            if status_val == "APPROVED":
                status_th = "✅ ซ่อมเสร็จเรียบร้อยแล้ว — พร้อมส่งมอบรถ ✨"
                action_th = "ท่านสามารถเข้ามารับรถที่อู่ได้เลยครับ"
            elif status_val == "PENDING_MECHANIC_APPROVAL":
                status_th = "⏳ อยู่ระหว่างช่างตรวจเช็คสภาพจริงและประเมินอะไหล่"
                action_th = "เมื่อช่างตรวจเช็คและประเมินราคาเสร็จ จะส่งสรุปให้ทราบทันทีครับ"
            elif status_val == "IN_PROGRESS":
                status_th = "🔧 ช่างกำลังดำเนินการซ่อมแซมและเปลี่ยนอะไหล่"
                action_th = "กำลังดำเนินงานตามมาตรฐานความปลอดภัยครับ"
            else:
                status_th = f"📌 {status_val}"
                action_th = "ติดต่อสอบถามเพิ่มเติมได้ที่ 081-234-5678"

            cost_val = ticket.final_cost if ticket.final_cost is not None else ticket.total_estimated_cost
            cost_str = f"{cost_val:,.2f} บาท" if cost_val else "รอสรุปราคาประเมิน"

            reply = (
                f"🚗 สถานะงานซ่อมของคุณ {cust_name}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🚘 รถยนต์: {car_str}\n"
                f"🔢 ทะเบียน: {plate_str}\n"
                f"📋 Ticket ID: #{ticket.id}\n"
                f"⚙️ สถานะ: {status_th}\n"
                f"💰 ยอดค่าบริการ: {cost_str}\n"
                f"📝 งานที่ทำ: {symptom}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💡 {action_th}"
            )
            return reply
        else:
            cust_name = customer.name if customer else "ลูกค้า"
            return (
                f"🚗 สวัสดีครับคุณ {cust_name}\n\n"
                f"ขณะนี้ไม่พบข้อมูลงานซ่อมที่กำลังดำเนินการอยู่ในระบบครับ ✨\n"
                f"หากท่านต้องการ:\n"
                f"• เช็คประวัติรถคันอื่น: กรุณาพิมพ์เลขทะเบียนรถ (เช่น `กข 1234`)\n"
                f"• นัดหมายเข้าตรวจเช็ค: พิมพ์ `นัดหมาย`\n"
                f"• สอบถามช่างประจำอู่: โทร 095-418-5332\n\n"
                f"Zero Garage ยินดีให้บริการครับ 🙏"
            )

    # ── CASE: Appointments (นัดหมาย) ──────────────────────────────────────────
    if any(k in m_lower for k in ["นัด", "จอง", "คิว", "book", "appointment"]):
        return (
            "📅 นัดหมายเข้าตรวจเช็คสภาพรถ — Zero Garage\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "ท่านสามารถนัดหมายล่วงหน้าได้โดยแจ้งข้อมูล:\n"
            "1. ทะเบียนรถ และรุ่นรถ\n"
            "2. งานที่ต้องการ (เช่น เปลี่ยนน้ำมันเครื่อง / เช็คระยะ / ตรวจเช็คช่วงล่าง)\n"
            "3. วันและเวลาที่สะดวกนำรถเข้า\n\n"
            "เจ้าหน้าที่จะทำการลงตารางนัดหมายและยืนยันคิวให้ท่านทันทีครับ 🚗"
        )

    # ── CASE: Default Greeting & Menu ─────────────────────────────────────────
    cust_greet = f"คุณ {customer.name}" if customer else "ท่าน"
    return (
        f"🚗 สวัสดีครับ {cust_greet} ยินดีต้อนรับสู่ Zero Garage\n"
        f"ศูนย์บริการตรวจเช็คและซ่อมบำรุงรถยนต์ครบวงจร ✨\n\n"
        f"ท่านสามารถพิมพ์สั่งงานได้ทันที เช่น:\n"
        f"• พิมพ์ 'สถานะซ่อม' หรือพิมพ์เลขทะเบียนรถ เพื่อเช็คงานซ่อมแบบเรียลไทม์\n"
        f"• พิมพ์ 'นัดหมาย' เพื่อจองคิวตรวจเช็คสภาพรถ\n"
        f"• โทรสอบถามด่วน: 095-418-5332\n\n"
        f"เปิดให้บริการ จันทร์ - เสาร์ (08:30 - 18:00 น.) ครับ 🙏"
    )


@router.post("/webhook", summary="LINE Messaging API Webhook")
async def line_webhook(
    request: Request,
    x_line_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    body_bytes = await request.body()
    secret = ai_service.get_configured_key("LINE_OA_CHANNEL_SECRET") or settings.LINE_OA_CHANNEL_SECRET
    token = ai_service.get_configured_key("LINE_OA_CHANNEL_TOKEN") or settings.LINE_OA_CHANNEL_TOKEN

    print(f"==> [INCOMING LINE WEBHOOK]: {body_bytes.decode('utf-8', errors='ignore')}")

    # Signature verification — this route is public, so reject anything not signed by LINE.
    # (Use POST /api/v1/line/test-query to test replies without LINE.)
    if not secret:
        raise HTTPException(status_code=503, detail="LINE_OA_CHANNEL_SECRET is not configured.")
    if not x_line_signature or not _verify_signature(body_bytes, x_line_signature, secret):
        print("⚠️ Rejected LINE webhook: missing or invalid X-Line-Signature.")
        raise HTTPException(status_code=401, detail="Invalid LINE signature.")

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        print(f"Error parsing JSON body: {e}")
        return {"status": "ok"}

    events = data.get("events", [])
    for ev in events:
        if ev.get("type") == "message":
            msg_obj = ev.get("message", {})
            if msg_obj.get("type") == "text":
                reply_token = ev.get("replyToken")
                user_id = ev.get("source", {}).get("userId", "")
                user_text = msg_obj.get("text", "")
                print(f"--> Received text from {user_id}: {user_text}")

                reply_text = handle_customer_line_text(db, user_id, user_text)
                _reply_line(reply_token, user_id, [{"type": "text", "text": reply_text}], token)

    return {"status": "ok"}


class TestQueryRequest(BaseModel):
    user_id: str = "U736b2b09bc7a5c85540f1f8bf24b3f08"
    message: str = "สถานะซ่อม"


@router.post("/test-query", summary="Simulate customer inquiring status via LINE")
def test_query(
    req: TestQueryRequest = TestQueryRequest(),
    db: Session = Depends(get_db),
):
    """
    Test helper endpoint: Simulates an incoming LINE message from a customer
    and returns the exact formatted reply message that would be sent back to LINE.
    """
    reply = handle_customer_line_text(db, user_id=req.user_id, text=req.message)
    return {
        "incoming_user_id": req.user_id,
        "incoming_message": req.message,
        "bot_reply": reply,
    }
