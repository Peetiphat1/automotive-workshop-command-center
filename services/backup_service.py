"""
Service: Data Backup, Export & Device Transfer
══════════════════════════════════════════════
Supports:
1. Full SQLite Database Export & Import (.db) with native online backup
2. Universal JSON Data Export & Import (.json) with all 15 tables
3. Automated pre-import safety backups & restore
4. Schema validation and integrity checks
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from core.config import settings
from core.database import engine
from models.db_models import (
    Appointment, Customer, Expense, FinanceBill, LedgerEntry,
    MarketingTask, PartsCatalog, PurchaseBill, ServiceTicket,
    StockHistory, StockItem, Supplier, Vehicle, VehicleHealthWatchlist,
    WorkOrder, Payment, TicketPhoto, AppSetting,
)

logger = logging.getLogger("workshop.backup")

BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))
NO_SEED_FLAG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".no_seed"))

# Order of tables for dependency-safe operations
TABLE_MODELS = [
    ("suppliers", Supplier),
    ("parts_catalog", PartsCatalog),
    ("stock_items", StockItem),
    ("customers", Customer),
    ("vehicles", Vehicle),
    ("vehicle_health_watchlist", VehicleHealthWatchlist),
    ("appointments", Appointment),
    ("expenses", Expense),
    ("finance_bills", FinanceBill),
    ("ledger_entries", LedgerEntry),
    ("purchase_bills", PurchaseBill),
    ("stock_history", StockHistory),
    ("service_tickets", ServiceTicket),
    ("work_orders", WorkOrder),
    ("marketing_tasks", MarketingTask),
    ("payments", Payment),
    ("ticket_photos", TicketPhoto),
    ("app_settings", AppSetting),
]

# Reverse order for child-first deletion
REVERSE_TABLE_MODELS = list(reversed(TABLE_MODELS))


def get_db_path() -> str:
    """Resolve the absolute filesystem path to the active SQLite database."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", path))
        return path
    raise ValueError(f"DATABASE_URL is not a local SQLite database: {url}")


def ensure_backup_dir() -> str:
    """Ensure the backups folder exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def touch_no_seed():
    """Touch the .no_seed marker so demo seed is skipped on subsequent app starts."""
    try:
        with open(NO_SEED_FLAG, "w", encoding="utf-8") as f:
            f.write(f"Created by data import at {datetime.now(timezone.utc).isoformat()}\n")
    except Exception as e:
        logger.warning(f"Could not touch .no_seed flag: {e}")


def get_backup_stats(db: Session) -> Dict[str, Any]:
    """Get counts of records in all tables and backup file statistics."""
    db_path = get_db_path()
    file_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    last_modified = (
        datetime.fromtimestamp(os.path.getmtime(db_path), tz=timezone.utc).isoformat()
        if os.path.exists(db_path)
        else None
    )

    counts = {}
    for table_name, model_cls in TABLE_MODELS:
        try:
            counts[table_name] = db.query(model_cls).count()
        except Exception:
            counts[table_name] = 0

    # List local safety backups
    ensure_backup_dir()
    backups_list = []
    if os.path.exists(BACKUP_DIR):
        for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if fname.endswith(".db"):
                fpath = os.path.join(BACKUP_DIR, fname)
                try:
                    fsize = os.path.getsize(fpath)
                    fmtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc).isoformat()
                    backups_list.append({
                        "filename": fname,
                        "size_bytes": fsize,
                        "size_kb": round(fsize / 1024, 1),
                        "created_at": fmtime,
                    })
                except Exception:
                    pass

    return {
        "database_file": os.path.basename(db_path),
        "file_size_bytes": file_size_bytes,
        "file_size_kb": round(file_size_bytes / 1024, 1),
        "last_modified": last_modified,
        "counts": counts,
        "summary": {
            "customers": counts.get("customers", 0),
            "vehicles": counts.get("vehicles", 0),
            "tickets": counts.get("service_tickets", 0),
            "stock_items": counts.get("stock_items", 0),
            "bills": counts.get("finance_bills", 0) + counts.get("purchase_bills", 0),
            "expenses": counts.get("expenses", 0),
            "appointments": counts.get("appointments", 0),
            "suppliers": counts.get("suppliers", 0),
        },
        "available_backups": backups_list[:10],
    }


def create_safety_backup() -> Optional[str]:
    """Create a timestamped safety backup of the active database in backups/ folder."""
    ensure_backup_dir()
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"auto_backup_before_import_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        dst.close()
        src.close()
        logger.info(f"Safety backup created at {backup_path}")
        return backup_filename
    except Exception as e:
        logger.error(f"Failed to create safety backup: {e}")
        return None


def export_sqlite_database() -> Tuple[str, str]:
    """
    Perform a clean online backup of the active SQLite database to a temporary file.
    Returns (temp_file_path, suggested_filename).
    """
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"workshop_backup_{timestamp}.db"

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_path = temp_file.name
    temp_file.close()

    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(temp_path)
        src.backup(dst)
        dst.close()
        src.close()
        return temp_path, filename
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


def validate_sqlite_database(file_path: str) -> Dict[str, Any]:
    """
    Validate that a given file is a genuine SQLite database with expected workshop tables.
    Returns table row counts if valid, or raises ValueError.
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 100:
        raise ValueError("ไฟล์มีขนาดเล็กเกินไปหรือไม่สมบูรณ์")

    # Check magic header
    with open(file_path, "rb") as f:
        header = f.read(16)
        if not header.startswith(b"SQLite format 3\x00"):
            raise ValueError("ไฟล์ที่อัปโหลดไม่ใช่ฐานข้อมูล SQLite ที่ถูกต้อง")

    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {"customers", "vehicles", "stock_items", "service_tickets"}
        missing = required_tables - tables
        if missing:
            conn.close()
            raise ValueError(f"ไฟล์ฐานข้อมูลไม่มีตารางที่จำเป็น: {', '.join(missing)}")

        table_counts = {}
        for table_name, _ in TABLE_MODELS:
            if table_name in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                table_counts[table_name] = cursor.fetchone()[0]
            else:
                table_counts[table_name] = 0

        conn.close()
        return table_counts
    except sqlite3.Error as e:
        raise ValueError(f"ไม่สามารถอ่านฐานข้อมูล SQLite ได้: {e}")


