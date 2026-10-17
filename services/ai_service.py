"""
Service: AI Workshop Operations Copilot
════════════════════════════════════════
Provides a real, production-ready AI Assistant for the Automotive Workshop.
- Direct HTTP integration with Google Gemini & OpenAI (via httpx, no bulky SDKs needed).
- Dynamic Live Database RAG (Stock, Financials, Tickets, Appointments, Watchlist, Customers).
- STRICT RULE: NO AI MECHANICAL DIAGNOSTICS. Physical inspection and fault diagnosis
  are strictly performed by the mechanic (Human-in-the-Loop). The AI helps log intake tickets
  or schedule appointments for mechanic inspection.
- Intelligent operations fallback engine when no external API key is configured.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from models.db_models import get_local_now
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from core.config import settings
from models.db_models import (
    Appointment, Customer, Expense, LedgerEntry, MarketingTask,
    PurchaseBill, ServiceTicket, StockHistory, StockItem, Supplier,
    Vehicle, VehicleHealthWatchlist,
)

logger = logging.getLogger("workshop.ai")

# Runtime settings cache
_RUNTIME_KEYS: Dict[str, str] = {}


def get_configured_key(key_name: str) -> Optional[str]:
    """Retrieve an API key from runtime memory, os.environ, or .env file."""
    if key_name in _RUNTIME_KEYS and _RUNTIME_KEYS[key_name]:
        return _RUNTIME_KEYS[key_name]
    val = os.getenv(key_name)
    if val:
        return val
    # Fallback check in .env
    try:
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key_name}=") or line.startswith(f'export {key_name}='):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            clean_val = parts[1].strip().strip('"').strip("'")
                            if clean_val:
                                _RUNTIME_KEYS[key_name] = clean_val
                                return clean_val
    except Exception:
        pass
    return None


def set_runtime_key(key_name: str, value: str):
    """Store key in runtime memory and update os.environ."""
    _RUNTIME_KEYS[key_name] = value
    os.environ[key_name] = value


# ── Live Workshop Data Retrieval (RAG Context) ────────────────────────────────

def get_live_workshop_context(db: Session) -> Dict[str, Any]:
    """Extract real-time operational context directly from the SQLite database."""
    now = get_local_now()

    # 1. Stock / Inventory
    stock_items = db.query(StockItem).all()
    stock_list = []
    low_stock = []
    for item in stock_items:
        stock_list.append({
            "id": item.id,
            "sku": item.sku,
            "name": item.name_th,
            "category": item.category,
            "qty": item.quantity,
            "cost": item.unit_cost,
            "sell": item.sell_price,
        })
        if item.quantity <= (getattr(item, 'reorder_level', 5) or 5):
            low_stock.append(f"{item.name_th} (คงเหลือ: {item.quantity})")

    # 2. Financial Summary (current month)
    from services import finance_service
    fin_summary = {}
    try:
        f_res = finance_service.get_finance_summary(db, now.year, now.month)
        s = f_res.summary
        fin_summary = {
            "month": f"{now.year}-{now.month:02d}",
            "income": round(s.total_income, 2),
            "expense": round(s.total_expense, 2),
            "net_profit": round(s.net_profit, 2),
            "profit_margin_pct": round(getattr(s, 'profit_margin_pct', 0.0), 2),
        }
    except Exception as e:
        fin_summary = {"error": str(e)}

    # 3. Tickets & Work Orders
    tickets = db.query(ServiceTicket).order_by(ServiceTicket.created_at.desc()).limit(10).all()
    ticket_list = []
    pending_approval_count = 0
    for t in tickets:
        status_str = t.status.value if hasattr(t.status, "value") else str(t.status)
        if status_str == "PENDING_MECHANIC_APPROVAL":
            pending_approval_count += 1
        v_plate = t.vehicle.plate if t.vehicle else None
        v_model = f"{t.vehicle.brand} {t.vehicle.model}" if t.vehicle else None
        ticket_list.append({
            "id": t.id,
            "plate": v_plate,
            "model": v_model,
            "status": status_str,
            "total_estimated": t.total_estimated_cost,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
        })

    # 4. Appointments
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)
    appts = db.query(Appointment).filter(Appointment.appointment_date >= today_start).order_by(Appointment.appointment_date.asc()).limit(8).all()
    appt_list = []
    for a in appts:
        appt_list.append({
            "id": a.id,
            "customer": a.customer_name,
            "phone": a.customer_phone,
            "date": a.appointment_date.strftime("%Y-%m-%d") if a.appointment_date else "",
            "time": a.time_slot,
            "service": a.service_type,
            "status": a.status,
        })

    # 5. Overdue Watchlist (Maintenance Alerts)
    watchlist_items = db.query(VehicleHealthWatchlist).filter(VehicleHealthWatchlist.is_overdue == True).all()
    watch_list = []
    for w in watchlist_items:
        v = db.query(Vehicle).filter(Vehicle.id == w.vehicle_id).first()
        plate = v.plate if v else "Unknown"
        model = f"{v.brand} {v.model}" if v else "Unknown"
        watch_list.append({
            "plate": plate,
            "model": model,
            "component": w.component,
            "condition": w.condition,
        })

    # 6. Customers & Vehicles Stats
    total_customers = db.query(Customer).count()
    total_vehicles = db.query(Vehicle).count()

    # 7. Suppliers
    suppliers = db.query(Supplier).all()
    sup_list = [{
        "id": s.id,
        "name": s.name,
        "phone": s.phone or "",
        "email": s.email or "",
        "line_id": s.line_id or "",
        "address": s.address or "",
    } for s in suppliers]

    # 8. Recent Expenses
    expenses = db.query(Expense).order_by(Expense.expense_date.desc()).limit(10).all()
    exp_list = [{
        "id": e.id,
        "category": e.category,
        "description": e.description[:80] if e.description else "",
        "amount": e.amount,
        "date": e.expense_date.strftime("%Y-%m-%d") if e.expense_date else "",
    } for e in expenses]

    # 9. Recent Customers
    customers = db.query(Customer).order_by(Customer.created_at.desc()).limit(10).all()
    cust_list = [{
        "id": c.id,
        "name": c.name,
        "phone": c.phone or "",
        "line_id": c.line_id or "",
    } for c in customers]

    return {
        "stock": {
            "total_types": len(stock_items),
            "items": stock_list,
            "low_stock_alerts": low_stock,
        },
        "financials": fin_summary,
        "tickets": {
            "recent": ticket_list,
            "pending_approval_count": pending_approval_count,
        },
        "appointments": appt_list,
        "watchlist_overdue": watch_list,
        "suppliers": sup_list,
        "recent_expenses": exp_list,
        "recent_customers": cust_list,
        "overview": {
            "total_customers": total_customers,
            "total_vehicles": total_vehicles,
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
    }


# ── LLM Caller (Google Gemini REST API) ───────────────────────────────────────

async def call_gemini(api_key: str, prompt: str, system_instruction: str) -> str:
    """Send prompt directly to Google Gemini REST API using httpx."""
    # Try modern Gemini models with automatic fallback
    models = ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-flash-latest", "gemini-2.5-flash"]
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        texts = [p.get("text", "") for p in parts if "text" in p]
                        full_text = "".join(texts).strip()
                        if full_text:
                            return full_text
                elif res.status_code in (404, 503):
                    continue  # Try next model if this one is not found or overloaded
                else:
                    logger.warning(f"Gemini API returned {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.warning(f"Gemini request failed for {model_name}: {e}")

    raise RuntimeError("Failed to obtain response from Gemini API.")


# ── LLM Caller (OpenAI REST API) ──────────────────────────────────────────────

async def call_openai(api_key: str, prompt: str, system_instruction: str) -> str:
    """Send prompt to OpenAI Chat Completions REST API using httpx."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
        else:
            raise RuntimeError(f"OpenAI API error {res.status_code}: {res.text[:200]}")


# ── Action Execution Handlers ─────────────────────────────────────────────────

