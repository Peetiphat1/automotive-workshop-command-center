"""
Shop settings shared by every computer (stored in the app_settings table).
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from models.db_models import AppSetting

# Known keys and their defaults. Values are stored as text.
DEFAULTS: Dict[str, str] = {
    "shop_name": "Zero Garage",
    "shop_phone": "",
    "shop_address": "",
    "shop_tax_id": "",             # เลขประจำตัวผู้เสียภาษี 13 หลัก
    "vat_registered": "0",         # "1" = print tax invoice with VAT 7%
    "vat_rate": "7",
    "commission_pct": "10",        # mechanic commission on labour
    "backup_extra_dir": "",        # extra folder for the daily backup copy (USB / Google Drive)
    "public_base_url": "",         # e.g. https://myshop.example.com — used in customer LINE links
}


def get_setting(db: Session, key: str, default: Optional[str] = None) -> str:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row and row.value is not None:
        return row.value
    return default if default is not None else DEFAULTS.get(key, "")


def get_all(db: Session) -> Dict[str, str]:
    values = dict(DEFAULTS)
    for row in db.query(AppSetting).all():
        if row.value is not None:
            values[row.key] = row.value
    return values


def set_many(db: Session, updates: Dict[str, Optional[str]]) -> Dict[str, str]:
    for key, value in updates.items():
        if key not in DEFAULTS or value is None:
            continue
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = str(value).strip()
        else:
            db.add(AppSetting(key=key, value=str(value).strip()))
    db.commit()
    return get_all(db)


def get_float(db: Session, key: str) -> float:
    try:
        return float(get_setting(db, key))
    except (TypeError, ValueError):
        return float(DEFAULTS.get(key) or 0)