def import_sqlite_database(uploaded_bytes: bytes, original_filename: str) -> Dict[str, Any]:
    """
    Import and restore a SQLite .db backup file:
    1. Validate structure
    2. Auto-backup current database
    3. Dispose SQLAlchemy connections
    4. Overwrite active database using SQLite native backup
    5. Write .no_seed flag
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_path = temp_file.name
    temp_file.write(uploaded_bytes)
    temp_file.close()

    try:
        table_counts = validate_sqlite_database(temp_path)
        safety_backup = create_safety_backup()

        db_path = get_db_path()

        # Dispose pool connections to prevent locks
        engine.dispose()

        src = sqlite3.connect(temp_path)
        dst = sqlite3.connect(db_path)
        src.backup(dst)
        dst.close()
        src.close()

        touch_no_seed()

        return {
            "ok": True,
            "message": "นำเข้าฐานข้อมูลเรียบร้อยแล้ว ข้อมูลทั้งหมดพร้อมใช้งานทันที",
            "imported_filename": original_filename,
            "safety_backup": safety_backup,
            "counts": table_counts,
            "summary": {
                "customers": table_counts.get("customers", 0),
                "vehicles": table_counts.get("vehicles", 0),
                "tickets": table_counts.get("service_tickets", 0),
                "stock_items": table_counts.get("stock_items", 0),
                "bills": table_counts.get("finance_bills", 0) + table_counts.get("purchase_bills", 0),
                "expenses": table_counts.get("expenses", 0),
                "appointments": table_counts.get("appointments", 0),
            }
        }
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert an ORM model instance to a JSON-serializable dictionary."""
    res = {}
    for col in sa_inspect(obj).mapper.column_attrs:
        val = getattr(obj, col.key)
        if isinstance(val, datetime):
            res[col.key] = val.isoformat()
        else:
            res[col.key] = val
    return res


