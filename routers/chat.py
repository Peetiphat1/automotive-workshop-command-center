"""
Router: Chat Command Center
═══════════════════════════
Handles natural language commands from the chat UI and routes them
to the AI Service, which performs live DB RAG, executes operational actions,
and strictly enforces that physical car diagnostics are done by mechanics.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import get_db
from services import ai_service

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = ""
    image_data: Optional[str] = None  # Base64 data URI e.g. "data:image/jpeg;base64,..."
    image_name: Optional[str] = None  # Original filename


class ChatResponse(BaseModel):
    type: str          # "ticket" | "bill" | "watchlist" | "summary" | "scan" | "approve_prompt" | "stock" | "expense" | "appointment" | "llm" | "error" | "info"
    text: str          # Human-readable response message
    data: Optional[Dict[str, Any]] = None
    pipeline_steps: Optional[List[Dict[str, Any]]] = None


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse, summary="Chat command endpoint")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    msg = (req.message or "").strip()
    if not msg and not req.image_data:
        return ChatResponse(
            type="error",
            text="กรุณาพิมพ์ข้อความหรือแนบรูปภาพครับ",
            pipeline_steps=[{"step": 1, "name": "Empty Input", "status": "error"}]
        )

    try:
        res = await ai_service.process_chat_message(
            db=db,
            user_msg=msg,
            image_data=req.image_data,
            image_name=req.image_name,
        )
        return ChatResponse(
            type=res.get("type", "info"),
            text=res.get("text", ""),
            data=res.get("data"),
            pipeline_steps=res.get("pipeline_steps"),
        )
    except Exception as e:
        return ChatResponse(
            type="error",
            text=f"❌ เกิดข้อผิดพลาดในการประมวลผล: {str(e)}",
            pipeline_steps=[{"step": 1, "name": "Processing Error", "status": "error"}]
        )
