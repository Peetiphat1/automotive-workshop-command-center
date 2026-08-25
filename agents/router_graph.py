"""
Router & Intake Graph  (R in R.O.S.E.)
─────────────────────────────────────
LangGraph StateGraph that:
  1. Classifies the intent of incoming Thai/English text.
  2. Extracts key entities (car brand/model, plate, mileage, phone, symptoms).
  3. Returns a routing decision for the orchestrator.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph


# ── Typed state ───────────────────────────────────────────────────────────────

class RouterState(TypedDict):
    raw_input: str
    intent: str              # 'ticket' | 'billing' | 'inquiry' | 'marketing'
    entities: Dict
    confidence: float
    routing_path: str
    error: Optional[str]


# ── Intent keyword maps ───────────────────────────────────────────────────────

_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "ticket": [
        "ซ่อม", "เสีย", "ผ้าเบรค", "เกียร์", "เครื่อง", "น้ำมัน", "ตรวจ", "เช็ค",
        "ยาง", "แบตเตอรี่", "ไฟ", "เบรค", "ช่วงล่าง", "คลัตช์", "อาการ", "รั่ว",
        "ร้อน", "สั่น", "ควัน", "เสียงดัง", "ไม่ติด", "repair", "fix", "check",
    ],
    "billing": [
        "ใบเสร็จ", "ค่าใช้จ่าย", "ราคา", "บิล", "จ่าย", "ค่าซ่อม", "ค่าอะไหล่",
        "รวม", "บาท", "bill", "receipt", "invoice", "expense", "cost",
    ],
    "inquiry": [
        "สอบถาม", "ถาม", "รายงาน", "สรุป", "ประวัติ", "ข้อมูล", "ยอด",
        "report", "summary", "history", "profile",
    ],
    "marketing": [
        "ส่งข้อความ", "แจ้งเตือน", "โปรโมชั่น", "ลูกค้า", "LINE", "ส่ง",
        "campaign", "notify", "promotion",
    ],
}

_CAR_BRANDS = [
    "Toyota", "Honda", "Isuzu", "Mazda", "Nissan", "Ford", "Mitsubishi",
    "Suzuki", "Yamaha", "Kawasaki", "BMW", "Mercedes", "Chevrolet", "Hyundai",
    "Kia", "Subaru", "Jeep",
]

_THAI_PLATE_RE = re.compile(
    r"[กขคงจฉชซญดตถทธนบปผฝพฟภมยรลวศษสหอฮ]{1,2}\s?\d{1,4}(?:\s?[ก-ฮ]+)?",
)
_MILEAGE_RE = re.compile(r"(\d[\d,]{2,})\s*(?:กม\.?|km\.?|กิโล)", re.IGNORECASE)
_PHONE_RE = re.compile(r"0[6-9]\d{8}")

_SYMPTOM_KEYWORDS = [
    "เสียงดัง", "สั่น", "รั่ว", "ร้อน", "ไม่ติด", "เบรคไม่อยู่",
    "เกียร์สะดุด", "ผ้าเบรคสึก", "น้ำมันรั่ว", "ควันดำ", "แบตหมด",
    "ยางแบน", "ช่วงล่างเสีย", "เสียงดังจากเบรค", "เกียร์ไม่เข้า",
]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def _classify_intent_node(state: RouterState) -> RouterState:
    """Keyword-frequency intent classifier."""
    text = state["raw_input"].lower()
    scores: Dict[str, int] = {}

    for intent, keywords in _INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for kw in keywords if kw.lower() in text)

    best_intent = max(scores, key=lambda k: scores[k])
    total = sum(scores.values()) or 1
    confidence = round(scores[best_intent] / total, 2)

    if scores[best_intent] == 0:
        best_intent = "inquiry"
        confidence = 0.5

    return {**state, "intent": best_intent, "confidence": confidence}


def _extract_entities_node(state: RouterState) -> RouterState:
    """Regex + keyword entity extractor (no LLM needed)."""
    text = state["raw_input"]
    entities: Dict = {}

    # Car brand & model
    for brand in _CAR_BRANDS:
        if brand.lower() in text.lower():
            entities["car_brand"] = brand
            m = re.search(rf"{brand}\s+(\S+)", text, re.IGNORECASE)
            if m:
                entities["car_model"] = f"{brand} {m.group(1)}"
            break

    # Plate number
    plate_m = _THAI_PLATE_RE.search(text)
    if plate_m:
        entities["plate"] = plate_m.group(0).strip()

    # Mileage
    mil_m = _MILEAGE_RE.search(text)
    if mil_m:
        entities["mileage"] = int(mil_m.group(1).replace(",", ""))

    # Phone number
    phone_m = _PHONE_RE.search(text)
    if phone_m:
        entities["phone"] = phone_m.group(0)

    # Symptoms
    found = [s for s in _SYMPTOM_KEYWORDS if s in text]
    if found:
        entities["symptoms"] = found

    routing_path = f"route_to_{state['intent']}"
    return {**state, "entities": entities, "routing_path": routing_path}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_router_graph():
    g = StateGraph(RouterState)
    g.add_node("classify_intent", _classify_intent_node)
    g.add_node("extract_entities", _extract_entities_node)
    g.set_entry_point("classify_intent")
    g.add_edge("classify_intent", "extract_entities")
    g.add_edge("extract_entities", END)
    return g.compile()


router_graph = build_router_graph()