def export_json_data(db: Session, shop_profile: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Export all records from all 15 database tables into a clean JSON structure.
    """
    tables_data = {}
    counts = {}

    for table_name, model_cls in TABLE_MODELS:
        records = db.query(model_cls).all()
        tables_data[table_name] = [_model_to_dict(r) for r in records]
        counts[table_name] = len(records)

    export_obj = {
        "export_version": "1.0",
        "system": "Automotive Workshop Command Center",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "shop_profile": shop_profile or {},
        "summary": {
            "customers": counts.get("customers", 0),
            "vehicles": counts.get("vehicles", 0),
            "tickets": counts.get("service_tickets", 0),
            "stock_items": counts.get("stock_items", 0),
            "bills": counts.get("finance_bills", 0) + counts.get("purchase_bills", 0),
            "expenses": counts.get("expenses", 0),
            "appointments": counts.get("appointments", 0),
            "suppliers": counts.get("suppliers", 0),
        },
        "counts": counts,
        "tables": tables_data,
    }
    return export_obj


def _dict_to_model(model_cls: Any, data: Dict[str, Any]) -> Any:
    """Create a model instance from dictionary, parsing dates appropriately."""
    mapper = sa_inspect(model_cls)
    col_types = {col.key: col.columns[0].type for col in mapper.column_attrs}
    kwargs = {}

    for k, v in data.items():
        if k in col_types:
            type_str = str(col_types[k]).lower()
            if "datetime" in type_str:
                if isinstance(v, str) and v.strip():
                    try:
                        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    except Exception:
                        pass
                elif not v:
                    v = None
            kwargs[k] = v

    return model_cls(**kwargs)


def import_json_data(
    db: Session,
    payload: Dict[str, Any],
    mode: str = "replace",  # "replace" or "merge"
) -> Dict[str, Any]:
    """
    Import data from exported JSON structure:
    - mode="replace": auto-backups, wipes existing records in reverse FK order, and inserts new records.
    - mode="merge": appends new records, matching customers by phone and vehicles by plate.
    """
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("รูปแบบไฟล์ JSON ไม่ถูกต้อง: ไม่พบส่วนข้อมูล 'tables'")

    # Create safety backup
    safety_backup = create_safety_backup()

    imported_counts = {}

    if mode == "replace":
        # Delete children first
        for _, model_cls in REVERSE_TABLE_MODELS:
            db.query(model_cls).delete()
        db.commit()

        # Insert parents first
        for table_name, model_cls in TABLE_MODELS:
            rows = tables.get(table_name, [])
            instances = [_dict_to_model(model_cls, row) for row in rows]
            if instances:
                db.add_all(instances)
                db.commit()
            imported_counts[table_name] = len(instances)

    elif mode == "merge":
        # Merge mode: smart insert / upsert
        # 1. Suppliers
        for row in tables.get("suppliers", []):
            existing = None
            if row.get("name"):
                existing = db.query(Supplier).filter(Supplier.name == row["name"]).first()
            if not existing:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                db.add(_dict_to_model(Supplier, row_copy))
        db.commit()

        # 2. Stock items
        for row in tables.get("stock_items", []):
            existing = None
            if row.get("sku"):
                existing = db.query(StockItem).filter(StockItem.sku == row["sku"]).first()
            elif row.get("name_th"):
                existing = db.query(StockItem).filter(StockItem.name_th == row["name_th"]).first()
            if not existing:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                db.add(_dict_to_model(StockItem, row_copy))
        db.commit()

        # 3. Customers
        customer_id_map = {}
        for row in tables.get("customers", []):
            phone = row.get("phone")
            existing = db.query(Customer).filter(Customer.phone == phone).first() if phone else None
            old_id = row.get("id")
            if existing:
                customer_id_map[old_id] = existing.id
            else:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                c = _dict_to_model(Customer, row_copy)
                db.add(c)
                db.flush()
                customer_id_map[old_id] = c.id
        db.commit()

        # 4. Vehicles
        vehicle_id_map = {}
        for row in tables.get("vehicles", []):
            plate = row.get("plate")
            existing = db.query(Vehicle).filter(Vehicle.plate == plate).first() if plate else None
            old_id = row.get("id")
            if existing:
                vehicle_id_map[old_id] = existing.id
            else:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                # map customer_id
                old_cust_id = row.get("customer_id")
                if old_cust_id in customer_id_map:
                    row_copy["customer_id"] = customer_id_map[old_cust_id]
                v = _dict_to_model(Vehicle, row_copy)
                db.add(v)
                db.flush()
                vehicle_id_map[old_id] = v.id
        db.commit()

        # 5. Tickets, Appointments, Expenses, and Ledger Entries (with strict deduplication)
        for row in tables.get("service_tickets", []):
            old_id = row.get("id")
            existing_ticket = None
            if old_id:
                existing_ticket = db.query(ServiceTicket).filter(ServiceTicket.id == old_id).first()

            cust_id = customer_id_map.get(row.get("customer_id"), row.get("customer_id"))
            veh_id = vehicle_id_map.get(row.get("vehicle_id"), row.get("vehicle_id"))
            raw_input = row.get("raw_input")
            created_at_val = row.get("created_at")

            if not existing_ticket and raw_input:
                q = db.query(ServiceTicket).filter(ServiceTicket.raw_input == raw_input)
                if veh_id is not None:
                    q = q.filter(ServiceTicket.vehicle_id == veh_id)
                existing_ticket = q.first()

            if not existing_ticket and created_at_val:
                try:
                    dt = datetime.fromisoformat(created_at_val.replace("Z", "+00:00")).replace(tzinfo=None)
                    q = db.query(ServiceTicket).filter(ServiceTicket.created_at == dt)
                    if veh_id is not None:
                        q = q.filter(ServiceTicket.vehicle_id == veh_id)
                    existing_ticket = q.first()
                except Exception:
                    pass

            if not existing_ticket:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                row_copy["customer_id"] = cust_id
                row_copy["vehicle_id"] = veh_id
                db.add(_dict_to_model(ServiceTicket, row_copy))

        for row in tables.get("appointments", []):
            old_id = row.get("id")
            existing_appt = None
            if old_id:
                existing_appt = db.query(Appointment).filter(Appointment.id == old_id).first()

            cust_id = customer_id_map.get(row.get("customer_id"), row.get("customer_id"))
            veh_id = vehicle_id_map.get(row.get("vehicle_id"), row.get("vehicle_id"))
            appt_date = row.get("appointment_date")

            if not existing_appt and appt_date:
                try:
                    dt = datetime.fromisoformat(appt_date.replace("Z", "+00:00")).replace(tzinfo=None)
                    q = db.query(Appointment).filter(Appointment.appointment_date == dt)
                    if veh_id is not None:
                        q = q.filter(Appointment.vehicle_id == veh_id)
                    if cust_id is not None:
                        q = q.filter(Appointment.customer_id == cust_id)
                    existing_appt = q.first()
                except Exception:
                    pass

            if not existing_appt:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                row_copy["customer_id"] = cust_id
                row_copy["vehicle_id"] = veh_id
                db.add(_dict_to_model(Appointment, row_copy))

        for row in tables.get("expenses", []):
            old_id = row.get("id")
            existing_exp = None
            if old_id:
                existing_exp = db.query(Expense).filter(Expense.id == old_id).first()

            exp_date = row.get("expense_date")
            cat = row.get("category")
            amt = row.get("amount")

            if not existing_exp and exp_date and cat and amt is not None:
                try:
                    dt = datetime.fromisoformat(exp_date.replace("Z", "+00:00")).replace(tzinfo=None)
                    existing_exp = db.query(Expense).filter(
                        Expense.expense_date == dt,
                        Expense.category == cat,
                        Expense.amount == amt
                    ).first()
                except Exception:
                    pass

            if not existing_exp:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                db.add(_dict_to_model(Expense, row_copy))

        for row in tables.get("ledger_entries", []):
            old_id = row.get("id")
            existing_ledger = None
            if old_id:
                existing_ledger = db.query(LedgerEntry).filter(LedgerEntry.id == old_id).first()
            if not existing_ledger and row.get("description") and row.get("amount") is not None:
                existing_ledger = db.query(LedgerEntry).filter(
                    LedgerEntry.description == row["description"],
                    LedgerEntry.amount == row["amount"]
                ).first()
            if not existing_ledger:
                row_copy = {k: v for k, v in row.items() if k != "id"}
                db.add(_dict_to_model(LedgerEntry, row_copy))

        db.commit()

        # Count final
        for table_name, model_cls in TABLE_MODELS:
            imported_counts[table_name] = db.query(model_cls).count()
    else:
        raise ValueError(f"โหมดการนำเข้าไม่ถูกต้อง: {mode}")

    touch_no_seed()

    return {
        "ok": True,
        "message": f"นำเข้าข้อมูล JSON ในโหมด '{mode}' เรียบร้อยแล้ว",
        "mode": mode,
        "safety_backup": safety_backup,
        "shop_profile": payload.get("shop_profile", {}),
        "counts": imported_counts,
    }


def restore_from_local_backup(backup_filename: str) -> Dict[str, Any]:
    """Restore database from a safety backup file inside backups/ folder."""
    # Prevent path traversal
    safe_name = os.path.basename(backup_filename)
    backup_path = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"ไม่พบไฟล์สำรองข้อมูล: {safe_name}")

    with open(backup_path, "rb") as f:
        file_bytes = f.read()

    return import_sqlite_database(file_bytes, safe_name)


def delete_local_backup(backup_filename: str) -> bool:
    """Delete a backup file from backups/ folder."""
    safe_name = os.path.basename(backup_filename)
    backup_path = os.path.join(BACKUP_DIR, safe_name)
    if os.path.exists(backup_path):
        os.remove(backup_path)
        return True
    return False


def wipe_all_data(db: Session, create_safety: bool = True) -> Dict[str, Any]:
    """
    Safely wipe all workshop data across all 15 tables in dependency-safe reverse FK order.
    Automatically creates a safety backup before wiping so data is never permanently lost.
    Also touches .no_seed so demo seed data doesn't repopulate on restart.
    """
    safety_backup = None
    if create_safety:
        safety_backup = create_safety_backup()

    deleted_counts = {}
    for table_name, model_cls in REVERSE_TABLE_MODELS:
        if model_cls is AppSetting:
            continue  # shop settings (backup folder, commission %, ...) survive a data wipe
        count = db.query(model_cls).count()
        db.query(model_cls).delete()
        deleted_counts[table_name] = count
    db.commit()

    touch_no_seed()

    return {
        "ok": True,
        "message": "ล้างข้อมูลทั้งหมดในระบบเรียบร้อยแล้ว",
        "safety_backup": safety_backup,
        "deleted_counts": deleted_counts,
        "total_deleted": sum(deleted_counts.values()),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Automatic daily backup
# ──────────────────────────────────────────────────────────────────────────────

DAILY_PREFIX = "daily_backup_"
DAILY_KEEP = 30  # days of daily backups kept in backups/

_last_auto_status: Dict[str, Any] = {"last_file": None, "last_run": None, "copied_to": None, "error": None}


def _sqlite_copy(src_path: str, dst_path: str) -> None:
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def run_daily_backup(extra_dir: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """Make today's backup once (backups/daily_backup_YYYYMMDD.db), keep the last 30,
    and copy it to extra_dir (USB drive / Google Drive / OneDrive folder) when given."""
    from models.db_models import get_local_now

    ensure_backup_dir()
    db_path = get_db_path()
    today = get_local_now().strftime("%Y%m%d")
    filename = f"{DAILY_PREFIX}{today}.db"
    path = os.path.join(BACKUP_DIR, filename)
    status = {"last_file": filename, "last_run": get_local_now().isoformat(timespec="seconds"),
              "copied_to": None, "error": None, "created": False}
    try:
        if force or not os.path.exists(path):
            _sqlite_copy(db_path, path)
            status["created"] = True
            logger.info(f"Daily backup created: {path}")

        # Keep only the newest DAILY_KEEP daily files
        dailies = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith(DAILY_PREFIX) and f.endswith(".db"))
        for old in dailies[:-DAILY_KEEP]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except OSError:
                pass

        if extra_dir:
            if os.path.isdir(extra_dir):
                target = os.path.join(extra_dir, filename)
                if force or status["created"] or not os.path.exists(target):
                    shutil.copy2(path, target)
                status["copied_to"] = target
            else:
                status["error"] = f"ไม่พบโฟลเดอร์สำรองเพิ่มเติม: {extra_dir} (เสียบ USB / เปิดไดรฟ์แล้วหรือยัง?)"
    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Daily backup failed: {e}")

    _last_auto_status.update(status)
    return dict(_last_auto_status)


def get_daily_backup_status() -> Dict[str, Any]:
    ensure_backup_dir()
    dailies = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith(DAILY_PREFIX) and f.endswith(".db"))
    return {**_last_auto_status, "daily_files": len(dailies), "newest": dailies[-1] if dailies else None,
            "keep_days": DAILY_KEEP}
