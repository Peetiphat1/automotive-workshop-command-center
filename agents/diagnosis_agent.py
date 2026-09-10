"""
Diagnosis Agent  (O in R.O.S.E. — Orchestrator)
────────────────────────────────────────────────
LangGraph StateGraph pipeline:
  parse_symptoms → diagnose → estimate_cost → apply_guardrail

Guardrail (E): total > 3,000 THB  OR  heavy repair  → PENDING_MECHANIC_APPROVAL
"""
from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from core.config import settings


# ── Typed state ───────────────────────────────────────────────────────────────

class DiagnosisState(TypedDict):
    raw_input: str
    customer_id: Optional[int]
    vehicle_plate: Optional[str]
    car_model: str
    mileage: int
    symptoms: List[str]
    diagnosed_issues: List[Dict]
    recommended_parts: List[str]
    line_items: List[Dict]
    estimated_labor_cost: float
    estimated_parts_cost: float
    total_estimated_cost: float
    requires_heavy_repair: bool
    status: str
    guardrail_reason: str
    error: Optional[str]
    parts_db: List[Dict]   # injected by service layer from DB


# ── Knowledge base (mock AI / expert system) ──────────────────────────────────
#   Each entry maps a Thai symptom keyword → diagnosis + repair prescription.
#   is_heavy=True triggers the HITL gate regardless of cost.

_KNOWLEDGE_BASE: Dict[str, Dict] = {
    "เสียงดังจากเบรค": dict(
        issue="ผ้าเบรคหน้าสึกหรอ",
        severity="high",
        parts=["Brake Pad (Front)"],
        labor_cost=500.0,
        is_heavy=False,
    ),
    "ผ้าเบรคสึก": dict(
        issue="ผ้าเบรคหน้าและหลังสึกหรอ จำเป็นต้องเปลี่ยน",
        severity="high",
        parts=["Brake Pad (Front)", "Brake Pad (Rear)"],
        labor_cost=800.0,
        is_heavy=False,
    ),
    "เบรคไม่อยู่": dict(
        issue="ระบบเบรคมีปัญหา — ตรวจน้ำมันเบรคและผ้าเบรค",
        severity="critical",
        parts=["Brake Pad (Front)", "Brake Fluid"],
        labor_cost=600.0,
        is_heavy=False,
    ),
    "เสียงดัง": dict(
        issue="อาจมีชิ้นส่วนหลวม หรือผ้าเบรคสึก",
        severity="medium",
        parts=["Brake Pad (Front)"],
        labor_cost=300.0,
        is_heavy=False,
    ),
    "เกียร์สะดุด": dict(
        issue="น้ำมันเกียร์เสื่อมสภาพ หรือชุดเกียร์มีปัญหา",
        severity="high",
        parts=["Transmission Fluid"],
        labor_cost=2500.0,
        is_heavy=True,
    ),
    "เกียร์ไม่เข้า": dict(
        issue="ชุดเกียร์ต้องตรวจเช็คเชิงลึก",
        severity="high",
        parts=["Transmission Fluid"],
        labor_cost=2500.0,
        is_heavy=True,
    ),
    "น้ำมันรั่ว": dict(
        issue="ซีลน้ำมันเสื่อมสภาพ — ต้องเปลี่ยนซีลและน้ำมัน",
        severity="high",
        parts=["Engine Oil 5W-30 (4L)", "Oil Filter"],
        labor_cost=1200.0,
        is_heavy=True,
    ),
    "ควันดำ": dict(
        issue="เครื่องยนต์เผาไหม้ไม่สมบูรณ์ — ตรวจหัวเทียนและกรองอากาศ",
        severity="high",
        parts=["Spark Plug (4 pcs)", "Air Filter"],
        labor_cost=800.0,
        is_heavy=False,
    ),
    "แบตหมด": dict(
        issue="แบตเตอรี่หมดอายุหรือประจุไม่ได้",
        severity="medium",
        parts=["Car Battery 75Ah"],
        labor_cost=200.0,
        is_heavy=False,
    ),
    "ยางแบน": dict(
        issue="ยางรั่วหรือสึกหรอ — ต้องเปลี่ยนยาง",
        severity="medium",
        parts=["Tire (195/65R15)"],
        labor_cost=400.0,
        is_heavy=False,
    ),
    "ร้อน": dict(
        issue="ระบบระบายความร้อนมีปัญหา — ตรวจหม้อน้ำและน้ำยาหม้อน้ำ",
        severity="critical",
        parts=["Coolant (1L)", "Radiator"],
        labor_cost=3500.0,
        is_heavy=True,
    ),
    "สั่น": dict(
        issue="ล้อไม่สมดุลหรือช่วงล่างเสื่อม",
        severity="medium",
        parts=["Tire (195/65R15)"],
        labor_cost=600.0,
        is_heavy=False,
    ),
    "ไม่ติด": dict(
        issue="ระบบจุดระเบิดหรือแบตเตอรี่มีปัญหา",
        severity="high",
        parts=["Car Battery 75Ah", "Spark Plug (4 pcs)"],
        labor_cost=500.0,
        is_heavy=False,
    ),
    "น้ำมันเครื่อง": dict(
        issue="ถึงรอบเปลี่ยนน้ำมันเครื่อง",
        severity="low",
        parts=["Engine Oil 5W-30 (4L)", "Oil Filter"],
        labor_cost=150.0,
        is_heavy=False,
    ),
    "ช่วงล่างเสีย": dict(
        issue="ช่วงล่างเสื่อมสภาพ — ต้องตรวจเช็คเชิงลึก",
        severity="high",
        parts=[],
        labor_cost=1500.0,
        is_heavy=True,
    ),
}

