"""
Router: Chat Command Center
Handles natural language commands from the chat UI and routes to the
appropriate module (tickets, finance, marketing, watchlist, summary).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import (
    BillParseTextRequest, TicketApproveRequest, TicketIngestRequest,
)
from services import finance_service, ticket_service
from models.db_models import (
    Customer, LedgerEntry, MarketingTask, ServiceTicket,
    VehicleHealthWatchlist, Vehicle,
)

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    type: str          # "ticket" | "bill" | "watchlist" | "summary" | "scan" | "approve" | "error" | "info"
    text: str          # Human-readable response message
    data: Optional[dict] = None   # Structured payload for the UI to render


# ── Intent detection ──────────────────────────────────────────────────────────

def _detect_intent(msg: str) -> str:
    """Rule-based intent detection from Thai/English natural language."""
    m = msg.lower().strip()

    # Approve ticket
    if re.search(r"(approve|อนุมัติ).*(ticket|ใบสั่ง|#?\d+)", m) or re.search(r"(ticket|#)\s*(\d+).*(approve|อนุมัติ)", m):
        return "ticket_approve"

    # Watchlist / health check
    if any(k in m for k in ["watchlist", "แจ้งเตือน", "overdue", "เกินกำหนด", "ตรวจสุขภาพ", "health"]):
        return "watchlist"

    # Summary / P&L
    if any(k in m for k in ["summary", "สรุป", "p&l", "กำไร", "รายได้", "ยอด", "profit", "revenue"]):
        return "summary"

    # Scan / marketing
    if any(k in m for k in ["scan", "สแกน", "retention", "marketing", "campaign", "ส่งข้อความ"]):
        return "scan"

    # Stock adjustment
    if any(k in m for k in ["สต็อก", "stock", "เพิ่มสต็อก", "ลดสต็อก", "adjust stock", "ปรับสต็อก", "จำนวน"]) and \
       any(k in m for k in ["เพิ่ม", "ลด", "ปรับ", "adjust", "+", "-"]):
        return "stock_adjust"

    # Add expense
    if any(k in m for k in ["ค่าไฟ", "ค่าน้ำ", "ค่าเช่า", "ค่าอินเทอร์", "ค่าใช้จ่าย", "expense", "จ่ายบิล", "ค่า"]) and \
       any(k in m for k in ["บาท", "thb", "บันทึก", "เพิ่ม", "add"]):
        return "add_expense"

    # Add appointment
    if any(k in m for k in ["นัด", "appointment", "จอง", "นัดหมาย"]):
        return "add_appointment"

    # Bill (expense) — look for vendor/price keywords
    if any(k in m for k in ["บิล", "bill", "ค่าใช้จ่าย", "expense", "ซื้อ", "จ่าย", "ใบแจ้งหนี้", "invoice"]):
        return "bill_expense"

    # Bill (income)
    if any(k in m for k in ["ยอดขาย", "รายรับ", "income", "sale", "ขายได้"]):
        return "bill_income"

    # Default: repair ticket intake (Thai car descriptions)
    if any(k in m for k in ["รถ", "ทะเบียน", "เปลี่ยน", "ซ่อม", "เช็ค", "เกียร์", "เบรค", "ยาง", "น้ำมัน", "แบต", "แอร์", "เครื่อง", "repair", "car", "vehicle", "plate", "brand"]):
        return "repair_ticket"

    return "unknown"


def _extract_ticket_id(msg: str) -> Optional[int]:
    """Extract a ticket ID number from messages like 'approve ticket 3' or '#5'."""
    m = re.search(r"(?:ticket|#)\s*(\d+)", msg, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d+)\b", msg)
    if m:
        return int(m.group(1))
    return None


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse, summary="Chat command endpoint")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    msg = req.message.strip()
    if not msg:
        return ChatResponse(type="error", text="Please type a message.")

    intent = _detect_intent(msg)

    # ── Repair ticket intake ──────────────────────────────────────────────────
    if intent == "repair_ticket":
        try:
            ticket = ticket_service.create_ticket(db, TicketIngestRequest(raw_input=msg))
            symptoms = [d.symptom for d in ticket.diagnosed_issues]
            total = ticket.total_estimated_cost
            status_str = ticket.status.value if hasattr(ticket.status, 'value') else str(ticket.status)
            return ChatResponse(
                type="ticket",
                text=f"✅ Repair ticket **#{ticket.id}** created — {ticket.car_model or 'Unknown'} ({ticket.vehicle_plate or 'No plate'})\n"
                     f"🔧 Symptoms: {', '.join(symptoms) or 'None detected'}\n"
                     f"💰 Estimated cost: ฿{total:,.0f}\n"
                     f"⏳ Status: **{status_str}** — awaiting mechanic approval",
                data={
                    "ticket_id": ticket.id,
                    "vehicle_plate": ticket.vehicle_plate,
                    "car_model": ticket.car_model,
                    "status": status_str,
                    "total_estimated_cost": total,
                    "diagnosed_issues": [d.model_dump() for d in ticket.diagnosed_issues],
                    "line_items": [i.model_dump() for i in ticket.line_items],
                }
            )
        except Exception as e:
            return ChatResponse(type="error", text=f"❌ Could not create ticket: {str(e)}")

    # ── Ticket approve ────────────────────────────────────────────────────────
    if intent == "ticket_approve":
        ticket_id = _extract_ticket_id(msg)
        if not ticket_id:
            return ChatResponse(
                type="info",
                text="Which ticket do you want to approve? Please type the ticket number, e.g. `approve ticket 3`"
            )
        # Return a special type so the UI opens the approval modal
        return ChatResponse(
            type="approve_prompt",
            text=f"Opening approval form for Ticket **#{ticket_id}**...",
            data={"ticket_id": ticket_id}
        )

    # ── Bill expense ──────────────────────────────────────────────────────────
    if intent == "bill_expense":
        try:
            bill_req = BillParseTextRequest(raw_input=msg, bill_type="expense")
            bill = finance_service.parse_text_bill(db, bill_req)
            verified = "✅ Math verified" if bill.math_verified else f"⚠️ Math discrepancy ฿{bill.math_discrepancy:,.2f}"
            return ChatResponse(
                type="bill",
                text=f"💸 **Expense bill** recorded (ID: #{bill.id})\n"
                     f"📦 Vendor: {bill.vendor_name or 'Unknown'}\n"
                     f"💰 Total: ฿{bill.extracted_total:,.2f}\n"
                     f"{verified}\n"
                     f"Status: **{bill.status}** — use `confirm bill #{bill.id}` or click Confirm below",
                data={
                    "bill_id": bill.id,
                    "bill_type": "expense",
                    "vendor_name": bill.vendor_name,
                    "extracted_total": bill.extracted_total,
                    "math_verified": bill.math_verified,
                    "status": bill.status,
                }
            )
        except Exception as e:
            return ChatResponse(type="error", text=f"❌ Could not parse bill: {str(e)}")

    # ── Bill income ───────────────────────────────────────────────────────────
    if intent == "bill_income":
        try:
            bill_req = BillParseTextRequest(raw_input=msg, bill_type="income")
            bill = finance_service.parse_text_bill(db, bill_req)
            return ChatResponse(
                type="bill",
                text=f"💰 **Income** recorded (ID: #{bill.id})\n"
                     f"📋 Description: {bill.raw_input[:80]}\n"
                     f"💵 Amount: ฿{bill.extracted_total:,.2f}\n"
                     f"Status: **{bill.status}** — use `confirm bill #{bill.id}` or click Confirm below",
                data={
                    "bill_id": bill.id,
                    "bill_type": "income",
                    "extracted_total": bill.extracted_total,
                    "math_verified": bill.math_verified,
                    "status": bill.status,
                }
            )
        except Exception as e:
            return ChatResponse(type="error", text=f"❌ Could not record income: {str(e)}")

    # ── Watchlist ─────────────────────────────────────────────────────────────
    if intent == "watchlist":
        items = db.query(VehicleHealthWatchlist).filter(
            VehicleHealthWatchlist.is_overdue == True
        ).all()
        if not items:
            return ChatResponse(type="watchlist", text="✅ All vehicles are healthy! No overdue components.", data={"items": []})

        lines = []
        watchlist_data = []
        for w in items:
            vehicle = db.query(Vehicle).filter(Vehicle.id == w.vehicle_id).first()
            plate = vehicle.plate if vehicle else "Unknown"
            brand = f"{vehicle.brand} {vehicle.model}" if vehicle else "Unknown"
            lines.append(f"🚨 **{brand}** ({plate}) — {w.component}: {w.condition}")
            watchlist_data.append({
                "plate": plate, "brand": brand,
                "component": w.component, "condition": w.condition, "notes": w.notes
            })

        return ChatResponse(
            type="watchlist",
            text="🔴 **Critical Watchlist** — " + str(len(items)) + " overdue component(s):\n\n" + "\n".join(lines),
            data={"items": watchlist_data}
        )

    # ── P&L Summary ───────────────────────────────────────────────────────────
    if intent == "summary":
        now = datetime.utcnow()
        try:
            result = finance_service.get_finance_summary(db, now.year, now.month)
            s = result.summary
            return ChatResponse(
                type="summary",
                text=f"📊 **{now.strftime('%B %Y')} Financial Summary**\n\n"
                     f"💚 Income:  ฿{s.total_income:,.2f}\n"
                     f"🔴 Expenses: ฿{s.total_expense:,.2f}\n"
                     f"{'💰' if s.net_profit >= 0 else '📉'} Net Profit: ฿{s.net_profit:,.2f}",
                data={
                    "month": now.month, "year": now.year,
                    "total_income": s.total_income,
                    "total_expense": s.total_expense,
                    "net_profit": s.net_profit,
                }
            )
        except Exception as e:
            return ChatResponse(type="error", text=f"❌ Could not load summary: {str(e)}")

    # ── Retention scan ────────────────────────────────────────────────────────
    if intent == "scan":
        try:
            from services import marketing_service
            result = marketing_service.run_retention_cron(db)
            return ChatResponse(
                type="scan",
                text=f"📣 **Retention scan complete!**\n"
                     f"🎯 {result['total_flagged']} customers flagged\n"
                     f"📋 {result['tasks_generated']} new LINE campaigns queued for approval",
                data=result
            )
        except Exception as e:
            return ChatResponse(type="error", text=f"❌ Scan failed: {str(e)}")

    # ── Stock adjust ──────────────────────────────────────────────────────────
    if intent == "stock_adjust":
        from models.db_models import StockItem, StockHistory
        # Try to extract item name and quantity from message
        numbers = re.findall(r'\d+', msg)
        delta = int(numbers[0]) if numbers else 1
        is_decrease = any(k in msg.lower() for k in ["ลด", "หัก", "ใช้", "เอาออก", "decrease"])
        if is_decrease:
            delta = -delta

        # Find matching stock item
        words = msg.replace('+', ' ').replace('-', ' ').split()
        matched_item = None
        for item in db.query(StockItem).all():
            for word in words:
                if len(word) > 2 and (word in item.name_th or word in (item.name_en or '') or word in (item.sku or '')):
                    matched_item = item
                    break
            if matched_item:
                break

        if not matched_item:
            items = db.query(StockItem).limit(5).all()
            item_list = "\n".join([f"• {i.name_th} (คงเหลือ {i.quantity})" for i in items])
            return ChatResponse(
                type="info",
                text=f"ไม่พบอะไหล่ที่ต้องการ กรุณาระบุชื่อให้ชัดเจน เช่น:\n"
                     f"`เพิ่มสต็อก น้ำมันเครื่อง 5 ชิ้น`\n\n"
                     f"รายการอะไหล่ในระบบ:\n{item_list}"
            )

        qty_before = matched_item.quantity
        matched_item.quantity = max(0, matched_item.quantity + delta)
        qty_after = matched_item.quantity
        history = StockHistory(
            stock_item_id=matched_item.id,
            change_type="adjust",
            delta=delta,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reason=f"ปรับโดย AI: {msg[:100]}",
            changed_by="AI Chat",
        )
        db.add(history)
        db.commit()
        action = "เพิ่ม" if delta > 0 else "ลด"
        return ChatResponse(
            type="stock",
            text=f"📦 **ปรับสต็อกเรียบร้อย!**\n"
                 f"🔧 {matched_item.name_th}\n"
                 f"{'➕' if delta > 0 else '➖'} {action} {abs(delta)} ชิ้น\n"
                 f"📊 คงเหลือ: **{qty_after}** ชิ้น",
            data={"item_id": matched_item.id, "item_name": matched_item.name_th,
                  "delta": delta, "qty_before": qty_before, "qty_after": qty_after}
        )

    # ── Add expense ───────────────────────────────────────────────────────────
    if intent == "add_expense":
        from models.db_models import Expense
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', msg.replace(',', ''))
        amount = float(numbers[0]) if numbers else 0.0

        # Detect category
        category = "อื่นๆ"
        if any(k in msg for k in ["ค่าไฟ", "ไฟฟ้า"]): category = "ค่าไฟฟ้า"
        elif any(k in msg for k in ["ค่าน้ำ", "น้ำประปา"]): category = "ค่าน้ำประปา"
        elif any(k in msg for k in ["ค่าเช่า", "เช่า"]): category = "ค่าเช่า"
        elif any(k in msg for k in ["อินเทอร์", "internet", "เน็ต"]): category = "ค่าอินเทอร์เน็ต"

        if amount == 0:
            return ChatResponse(type="info", text="กรุณาระบุจำนวนเงิน เช่น `ค่าไฟ 2,800 บาท`")

        expense = Expense(category=category, description=msg[:200], amount=amount, added_by="AI Chat")
        db.add(expense)
        db.commit()
        return ChatResponse(
            type="expense",
            text=f"💸 **บันทึกค่าใช้จ่ายเรียบร้อย!**\n"
                 f"📂 หมวด: {category}\n"
                 f"💰 จำนวน: ฿{amount:,.2f}",
            data={"expense_id": expense.id, "category": category, "amount": amount}
        )

    # ── Add appointment ───────────────────────────────────────────────────────
    if intent == "add_appointment":
        from models.db_models import Appointment
        from datetime import datetime, timedelta
        # Parse basic info from message
        # Extract phone if present
        phone_match = re.search(r'0\d{9}', msg)
        phone = phone_match.group(0) if phone_match else None

        # Extract time slot
        time_match = re.search(r'(\d{1,2})[:.：](\d{2})', msg)
        time_slot = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "09:00"

        # Determine appointment date (default tomorrow)
        appt_date = datetime.utcnow() + timedelta(days=1)
        if any(k in msg for k in ["วันนี้", "today"]): appt_date = datetime.utcnow()
        elif any(k in msg for k in ["มะรืน"]): appt_date = datetime.utcnow() + timedelta(days=2)

        appt = Appointment(
            customer_name="ลูกค้า (AI Chat)",
            customer_phone=phone,
            appointment_date=appt_date,
            time_slot=time_slot,
            service_type=msg[:100],
            status="confirmed"
        )
        db.add(appt)
        db.commit()
        return ChatResponse(
            type="appointment",
            text=f"📅 **บันทึกนัดหมายเรียบร้อย!**\n"
                 f"🕐 เวลา: {time_slot} น.\n"
                 f"📋 บริการ: {msg[:80]}...\n"
                 f"✅ ดูรายละเอียดได้ที่หน้าปฏิทินนัดหมาย",
            data={"appointment_id": appt.id, "time_slot": time_slot}
        )

    # ── Unknown ───────────────────────────────────────────────────────────────
    pending_tickets = db.query(ServiceTicket).filter(
        ServiceTicket.status == "PENDING_MECHANIC_APPROVAL"
    ).count()
    overdue = db.query(VehicleHealthWatchlist).filter(
        VehicleHealthWatchlist.is_overdue == True
    ).count()
    return ChatResponse(
        type="info",
        text=f"ไม่เข้าใจคำสั่ง — Here's what you can type:\n\n"
             f"📋 **รับรถซ่อม**: `รถ Toyota Camry ทะเบียน กข 1234 มาเปลี่ยนน้ำมันเครื่อง`\n"
             f"💸 **บิลค่าใช้จ่าย**: `บิลน้ำมัน 850 บาท ร้าน YS อะไหล่`\n"
             f"💰 **บันทึกรายรับ**: `ยอดขายวันนี้ 4,500 บาท`\n"
             f"✅ **อนุมัติ Ticket**: `approve ticket 3`\n"
             f"📦 **ปรับสต็อก**: `เพิ่มสต็อก น้ำมันเครื่อง 5 ขวด`\n"
             f"💡 **ค่าใช้จ่าย**: `ค่าไฟ 2800 บาท`\n"
             f"📅 **นัดหมาย**: `นัดลูกค้า เปลี่ยนยาง 10:00`\n"
             f"👁 **Watchlist**: `watchlist`\n"
             f"📊 **สรุป P&L**: `summary`\n\n"
             f"ปัจจุบัน: **{pending_tickets}** งานรออนุมัติ · **{overdue}** รายการเกินกำหนด"
    )
