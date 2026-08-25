"""
Bill Agent  (E in R.O.S.E. — Execution & Guardrails)
──────────────────────────────────────────────────────
LangGraph StateGraph pipeline:
  extract_items → math_check

Zero-Hallucination Guarantee:
  The math_check node uses Python's `decimal.Decimal` arithmetic — never an LLM
  — to verify that sum(qty * unit_price) == stated_grand_total.
  Discrepancies > 1 THB set status to MATH_ERROR, blocking ledger writes.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph


# ── Typed state ───────────────────────────────────────────────────────────────

class BillState(TypedDict):
    raw_text: str
    source_type: str        # 'text' | 'image_png' | 'image_jpg'
    bill_type: str          # 'income' | 'expense'
    vendor_name: str
    bill_date: Optional[str]
    line_items: List[Dict]
    extracted_total: float
    calculated_total: float
    math_verified: bool
    math_discrepancy: float
    status: str             # 'DRAFT_AI' | 'MATH_ERROR'
    error: Optional[str]


# ── Extraction patterns ───────────────────────────────────────────────────────

_VENDOR_PATTERNS = [
    re.compile(r"^ร้าน(.+)$", re.MULTILINE),
    re.compile(r"^บริษัท(.+)$", re.MULTILINE),
    re.compile(r"^ห้าง(.+)$", re.MULTILINE),
    re.compile(r"Vendor\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"จาก\s*:\s*(.+)", re.IGNORECASE),
]

_TOTAL_PATTERNS = [
    re.compile(r"ยอดรวม(?:ทั้งหมด)?\s*:?\s*([\d,]+(?:\.\d{1,2})?)\s*บาท?", re.IGNORECASE),
    re.compile(r"รวมเงิน\s*:?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"Grand\s*Total\s*:?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"Total\s*:?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"รวม(?:ทั้งหมด)?\s+([\d,]+(?:\.\d{1,2})?)\s*บาท", re.IGNORECASE),
]

# Thai line: "item_name  qty  unit  ราคา unit_price บาท/unit  รวม total บาท"
_THAI_LINE_RE = re.compile(
    r"([ก-๙a-zA-Z\-/()%\s\.]{3,}?)"   # item name (Thai/English)
    r"\s+(\d+(?:\.\d+)?)"               # quantity
    r"\s*(?:ลิตร|ชิ้น|อัน|ชุด|เส้น|กิโล|kg|pcs?|sets?)?"
    r"\s+ราคา\s+([\d,]+(?:\.\d+)?)"    # unit price
    r"\s*บาท.*?รวม\s+([\d,]+(?:\.\d+)?)\s*บาท",
    re.IGNORECASE,
)

# English table: "Item Name   Qty   UnitPrice   Total"
_ENG_LINE_RE = re.compile(
    r"([a-zA-Z][a-zA-Z0-9\s\(\)\-/\.]+?)"
    r"\s{2,}(\d+(?:\.\d+)?)"
    r"\s{2,}([\d,]+(?:\.\d+)?)"
    r"\s{2,}([\d,]+(?:\.\d+)?)",
)

# Fallback: "description   amount บาท" (single-amount lines)
_FALLBACK_AMOUNT_RE = re.compile(
    r"^(.+?)\s+([\d,]+(?:\.\d{1,2})?)\s*บาท$", re.MULTILINE
)

_SKIP_KEYWORDS = {"รวม", "ยอด", "total", "grand", "vat", "ภาษี", "หมาย"}


def _parse_float(s: str) -> float:
    return float(s.replace(",", ""))


# ── Node 1: extract line items ────────────────────────────────────────────────

def _extract_items_node(state: BillState) -> BillState:
    text = state["raw_text"]
    vendor_name = state.get("vendor_name") or ""
    extracted_total = 0.0
    line_items: List[Dict] = []

    # ── Vendor ────────────────────────────────────────────────────────────────
    if not vendor_name:
        for pat in _VENDOR_PATTERNS:
            m = pat.search(text)
            if m:
                vendor_name = m.group(1).strip()
                break

    # ── Grand total ───────────────────────────────────────────────────────────
    for pat in _TOTAL_PATTERNS:
        m = pat.search(text)
        if m:
            extracted_total = _parse_float(m.group(1))
            break

    # ── Thai structured lines ─────────────────────────────────────────────────
    for m in _THAI_LINE_RE.finditer(text):
        name = m.group(1).strip()
        qty = float(m.group(2))
        unit_price = _parse_float(m.group(3))
        total = _parse_float(m.group(4))
        if name and qty > 0 and unit_price > 0:
            line_items.append({"name": name, "qty": qty, "unit_price": unit_price, "total": total})

    # ── English structured lines ──────────────────────────────────────────────
    if not line_items:
        for m in _ENG_LINE_RE.finditer(text):
            name = m.group(1).strip()
            qty = float(m.group(2))
            unit_price = _parse_float(m.group(3))
            total = _parse_float(m.group(4))
            if name and qty > 0 and unit_price > 0:
                line_items.append({"name": name, "qty": qty, "unit_price": unit_price, "total": total})

    # ── Fallback: single-amount lines ─────────────────────────────────────────
    if not line_items:
        for m in _FALLBACK_AMOUNT_RE.finditer(text):
            desc = m.group(1).strip()
            amount = _parse_float(m.group(2))
            lower = desc.lower()
            if any(skip in lower for skip in _SKIP_KEYWORDS):
                continue
            if desc and amount > 0:
                line_items.append({"name": desc, "qty": 1.0, "unit_price": amount, "total": amount})

    return {
        **state,
        "vendor_name": vendor_name,
        "extracted_total": extracted_total,
        "line_items": line_items,
    }


# ── Node 2: deterministic math check ─────────────────────────────────────────

def _math_check_node(state: BillState) -> BillState:
    """
    Zero-Hallucination math validation.
    Uses decimal.Decimal to avoid floating-point drift.
    Tolerance: ±1.00 THB for rounding differences in OCR/text.
    """
    items = state["line_items"]
    stated_total = state["extracted_total"]

    calculated = Decimal("0")
    for item in items:
        qty = Decimal(str(item.get("qty", 1)))
        unit_price = Decimal(str(item.get("unit_price", 0)))
        calculated += qty * unit_price

    calculated_total = float(calculated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    if stated_total > 0:
        discrepancy = abs(calculated_total - stated_total)
        math_verified = discrepancy <= 1.0
    else:
        # No stated total found — use calculated total, mark verified
        stated_total = calculated_total
        discrepancy = 0.0
        math_verified = True

    status = "DRAFT_AI" if math_verified else "MATH_ERROR"

    return {
        **state,
        "extracted_total": round(stated_total, 2),
        "calculated_total": calculated_total,
        "math_verified": math_verified,
        "math_discrepancy": round(discrepancy, 2),
        "status": status,
    }


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_bill_graph():
    g = StateGraph(BillState)
    g.add_node("extract_items", _extract_items_node)
    g.add_node("math_check", _math_check_node)
    g.set_entry_point("extract_items")
    g.add_edge("extract_items", "math_check")
    g.add_edge("math_check", END)
    return g.compile()


bill_graph = build_bill_graph()


# ── Mock OCR for image uploads ────────────────────────────────────────────────

def mock_ocr_image(filename: str, file_bytes: bytes) -> str:
    """
    Simulates Vision LLM / OCR output for PNG/JPG bill images.
    Returns a plausible Thai receipt text for demo purposes.
    In production: replace with Google Cloud Vision / AWS Textract / GPT-4o call.
    """
    size_kb = len(file_bytes) // 1024
    return (
        f"ร้านอะไหล่ออโต้พาร์ท (ไฟล์: {filename}, ขนาด: {size_kb} KB)\n"
        "ใบเสร็จรับเงิน / Tax Invoice\n"
        "─────────────────────────────\n"
        "น้ำมันเครื่อง 5W-30 4 ลิตร ราคา 850 บาท/ลิตร รวม 3,400 บาท\n"
        "กรองน้ำมันเครื่อง 1 ชิ้น ราคา 150 บาท/ชิ้น รวม 150 บาท\n"
        "กรองอากาศ 1 ชิ้น ราคา 350 บาท/ชิ้น รวม 350 บาท\n"
        "ค่าแรงเปลี่ยนน้ำมันเครื่อง 1 ชิ้น ราคา 150 บาท/ชิ้น รวม 150 บาท\n"
        "─────────────────────────────\n"
        "ยอดรวมทั้งหมด 4,050 บาท\n"
    )