_DEFAULT_DIAGNOSIS = dict(
    issue="ต้องตรวจเช็คเพิ่มเติมโดยช่าง",
    severity="unknown",
    parts=[],
    labor_cost=300.0,
    is_heavy=False,
)


# ── Node 1: parse symptoms ────────────────────────────────────────────────────

def _parse_symptoms_node(state: DiagnosisState) -> DiagnosisState:
    text = state["raw_input"]
    found = [s for s in _KNOWLEDGE_BASE if s in text]
    # Generic fallback: common action words
    if not found:
        fallback_map = {
            "เปลี่ยน": "น้ำมันเครื่อง",
            "ตรวจ": "น้ำมันเครื่อง",
            "เช็ค": "น้ำมันเครื่อง",
        }
        for kw, symptom in fallback_map.items():
            if kw in text:
                found.append(symptom)
                break

    if not found:
        found = ["ตรวจเช็คทั่วไป"]

    return {**state, "symptoms": found}


# ── Node 2: diagnose ──────────────────────────────────────────────────────────

def _diagnose_node(state: DiagnosisState) -> DiagnosisState:
    # If line items are already provided (e.g. from mechanic paper sheet or direct input), preserve them
    if state.get("line_items"):
        return state

    # Otherwise, symptoms are noted but NO costs or diagnoses are auto-generated by AI
    text = state["raw_input"]
    return {
        **state,
        "diagnosed_issues": [{"symptom": text, "issue": "รอช่างผู้เชี่ยวชาญเข้าตรวจเช็คสภาพรถ", "severity": "pending"}],
        "recommended_parts": [],
        "requires_heavy_repair": False,
    }


# ── Node 3: estimate cost ─────────────────────────────────────────────────────

def _estimate_cost_node(state: DiagnosisState) -> DiagnosisState:
    # If explicit line items exist (e.g., OCR / mechanic entry), compute exact sum from them
    existing_items = state.get("line_items", [])
    if existing_items:
        labor = sum(item.get("total", 0) for item in existing_items if item.get("type") == "labor")
        parts = sum(item.get("total", 0) for item in existing_items if item.get("type") == "part")
        total = labor + parts
        return {
            **state,
            "estimated_labor_cost": labor,
            "estimated_parts_cost": parts,
            "total_estimated_cost": total,
        }

    # Prohibit AI auto-estimating costs. Leave total at 0.0 for mechanic review.
    return {
        **state,
        "line_items": [],
        "estimated_labor_cost": 0.0,
        "estimated_parts_cost": 0.0,
        "total_estimated_cost": 0.0,
    }


# ── Node 4: guardrail gate ────────────────────────────────────────────────────


def _guardrail_node(state: DiagnosisState) -> DiagnosisState:
    threshold = settings.QUOTE_APPROVAL_THRESHOLD_THB
    total = state["total_estimated_cost"]
    is_heavy = state["requires_heavy_repair"]

    reasons = []
    if total > threshold:
        reasons.append(f"ราคาประเมิน {total:,.0f} บาท เกิน {threshold:,.0f} บาท")
    if is_heavy:
        reasons.append("งานซ่อมหนัก (เกียร์/เครื่องยนต์/ระบบส่งกำลัง)")

    status = "PENDING_MECHANIC_APPROVAL"
    if reasons:
        reason_str = " | ".join(reasons)
    else:
        reason_str = "ผ่านเกณฑ์ราคาอัตโนมัติ"

    return {**state, "status": status, "guardrail_reason": reason_str}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_diagnosis_graph():
    g = StateGraph(DiagnosisState)
    g.add_node("parse_symptoms", _parse_symptoms_node)
    g.add_node("diagnose", _diagnose_node)
    g.add_node("estimate_cost", _estimate_cost_node)
    g.add_node("apply_guardrail", _guardrail_node)

    g.set_entry_point("parse_symptoms")
    g.add_edge("parse_symptoms", "diagnose")
    g.add_edge("diagnose", "estimate_cost")
    g.add_edge("estimate_cost", "apply_guardrail")
    g.add_edge("apply_guardrail", END)

    return g.compile()


diagnosis_graph = build_diagnosis_graph()
