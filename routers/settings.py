"""
Router: System Settings & External Integrations
═══════════════════════════════════════════════
Handles configuration of AI Providers (Google Gemini, OpenAI),
LINE OA Messaging API, and Google Sheets Sync.
"""
from __future__ import annotations

import os
import time
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from core.dependencies import get_db
from services import ai_service, shop_settings

router = APIRouter()


class SettingsResponse(BaseModel):
    gemini_configured: bool
    gemini_key_preview: Optional[str] = None
    openai_configured: bool
    openai_key_preview: Optional[str] = None
    line_oa_configured: bool
    line_token_preview: Optional[str] = None
    active_ai_provider: str  # "gemini" | "openai" | "local_rose"


class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    line_oa_channel_token: Optional[str] = None


class TestAIRequest(BaseModel):
    provider: str = "gemini"  # "gemini" | "openai"
    api_key: Optional[str] = None


class TestAIResponse(BaseModel):
    ok: bool
    provider: str
    latency_ms: int
    message: str


def _mask(key: Optional[str]) -> Optional[str]:
    if not key or len(key) < 8:
        return None
    return key[:4] + "••••••••" + key[-4:]


def _update_env_file(updates: dict):
    """Write or update keys in .env file safely."""
    env_path = ".env"
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    keys_written = set()
    new_lines = []
    for line in existing_lines:
        matched = False
        for k, v in updates.items():
            if v is not None and (line.strip().startswith(f"{k}=") or line.strip().startswith(f"export {k}=")):
                new_lines.append(f'{k}="{v}"\n')
                keys_written.add(k)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    for k, v in updates.items():
        if v is not None and k not in keys_written:
            new_lines.append(f'{k}="{v}"\n')

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


@router.get("/", response_model=SettingsResponse, summary="Get active configuration status")
def get_settings():
    g_key = ai_service.get_configured_key("GEMINI_API_KEY") or ai_service.get_configured_key("GOOGLE_API_KEY")
    o_key = ai_service.get_configured_key("OPENAI_API_KEY")
    l_token = ai_service.get_configured_key("LINE_OA_CHANNEL_TOKEN")

    active = "local_rose"
    if g_key:
        active = "gemini"
    elif o_key:
        active = "openai"

    is_line_real = bool(l_token and l_token != "MOCK_LINE_TOKEN")

    return SettingsResponse(
        gemini_configured=bool(g_key),
        gemini_key_preview=_mask(g_key),
        openai_configured=bool(o_key),
        openai_key_preview=_mask(o_key),
        line_oa_configured=is_line_real,
        line_token_preview=_mask(l_token) if is_line_real else "MOCK_LINE_TOKEN",
        active_ai_provider=active,
    )


@router.get("/shop", summary="Shop settings shared by every computer")
def get_shop_settings(db: Session = Depends(get_db)) -> Dict[str, str]:
    return shop_settings.get_all(db)


@router.put("/shop", summary="Update shop settings")
def update_shop_settings(updates: Dict[str, Optional[str]], db: Session = Depends(get_db)) -> Dict[str, str]:
    unknown = [k for k in updates if k not in shop_settings.DEFAULTS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"ไม่รู้จักการตั้งค่า: {', '.join(unknown)}")
    if "commission_pct" in updates and updates["commission_pct"] not in (None, ""):
        try:
            pct = float(updates["commission_pct"])
        except ValueError:
            raise HTTPException(status_code=400, detail="% ค่าคอมต้องเป็นตัวเลข")
        if not 0 <= pct <= 100:
            raise HTTPException(status_code=400, detail="% ค่าคอมต้องอยู่ระหว่าง 0-100")
    tax_id = (updates.get("shop_tax_id") or "").replace("-", "").strip()
    if tax_id and not (tax_id.isdigit() and len(tax_id) == 13):
        raise HTTPException(status_code=400, detail="เลขประจำตัวผู้เสียภาษีต้องเป็นตัวเลข 13 หลัก")
    return shop_settings.set_many(db, updates)


@router.post("/", summary="Update system settings & API keys")
def update_settings(req: SettingsUpdateRequest):
    updates = {}
    if req.gemini_api_key is not None:
        val = req.gemini_api_key.strip()
        ai_service.set_runtime_key("GEMINI_API_KEY", val)
        ai_service.set_runtime_key("GOOGLE_API_KEY", val)
        updates["GEMINI_API_KEY"] = val
        updates["GOOGLE_API_KEY"] = val

    if req.openai_api_key is not None:
        val = req.openai_api_key.strip()
        ai_service.set_runtime_key("OPENAI_API_KEY", val)
        updates["OPENAI_API_KEY"] = val

    if req.line_oa_channel_token is not None:
        val = req.line_oa_channel_token.strip()
        ai_service.set_runtime_key("LINE_OA_CHANNEL_TOKEN", val)
        updates["LINE_OA_CHANNEL_TOKEN"] = val

    if updates:
        _update_env_file(updates)

    return {"status": "ok", "message": "ตั้งค่าระบบเรียบร้อยแล้ว", "updated_keys": list(updates.keys())}