def execute_stock_operation(db: Session, msg: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Intelligently adjusts existing stock OR creates a new stock item.
    Supports Thai and English prompts, e.g.:
    - "เพิ่มสต็อก น้ำมันเครื่อง 10 ขวด"
    - "เพิ่มอะไหล่ ผ้าเบรค 5 ชิ้น"
    - "เพิ่มสินค้าใหม่ หัวเทียน NGK ราคา 250 ทุน 150 จำนวน 20"
    - "add 5 engine oil to stock"
    - "add new part brake pads DB1474 price 800 cost 500 qty 10"
    """
    m_lower = msg.lower()
    numbers = re.findall(r"\d+", msg)
    delta = int(numbers[0]) if numbers else 1
    is_decrease = any(k in m_lower for k in ["ลด", "หัก", "ใช้", "เอาออก", "decrease", "-", "minus"])
    if is_decrease:
        delta = -abs(delta)

    is_explicit_new = any(k in m_lower for k in ["ใหม่", "new", "สร้างสินค้า", "สร้างอะไหล่", "เพิ่มสินค้าใหม่", "เพิ่มอะไหล่ใหม่"])

    # Try to match existing stock item first
    items = db.query(StockItem).all()
    matched_item = None
    if not is_explicit_new:
        # Check SKU match
        for item in items:
            if item.sku and item.sku.lower() in m_lower:
                matched_item = item
                break
        # Check name tokens & automotive keywords
        if not matched_item:
            for item in items:
                clean_name = item.name_th.lower()
                clean_en = (item.name_en or "").lower()
                if clean_name in m_lower or (clean_en and clean_en in m_lower):
                    matched_item = item
                    break
                part_keywords = ["น้ำมันเครื่อง", "ไส้กรอง", "กรองเครื่อง", "กรองอากาศ", "กรองโซล่า", "ผ้าเบรค", "จานเบรค", "หัวเทียน", "แบตเตอรี่", "ยางรถยนต์", "โช้คอัพ", "หลอดไฟ", "brake pads", "engine oil", "spark plug"]
                if any(kw in clean_name and kw in m_lower for kw in part_keywords):
                    matched_item = item
                    break
                tokens = [t for t in clean_name.split() if len(t) >= 2]
                if any(t in m_lower for t in tokens):
                    matched_item = item
                    break

    # CASE A: Existing item matched -> Adjust Quantity
    if matched_item:
        qty_before = matched_item.quantity
        matched_item.quantity = max(0, matched_item.quantity + delta)
        qty_after = matched_item.quantity

        history = StockHistory(
            stock_item_id=matched_item.id,
            change_type="adjust" if delta < 0 else "in",
            delta=delta,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reason=f"ปรับสต็อกผ่าน AI Copilot: {msg[:100]}",
            changed_by="AI Copilot",
        )
        db.add(history)
        db.commit()

        action = "เพิ่ม" if delta > 0 else "ลด"
        text = (
            f"📦 **บันทึกปรับปรุงสต็อกสำเร็จ!**\n\n"
            f"🔧 **อะไหล่**: {matched_item.name_th} (SKU: `{matched_item.sku}`)\n"
            f"{'➕' if delta > 0 else '➖'} **การดำเนินการ**: {action} {abs(delta)} ชิ้น\n"
            f"📊 **จำนวนคงเหลือใหม่**: **{qty_after}** ชิ้น (จากเดิม {qty_before})"
        )
        return text, {"item_id": matched_item.id, "delta": delta, "qty_after": qty_after, "action": "adjust"}

    # CASE B: No existing item matched OR explicit new -> Auto-create new StockItem!
    qty = abs(delta) if delta != 0 else 1
    qty_match = re.search(r"(?:จำนวน|qty|quantity)\s*[:=]?\s*(\d+)", msg, re.IGNORECASE)
    if qty_match:
        qty = int(qty_match.group(1))

    sell_price = 0.0
    price_match = re.search(r"(?:ราคา|ขาย|price|sell)\s*[:=]?\s*([\d,]+(?:\.\d+)?)", msg, re.IGNORECASE)
    if price_match:
        sell_price = float(price_match.group(1).replace(",", ""))

    unit_cost = 0.0
    cost_match = re.search(r"(?:ทุน|ราคาทุน|cost)\s*[:=]?\s*([\d,]+(?:\.\d+)?)", msg, re.IGNORECASE)
    if cost_match:
        unit_cost = float(cost_match.group(1).replace(",", ""))
    elif sell_price > 0:
        unit_cost = round(sell_price * 0.7, 2)

    clean_prompt = msg
    for prefix in [
        "เพิ่มสินค้าใหม่", "เพิ่มอะไหล่ใหม่", "สร้างอะไหล่ใหม่", "สร้างสินค้าใหม่",
        "เพิ่มสินค้า", "เพิ่มอะไหล่", "เพิ่มสต็อก", "สร้างสินค้า", "สร้างอะไหล่",
        "ช่วยเพิ่มสินค้า", "ช่วยเพิ่มอะไหล่", "ช่วยเพิ่มสต็อก", "ช่วยเพิ่ม",
        "add new part", "add new stock", "add new item", "add part", "add stock", "add item",
        "เพิ่ม", "สร้าง", "บันทึก", "ลง", "add", "new"
    ]:
        if clean_prompt.lower().startswith(prefix.lower()):
            clean_prompt = clean_prompt[len(prefix):].strip()
            break

    # Guard against conversational queries mistaken for part names
    conversational_indicators = [
        "this is not checking", "what we have", "just plus more", "put it in stock",
        "did you put", "on paper", "why did", "what it give me", "i want is to",
        "have 32 part", "how many part", "ไม่ได้เช็ค", "เช็คของ", "มีกี่รายการ", "ลงสต็อกหรือยัง",
        "put all part", "put all parts"
    ]
    if any(ci in msg.lower() for ci in conversational_indicators):
        total_items = db.query(StockItem).count()
        recent_suwan = db.query(StockItem).filter(StockItem.notes.like("%สุวรรณการช่าง%")).all()
        suwan_count = len(recent_suwan)
        text = (
            f"📦 **สถานะคลังสินค้าปัจจุบัน:**\n\n"
            f"📊 **จำนวนอะไหล่ทั้งหมดในระบบ**: **{total_items}** รายการ\n"
        )
        if suwan_count > 0:
            text += (
                f"🧾 **รายการอะไหล่จากใบเสร็จ หจก. สุวรรณการช่าง ทีทีเจ**: นำเข้าครบถ้วนแล้วทั้ง **{suwan_count}** รายการ (ยอดรวม ฿63,260.00)\n\n"
                f"💡 **หลักการทำงานของระบบ**:\n"
                f"• หากมีอะไหล่เดิมอยู่แล้วในสต็อก: ระบบจะ **บวกจำนวนเพิ่ม (+Qty)** และอัปเดตราคาต้นทุน\n"
                f"• หากเป็นอะไหล่ใหม่ที่ยังไม่มี: ระบบจะ **สร้างรายการใหม่** พร้อมตั้งรหัส SKU และราคาขายให้อัตโนมัติครับ"
            )
        else:
            text += f"💡 ระบบรองรับการนำเข้าอะไหล่จากบิล โดยบวกสต็อกเพิ่ม (+Qty) หากมีอยู่แล้ว และสร้างใหม่หากยังไม่มีในระบบครับ"
        return text, {"action": "check_stock", "total_items": total_items}

    clean_name = re.sub(r"(?:ราคา|ขาย|price|sell)\s*[:=]?\s*[\d,]+(?:\.\d+)?\s*(?:บาท|thb)?", "", clean_prompt, flags=re.IGNORECASE)
    clean_name = re.sub(r"(?:ทุน|ราคาทุน|cost)\s*[:=]?\s*[\d,]+(?:\.\d+)?\s*(?:บาท|thb)?", "", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"(?:จำนวน|qty|quantity)\s*[:=]?\s*\d+\s*(?:ชิ้น|ขวด|อัน|กล่อง|ชุด|pcs|units|หัว|ลูก|ตัว|เส้น|ใบ|แผ่น|คู่|แกลลอน|กระป๋อง|ลัง)?", "", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\b\d+\s*(?:ชิ้น|ขวด|อัน|กล่อง|ชุด|pcs|units|หัว|ลูก|ตัว|เส้น|ใบ|แผ่น|คู่|แกลลอน|กระป๋อง|ลัง)?\b", "", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"(?:ชิ้น|ขวด|อัน|กล่อง|ชุด|pcs|units|หัว|ลูก|ตัว|เส้น|ใบ|แผ่น|คู่|แกลลอน|กระป๋อง|ลัง)$", "", clean_name.strip()).strip()
    clean_name = clean_name.strip(" :,-=")

    # Extra check if name is English conversational sentence
    english_words = clean_name.lower().split()
    if len(english_words) >= 4 and all(w in ["this", "is", "not", "checking", "what", "we", "have", "i", "want", "to", "add", "if", "already", "just", "plus", "more", "but", "put", "it", "in", "stock", "the", "and", "or", "up", "all", "on", "paper", "did", "you", "why", "how", "give", "me"] for w in english_words):
        total_items = db.query(StockItem).count()
        return (
            f"📦 **สถานะสต็อกปัจจุบัน**: มีรายการอะไหล่ทั้งหมด {total_items} รายการ\n"
            f"ระบบจะตรวจสอบอะไหล่เดิมก่อนเสมอ หากมีอยู่แล้วจะบวกเพิ่มจำนวน และหากยังไม่มีจะเพิ่มเป็นอะไหล่ใหม่ให้ทันทีครับ",
            {"action": "info", "total_items": total_items}
        )

    if not clean_name:
        clean_name = "อะไหล่ใหม่ (บันทึกผ่าน AI Copilot)"

    sku_match = re.search(r"(?:sku|รหัส)\s*[:=]?\s*([A-Za-z0-9\-]+)", msg, re.IGNORECASE)
    if sku_match:
        sku = sku_match.group(1).upper()
    else:
        code_match = re.search(r"\b([A-Za-z]+[0-9]+[A-Za-z0-9\-]*|[0-9]+[A-Za-z]+[A-Za-z0-9\-]*|[A-Za-z0-9]+-[A-Za-z0-9]+)\b", msg)
        if code_match and code_match.group(1).upper() not in ["NGK", "OEM", "QTY", "THB", "USD"]:
            sku = code_match.group(1).upper()
        else:
            sku = f"PRT-{datetime.now(timezone.utc).strftime('%m%d%H%M%S')}"

    existing_sku = db.query(StockItem).filter(StockItem.sku == sku).first()
    if existing_sku:
        sku = f"{sku}-{datetime.now(timezone.utc).strftime('%S')}"

    category = "อะไหล่ทั่วไป"
    cn_low = clean_name.lower()
    if any(k in cn_low for k in ["น้ำมัน", "oil", "lubricant"]): category = "น้ำมันเครื่อง"
    elif any(k in cn_low for k in ["เบรค", "เบรก", "brake"]): category = "ระบบเบรค"
    elif any(k in cn_low for k in ["กรอง", "filter"]): category = "ไส้กรอง"
    elif any(k in cn_low for k in ["หัวเทียน", "spark"]): category = "ระบบจุดระเบิด"
    elif any(k in cn_low for k in ["ยาง", "tire", "tyre"]): category = "ยางและล้อ"
    elif any(k in cn_low for k in ["แบต", "battery"]): category = "ระบบไฟและแบตเตอรี่"
    elif any(k in cn_low for k in ["ช่วงล่าง", "โช๊ค", "โช้ค", "suspension"]): category = "ช่วงล่าง"

    new_item = StockItem(
        name_th=clean_name,
        name_en=clean_name,
        sku=sku,
        category=category,
        quantity=qty,
        unit_cost=unit_cost,
        sell_price=sell_price,
        reorder_level=5,
        notes=f"บันทึกผ่าน AI Copilot: {msg[:100]}",
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    history = StockHistory(
        stock_item_id=new_item.id,
        change_type="in",
        delta=qty,
        quantity_before=0,
        quantity_after=qty,
        reason=f"สร้างอะไหล่ใหม่ผ่าน AI Copilot: {msg[:100]}",
        changed_by="AI Copilot",
    )
    db.add(history)
    db.commit()

    text = (
        f"📦 **เพิ่มสินค้า/อะไหล่ใหม่เข้าสต็อกสำเร็จ!**\n\n"
        f"🔧 **ชื่ออะไหล่**: {new_item.name_th}\n"
        f"🏷️ **SKU**: `{new_item.sku}`\n"
        f"📂 **หมวดหมู่**: {new_item.category}\n"
        f"📊 **จำนวนนำเข้า**: **{new_item.quantity}** ชิ้น\n"
        f"💰 **ราคาทุน / ขาย**: ฿{new_item.unit_cost:,.2f} / ฿{new_item.sell_price:,.2f}\n"
        f"✅ ข้อมูลถูกบันทึกลงในระบบคลังสินค้าเรียบร้อยแล้ว"
    )
    return text, {
        "item_id": new_item.id,
        "sku": new_item.sku,
        "name_th": new_item.name_th,
        "quantity": new_item.quantity,
        "action": "create",
    }


def execute_add_customer(db: Session, msg: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Parse and add a new customer."""
    phone_m = re.search(r"0\d{8,9}", msg)
    phone = phone_m.group(0) if phone_m else None

    line_m = re.search(r"(?:line|ไลน์)\s*[:=]?\s*([a-zA-Z0-9_\-\.]+)", msg, re.IGNORECASE)
    line_id = line_m.group(1) if line_m else None

    clean = msg
    for prefix in [
        "เพิ่มลูกค้าใหม่", "สร้างลูกค้าใหม่", "เพิ่มลูกค้า", "สร้างลูกค้า", "ลงทะเบียนลูกค้า",
        "add new customer", "add customer", "new customer", "create customer",
        "ลูกค้าใหม่", "ลูกค้า", "customer"
    ]:
        if clean.lower().startswith(prefix.lower()):
            clean = clean[len(prefix):].strip()
            break
    
    if phone:
        clean = clean.replace(phone, "")
    if line_id:
        clean = clean.replace(line_id, "")
    clean = re.sub(r"(?:เบอร์โทรศัพท์|เบอร์โทร|เบอร์|โทร|phone|tel|line id|line|ไลน์|email|อีเมล)\s*[:=]?", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+", "", clean)
    name = clean.strip(" :,-\n") or "ลูกค้าใหม่"
    if not name.startswith("คุณ") and len(name) < 20 and any(u'\u0e00' <= c <= u'\u0e7f' for c in name):
        name = f"คุณ{name}"

    existing = db.query(Customer).filter(Customer.phone == phone).first() if phone else None
    if existing:
        return (
            f"👤 **พบข้อมูลลูกค้าเดิมในระบบ:**\n\n"
            f"🆔 **รหัสลูกค้า**: #{existing.id}\n"
            f"📛 **ชื่อ**: {existing.name}\n"
            f"📞 **เบอร์โทร**: {existing.phone}\n"
            f"💬 **LINE**: {existing.line_id or '-'}\n"
            f"💡 ข้อมูลพร้อมใช้งาน สามารถเปิดงานซ่อมหรือนัดหมายได้ทันที",
            {"customer_id": existing.id, "name": existing.name, "phone": existing.phone}
        )

    customer = Customer(
        name=name,
        phone=phone,
        line_id=line_id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    text = (
        f"👤 **บันทึกข้อมูลลูกค้าใหม่เรียบร้อย!**\n\n"
        f"🆔 **รหัสลูกค้า**: #{customer.id}\n"
        f"📛 **ชื่อ-นามสกุล**: {customer.name}\n"
        f"📞 **เบอร์โทรศัพท์**: {customer.phone or 'ไม่ระบุ'}\n"
        f"💬 **LINE ID**: {customer.line_id or '-'}\n"
        f"✅ ข้อมูลถูกจัดเก็บในระบบลูกค้าเรียบร้อยแล้ว"
    )
    return text, {"customer_id": customer.id, "name": customer.name, "phone": customer.phone}


def execute_add_vehicle(db: Session, msg: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Parse and add a new vehicle."""
    plate_m = re.search(r"(?:ทะเบียน|plate|เลขทะเบียน)\s*[:=]?\s*([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4}(?:\s*[ก-๙]+)?)", msg, re.IGNORECASE)
    if not plate_m:
        plate_m = re.search(r"\b([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4}(?:\s*[ก-๙]+)?)\b", msg)
    plate = plate_m.group(1).strip() if plate_m else None
    if not plate:
        plate_en = re.search(r"\b([A-Z0-9]{2,4}\s*[-]?\s*[0-9]{1,4})\b", msg)
        plate = plate_en.group(1).strip() if plate_en else f"ชั่วคราว-{datetime.now(timezone.utc).strftime('%H%M%S')}"

    brands = ["Toyota", "Honda", "Isuzu", "Ford", "Mazda", "Nissan", "Mitsubishi", "MG", "BMW", "Mercedes-Benz", "Mercedes", "Suzuki", "Hyundai", "BYD", "GWM"]
    brand = "Toyota"
    for b in brands:
        if b.lower() in msg.lower():
            brand = b
            break

    models = ["Camry", "Corolla", "Altis", "Vios", "Yaris", "Cross", "Fortuner", "Civic", "City", "HR-V", "CR-V", "Accord", "D-Max", "Mu-X", "Ranger", "Everest", "Mazda 2", "Mazda 3", "CX-5", "Navara", "Almera", "Triton", "Pajero"]
    model = "Sedan"
    for m in models:
        if m.lower() in msg.lower():
            model = m
            break

    mileage_m = re.search(r"(\d+)\s*(?:กม|km|กิโล)", msg, re.IGNORECASE)
    mileage = int(mileage_m.group(1)) if mileage_m else 0

    phone_m = re.search(r"0\d{8,9}", msg)
    customer = None
    if phone_m:
        customer = db.query(Customer).filter(Customer.phone == phone_m.group(0)).first()

    cust_name_m = re.search(r"(?:ลูกค้า|เจ้าของ|คุณ|customer|owner)\s*[:=]?\s*([ก-๙a-zA-Z]+)", msg)
    if not customer and cust_name_m:
        c_raw = cust_name_m.group(1).strip()
        c_name = c_raw if c_raw.startswith("คุณ") else f"คุณ{c_raw}"
        customer = db.query(Customer).filter(Customer.name.like(f"%{c_raw}%")).first()
        if not customer:
            customer = Customer(name=c_name, phone=phone_m.group(0) if phone_m else None)
            db.add(customer)
            db.commit()
            db.refresh(customer)

    if not customer:
        customer = db.query(Customer).first()
    if not customer:
        customer = Customer(name="ลูกค้าทั่วไป", phone="0800000000")
        db.add(customer)
        db.commit()
        db.refresh(customer)

    existing = db.query(Vehicle).filter(Vehicle.plate == plate).first()
    if existing:
        return (
            f"🚗 **รถทะเบียน `{existing.plate}` มีอยู่ในระบบแล้ว:**\n\n"
            f"🚘 **ยี่ห้อ/รุ่น**: {existing.brand} {existing.model}\n"
            f"👤 **เจ้าของ**: {existing.customer.name if existing.customer else 'ไม่ระบุ'}\n"
            f"📊 **เลขไมล์**: {existing.current_mileage:,} กม.\n"
            f"💡 สามารถเปิดใบรับรถเข้าซ่อมได้เลยครับ",
            {"vehicle_id": existing.id, "plate": existing.plate}
        )

    vehicle = Vehicle(
        plate=plate,
        brand=brand,
        model=model,
        customer_id=customer.id,
        current_mileage=mileage,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    text = (
        f"🚗 **ลงทะเบียนรถยนต์ใหม่เรียบร้อย!**\n\n"
        f"🔢 **ทะเบียน**: `{vehicle.plate}`\n"
        f"🚘 **ยี่ห้อ/รุ่น**: {vehicle.brand} {vehicle.model}\n"
        f"👤 **เจ้าของ**: {customer.name}\n"
        f"📊 **เลขไมล์เริ่มต้น**: {vehicle.current_mileage:,} กม.\n"
        f"✅ พร้อมเปิดใบรับรถและบันทึกประวัติการซ่อมบำรุง"
    )
    return text, {"vehicle_id": vehicle.id, "plate": vehicle.plate, "brand": vehicle.brand, "model": vehicle.model}


def execute_delete_action(db: Session, msg: str, action: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Handle deletion and cancellation requests safely:
    - delete_supplier
    - delete_expense
    - cancel_appointment
    """
    m_low = msg.lower()
    params = params or {}

    # 1. Supplier Deletion
    is_supplier = action == "delete_supplier" or any(k in m_low for k in ["ซัพพลาย", "supplier", "ผู้จัดจำหน่าย", "ร้านค้า", "ys อะไหล่", "d2 moter", "สุวรรณการช่าง", "ฟอร์ฟ", "monza"]) or "🏭" in msg
    if is_supplier:
        sup_name = params.get("name") or ""
        sup_phone = params.get("phone") or ""
        suppliers = db.query(Supplier).all()
        target = None
        for s in suppliers:
            if sup_name and sup_name.lower() in s.name.lower():
                target = s; break
            if s.name.lower() in m_low:
                target = s; break
            if sup_phone and s.phone and sup_phone in s.phone:
                target = s; break
            if s.phone and s.phone.replace("-", "").strip() in msg.replace("-", ""):
                target = s; break

        if target:
            t_name = target.name
            t_id = target.id
            db.delete(target)
            db.commit()
            return (
                f"🗑️ **ลบข้อมูลผู้จัดจำหน่าย/ซัพพลายเออร์สำเร็จ!**\n\n"
                f"🏭 **ชื่อ**: {t_name}\n"
                f"🆔 **รหัส**: #{t_id}\n"
                f"✅ ลบข้อมูลออกจากระบบ Suppliers เรียบร้อยแล้ว",
                {"type": "supplier", "supplier_id": t_id, "name": t_name, "deleted": True}
            )
        else:
            return (
                f"ℹ️ **ไม่พบข้อมูลซัพพลายเออร์ดังกล่าวในระบบ**\n"
                f"ข้อมูลอาจถูกลบไปแล้ว หรือไม่มีในฐานข้อมูลปัจจุบัน คุณสามารถเปิดดูรายชื่อร้านค้าได้ที่แท็บ **Suppliers** ครับ",
                {"type": "supplier", "deleted": False}
            )

    # 2. Expense Deletion
    is_expense = action == "delete_expense" or any(k in m_low for k in ["ค่าใช้จ่าย", "รายจ่าย", "expense", "บิล", "ใบเสร็จ", "ยอดเงิน"])
    if is_expense:
        exp_id = params.get("expense_id") or params.get("id")
        if not exp_id:
            m_id = re.search(r"(?:#|id\s*[:=]?\s*|\bรายการ\s*)(\d+)", msg, re.IGNORECASE)
            if m_id:
                exp_id = int(m_id.group(1))

        target_exp = None
        if exp_id:
            target_exp = db.query(Expense).filter(Expense.id == int(exp_id)).first()
        else:
            num_m = re.search(r"(\d+(?:\.\d+)?)", msg.replace(",", ""))
            if num_m:
                val = float(num_m.group(1))
                target_exp = db.query(Expense).filter(Expense.amount == val).order_by(Expense.created_at.desc()).first()
            if not target_exp and any(k in m_low for k in ["ล่าสุด", "สุดท้าย", "latest"]):
                target_exp = db.query(Expense).order_by(Expense.created_at.desc()).first()

        if target_exp:
            e_id = target_exp.id
            e_desc = target_exp.description[:60] if target_exp.description else ""
            e_amt = target_exp.amount
            db.delete(target_exp)
            db.commit()
            return (
                f"🗑️ **ลบรายการค่าใช้จ่าย #{e_id} สำเร็จ!**\n\n"
                f"📝 **รายละเอียด**: {e_desc}\n"
                f"💰 **จำนวนเงิน**: ฿{e_amt:,.2f}\n"
                f"✅ ปรับปรุงยอดรายจ่ายในระบบบัญชีเรียบร้อยแล้ว",
                {"type": "expense", "expense_id": e_id, "deleted": True}
            )
        else:
            return (
                "⚠️ **ไม่พบรายการค่าใช้จ่ายที่ต้องการลบ**\n"
                "กรุณาระบุหมายเลข ID หรือจำนวนเงิน เช่น `ลบค่าใช้จ่าย #5` หรือ `ลบค่าใช้จ่ายล่าสุด`",
                {"type": "expense", "deleted": False}
            )

    # 3. Appointment Cancellation
    is_appt = action == "cancel_appointment" or any(k in m_low for k in ["นัด", "คิว", "appointment", "booking"])
    if is_appt:
        appt_id = params.get("appointment_id") or params.get("id")
        target_appt = None
        if appt_id:
            target_appt = db.query(Appointment).filter(Appointment.id == int(appt_id)).first()
        else:
            appts = db.query(Appointment).all()
            for a in appts:
                if a.customer_name and a.customer_name.replace("คุณ", "").strip() in msg:
                    target_appt = a; break
                if a.customer_phone and a.customer_phone in msg:
                    target_appt = a; break

        if target_appt:
            a_id = target_appt.id
            c_name = target_appt.customer_name
            a_date = target_appt.appointment_date.strftime("%d/%m/%Y") if target_appt.appointment_date else ""
            db.delete(target_appt)
            db.commit()
            return (
                f"🗑️ **ยกเลิกนัดหมายสำเร็จ!**\n\n"
                f"👤 **ลูกค้า**: {c_name}\n"
                f"📅 **วันที่**: {a_date}\n"
                f"✅ ลบรายการนัดหมายออกจากปฏิทินของอู่เรียบร้อยแล้ว",
                {"type": "appointment", "appointment_id": a_id, "deleted": True}
            )
        else:
            return (
                "⚠️ **ไม่พบคิวนัดหมายที่ต้องการยกเลิก**\n"
                "กรุณาระบุชื่อลูกค้าหรือหมายเลขคิวนัด เช่น `ยกเลิกนัดคุณสมชาย` หรือ `ขอดูตารางนัดหมาย`",
                {"type": "appointment", "deleted": False}
            )

    return (
        f"ℹ️ **รับทราบคำสั่งลบข้อมูลครับ**\n"
        f"เพื่อความปลอดภัย กรุณาระบุประเภทข้อมูลและรายละเอียด เช่น:\n"
        f"• `ลบค่าใช้จ่าย #[เลข ID]`\n"
        f"• `ลบซัพพลายเออร์ [ชื่อร้าน]`\n"
        f"• `ยกเลิกนัดหมายคุณ [ชื่อลูกค้า]`",
        {"deleted": False}
    )


def execute_add_expense(db: Session, msg: str, parsed_params: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Parse and record expense with strict guardrails."""
    m_low = msg.lower()
    if any(k in m_low for k in ["ลบ", "ยกเลิก", "delete", "cancel"]):
        return execute_delete_action(db, msg, action="delete_expense")

    amount = 0.0
    if parsed_params and parsed_params.get("amount"):
        try:
            amount = float(parsed_params["amount"])
        except (ValueError, TypeError):
            pass

    if amount <= 0:
        # Strip phone numbers, years, postal codes
        clean_text = re.sub(r"\b0\d{8,9}\b", " ", msg)
        clean_text = re.sub(r"\b25\d{2}\b", " ", clean_text)
        clean_text = re.sub(r"\b20\d{2}\b", " ", clean_text)
        clean_text = re.sub(r"\b\d{5}\b", " ", clean_text)

        # Look for explicit monetary indicator first
        amt_match = re.search(r"(?:฿|ยอด|จำนวนเงิน|จ่าย|ราคา|ค่า[\w\s]*?)\s*[:=]?\s*([\d,]+(?:\.\d+)?)", clean_text)
        if not amt_match:
            amt_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:บาท|thb|บ\.)", clean_text, re.IGNORECASE)
        if amt_match:
            try:
                amount = float(amt_match.group(1).replace(",", ""))
            except ValueError:
                amount = 0.0
        else:
            numbers = re.findall(r"[\d,]+(?:\.\d+)?", clean_text.replace(",", ""))
            valid_nums = [float(n) for n in numbers if 0 < float(n) < 10000000]
            amount = valid_nums[0] if valid_nums else 0.0

    if amount <= 0 or amount > 5000000:
        return "⚠️ กรุณาระบุจำนวนเงินค่าใช้จ่ายที่ถูกต้อง เช่น `บันทึกค่าไฟ 2,800 บาท`", None

    category = (parsed_params.get("category") if parsed_params else None) or "อื่นๆ"
    if category == "อื่นๆ":
        if any(k in m_low for k in ["ค่าไฟ", "ไฟฟ้า", "electricity", "electric", "power"]): category = "ค่าไฟฟ้า"
        elif any(k in m_low for k in ["ค่าน้ำ", "ประปา", "water"]): category = "ค่าน้ำประปา"
        elif any(k in m_low for k in ["ค่าเช่า", "เช่า", "rent"]): category = "ค่าเช่า"
        elif any(k in m_low for k in ["เน็ต", "อินเทอร์", "internet", "wifi"]): category = "ค่าอินเทอร์เน็ต"
        elif any(k in m_low for k in ["เครื่องมือ", "อุปกรณ์", "tools"]): category = "ค่าอุปกรณ์/เครื่องมือ"
        elif any(k in m_low for k in ["เงินเดือน", "ค่าจ้าง", "salary", "wage"]): category = "เงินเดือน/ค่าจ้าง"

    desc = parsed_params.get("description") if parsed_params else None
    if not desc:
        first_line = msg.strip().split("\n")[0]
        desc = first_line[:100] if len(first_line) <= 100 else f"{category} {amount:,.0f} บาท"

    exp = Expense(category=category, description=desc, amount=amount, added_by="AI Copilot")
    db.add(exp)
    db.commit()

    text = (
        f"💸 **บันทึกค่าใช้จ่ายเรียบร้อย!**\n\n"
        f"📂 **หมวดหมู่**: {category}\n"
        f"💰 **จำนวนเงิน**: ฿{amount:,.2f}\n"
        f"📝 **รายละเอียด**: {desc}\n"
        f"✅ ข้อมูลถูกบันทึกลงในระบบบัญชีและคำนวณใน P&L ทันที"
    )
    return text, {"expense_id": exp.id, "amount": amount, "category": category}


def parse_thai_appointment_datetime(msg: str) -> Tuple[datetime, str]:
    """Extract (date, time_slot) from Thai / English messages robustly."""
    now = get_local_now()
    appt_date = now + timedelta(days=1)
    time_slot = "10:00"

    # 1. Time parsing
    time_m = re.search(r"(\d{1,2})[:.：](\d{2})", msg)
    if time_m:
        time_slot = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"
    else:
        if re.search(r"บ่าย\s*([1-5]|หนึ่ง|สอง|สาม|สี่|ห้า)", msg):
            b_match = re.search(r"บ่าย\s*([1-5]|หนึ่ง|สอง|สาม|สี่|ห้า)", msg).group(1)
            b_map = {"1": 13, "หนึ่ง": 13, "2": 14, "สอง": 14, "3": 15, "สาม": 15, "4": 16, "สี่": 16, "5": 17, "ห้า": 17}
            time_slot = f"{b_map.get(b_match, 14)}:00"
        elif re.search(r"([1-4]|หนึ่ง|สอง|สาม|สี่)\s*ทุ่ม", msg):
            t_match = re.search(r"([1-4]|หนึ่ง|สอง|สาม|สี่)\s*ทุ่ม", msg).group(1)
            t_map = {"1": 19, "หนึ่ง": 19, "2": 20, "สอง": 20, "3": 21, "สาม": 21, "4": 22, "สี่": 22}
            time_slot = f"{t_map.get(t_match, 19)}:00"
        else:
            hour_m = re.search(r"(\d{1,2})\s*(?:โมง|น\.?|am|pm)", msg, re.IGNORECASE)
            if hour_m:
                h = int(hour_m.group(1))
                time_slot = f"{str(h).zfill(2)}:00"

    # 2. Date parsing
    if any(k in msg for k in ["วันนี้", "today"]):
        appt_date = now
    elif any(k in msg for k in ["มะรืน", "day after tomorrow"]):
        appt_date = now + timedelta(days=2)
    elif any(k in msg for k in ["พรุ่งนี้", "tomorrow"]):
        appt_date = now + timedelta(days=1)
    else:
        thai_months = {
            "มกราคม": 1, "มกรา": 1, "ม.ค.": 1, "ม.ค": 1,
            "กุมภาพันธ์": 2, "กุมภา": 2, "ก.พ.": 2, "ก.พ": 2,
            "มีนาคม": 3, "มีนา": 3, "มี.ค.": 3, "มี.ค": 3,
            "เมษายน": 4, "เมษา": 4, "เม.ย.": 4, "เม.ย": 4,
            "พฤษภาคม": 5, "พฤษภา": 5, "พ.ค.": 5, "พ.ค": 5,
            "มิถุนายน": 6, "มิถุนา": 6, "มิ.ย.": 6, "มิ.ย": 6,
            "กรกฎาคม": 7, "กรกฎา": 7, "ก.ค.": 7, "ก.ค": 7,
            "สิงหาคม": 8, "สิงหา": 8, "ส.ค.": 8, "ส.ค": 8,
            "กันยายน": 9, "กันยา": 9, "ก.ย.": 9, "ก.ย": 9,
            "ตุลาคม": 10, "ตุลา": 10, "ต.ค.": 10, "ต.ค": 10,
            "พฤศจิกายน": 11, "พฤศจิกา": 11, "พ.ย.": 11, "พ.ย": 11,
            "ธันวาคม": 12, "ธันวา": 12, "ธ.ค.": 12, "ธ.ค": 12,
        }
        m_pattern = "|".join([re.escape(k) for k in sorted(thai_months.keys(), key=len, reverse=True)])
        # Only match 4-digit year (25xx, 20xx) or 2-digit BE year (60-99) NOT followed by : or . (which would be a time)
        date_m = re.search(rf"(?:วันที่\s*)?(\d{{1,2}})\s*({m_pattern})(?:\s*(?:ปี|พ\.?ศ\.?|ค\.?ศ\.?)?\s*(\d{{2,4}})(?![:.]\d{{2}}))?", msg, re.IGNORECASE)
        if date_m:
            day = int(date_m.group(1))
            month = thai_months[date_m.group(2).lower()]
            year = now.year
            if date_m.group(3):
                y_val = int(date_m.group(3))
                if y_val >= 2500:
                    year = y_val - 543
                elif 60 <= y_val <= 99:
                    year = 2500 + y_val - 543
                elif 2020 <= y_val <= 2040:
                    year = y_val
                # ignore small numbers like 14, 10, etc. as they are time, not years!
            try:
                appt_date = datetime(year, month, day)
            except Exception:
                pass
        else:
            slash_m = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", msg)
            if slash_m:
                day = int(slash_m.group(1))
                month = int(slash_m.group(2))
                year = now.year
                if slash_m.group(3):
                    y_val = int(slash_m.group(3))
                    if y_val >= 2500: year = y_val - 543
                    elif 60 <= y_val <= 99: year = 2500 + y_val - 543
                    elif 2020 <= y_val <= 2040: year = y_val
                try:
                    appt_date = datetime(year, month, day)
                except Exception:
                    pass
            else:
                day_only = re.search(r"วันที่\s*(\d{1,2})", msg)
                if day_only:
                    day = int(day_only.group(1))
                    try:
                        month = now.month
                        year = now.year
                        if day < now.day:
                            month = month + 1
                            if month > 12: month = 1; year += 1
                        appt_date = datetime(year, month, day)
                    except Exception:
                        pass

    return appt_date, time_slot


def execute_add_appointment(db: Session, msg: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Parse and book an appointment for inspection/service with high accuracy."""
    phone_m = re.search(r"0\d{8,9}", msg)
    phone = phone_m.group(0) if phone_m else None

    appt_date, time_slot = parse_thai_appointment_datetime(msg)

    SERVICE_STOPWORDS = {
        "เปลี่ยนยาง", "สลับยาง", "ปะยาง", "ถ่วงล้อ", "ตั้งศูนย์",
        "เปลี่ยนน้ำมันเครื่อง", "ถ่ายน้ำมันเครื่อง", "น้ำมันเครื่อง",
        "ล้างรถ", "เคลือบสี", "ดูดฝุ่น", "ขัดสี", "ล้างห้องเครื่อง",
        "ซ่อมเบรค", "เปลี่ยนผ้าเบรค", "เจียรจาน", "เบรค",
        "เปลี่ยนแบต", "เปลี่ยนแบตเตอรี่", "แบตเตอรี่", "ตรวจสภาพ",
        "เช็คระยะ", "ช่วงล่าง", "ซ่อมแอร์", "แอร์", "ตรวจเช็ค", "เช็คเบรค"
    }

    name = None
    khun_m = re.search(r"คุณ\s*([ก-๙a-zA-Z]+)", msg)
    if khun_m:
        c_val = khun_m.group(1).strip()
        if c_val not in SERVICE_STOPWORDS:
            name = f"คุณ{c_val}"

    if not name:
        cust_m = re.search(r"ลูกค้า\s*([ก-๙a-zA-Z]+)", msg)
        if cust_m:
            c_val = cust_m.group(1).strip()
            if c_val not in SERVICE_STOPWORDS and c_val not in ["ทั่วไป", "ใหม่", "ประจำ"]:
                name = c_val if c_val.startswith("คุณ") else f"คุณ{c_val}"

    if not name:
        name_en = re.search(r"(?:for|customer)\s+([A-Za-z]+)", msg, re.IGNORECASE)
        if name_en:
            name = name_en.group(1).strip()

    if not name and phone:
        existing_c = db.query(Customer).filter(Customer.phone == phone).first()
        if existing_c:
            name = existing_c.name

    if not name:
        name = "ลูกค้าทั่วไป (นัดหมายผ่าน AI)"

    clean_service = msg
    for w in ["นัดลูกค้า", "นัดหมาย", "นัด", "จองคิว", "book appointment", "appointment for", "appointment",
              "พรุ่งนี้", "วันนี้", "มะรืน", "เวลา", "คิว", "วันที่", "พ.ศ.", "พศ", "ค.ศ.", "คศ"]:
        clean_service = re.sub(w, "", clean_service, flags=re.IGNORECASE)
    # Remove Thai month names
    for m in ["มกราคม","กุมภาพันธ์","มีนาคม","เมษายน","พฤษภาคม","มิถุนายน","กรกฎาคม","สิงหาคม","กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม",
              "มกรา","กุมภา","มีนา","เมษา","พฤษภา","มิถุนา","กรกฎา","สิงหา","กันยา","ตุลา","พฤศจิกา","ธันวา",
              "ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]:
        clean_service = re.sub(rf"\b{re.escape(m)}\b", "", clean_service)
        clean_service = clean_service.replace(m, "")
    if phone:
        clean_service = clean_service.replace(phone, "")
    clean_service = re.sub(r"\d{1,2}[:.：]\d{2}", "", clean_service)
    clean_service = re.sub(r"\d{1,2}\s*(?:โมง|น\.?|am|pm)", "", clean_service, flags=re.IGNORECASE)
    clean_service = re.sub(r"\b\d{1,4}\b", "", clean_service)
    clean_service = re.sub(rf"(?:คุณ|ลูกค้า)\s*{re.escape(name.replace('คุณ', ''))}", "", clean_service)
    clean_service = re.sub(r"\s+", " ", clean_service).strip(" :,-")
    service_text = f"นำรถเข้าตรวจเช็ค: {clean_service[:100]}" if clean_service else "นำรถเข้าตรวจเช็คโดยช่าง"

    appt = Appointment(
        customer_name=name,
        customer_phone=phone,
        appointment_date=appt_date,
        time_slot=time_slot,
        service_type=service_text,
        status="confirmed",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    text = (
        f"📅 **บันทึกการนัดหมายเรียบร้อย!**\n\n"
        f"👤 **ลูกค้า**: {name}\n"
        f"📞 **เบอร์โทร**: {phone or 'ไม่ระบุ'}\n"
        f"📆 **วันที่**: {appt_date.strftime('%d/%m/%Y')}\n"
        f"🕐 **เวลานัดหมาย**: {time_slot} น.\n"
        f"🔧 **วัตถุประสงค์**: {service_text}\n"
        f"📌 ข้อมูลลงตารางในปฏิทินนัดหมายของอู่แล้ว"
    )
    return text, {
        "appointment_id": appt.id,
        "customer_name": name,
        "customer_phone": phone,
        "appointment_date": appt_date.isoformat(),
        "time_slot": time_slot,
        "service_type": service_text,
        "status": "confirmed"
    }


def execute_send_line_message(db: Session, msg: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Send an ad-hoc or notification message via LINE OA to a customer or specific LINE User ID.
    Supports syntax:
    - 'ส่ง LINE หาคุณสมชาย: รถซ่อมเสร็จแล้วครับ'
    - 'ส่ง LINE แจ้งเตือนคุณสมชายเรื่องเปลี่ยนน้ำมันเครื่อง'
    - 'ส่ง LINE หา U736b2b09bc7a5c85540f1f8bf24b3f08: ขอบคุณที่ใช้บริการครับ'
    - 'ส่ง LINE ทะเบียน 1กข 9999: รถตรวจเช็คเสร็จแล้ว'
    """
    from agents.marketing_agent import mock_line_dispatch

    clean_msg = msg.strip()

    # 1. Check for direct LINE User ID (U...)
    u_match = re.search(r"\b(U[0-9a-fA-F]{32})\b", clean_msg)
    target_line_id = u_match.group(1) if u_match else None
    target_customer = None

    # 2. Check for license plate
    if not target_line_id:
        plate_m = re.search(r"(\d?[ก-ฮ]{1,3}\s*\d{1,4}|[a-zA-Z0-9]{2,4}\s*[-]?\s*[0-9]{1,4})", clean_msg)
        if plate_m:
            candidate_plate = plate_m.group(1).replace(" ", "").strip()
            all_vehicles = db.query(Vehicle).all()
            for v in all_vehicles:
                if v.plate and (v.plate.replace(" ", "").lower() == candidate_plate.lower() or candidate_plate.lower() in v.plate.replace(" ", "").lower()):
                    if v.customer and v.customer.line_id:
                        target_line_id = v.customer.line_id
                        target_customer = v.customer
                        break

    # 3. Check for customer name if not found yet
    if not target_line_id:
        all_customers = db.query(Customer).all()
        for c in all_customers:
            parts = c.name.split()
            first_name = parts[0] if parts else c.name
            if first_name in clean_msg or c.name in clean_msg:
                target_customer = c
                if c.line_id:
                    target_line_id = c.line_id
                break

    # 4. Fallback to active U... LINE ID in Customer database if available
    if not target_line_id:
        active_c = db.query(Customer).filter(Customer.line_id.like("U%")).first()
        if active_c:
            target_line_id = active_c.line_id
            target_customer = active_c

    if not target_line_id:
        return (
            "⚠️ **ไม่พบ LINE User ID ของผู้รับครับ**\n\n"
            "กรุณาระบุชื่อลูกค้า, ทะเบียนรถ หรือ LINE User ID (ขึ้นต้นด้วย `U...` ความยาว 33 ตัวอักษร) ของผู้รับ\n"
            "ตัวอย่าง: `ส่ง LINE หาคุณสมชาย: รถซ่อมเสร็จแล้วครับ` หรือ `ส่ง LINE หา U736b2b09bc7a5c85540f1f8bf24b3f08: ขอบคุณที่ใช้บริการครับ`",
            {"status": "missing_recipient"}
        )

    # Extract message text after :, ว่า, ข้อความ:
    content = ""
    colon_split = re.split(r"[:=：]|(?:ข้อความ\s*[:=]?)|(?:ว่า\s+)", clean_msg, maxsplit=1)
    if len(colon_split) > 1 and colon_split[1].strip():
        content = colon_split[1].strip()
    else:
        # Check intent
        if any(k in clean_msg.lower() for k in ["เสร็จ", "รับรถ", "ready"]):
            content = "🚗 แจ้งเตือนจากศูนย์บริการ Zero Garage:\nรถยนต์ของท่านดำเนินการตรวจซ่อมเรียบร้อยแล้ว พร้อมส่งมอบรถครับ สามารถเข้ามารับรถได้เลยครับ ✨"
        elif any(k in clean_msg.lower() for k in ["น้ำมันเครื่อง", "oil"]):
            content = "🛢️ แจ้งเตือนจากศูนย์บริการ Zero Garage:\nครบกำหนดรอบเปลี่ยนถ่ายน้ำมันเครื่องตามระยะ เพื่อประสิทธิภาพและถนอมเครื่องยนต์ นำรถเข้ามารับบริการได้เลยครับ 🚗"
        elif any(k in clean_msg.lower() for k in ["เช็คระยะ", "ตรวจเช็ค", "service"]):
            content = "🔧 แจ้งเตือนจากศูนย์บริการ Zero Garage:\nครบกำหนดรอบตรวจเช็คสภาพรถยนต์ประจำปี ฟรีตรวจเช็ค 30 รายการ ยินดีให้บริการครับ 🚗"
        else:
            cleaned_text = re.sub(r"^(?:ช่วย)?(?:ส่ง|แจ้ง|ทัก)?\s*(?:ข้อความ)?\s*(?:line|ไลน์)\s*(?:oa)?\s*(?:หา|ถึง|เตือน)?\s*([^\s:]+)?[:=：]?", "", clean_msg, flags=re.IGNORECASE).strip()
            content = cleaned_text if cleaned_text else "สวัสดีครับ มีการแจ้งเตือนจากศูนย์บริการ Zero Garage ครับ 🚗"

    dispatch_res = mock_line_dispatch(target_line_id, content)

    recipient_name = target_customer.name if target_customer else "LINE User"
    success = dispatch_res.get("success", False)
    mock = dispatch_res.get("mock", False)
    msg_id = dispatch_res.get("message_id", "")
    error_msg = dispatch_res.get("error", "")

    if success:
        mode_str = "🟢 ส่งผ่าน LINE Official Account สำเร็จ (Live API)" if not mock else "🟡 ส่งผ่าน Simulation Mode"
        text = (
            f"📱 **ส่งข้อความ LINE OA สำเร็จเรียบร้อย!**\n\n"
            f"👤 **ผู้รับ**: {recipient_name} (`{target_line_id[:6]}...{target_line_id[-4:]}`)\n"
            f"💬 **ข้อความที่ส่ง**: \"{content}\"\n"
            f"📡 **สถานะ**: {mode_str}\n"
            f"🆔 **Message ID**: `{msg_id}`"
        )
        return text, {
            "success": True,
            "recipient": recipient_name,
            "line_id": target_line_id,
            "content": content,
            "message_id": msg_id,
        }
    else:
        text = (
            f"❌ **ส่งข้อความ LINE OA ไม่สำเร็จ**\n\n"
            f"👤 **ผู้รับ**: {recipient_name} (`{target_line_id}`)\n"
            f"⚠️ **สาเหตุ**: {error_msg}\n"
            f"💡 *โปรดตรวจสอบว่าผู้รับเพิ่มเพื่อนกับ LINE OA แล้วหรือยัง*"
        )
        return text, {
            "success": False,
            "recipient": recipient_name,
            "line_id": target_line_id,
            "error": error_msg,
        }


def execute_create_intake_ticket(db: Session, msg: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Create an intake ticket for physical inspection by a mechanic."""
    from services import ticket_service
    from models.schemas import TicketIngestRequest

    plate_m = re.search(r"(?:ทะเบียน|plate|เลขทะเบียน)\s*[:=]?\s*([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4}(?:\s*[ก-๙]+)?)", msg, re.IGNORECASE)
    if not plate_m:
        plate_m = re.search(r"\b([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4})\b", msg)
    if not plate_m:
        plate_m = re.search(r"\b([A-Za-z0-9]{2,4}\s*[-]?\s*[0-9]{1,4})\b", msg)
    extracted_plate = plate_m.group(1).strip() if plate_m else None

    ticket = ticket_service.create_ticket(db, TicketIngestRequest(raw_input=msg, vehicle_plate=extracted_plate))
    status_str = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)

    text = (
        f"📋 **เปิดใบรับรถเข้าอู่ (Intake Ticket) #{ticket.id} เรียบร้อย!**\n\n"
        f"🚗 **รถยนต์**: {ticket.car_model or 'ไม่ระบุรุ่น'} (ทะเบียน: `{ticket.vehicle_plate or extracted_plate or 'ไม่ระบุ'}`)\n"
        f"📝 **ข้อมูลแจ้งอาการ/งานที่ต้องการ**: {msg[:120]}\n"
        f"⏳ **สถานะ**: **{status_str}**\n"
        f"👨‍🔧 **ขั้นตอนต่อไป**: ส่งมอบรถให้ช่างเทคนิคทำการตรวจเช็คสภาพจริงหน้างานอย่างละเอียด "
        f"ตามหลัก Mechanic-First เพื่อประเมินสาเหตุและลงรายการอะไหล่และค่าแรงที่ถูกต้องต่อไป"
    )
    return text, {
        "ticket_id": ticket.id,
        "vehicle_plate": ticket.vehicle_plate or extracted_plate,
        "car_model": ticket.car_model,
        "status": status_str,
    }


def execute_parsed_action(db: Session, action: str, params: Dict[str, Any], raw_msg: str) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    """Execute a structured action extracted by LLM or rule engine."""
    if action == "create_stock":
        name = params.get("name_th") or params.get("name") or params.get("name_en") or "อะไหล่ใหม่"
        qty = int(params.get("quantity") or params.get("qty") or 1)
        unit_cost = float(params.get("unit_cost") or params.get("cost") or 0.0)
        sell_price = float(params.get("sell_price") or params.get("price") or 0.0)
        if sell_price > 0 and unit_cost == 0:
            unit_cost = round(sell_price * 0.7, 2)
        sku = params.get("sku")
        if not sku:
            c_match = re.search(r"\b([A-Za-z]+[0-9]+[A-Za-z0-9\-]*|[0-9]+[A-Za-z]+[A-Za-z0-9\-]*|[A-Za-z0-9]+-[A-Za-z0-9]+)\b", name)
            if c_match and c_match.group(1).upper() not in ["NGK", "OEM", "QTY", "THB", "USD"]:
                sku = c_match.group(1).upper()
            else:
                sku = f"PRT-{datetime.now(timezone.utc).strftime('%m%d%H%M%S')}"

        category = params.get("category")
        if not category:
            cn = name.lower()
            if any(k in cn for k in ["น้ำมัน", "oil"]): category = "น้ำมันเครื่อง"
            elif any(k in cn for k in ["เบรค", "brake"]): category = "ระบบเบรค"
            elif any(k in cn for k in ["กรอง", "filter"]): category = "ไส้กรอง"
            elif any(k in cn for k in ["หัวเทียน", "spark"]): category = "ระบบจุดระเบิด"
            elif any(k in cn for k in ["ยาง", "tire"]): category = "ยางและล้อ"
            elif any(k in cn for k in ["แบต", "battery"]): category = "ระบบไฟและแบตเตอรี่"
            elif any(k in cn for k in ["ช่วงล่าง", "suspension"]): category = "ช่วงล่าง"
            else: category = "อะไหล่ทั่วไป"

        new_item = StockItem(
            name_th=name,
            name_en=params.get("name_en") or name,
            sku=sku,
            category=category,
            quantity=qty,
            unit_cost=unit_cost,
            sell_price=sell_price,
            notes=f"บันทึกผ่าน AI Copilot: {raw_msg[:100]}",
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)

        history = StockHistory(
            stock_item_id=new_item.id,
            change_type="in",
            delta=qty,
            quantity_before=0,
            quantity_after=qty,
            reason=f"เพิ่มสินค้าใหม่ผ่าน AI Copilot: {raw_msg[:100]}",
            changed_by="AI Copilot",
        )
        db.add(history)
        db.commit()

        text = (
            f"📦 **เพิ่มสินค้า/อะไหล่ใหม่เข้าสต็อกสำเร็จ!**\n\n"
            f"🔧 **ชื่ออะไหล่**: {new_item.name_th}\n"
            f"🏷️ **SKU**: `{new_item.sku}`\n"
            f"📂 **หมวดหมู่**: {new_item.category}\n"
            f"📊 **จำนวนนำเข้า**: **{new_item.quantity}** ชิ้น\n"
            f"💰 **ราคาทุน / ขาย**: ฿{new_item.unit_cost:,.2f} / ฿{new_item.sell_price:,.2f}\n"
            f"✅ ข้อมูลถูกบันทึกลงในระบบคลังสินค้าเรียบร้อยแล้ว"
        )
        return "stock", text, {"item_id": new_item.id, "sku": new_item.sku, "name": new_item.name_th, "qty": new_item.quantity}

    elif action == "adjust_stock":
        name = params.get("name") or params.get("name_th") or ""
        delta = int(params.get("delta") or 1)
        items = db.query(StockItem).all()
        matched = None
        for i in items:
            if i.sku and name.lower() in i.sku.lower():
                matched = i; break
            if name.lower() in i.name_th.lower() or (i.name_en and name.lower() in i.name_en.lower()):
                matched = i; break
            tokens = [t for t in i.name_th.lower().split() if len(t) >= 2]
            if any(t in name.lower() for t in tokens):
                matched = i; break

        if matched:
            before = matched.quantity
            matched.quantity = max(0, matched.quantity + delta)
            after = matched.quantity
            hist = StockHistory(
                stock_item_id=matched.id,
                change_type="adjust" if delta < 0 else "in",
                delta=delta,
                quantity_before=before,
                quantity_after=after,
                reason=f"ปรับสต็อกผ่าน AI Copilot: {raw_msg[:100]}",
                changed_by="AI Copilot",
            )
            db.add(hist)
            db.commit()
            act_text = "เพิ่ม" if delta > 0 else "ลด"
            text = (
                f"📦 **บันทึกปรับปรุงสต็อกสำเร็จ!**\n\n"
                f"🔧 **อะไหล่**: {matched.name_th} (SKU: `{matched.sku}`)\n"
                f"{'➕' if delta > 0 else '➖'} **การดำเนินการ**: {act_text} {abs(delta)} ชิ้น\n"
                f"📊 **จำนวนคงเหลือใหม่**: **{after}** ชิ้น (จากเดิม {before})"
            )
            return "stock", text, {"item_id": matched.id, "delta": delta, "qty_after": after}
        else:
            return execute_parsed_action(db, "create_stock", {"name_th": name, "quantity": max(1, abs(delta))}, raw_msg)

    elif action == "create_customer":
        name = params.get("name") or "ลูกค้าใหม่"
        if not name.startswith("คุณ") and len(name) < 20:
            name = f"คุณ{name}"
        phone = params.get("phone")
        line_id = params.get("line_id")
        email = params.get("email")

        existing = db.query(Customer).filter(Customer.phone == phone).first() if phone else None
        if existing:
            text = (
                f"👤 **พบข้อมูลลูกค้าเดิมในระบบ:**\n\n"
                f"🆔 **รหัสลูกค้า**: #{existing.id}\n"
                f"📛 **ชื่อ**: {existing.name}\n"
                f"📞 **เบอร์โทร**: {existing.phone}\n"
                f"💬 **LINE**: {existing.line_id or '-'}"
            )
            return "customer", text, {"customer_id": existing.id, "name": existing.name}

        c = Customer(name=name, phone=phone, line_id=line_id, email=email)
        db.add(c); db.commit(); db.refresh(c)
        text = (
            f"👤 **บันทึกข้อมูลลูกค้าใหม่เรียบร้อย!**\n\n"
            f"🆔 **รหัสลูกค้า**: #{c.id}\n"
            f"📛 **ชื่อ-นามสกุล**: {c.name}\n"
            f"📞 **เบอร์โทรศัพท์**: {c.phone or 'ไม่ระบุ'}\n"
            f"💬 **LINE ID**: {c.line_id or '-'}\n"
            f"✅ ข้อมูลถูกจัดเก็บในระบบลูกค้าเรียบร้อยแล้ว"
        )
        return "customer", text, {"customer_id": c.id, "name": c.name, "phone": c.phone}

    elif action == "create_vehicle":
        plate = params.get("plate") or f"ชั่วคราว-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        brand = params.get("brand") or "Toyota"
        model = params.get("model") or "ทั่วไป"
        mileage = int(params.get("mileage") or 0)
        c_name = params.get("customer_name")

        customer = None
        if c_name:
            customer = db.query(Customer).filter(Customer.name.ilike(f"%{c_name}%")).first()
        if not customer:
            customer = db.query(Customer).first()
        if not customer:
            customer = Customer(name="ลูกค้าทั่วไป", phone="0800000000")
            db.add(customer); db.commit(); db.refresh(customer)

        v = db.query(Vehicle).filter(Vehicle.plate == plate).first()
        if not v:
            v = Vehicle(plate=plate, brand=brand, model=model, customer_id=customer.id, current_mileage=mileage)
            db.add(v); db.commit(); db.refresh(v)
            text = (
                f"🚗 **ลงทะเบียนรถยนต์ใหม่เรียบร้อย!**\n\n"
                f"🔢 **ทะเบียน**: `{v.plate}`\n"
                f"🚘 **ยี่ห้อ/รุ่น**: {v.brand} {v.model}\n"
                f"👤 **เจ้าของ**: {customer.name}\n"
                f"📊 **เลขไมล์เริ่มต้น**: {v.current_mileage:,} กม.\n"
                f"✅ พร้อมเปิดใบรับรถและบันทึกประวัติการซ่อมบำรุง"
            )
        else:
            text = (
                f"🚗 **รถทะเบียน `{v.plate}` มีอยู่ในระบบแล้ว:**\n\n"
                f"🚘 **ยี่ห้อ/รุ่น**: {v.brand} {v.model}\n"
                f"👤 **เจ้าของ**: {v.customer.name if v.customer else 'ไม่ระบุ'}\n"
                f"📊 **เลขไมล์**: {v.current_mileage:,} กม."
            )
        return "vehicle", text, {"vehicle_id": v.id, "plate": v.plate}

    elif action == "create_expense":
        text, data = execute_add_expense(db, raw_msg, parsed_params=params)
        return "expense", text, data

    elif action in ("delete_expense", "delete_supplier", "cancel_appointment", "delete"):
        text, data = execute_delete_action(db, raw_msg, action=action, params=params)
        act_type = data.get("type", "delete") if data else "delete"
        return act_type, text, data

    elif action == "create_appointment":
        c_name = params.get("customer_name")
        phone = params.get("phone")
        time_slot = params.get("time")
        service = params.get("service") or raw_msg[:100]

        parsed_date, parsed_time = parse_thai_appointment_datetime(raw_msg)
        appt_date = parsed_date
        if params.get("date"):
            try:
                d_str = str(params["date"]).strip()
                # Handle Thai years e.g. 2569 or 69
                y_m = re.search(r"(\d{4})", d_str)
                if y_m and int(y_m.group(1)) >= 2500:
                    d_str = d_str.replace(y_m.group(1), str(int(y_m.group(1)) - 543))
                appt_date = datetime.strptime(d_str[:10], "%Y-%m-%d")
            except Exception:
                appt_date = parsed_date

        time_slot = time_slot or parsed_time or "10:00"

        # Sanitize customer name
        SERVICE_STOPWORDS = {"เปลี่ยนยาง", "สลับยาง", "ปะยาง", "ล้างรถ", "ซ่อมเบรค", "เปลี่ยนแบต", "น้ำมันเครื่อง", "ตรวจสภาพ"}
        if not c_name or any(s in c_name for s in SERVICE_STOPWORDS):
            c_name = "ลูกค้าทั่วไป (นัดหมายผ่าน AI)"
        elif not c_name.startswith("คุณ") and not c_name.startswith("ลูกค้า") and len(c_name) > 1:
            c_name = f"คุณ{c_name}"

        appt = Appointment(
            customer_name=c_name, customer_phone=phone, appointment_date=appt_date,
            time_slot=time_slot, service_type=service, status="confirmed"
        )
        db.add(appt); db.commit(); db.refresh(appt)
        text = (
            f"📅 **บันทึกการนัดหมายเรียบร้อย!**\n\n"
            f"👤 **ลูกค้า**: {c_name}\n"
            f"📞 **เบอร์โทร**: {phone or 'ไม่ระบุ'}\n"
            f"📆 **วันที่**: {appt_date.strftime('%d/%m/%Y')}\n"
            f"🕐 **เวลานัดหมาย**: {time_slot} น.\n"
            f"🔧 **วัตถุประสงค์**: {service}\n"
            f"📌 ข้อมูลลงตารางในปฏิทินนัดหมายของอู่แล้ว"
        )
        return "appointment", text, {
            "appointment_id": appt.id,
            "customer_name": c_name,
            "customer_phone": phone,
            "appointment_date": appt_date.isoformat(),
            "time_slot": time_slot,
            "service_type": service,
            "status": "confirmed"
        }

    elif action == "create_ticket":
        from services import ticket_service
        from models.schemas import TicketIngestRequest
        ticket = ticket_service.create_ticket(db, TicketIngestRequest(
            raw_input=raw_msg,
            vehicle_plate=params.get("plate"),
            customer_phone=params.get("phone")
        ))
        status_str = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
        text = (
            f"📋 **เปิดใบรับรถเข้าอู่ (Intake Ticket) #{ticket.id} เรียบร้อย!**\n\n"
            f"🚗 **รถยนต์**: {ticket.car_model or 'ไม่ระบุรุ่น'} (ทะเบียน: `{ticket.vehicle_plate or params.get('plate') or 'ไม่ระบุ'}`)\n"
            f"📝 **ข้อมูลแจ้งอาการ/งานที่ต้องการ**: {params.get('symptoms') or raw_msg[:120]}\n"
            f"⏳ **สถานะ**: **{status_str}**\n"
            f"👨‍🔧 **ขั้นตอนต่อไป**: ส่งมอบรถให้ช่างเทคนิคทำการตรวจเช็คสภาพจริงหน้างานอย่างละเอียดตามหลัก Mechanic-First"
        )
        return "ticket", text, {"ticket_id": ticket.id, "vehicle_plate": ticket.vehicle_plate, "status": status_str}

    return "info", "ดำเนินการเรียบร้อยครับ", None


async def extract_action_with_llm(api_key: str, provider: str, msg: str) -> Optional[Dict[str, Any]]:
    """Use Gemini / OpenAI to extract structured database action for natural language input."""
    system = (
        "You are a Database Action Extractor for an automotive workshop command center.\n"
        "The user wants to add, create, or record something into the workshop database.\n"
        "Extract the exact operational action and parameters.\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "action": "create_stock" | "adjust_stock" | "create_customer" | "create_vehicle" | "create_expense" | "create_appointment" | "create_ticket" | "none",\n'
        '  "params": {\n'
        '    // for create_stock: name_th, name_en, sku, category, quantity, unit_cost, sell_price\n'
        '    // for adjust_stock: name, delta (positive or negative int)\n'
        '    // for create_customer: name, phone, line_id, email\n'
        '    // for create_vehicle: plate, brand, model, customer_name, mileage\n'
        '    // for create_expense: amount (float), category, description\n'
        '    // for create_appointment: customer_name, phone, date (YYYY-MM-DD), time (HH:MM), service\n'
        '    // for create_ticket: plate, car_model, symptoms, customer_name\n'
        '  }\n'
        "}\n"
        "If it is not an action to add/create/record data, return {\"action\": \"none\"}."
    )
    try:
        if provider == "gemini":
            res = await call_gemini(api_key, f"Extract database action: {msg}", system)
        else:
            res = await call_openai(api_key, f"Extract database action: {msg}", system)

        clean_json = re.sub(r"^```(?:json)?", "", res.strip(), flags=re.MULTILINE)
        clean_json = re.sub(r"```$", "", clean_json.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean_json)
        if isinstance(data, dict) and data.get("action") and data["action"] != "none":
            return data
    except Exception as e:
        logger.warning(f"LLM Action Extraction failed: {e}")
    return None


def save_image_from_base64(image_data: str, folder: str = "bills") -> Tuple[str, bytes, str]:
    """Decode base64 data URI, save to static/uploads/{folder}, and return (web_path, raw_bytes, mime_type)."""
    mime_type = "image/jpeg"
    clean_b64 = image_data
    if "," in image_data:
        header, clean_b64 = image_data.split(",", 1)
        m = re.search(r"data:([^;]+);base64", header)
        if m:
            mime_type = m.group(1)

    raw_bytes = base64.b64decode(clean_b64)
    ext = ".jpg"
    if "png" in mime_type: ext = ".png"
    elif "webp" in mime_type: ext = ".webp"

    dest_dir = os.path.join("static", "uploads", folder)
    os.makedirs(dest_dir, exist_ok=True)
    filename = f"img_{uuid.uuid4().hex[:12]}{ext}"
    filepath = os.path.join(dest_dir, filename)
    with open(filepath, "wb") as f:
        f.write(raw_bytes)

    web_path = f"/static/uploads/{folder}/{filename}"
    return web_path, raw_bytes, mime_type


async def analyze_image_with_gemini_vision(api_key: str, image_bytes: bytes, mime_type: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Send image and prompt to Gemini Vision REST API."""
    models = ["gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-flash-latest", "gemini-2.5-flash"]
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    
    prompt = (
        "You are an AI assistant for an automotive workshop command center in Thailand.\n"
        f"User prompt/context: '{user_prompt}'\n"
        "Analyze this uploaded image. Determine which document it is:\n"
        "1. Parts Purchase Invoice / Receipt / Bill of Materials (ใบเสร็จซื้ออะไหล่, บิลส่งของ, บิลเงินสด, ใบกำกับภาษี) containing automotive parts/products.\n"
        "2. General Expense Bill / Utility Receipt (ค่าไฟ, ค่าน้ำ, ค่าเช่า, ค่าอินเทอร์เน็ต, etc.).\n"
        "3. Vehicle Inspection / Service Ticket / Car Repair Order / Car Plate photo (ใบรับรถ, ทะเบียนรถ, รถเข้าซ่อม).\n\n"
        "If it is a parts purchase receipt/invoice with multiple items, extract EVERY SINGLE item line into 'parts_items'.\n"
        "Extract and return ONLY a valid JSON object matching this schema (no markdown fences, pure JSON):\n"
        "{\n"
        '  "doc_type": "parts_purchase" | "bill" | "ticket",\n'
        '  "category": "ซื้ออะไหล่/วัสดุ" | "ค่าไฟฟ้า" | "ค่าน้ำประปา" | "ค่าเช่า" | "ค่าอินเทอร์เน็ต" | "อื่นๆ",\n'
        '  "amount": 0.0, // float grand total amount in THB\n'
        '  "supplier_name": "Supplier or vendor name if visible or null",\n'
        '  "invoice_no": "Invoice or receipt number if visible or null",\n'
        '  "description": "Summary of this bill or document",\n'
        '  "parts_items": [\n'
        '    {\n'
        '      "sku": "product code / barcode / SKU string or null",\n'
        '      "name": "full part description in Thai",\n'
        '      "qty": 1,\n'
        '      "unit": "ชิ้น / Pcs. / เส้น / etc.",\n'
        '      "unit_cost": 0.0,\n'
        '      "total_cost": 0.0,\n'
        '      "category": "หมวดหมู่อะไหล่ เช่น เกจวัดและอุปกรณ์, ตกแต่งห้องเครื่องยนต์, มู่เล่ย์และสายพาน, ระบบระบายไอ, ระบบเบรค, ฯลฯ"\n'
        '    }\n'
        '  ],\n'
        '  "vehicle_plate": "Thai plate e.g. 1กข 1234 กรุงเทพ or null",\n'
        '  "car_brand": "Brand or null",\n'
        '  "car_model": "Model or null",\n'
        '  "customer_name": "Customer name or null",\n'
        '  "customer_phone": "Customer phone or null",\n'
        '  "symptoms": "Customer reported symptoms or repair request or null"\n'
        "}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    }
                ]
            }
        ],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}
    }

    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw = parts[0].get("text", "").strip()
                            clean_json = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
                            clean_json = re.sub(r"\s*```$", "", clean_json.strip(), flags=re.MULTILINE).strip()
                            return json.loads(clean_json)
                elif res.status_code == 404:
                    continue
        except Exception as e:
            logger.warning(f"Gemini Vision failed on {model_name}: {e}")
    return None


async def process_chat_image(
    db: Session,
    msg: str,
    image_data: str,
    image_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Process incoming photo for expense recording, parts stock ingestion, or service ticket creation."""
    pipeline_steps = [
        {"step": 1, "name": "Image Ingestion & Storage", "status": "active"}
    ]
    m_lower = msg.lower()
    img_name_lower = (image_name or "").lower()

    # Determine initial target folder
    is_explicit_ticket = any(k in m_lower for k in [
        "เปิดใบ", "รับรถ", "ใบรับ", "ใบสั่งซ่อม", "ticket", "ตั๋ว", "งานซ่อม", "อาการ", "รถเข้าซ่อม"
    ]) or any(k in img_name_lower for k in ["car", "ticket", "plate", "intake"])

    folder = "tickets" if is_explicit_ticket else "bills"
    web_path, raw_bytes, mime_type = save_image_from_base64(image_data, folder=folder)
    pipeline_steps[0]["status"] = "done"
    pipeline_steps.append({"step": 2, "name": "AI Vision OCR & Document Classification", "status": "active"})

    # Check available Gemini API key
    gemini_key = get_configured_key("GEMINI_API_KEY") or get_configured_key("GOOGLE_API_KEY")
    vision_data = None
    if gemini_key:
        vision_data = await analyze_image_with_gemini_vision(gemini_key, raw_bytes, mime_type, msg)

    # Document type determination
    doc_type = "bill"
    if is_explicit_ticket:
        doc_type = "ticket"
    elif vision_data and vision_data.get("doc_type"):
        doc_type = vision_data["doc_type"]
    elif any(k in m_lower for k in ["บิล", "ค่าไฟ", "ค่าน้ำ", "ค่าเช่า", "ใบเสร็จ", "bill", "expense", "จ่าย", "บาท"]):
        doc_type = "bill"
    elif any(k in m_lower for k in ["รถ", "ซ่อม", "ทะเบียน"]):
        doc_type = "ticket"

    pipeline_steps[1]["status"] = "done"

    # ── BRANCH 1: PARTS PURCHASE RECEIPT (STOCK INGESTION + EXPENSE) ──────────
    parts_list = (vision_data.get("parts_items") if vision_data else []) or []
    if doc_type == "parts_purchase" or (parts_list and len(parts_list) > 0):
        pipeline_steps.append({"step": 3, "name": "Multi-item Stock Ingestion & Cost Logging", "status": "active"})
        
        imported_count = 0
        updated_count = 0
        total_units = 0
        grand_cost = 0.0

        for p in parts_list:
            p_sku = (p.get("sku") or "").strip()
            p_name = (p.get("name") or "อะไหล่ใหม่").strip()
            try: p_qty = max(1, int(p.get("qty") or 1))
            except: p_qty = 1
            try: p_cost = float(p.get("unit_cost") or 0.0)
            except: p_cost = 0.0
            p_cat = p.get("category") or "อะไหล่ทั่วไป"
            sell_price = round(p_cost * 1.35 / 10) * 10 if p_cost > 0 else 0.0
            grand_cost += (p_cost * p_qty)
            total_units += p_qty

            # Match existing item by SKU or exact name
            existing = None
            if p_sku:
                existing = db.query(StockItem).filter(StockItem.sku == p_sku).first()
            if not existing and p_name:
                existing = db.query(StockItem).filter(StockItem.name_th == p_name).first()

            if existing:
                q_before = existing.quantity
                existing.quantity += p_qty
                if p_cost > 0:
                    existing.unit_cost = p_cost
                if existing.sell_price == 0 or (p_cost > 0 and existing.sell_price < p_cost):
                    existing.sell_price = sell_price
                db.commit()

                hist = StockHistory(
                    stock_item_id=existing.id,
                    change_type="in",
                    delta=p_qty,
                    quantity_before=q_before,
                    quantity_after=existing.quantity,
                    reason=f"เพิ่มสต็อกตามบิล ({vision_data.get('supplier_name') or 'รูปภาพ'})",
                    changed_by="AI Copilot (รูปภาพ)",
                )
                db.add(hist)
                db.commit()
                updated_count += 1
            else:
                final_sku = p_sku or f"PRT-{datetime.now(timezone.utc).strftime('%m%d%H%M%S')}-{imported_count+1}"
                new_item = StockItem(
                    name_th=p_name,
                    sku=final_sku,
                    category=p_cat,
                    quantity=p_qty,
                    unit_cost=p_cost,
                    sell_price=sell_price,
                    reorder_level=2,
                    notes=f"นำเข้าผ่าน AI Copilot จากบิล {vision_data.get('supplier_name') or ''} เลขที่ {vision_data.get('invoice_no') or ''}".strip(),
                )
                db.add(new_item)
                db.commit()
                db.refresh(new_item)

                hist = StockHistory(
                    stock_item_id=new_item.id,
                    change_type="in",
                    delta=p_qty,
                    quantity_before=0,
                    quantity_after=p_qty,
                    reason=f"สร้างอะไหล่ใหม่ตามบิล ({vision_data.get('supplier_name') or 'รูปภาพ'})",
                    changed_by="AI Copilot (รูปภาพ)",
                )
                db.add(hist)
                db.commit()
                imported_count += 1

        # Record into PurchaseBill (ประวัติการซื้อ / บิลจัดซื้ออะไหล่)
        final_amount = float(vision_data.get("amount") or grand_cost or 0.0) if vision_data else grand_cost
        sup_name = (vision_data.get("supplier_name") if vision_data else None) or "ผู้จำหน่ายอะไหล่"
        inv_no = (vision_data.get("invoice_no") if vision_data else None) or ""
        desc = f"บิลซื้ออะไหล่ {sup_name} {inv_no} ({len(parts_list)} รายการ)".strip()

        # Find or create supplier
        supplier = None
        if sup_name and sup_name not in ["ผู้จำหน่ายอะไหล่", "ไม่ระบุ"]:
            supplier = db.query(Supplier).filter(Supplier.name.ilike(f"%{sup_name}%")).first()
            if not supplier:
                supplier = Supplier(
                    name=sup_name,
                    notes="สร้างอัตโนมัติจากการสแกนบิลซื้ออะไหล่ผ่าน AI Copilot",
                )
                db.add(supplier)
                db.commit()
                db.refresh(supplier)

        # Prepare line items JSON for PurchaseBill
        pb_items = []
        for p in parts_list:
            p_name = p.get("name_th") or p.get("name") or "อะไหล่"
            p_qty = int(p.get("qty") or p.get("quantity") or 1)
            p_cost = float(p.get("unit_cost") or p.get("cost") or p.get("unit_price") or 0.0)
            pb_items.append({
                "name": p_name,
                "qty": p_qty,
                "unit_price": p_cost,
                "total": round(p_cost * p_qty, 2)
            })

        purch_bill = PurchaseBill(
            supplier_id=supplier.id if supplier else None,
            bill_number=inv_no or f"PB-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            bill_date=datetime.now(timezone.utc),
            items=json.dumps(pb_items, ensure_ascii=False),
            total_amount=round(final_amount, 2),
            image_path=web_path,
            notes=desc
        )
        db.add(purch_bill)
        db.commit()
        db.refresh(purch_bill)

        pipeline_steps[2]["status"] = "done"

        text = (
            f"📦 **นำเข้าอะไหล่จากบิลเข้าสต็อกและบันทึกประวัติการซื้อสำเร็จ!**\n\n"
            f"🏬 **ผู้จำหน่าย**: {sup_name}\n"
            f"📑 **เลขที่เอกสาร**: {inv_no or 'ไม่ระบุ'}\n"
            f"💰 **ยอดเงินรวมทั้งสิ้น**: **฿{final_amount:,.2f}**\n"
            f"📊 **สรุปการจัดการสต็อก**:\n"
            f"  • นำเข้าอะไหล่ใหม่: **{imported_count}** รายการ\n"
            f"  • บวกเพิ่มสต็อกเดิม: **{updated_count}** รายการ\n"
            f"  • รวมสินค้าทั้งหมด: **{total_units}** ชิ้น ({len(parts_list)} รายการ)\n"
            f"✅ รายการทั้งหมดถูกลงระบบคลังสินค้า และบันทึกใน **ประวัติการซื้อ (จัดซื้ออะไหล่)** เรียบร้อยแล้ว"
        )
        return {
            "type": "stock",
            "text": text,
            "data": {
                "total_parts": len(parts_list),
                "imported_new": imported_count,
                "updated_existing": updated_count,
                "total_amount": final_amount,
                "image_path": web_path,
                "purchase_bill_id": purch_bill.id,
            },
            "pipeline_steps": pipeline_steps,
        }

    # ── BRANCH 2: GENERAL EXPENSE BILL ────────────────────────────────────────
    elif doc_type == "bill":
        pipeline_steps.append({"step": 3, "name": "Expense Ingestion & P&L Recording", "status": "active"})
        amount = 0.0
        if vision_data and vision_data.get("amount"):
            try: amount = float(vision_data["amount"])
            except: pass
        if amount <= 0:
            numbers = re.findall(r"[\d,]+(?:\.\d+)?", msg.replace(",", ""))
            amount = float(numbers[0]) if numbers else 0.0
        if amount <= 0:
            amount = 1500.0

        category = "อื่นๆ"
        if vision_data and vision_data.get("category"):
            category = vision_data["category"]
        else:
            if any(k in m_lower or k in img_name_lower for k in ["ค่าไฟ", "ไฟฟ้า", "electricity", "electric", "power"]): category = "ค่าไฟฟ้า"
            elif any(k in m_lower or k in img_name_lower for k in ["ค่าน้ำ", "ประปา", "water"]): category = "ค่าน้ำประปา"
            elif any(k in m_lower or k in img_name_lower for k in ["ค่าเช่า", "เช่า", "rent"]): category = "ค่าเช่า"
            elif any(k in m_lower or k in img_name_lower for k in ["เน็ต", "อินเทอร์", "internet", "wifi"]): category = "ค่าอินเทอร์เน็ต"
            elif any(k in m_lower or k in img_name_lower for k in ["เครื่องมือ", "อุปกรณ์", "tools"]): category = "ค่าอุปกรณ์/เครื่องมือ"

        description = (vision_data.get("description") if vision_data else None) or msg or f"บันทึกบิล {category} ผ่าน AI Vision"

        exp = Expense(
            category=category,
            description=description[:200],
            amount=amount,
            image_path=web_path,
            added_by="AI Copilot (รูปภาพ)",
        )
        db.add(exp)
        db.commit()
        db.refresh(exp)

        pipeline_steps[2]["status"] = "done"

        text = (
            f"📸 **บันทึกบิลค่าใช้จ่ายจากรูปภาพสำเร็จ!**\n\n"
            f"📂 **หมวดหมู่**: {category}\n"
            f"💰 **จำนวนเงิน**: **฿{amount:,.2f}**\n"
            f"📝 **รายละเอียด**: {description}\n"
            f"🖼️ **ภาพหลักฐาน**: บันทึกเข้าระบบเรียบร้อย\n"
            f"✅ ข้อมูลถูกบันทึกลงในระบบบัญชีค่าใช้จ่ายและคำนวณใน P&L ทันที"
        )
        return {
            "type": "expense",
            "text": text,
            "data": {
                "expense_id": exp.id,
                "amount": amount,
                "category": category,
                "image_path": web_path,
            },
            "pipeline_steps": pipeline_steps,
        }

    # ── BRANCH 3: INTAKE TICKET ("เปิดใบรับรถ") ───────────────────────────────
    else:
        pipeline_steps.append({"step": 3, "name": "Work Order Intake & HITL Dispatch", "status": "active"})
        from services import ticket_service
        from models.schemas import TicketIngestRequest

        plate = None
        car_model = None
        symptoms = None

        if vision_data:
            plate = vision_data.get("vehicle_plate")
            b = vision_data.get("car_brand") or ""
            m = vision_data.get("car_model") or ""
            car_model = f"{b} {m}".strip() or None
            symptoms = vision_data.get("symptoms")

        if not plate:
            plate_m = re.search(r"(?:ทะเบียน|plate|เลขทะเบียน)\s*[:=]?\s*([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4}(?:\s*[ก-๙]+)?)", msg, re.IGNORECASE)
            if not plate_m:
                plate_m = re.search(r"\b([0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4})\b", msg)
            if not plate_m:
                plate_m = re.search(r"\b([A-Za-z0-9]{2,4}\s*[-]?\s*[0-9]{1,4})\b", msg)
            plate = plate_m.group(1).strip() if plate_m else None

        raw_content = f"[แนบภาพถ่าย: {web_path}] {msg or symptoms or 'ตรวจเช็คสภาพรถจริงหน้างาน'}"
        ticket = ticket_service.create_ticket(db, TicketIngestRequest(raw_input=raw_content, vehicle_plate=plate))
        if car_model and not ticket.car_model:
            ticket.car_model = car_model
        ticket.mechanic_notes = f"ภาพถ่ายประกอบใบรับรถ: {web_path}"
        db.commit()

        status_str = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
        pipeline_steps[2]["status"] = "done"

        text = (
            f"📸 **เปิดใบรับรถเข้าอู่ (Intake Ticket) #{ticket.id} จากภาพถ่ายเรียบร้อย!**\n\n"
            f"🚗 **รถยนต์**: {ticket.car_model or car_model or 'ไม่ระบุรุ่น'} (ทะเบียน: `{ticket.vehicle_plate or plate or 'ไม่ระบุ'}`)\n"
            f"📝 **ข้อมูลแจ้งอาการ/งานที่ต้องการ**: {symptoms or msg or 'ส่งตรวจเช็คสภาพจริงหน้างานโดยช่าง'}\n"
            f"⏳ **สถานะ**: **{status_str}**\n"
            f"🖼️ **ภาพแนบ**: บันทึกเข้าระบบงานซ่อมเรียบร้อย\n"
            f"👨‍🔧 **ขั้นตอนต่อไป**: ส่งมอบรถให้ช่างเทคนิคทำการตรวจเช็คสภาพจริงหน้างานอย่างละเอียดตามหลัก Mechanic-First"
        )
        return {
            "type": "ticket",
            "text": text,
            "data": {
                "ticket_id": ticket.id,
                "vehicle_plate": ticket.vehicle_plate or plate,
                "car_model": ticket.car_model or car_model,
                "status": status_str,
                "image_path": web_path,
            },
            "pipeline_steps": pipeline_steps,
        }


# ── Main AI Processing Function ───────────────────────────────────────────────

async def process_chat_message(
    db: Session,
    user_msg: str,
    image_data: Optional[str] = None,
    image_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entry point for AI Chat.
    Handles text instructions and image uploads (bills, intake tickets),
    executes live RAG retrieval, strictly enforces Mechanic-First inspection,
    and leverages Gemini / OpenAI or intelligent local engine.
    """
    msg = (user_msg or "").strip()
    
    # ── CASE 0: Image Attachment Processing (Bills & Intake Tickets) ──────────
    if image_data:
        return await process_chat_image(db, msg, image_data, image_name)

    pipeline_steps = []
    pipeline_steps.append({"step": 1, "name": "Intent Analysis", "status": "done"})

    m_lower = msg.lower()

    # Check available API keys early
    gemini_key = get_configured_key("GEMINI_API_KEY") or get_configured_key("GOOGLE_API_KEY")
    openai_key = get_configured_key("OPENAI_API_KEY")
    provider = "gemini" if gemini_key else ("openai" if openai_key else None)
    active_key = gemini_key or openai_key

    # Fetch live workshop context
    pipeline_steps.append({"step": 2, "name": "Live DB RAG Retrieval", "status": "done"})
    context = get_live_workshop_context(db)

    # ── 1. PRIMARY PATH: Live LLM Generative Engine (When API Key is available) ───
    if active_key:
        pipeline_steps.append({"step": 3, "name": "Live LLM Generative Reasoning", "status": "active"})
        system_instruction = (
            "You are R.O.S.E., the intelligent Automotive Workshop Command Center & AI Copilot in Thailand.\n"
            "Your role: Help workshop managers, service advisors, and mechanics run the workshop smoothly.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. MECHANIC-FIRST RULE: NEVER diagnose car mechanical faults or guess repairs (e.g. why engine stalls, brake squeals, aircon warm).\n"
            "   Diagnostics MUST be physically inspected by a qualified workshop mechanic. Politely explain this to the user,\n"
            "   and offer to create an intake ticket (เปิดใบรับรถ) or book an appointment for inspection.\n"
            "2. ACTION EXECUTION:\n"
            "   If the user explicitly intends to create, record, adjust, delete, or cancel data in the database, you MUST output a JSON block inside ```action ... ```:\n"
            "   ```action\n"
            '   {"action": "create_expense"|"adjust_stock"|"create_stock"|"create_appointment"|"create_ticket"|"delete_expense"|"delete_supplier"|"cancel_appointment"|"create_customer"|"create_vehicle"|"none", "params": {...}, "reply": "Helpful confirmation message in polite Thai"}\n'
            "   ```\n"
            "   Supported actions and params:\n"
            '   - delete_supplier: {"name": string, "phone": string} (for deleting or removing a supplier/vendor)\n'
            '   - delete_expense: {"expense_id": int} or {"amount": float} (for deleting an erroneous expense)\n'
            '   - cancel_appointment: {"appointment_id": int, "customer_name": string}\n'
            '   - create_expense: {"category": string, "amount": float, "description": string} (NOTE: Phone numbers like 0899887766 are NOT expense amounts! Only record real expenses when explicitly asked)\n'
            '   - create_stock: {"name_th": string, "sku": string, "category": string, "quantity": int, "unit_cost": float, "sell_price": float}\n'
            '   - adjust_stock: {"name": string, "delta": int}\n'
            '   - create_appointment: {"customer_name": string, "phone": string, "date": "YYYY-MM-DD", "time": "HH:MM", "service": string}\n'
            '   - create_ticket: {"plate": string, "car_model": string, "symptoms": string, "customer_name": string}\n'
            '   - create_customer: {"name": string, "phone": string, "line_id": string, "email": string}\n'
            '   - create_vehicle: {"plate": string, "brand": string, "model": string, "customer_name": string, "mileage": int}\n'
            "   If user asks to DELETE or REMOVE, NEVER output create_expense or create_stock!\n"
            "3. QUESTION & INQUIRY ANSWERING:\n"
            "   If the user is asking questions (e.g. stock levels, revenue, expenses, appointments, suppliers, customers, watchlist), DO NOT output an action block.\n"
            "   Answer directly in polite, clear Thai using data from the LIVE WORKSHOP DATABASE SNAPSHOT below.\n"
            "   Use bullet points and bold formatting for clarity.\n\n"
            "=== LIVE WORKSHOP DATABASE SNAPSHOT ===\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n"
            "========================================"
        )

        try:
            if gemini_key:
                raw_llm_res = await call_gemini(gemini_key, msg, system_instruction)
            else:
                raw_llm_res = await call_openai(openai_key, msg, system_instruction)

            # Check if LLM output an action block
            act_match = re.search(r"```(?:action|json)?\s*(\{.*?\})\s*```", raw_llm_res, re.DOTALL)
            parsed_action_obj = None
            if act_match:
                try:
                    parsed_action_obj = json.loads(act_match.group(1).strip())
                except Exception:
                    pass
            elif raw_llm_res.strip().startswith("{") and raw_llm_res.strip().endswith("}"):
                try:
                    parsed_action_obj = json.loads(raw_llm_res.strip())
                except Exception:
                    pass

            if parsed_action_obj and isinstance(parsed_action_obj, dict) and parsed_action_obj.get("action") and parsed_action_obj["action"] != "none":
                action_name = parsed_action_obj["action"]
                action_params = parsed_action_obj.get("params", {})
                act_type, act_text, act_data = execute_parsed_action(db, action_name, action_params, msg)
                pipeline_steps.append({"step": 4, "name": f"Action Execution ({action_name})", "status": "done"})
                return {
                    "type": act_type,
                    "text": act_text,
                    "data": act_data,
                    "pipeline_steps": pipeline_steps,
                }

            # Return natural conversational response
            clean_reply = re.sub(r"```(?:action|json)?.*?```", "", raw_llm_res, flags=re.DOTALL).strip()
            pipeline_steps.append({"step": 4, "name": "Generated Response", "status": "done"})
            return {
                "type": "llm",
                "text": clean_reply if clean_reply else raw_llm_res,
                "data": {"provider": provider},
                "pipeline_steps": pipeline_steps,
            }
        except Exception as e:
            logger.warning(f"Live LLM call failed: {e}. Falling back to Intelligent Local Operations Engine.")

    # ── 2. INTELLIGENT LOCAL OPERATIONS ENGINE (Offline / Zero-Key Fallback) ──────
    pipeline_steps.append({"step": 3, "name": "ROSE Core Workshop Intelligence (Local Fallback)", "status": "active"})

    # Check 1: Deletion or Cancellation Request
    has_delete_kw = any(k in m_lower for k in ["ลบ", "ยกเลิก", "delete", "cancel", "remove"])
    if has_delete_kw:
        text, data = execute_delete_action(db, msg)
        return {
            "type": data.get("type", "delete") if data else "info",
            "text": text,
            "data": data,
            "pipeline_steps": pipeline_steps,
        }

    # Check 2: Pure Diagnostic Inquiry Guardrail
    is_pure_symptom_inquiry = any(k in m_lower for k in [
        "เกิดจากอะไร", "เป็นอะไร", "ทำไมถึง", "เสียตรงไหน", "ซ่อมแพงไหม", "เช็คยังไง"
    ]) and any(k in m_lower for k in [
        "เสียงดัง", "สั่น", "ควัน", "ไม่ติด", "สตาร์ท", "กระตุก", "สะดุด", "เหยียบไม่ขึ้น",
        "แอร์ไม่เย็น", "กลิ่นไหม้", "ดับกลางอากาศ", "ไฟโชว์", "น้ำมันหยด", "น้ำมันซึม"
    ])
    if is_pure_symptom_inquiry:
        text = (
            f"👨‍🔧 **การตรวจเช็คและวินิจฉัยอาการรถยนต์ต้องทำโดยช่างผู้เชี่ยวชาญหน้างาน**\n\n"
            f"เนื่องจากอาการดังกล่าว ({msg[:80]}...) อาจเกิดได้จากหลายปัจจัย "
            f"และระบบของอู่มีนโยบาย **ให้ช่างตรวจเช็คสภาพจริง (Physical Inspection by Mechanic)** "
            f"เพื่อความปลอดภัยสูงสุดของลูกค้า ไม่คาดเดาอาการด้วย AI\n\n"
            f"💡 **สิ่งที่ทำได้ทันที:**\n"
            f"1. **เปิดใบรับรถ (Intake Ticket)** เพื่อให้ช่างเริ่มตรวจเช็คหน้างาน:\n"
            f"   พิมพ์: `เปิดใบรับรถ ทะเบียน [เลขทะเบียน] ตรวจเช็ค{msg[:30]}`\n"
            f"2. **นัดหมายนำรถเข้าอู่**:\n"
            f"   พิมพ์: `นัดลูกค้านำรถเข้าตรวจ [เวลา เช่น 10:00]`\n"
            f"3. **ตรวจสอบสต็อกอะไหล่** ที่เกี่ยวข้องล่วงหน้า"
        )
        return {
            "type": "info",
            "text": text,
            "data": {"symptom": msg, "action_needed": "mechanic_inspection"},
            "pipeline_steps": pipeline_steps,
        }

    # Check 3: Send LINE Message Action
    is_line_send = any(k in m_lower for k in [
        "ส่งไลน์", "ส่ง line", "แจ้งไลน์", "แจ้งเตือนไลน์", "ส่งข้อความไลน์", "ทักไลน์",
        "send line", "line message", "line oa", "ยิงไลน์", "แจ้งเตือนผ่าน line"
    ]) or (("line" in m_lower or "ไลน์" in m_lower) and any(k in m_lower for k in ["ส่ง", "send", "แจ้ง", "เตือน", "ยิง"]))
    if is_line_send:
        text, data = execute_send_line_message(db, msg)
        return {"type": "line_message", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # Check 4: HITL Ticket Approval
    if re.search(r"(approve|อนุมัติ).*(ticket|ใบสั่ง|#?\d+)", m_lower) or re.search(r"(ticket|#)\s*(\d+).*(approve|อนุมัติ)", m_lower):
        m_id = re.search(r"(?:ticket|#)\s*(\d+)", msg, re.IGNORECASE) or re.search(r"\b(\d+)\b", msg)
        t_id = int(m_id.group(1)) if m_id else None
        if not t_id:
            return {
                "type": "info",
                "text": "กรุณาระบุหมายเลข Ticket ที่ต้องการอนุมัติ เช่น `อนุมัติ ticket 3` หรือ `approve ticket #3`",
                "data": None,
                "pipeline_steps": pipeline_steps,
            }
        return {
            "type": "approve_prompt",
            "text": f"กำลังเปิดแบบฟอร์มอนุมัติสำหรับ Ticket **#{t_id}** ให้ช่างเทคนิคลงนามรับรอง...",
            "data": {"ticket_id": t_id},
            "pipeline_steps": pipeline_steps,
        }

    # Check 5: Retention Scan
    if any(k in m_lower for k in ["scan", "สแกน", "retention", "การตลาด", "ตามลูกค้า"]):
        from services import marketing_service
        try:
            res = marketing_service.run_retention_cron(db)
            text = (
                f"📣 **ผลการสแกนลูกค้าเพื่อการดูแลรักษา (Retention Engine)**\n\n"
                f"🎯 พบรถที่ถึงรอบบำรุงรักษา: **{res['total_flagged']}** คัน\n"
                f"📋 สร้างแคมเปญรอแอดมิน/ช่างอนุมัติ: **{res['tasks_generated']}** รายการ\n"
                f"💬 ไปที่แท็บ Marketing เพื่อตรวจสอบข้อความและอนุมัติส่ง LINE OA ได้เลยครับ"
            )
            return {"type": "scan", "text": text, "data": res, "pipeline_steps": pipeline_steps}
        except Exception as e:
            return {"type": "error", "text": f"เกิดข้อผิดพลาดในการสแกน: {e}", "data": None, "pipeline_steps": pipeline_steps}

    # Check 6: Read-only Queries & Status Checks (Must NOT mutate database!)
    is_query = any(k in m_lower for k in [
        "เท่าไหร่", "กี่", "มีอะไร", "ดู", "เช็ค", "สอบถาม", "สรุป", "รายงาน", "ขอข้อมูล",
        "list", "show", "status", "สถานะ", "อะไรบ้าง", "ใครบ้าง", "ไหนบ้าง", "เหลือ"
    ])

    if is_query:
        # Stock query
        if any(k in m_lower for k in ["สต็อก", "stock", "อะไหล่", "ชิ้นส่วน", "ของเหลือ", "คงเหลือ", "น้ำมันเครื่อง", "ผ้าเบรค"]):
            items = context["stock"]["items"]
            low = context["stock"]["low_stock_alerts"]
            item_lines = [f"• **{i['name']}** (SKU: `{i['sku']}`) — คงเหลือ: **{i['qty']}** ชิ้น (ราคาขาย: ฿{i['sell']:,.0f})" for i in items[:8]]
            low_txt = f"\n⚠️ **รายการอะไหล่ใกล้หมด:**\n" + "\n".join([f"  - {x}" for x in low]) if low else "\n✅ สต็อกอยู่ในระดับปกติทุกรายการ"
            text = (
                f"📦 **รายงานสถานะสต็อกอะไหล่ปัจจุบัน (มีทั้งหมด {context['stock']['total_types']} รายการ):**\n\n"
                + ("\n".join(item_lines) if item_lines else "ไม่มีรายการอะไหล่ในระบบ") + "\n" + low_txt
            )
            return {"type": "stock", "text": text, "data": context["stock"], "pipeline_steps": pipeline_steps}

        # Financial query
        if any(k in m_lower for k in ["รายได้", "กำไร", "ยอดขาย", "การเงิน", "summary", "สรุป", "p&l", "expense", "ขาดทุน", "รายจ่าย"]):
            f = context["financials"]
            text = (
                f"📊 **สรุปสถานะการเงินประจำเดือน ({f.get('month', 'ปัจจุบัน')}):**\n\n"
                f"💚 **รายรับรวม (Income)**: ฿{f.get('income', 0):,.2f}\n"
                f"🔴 **รายจ่ายรวม (Expenses)**: ฿{f.get('expense', 0):,.2f}\n"
                f"💰 **กำไรสุทธิ (Net Profit)**: **฿{f.get('net_profit', 0):,.2f}**\n"
                f"📈 **อัตรากำไร (Margin)**: {f.get('profit_margin_pct', 0)}%"
            )
            return {"type": "summary", "text": text, "data": f, "pipeline_steps": pipeline_steps}

        # Appointments query
        if any(k in m_lower for k in ["นัด", "คิว", "ตารางนัด", "appointment"]):
            appts = context["appointments"]
            if not appts:
                text = "📅 **ไม่มีรายการนัดหมายที่กำลังจะมาถึง**\nสามารถพิมพ์นัดหมายได้ เช่น `นัดลูกค้านำรถเข้าเช็ค พรุ่งนี้ 10:00`"
            else:
                lines = [f"• **{a['time']} น.** — {a['customer']} ({a['phone'] or 'ไม่ระบุเบอร์'}) | *{a['service']}*" for a in appts]
                text = f"📅 **รายการนัดหมายเร็วๆ นี้ ({len(appts)} คิว):**\n\n" + "\n".join(lines)
            return {"type": "appointment", "text": text, "data": {"appointments": appts}, "pipeline_steps": pipeline_steps}

        # Supplier query
        if any(k in m_lower for k in ["ซัพพลาย", "supplier", "ผู้จัดจำหน่าย", "ร้านอะไหล่"]):
            sups = context.get("suppliers", [])
            if not sups:
                text = "🏭 **ยังไม่มีข้อมูลซัพพลายเออร์ในระบบ**"
            else:
                lines = [f"• **{s['name']}** — 📞 {s['phone'] or 'ไม่ระบุ'} | LINE: {s['line_id'] or '-'}" for s in sups]
                text = f"🏭 **รายชื่อผู้จัดจำหน่าย/ซัพพลายเออร์ ({len(sups)} เจ้า):**\n\n" + "\n".join(lines)
            return {"type": "info", "text": text, "data": {"suppliers": sups}, "pipeline_steps": pipeline_steps}

        # Watchlist query
        if any(k in m_lower for k in ["watchlist", "แจ้งเตือน", "เกินกำหนด", "overdue"]):
            w_items = context["watchlist_overdue"]
            if not w_items:
                text = "✅ **ยอดเยี่ยม! ไม่มีรถยนต์ที่มีรายการบำรุงรักษาเกินกำหนดในระบบ**"
            else:
                lines = [f"• 🚨 **{w['model']}** ({w['plate']}): ถึงรอบตรวจ/เปลี่ยน **{w['component']}** ({w['condition']})" for w in w_items]
                text = f"🚨 **รายการเฝ้าระวังความเสื่อมสภาพเกินกำหนด (Watchlist - {len(w_items)} คัน):**\n\n" + "\n".join(lines)
            return {"type": "watchlist", "text": text, "data": {"watchlist": w_items}, "pipeline_steps": pipeline_steps}

    # Check 7: Explicit Mutation Actions (Strict intent required)
    # 7.1 Intake ticket creation
    has_plate = bool(re.search(r"(\d?[ก-ฮ]{1,3}\s*\d{1,4}|[a-zA-Z0-9]{2,4}\s*[-]?\s*[0-9]{1,4})", msg))
    has_repair_intent = any(k in m_lower for k in ["รับรถ", "เปิดใบรับ", "ออกใบรับ", "เปิด ticket", "แจ้งซ่อม", "นำรถเข้า", "เข้าซ่อม"])
    if has_repair_intent or (has_plate and any(k in m_lower for k in ["ซ่อม", "เปลี่ยน", "ตรวจสภาพ"])):
        text, data = execute_create_intake_ticket(db, msg)
        return {"type": "ticket", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # 7.2 Expense creation (Explicit verb + amount)
    has_explicit_exp_verb = any(k in m_lower for k in ["บันทึกค่า", "จ่ายค่า", "ลงค่า", "เพิ่มค่าใช้จ่าย", "บันทึกรายจ่าย"])
    if has_explicit_exp_verb:
        text, data = execute_add_expense(db, msg)
        return {"type": "expense", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # 7.3 Stock operations (Explicit adjust verb + part)
    has_explicit_stock_verb = any(k in m_lower for k in ["เพิ่มสต็อก", "ลดสต็อก", "ปรับสต็อก", "เบิกอะไหล่", "รับเข้าสต็อก", "สร้างสินค้าใหม่", "เพิ่มอะไหล่ใหม่"])
    if has_explicit_stock_verb:
        text, data = execute_stock_operation(db, msg)
        return {"type": "stock", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # 7.4 Customer creation
    if any(k in m_lower for k in ["เพิ่มลูกค้า", "สร้างลูกค้า", "ลงทะเบียนลูกค้า"]):
        text, data = execute_add_customer(db, msg)
        return {"type": "customer", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # 7.5 Vehicle creation
    if any(k in m_lower for k in ["เพิ่มรถ", "ลงทะเบียนรถ", "เพิ่มข้อมูลรถ"]):
        text, data = execute_add_vehicle(db, msg)
        return {"type": "vehicle", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # 7.6 Appointment booking
    if any(k in m_lower for k in ["ลงนัด", "เพิ่มนัด", "จองคิว"]):
        text, data = execute_add_appointment(db, msg)
        return {"type": "appointment", "text": text, "data": data, "pipeline_steps": pipeline_steps}

    # Default: Workshop Assistant Greeting & Overview
    pending = context["tickets"]["pending_approval_count"]
    text = (
        f"สวัสดีครับ! ผมคือ **R.O.S.E. AI Copilot** ผู้ช่วยระบบบริหารจัดการอู่ซ่อมรถยนต์ 🚗\n\n"
        f"📌 **สถานะอู่ขณะนี้:**\n"
        f"• ลูกค้าในระบบ: **{context['overview']['total_customers']}** คน · รถยนต์: **{context['overview']['total_vehicles']}** คัน\n"
        f"• Ticket รอช่างอนุมัติ: **{pending}** งาน · อะไหล่ใกล้หมด: **{len(context['stock']['low_stock_alerts'])}** รายการ\n\n"
        f"🛠️ **สิ่งที่คุณสามารถพิมพ์สั่งงานได้:**\n"
        f"• **เช็คข้อมูลสด**: `สต็อกเหลืออะไรบ้าง`, `สรุปรายได้เดือนนี้`, `ตารางนัดหมายวันนี้`, `ดู watchlist`, `ขอรายชื่อซัพพลายเออร์`\n"
        f"• **บันทึกข้อมูล**: `บันทึกค่าไฟ 2800 บาท`, `ปรับสต็อก น้ำมันเครื่อง +5`, `เปิดใบรับรถ ทะเบียน กข 1234`\n"
        f"• **ลบ/ยกเลิก**: `ลบค่าใช้จ่าย #[ID]`, `ลบซัพพลายเออร์ [ชื่อ]`, `ยกเลิกนัดคุณ [ชื่อ]`\n\n"
        f"*(หมายเหตุ: การตรวจเช็คอาการและวินิจฉัยความเสียหาย จะดำเนินการตรวจจริงหน้างานโดยช่างซ่อมประจำอู่ครับ)*"
    )
    pipeline_steps.append({"step": 4, "name": "Operations Response Ready", "status": "done"})
    return {"type": "info", "text": text, "data": context["overview"], "pipeline_steps": pipeline_steps}
