"""
Router: Backup, Data Export & Device Transfer
═════════════════════════════════════════════
Endpoints for exporting data to move to other devices,
and importing backups with automated safety points.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from core.dependencies import get_db
from services import backup_service

router = APIRouter()


class LocalRestoreRequest(BaseModel):
    filename: str


@router.get("/stats", summary="Get database size and row statistics")
def get_backup_stats(db: Session = Depends(get_db)):
    """Returns row counts of all 15 workshop tables, DB size, and list of safety backups."""
    try:
        return backup_service.get_backup_stats(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการดึงสถิติ: {str(e)}")


@router.get("/export-db", summary="Export complete SQLite database file (.db)")
def export_database():
    """
    Performs an atomic SQLite online backup and sends the resulting .db file
    as a download. The user can move this file to another device running this software.
    """
    try:
        temp_path, filename = backup_service.export_sqlite_database()
        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            background=BackgroundTask(os.remove, temp_path),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถส่งออกฐานข้อมูลได้: {str(e)}")


@router.get("/export-json", summary="Export all tables as JSON data")
def export_json(
    shop_name: Optional[str] = Query(None),
    shop_phone: Optional[str] = Query(None),
    shop_address: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Exports all records across 15 workshop tables and shop profile into a single JSON file.
    Ideal for inspection, external analytics, or cross-platform migrations.
    """
    try:
        shop_profile = {}
        if shop_name:
            shop_profile["shop_name"] = shop_name
        if shop_phone:
            shop_profile["shop_phone"] = shop_phone
        if shop_address:
            shop_profile["shop_address"] = shop_address

        data = backup_service.export_json_data(db, shop_profile)
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"workshop_data_{timestamp}.json"

        return Response(
            content=json_bytes,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถส่งออก JSON ได้: {str(e)}")


@router.post("/import-db", summary="Import and restore SQLite database file (.db)")
async def import_database(file: UploadFile = File(...)):
    """
    Upload a .db or .sqlite backup file to restore into this system.
    Automatically creates a safety backup of the current database before restoring.
    """
    if not file.filename.lower().endswith((".db", ".sqlite", ".sqlite3")):
        raise HTTPException(
            status_code=400,
            detail="ไฟล์ต้องเป็นนามสกุล .db หรือ .sqlite เท่านั้น",
        )

    try:
        content = await file.read()
        result = backup_service.import_sqlite_database(content, file.filename)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการนำเข้าฐานข้อมูล: {str(e)}")


@router.post("/import-json", summary="Import data from JSON backup file")
async def import_json(
    file: Optional[UploadFile] = File(None),
    mode: str = Form("replace"),  # "replace" or "merge"
    db: Session = Depends(get_db),
):
    """
    Upload a .json backup file to restore or merge into this system.
    Options for mode: 'replace' (wipe and restore) or 'merge' (append/upsert).
    Automatically creates a safety backup before applying changes.
    """
    if not file:
        raise HTTPException(status_code=400, detail="กรุณาเลือกไฟล์ JSON ที่ต้องการนำเข้า")

    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="ไฟล์ต้องเป็นนามสกุล .json เท่านั้น")

    try:
        content = await file.read()
        payload = json.loads(content.decode("utf-8"))
        result = backup_service.import_json_data(db, payload, mode=mode)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการนำเข้า JSON: {str(e)}")


@router.post("/restore-local", summary="Restore from local safety backup")
def restore_local(req: LocalRestoreRequest):
    """Restore database from a safety backup file in the backups/ folder."""
    try:
        return backup_service.restore_from_local_backup(req.filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถกู้คืนข้อมูลได้: {str(e)}")


@router.delete("/backups/{filename}", summary="Delete an old safety backup")
def delete_backup(filename: str):
    """Delete a safety backup file from the backups/ folder."""
    success = backup_service.delete_local_backup(filename)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์สำรองข้อมูล")
    return {"ok": True, "message": f"ลบไฟล์ {filename} เรียบร้อยแล้ว"}


@router.post("/wipe-all-data", summary="Wipe all workshop data with automated safety backup")
def wipe_all_data(db: Session = Depends(get_db)):
    """
    Completely wipes all records from all 15 tables.
    Automatically generates a timestamped safety backup in backups/ first.
    """
    try:
        return backup_service.wipe_all_data(db, create_safety=True)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการล้างข้อมูล: {str(e)}")


@router.get("/daily-status", summary="Automatic daily backup status")
def daily_backup_status(db: Session = Depends(get_db)):
    from services import shop_settings
    status = backup_service.get_daily_backup_status()
    status["extra_dir"] = shop_settings.get_setting(db, "backup_extra_dir")
    return status


@router.post("/run-daily", summary="Make today's backup now (and copy it to the extra folder)")
def run_daily_backup_now(db: Session = Depends(get_db)):
    from services import shop_settings
    extra = shop_settings.get_setting(db, "backup_extra_dir") or None
    result = backup_service.run_daily_backup(extra, force=True)
    if result.get("error") and not result.get("created"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result