@router.post("/test-ai", response_model=TestAIResponse, summary="Test AI Key connection")
async def test_ai_connection(req: TestAIRequest):
    provider = req.provider.lower()
    start_time = time.time()

    if provider == "gemini":
        key = req.api_key or ai_service.get_configured_key("GEMINI_API_KEY") or ai_service.get_configured_key("GOOGLE_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="กรุณาระบุ Gemini API Key ก่อนทดสอบ")
        
        models_to_try = [
            "gemini-flash-lite-latest",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-flash-latest",
            "gemini-2.5-flash",
        ]
        
        payload = {
            "contents": [{"parts": [{"text": "Hello, respond with 'OK'"}]}],
            "generationConfig": {"maxOutputTokens": 50}
        }
        
        last_err = "ไม่สามารถเชื่อมต่อได้"
        last_code = 500
        
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                for model_name in models_to_try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                    res = await client.post(url, json=payload)
                    latency = int((time.time() - start_time) * 1000)
                    if res.status_code == 200:
                        return TestAIResponse(
                            ok=True,
                            provider=f"Google Gemini ({model_name})",
                            latency_ms=latency,
                            message=f"เชื่อมต่อกับ Google Gemini API สำเร็จ! ({model_name}) พร้อมใช้งานเต็มรูปแบบ"
                        )
                    elif res.status_code == 404:
                        last_code = res.status_code
                        last_err = res.text
                        continue  # Try next model
                    else:
                        last_code = res.status_code
                        last_err = res.text
                        break

            latency = int((time.time() - start_time) * 1000)
            return TestAIResponse(
                ok=False,
                provider="Google Gemini",
                latency_ms=latency,
                message=f"เชื่อมต่อไม่สำเร็จ (HTTP {last_code}): {last_err[:150]}"
            )
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            return TestAIResponse(
                ok=False,
                provider="Google Gemini",
                latency_ms=latency,
                message=f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {str(e)}"
            )

    elif provider == "openai":
        key = req.api_key or ai_service.get_configured_key("OPENAI_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="กรุณาระบุ OpenAI API Key ก่อนทดสอบ")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 5,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                latency = int((time.time() - start_time) * 1000)
                if res.status_code == 200:
                    return TestAIResponse(
                        ok=True,
                        provider="OpenAI (GPT-4o-mini)",
                        latency_ms=latency,
                        message="เชื่อมต่อกับ OpenAI API สำเร็จ!"
                    )
                else:
                    return TestAIResponse(
                        ok=False,
                        provider="OpenAI",
                        latency_ms=latency,
                        message=f"เชื่อมต่อไม่สำเร็จ (HTTP {res.status_code}): {res.text[:150]}"
                    )
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            return TestAIResponse(
                ok=False,
                provider="OpenAI",
                latency_ms=latency,
                message=f"เกิดข้อผิดพลาด: {str(e)}"
            )

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


class TestLineRequest(BaseModel):
    token: Optional[str] = None
    user_id: Optional[str] = None


class TestLineResponse(BaseModel):
    ok: bool
    bot_name: Optional[str] = None
    basic_id: Optional[str] = None
    message: str


@router.post("/test-line", response_model=TestLineResponse, summary="Test LINE OA Connection")
async def test_line_connection(req: TestLineRequest):
    token = req.token or ai_service.get_configured_key("LINE_OA_CHANNEL_TOKEN")
    if not token or token == "MOCK_LINE_TOKEN":
        raise HTTPException(status_code=400, detail="กรุณาระบุ LINE OA Channel Access Token ก่อนทดสอบ")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get("https://api.line.me/v2/bot/info", headers=headers)
            if res.status_code != 200:
                return TestLineResponse(
                    ok=False,
                    message=f"เชื่อมต่อไม่สำเร็จ (HTTP {res.status_code}): {res.text[:150]}"
                )

            info = res.json()
            bot_name = info.get("displayName", "Bot")
            basic_id = info.get("basicId", "")

            if req.user_id and req.user_id.strip():
                push_url = "https://api.line.me/v2/bot/message/push"
                push_payload = {
                    "to": req.user_id.strip(),
                    "messages": [
                        {
                            "type": "text",
                            "text": "🚗 [Auto Service — Command Center]\nการเชื่อมต่อ LINE OA สำเร็จเรียบร้อยแล้วครับ! พร้อมส่งการแจ้งเตือนงานซ่อมและโปรโมชั่น"
                        }
                    ]
                }
                push_res = await client.post(push_url, headers=headers, json=push_payload)
                if push_res.status_code == 200:
                    return TestLineResponse(
                        ok=True,
                        bot_name=bot_name,
                        basic_id=basic_id,
                        message=f"เชื่อมต่อสำเร็จ! ชื่อบอท: {bot_name} ({basic_id}) และส่งข้อความทดสอบไปยัง {req.user_id} เรียบร้อยแล้ว 🎉"
                    )
                else:
                    return TestLineResponse(
                        ok=True,
                        bot_name=bot_name,
                        basic_id=basic_id,
                        message=f"เชื่อมต่อบอทสำเร็จ ({bot_name} {basic_id}) แต่ส่งข้อความหา {req.user_id} ไม่ผ่าน (HTTP {push_res.status_code}: ตรวจสอบว่าผู้ใช้เพิ่มเพื่อนกับบอทแล้วหรือยัง)"
                    )

            return TestLineResponse(
                ok=True,
                bot_name=bot_name,
                basic_id=basic_id,
                message=f"เชื่อมต่อ LINE OA สำเร็จ! ชื่อบัญชี: {bot_name} (LINE ID: {basic_id}) พร้อมใช้งาน 🟢"
            )
    except Exception as e:
        return TestLineResponse(
            ok=False,
            message=f"เกิดข้อผิดพลาดในการเชื่อมต่อ LINE API: {str(e)}"
        )

