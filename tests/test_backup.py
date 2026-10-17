"""
Tests for Data Backup, Export & Device Transfer Router
"""
import io
import json
import os
import sqlite3
import pytest
from starlette.testclient import TestClient

from main import app
from core.database import SessionLocal
from models.db_models import Customer, Vehicle, StockItem


def test_backup_stats(client):
    res = client.get("/api/v1/backup/stats")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "counts" in data
    assert "file_size_kb" in data
    assert "customers" in data["summary"]
    assert "vehicles" in data["summary"]
    assert "stock_items" in data["summary"]


def test_export_db(client):
    res = client.get("/api/v1/backup/export-db")
    assert res.status_code == 200
    content = res.content
    assert len(content) > 100
    assert content.startswith(b"SQLite format 3\x00")


def test_export_json(client):
    res = client.get("/api/v1/backup/export-json?shop_name=TestGarage&shop_phone=0899999999")
    assert res.status_code == 200
    data = res.json()
    assert data["export_version"] == "1.0"
    assert "tables" in data
    assert "customers" in data["tables"]
    assert "vehicles" in data["tables"]
    assert "stock_items" in data["tables"]
    assert data["shop_profile"].get("shop_name") == "TestGarage"
    assert data["shop_profile"].get("shop_phone") == "0899999999"


def test_import_db_reject_invalid_file(client):
    fake_content = b"This is not a sqlite database at all and needs to exceed 100 bytes for header check! " * 3
    files = {"file": ("test.db", io.BytesIO(fake_content), "application/octet-stream")}
    res = client.post("/api/v1/backup/import-db", files=files)
    assert res.status_code == 400
    assert "ไม่ใช่ฐานข้อมูล SQLite" in res.json()["detail"]


def test_import_db_reject_wrong_extension(client):
    files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
    res = client.post("/api/v1/backup/import-db", files=files)
    assert res.status_code == 400
    assert ".db หรือ .sqlite" in res.json()["detail"]


def test_import_json_roundtrip(client):
    # 1. Export json
    export_res = client.get("/api/v1/backup/export-json")
    assert export_res.status_code == 200
    json_bytes = export_res.content

    # 2. Import back in merge mode
    files = {"file": ("backup.json", io.BytesIO(json_bytes), "application/json")}
    import_res = client.post("/api/v1/backup/import-json", files=files, data={"mode": "merge"})
    assert import_res.status_code == 200
    data = import_res.json()
    assert data["ok"] is True
    assert "safety_backup" in data


def test_wipe_all_data_endpoint(client, db):
    # Add a customer
    c = Customer(name="ทดสอบก่อนลบ", phone="0881112233")
    db.add(c)
    db.commit()

    res = client.post("/api/v1/backup/wipe-all-data")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "safety_backup" in data
    assert data["total_deleted"] >= 1
    # Check customer table is now empty
    assert db.query(Customer).count() == 0
