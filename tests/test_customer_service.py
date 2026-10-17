"""
Unit tests for customer_service.py — Module 3: Customer & Vehicle 360°

Covers:
- create_customer / duplicate phone guard
- get_customer / 404
- list_customers pagination
- update_customer / duplicate phone guard
- add_vehicle / duplicate plate guard
- update_vehicle_mileage / backwards mileage guard
- get_vehicle_health / 404
- _classify_segment helper
- get_customer_360 aggregation
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from models.db_models import Customer, ServiceTicket, TicketStatus, Vehicle, VehicleHealthWatchlist
from models.schemas import CustomerCreate, CustomerUpdate, VehicleCreate, VehicleMileageUpdate
from services import customer_service


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_customer(db, name="สมชาย", phone="0812345678") -> Customer:
    c = Customer(name=name, phone=phone)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_vehicle(db, customer_id: int, plate="กข 1234 กทม") -> Vehicle:
    v = Vehicle(
        plate=plate,
        brand="Toyota",
        model="Camry",
        customer_id=customer_id,
        current_mileage=10000,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


# ─── create_customer ──────────────────────────────────────────────────────────

def test_create_customer_success(db):
    req = CustomerCreate(name="สมหมาย ใจดี", phone="0891234567")
    resp = customer_service.create_customer(db, req)
    assert resp.id is not None
    assert resp.name == "สมหมาย ใจดี"
    assert resp.phone == "0891234567"


def test_create_customer_duplicate_phone_raises_409(db):
    from fastapi import HTTPException
    _make_customer(db, phone="0812345678")
    req = CustomerCreate(name="คนอื่น", phone="0812345678")
    with pytest.raises(HTTPException) as exc:
        customer_service.create_customer(db, req)
    assert exc.value.status_code == 409


# ─── get_customer ─────────────────────────────────────────────────────────────

def test_get_customer_success(db):
    c = _make_customer(db)
    resp = customer_service.get_customer(db, c.id)
    assert resp.id == c.id
    assert resp.name == c.name


def test_get_customer_not_found_raises_404(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        customer_service.get_customer(db, 99999)
    assert exc.value.status_code == 404


# ─── list_customers ───────────────────────────────────────────────────────────

def test_list_customers_returns_all(db):
    _make_customer(db, phone="0811111111")
    _make_customer(db, phone="0822222222")
    result = customer_service.list_customers(db)
    assert result["total"] >= 2
    assert len(result["items"]) >= 2


def test_list_customers_pagination(db):
    for i in range(5):
        _make_customer(db, phone=f"08{i}0000001")
    result = customer_service.list_customers(db, limit=2, offset=0)
    assert len(result["items"]) <= 2


# ─── update_customer ──────────────────────────────────────────────────────────

def test_update_customer_name(db):
    c = _make_customer(db)
    req = CustomerUpdate(name="ชื่อใหม่")
    resp = customer_service.update_customer(db, c.id, req)
    assert resp.name == "ชื่อใหม่"


def test_update_customer_phone_duplicate_raises_409(db):
    from fastapi import HTTPException
    c1 = _make_customer(db, phone="0811111111")
    c2 = _make_customer(db, phone="0822222222")
    req = CustomerUpdate(phone=c1.phone)
    with pytest.raises(HTTPException) as exc:
        customer_service.update_customer(db, c2.id, req)
    assert exc.value.status_code == 409


def test_update_customer_not_found_raises_404(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        customer_service.update_customer(db, 99999, CustomerUpdate(name="X"))
    assert exc.value.status_code == 404


# ─── add_vehicle ──────────────────────────────────────────────────────────────

def test_add_vehicle_success(db):
    c = _make_customer(db)
    req = VehicleCreate(plate="ดต 9999 กทม", brand="Honda", model="Civic", current_mileage=0)
    resp = customer_service.add_vehicle(db, c.id, req)
    assert resp.id is not None
    assert resp.plate == "ดต 9999 กทม"
    assert resp.customer_id == c.id


def test_add_vehicle_duplicate_plate_raises_409(db):
    from fastapi import HTTPException
    c = _make_customer(db)
    _make_vehicle(db, customer_id=c.id, plate="ซซ 5555 กทม")
    req = VehicleCreate(plate="ซซ 5555 กทม", brand="Ford", model="Ranger", current_mileage=0)
    with pytest.raises(HTTPException) as exc:
        customer_service.add_vehicle(db, c.id, req)
    assert exc.value.status_code == 409


def test_add_vehicle_customer_not_found_raises_404(db):
    from fastapi import HTTPException
    req = VehicleCreate(plate="ซซ 5555 กทม", brand="Ford", model="Ranger", current_mileage=0)
    with pytest.raises(HTTPException) as exc:
        customer_service.add_vehicle(db, 99999, req)
    assert exc.value.status_code == 404


# ─── update_vehicle_mileage ───────────────────────────────────────────────────

def test_update_vehicle_mileage_success(db):
    c = _make_customer(db)
    v = _make_vehicle(db, customer_id=c.id)
    req = VehicleMileageUpdate(current_mileage=20000)
    resp = customer_service.update_vehicle_mileage(db, v.plate, req)
    assert resp.current_mileage == 20000


def test_update_vehicle_mileage_backwards_raises_400(db):
    from fastapi import HTTPException
    c = _make_customer(db)
    v = _make_vehicle(db, customer_id=c.id)  # current_mileage=10000
    req = VehicleMileageUpdate(current_mileage=5000)
    with pytest.raises(HTTPException) as exc:
        customer_service.update_vehicle_mileage(db, v.plate, req)
    assert exc.value.status_code == 400


def test_update_vehicle_mileage_not_found_raises_404(db):
    from fastapi import HTTPException
    req = VehicleMileageUpdate(current_mileage=1000)
    with pytest.raises(HTTPException) as exc:
        customer_service.update_vehicle_mileage(db, "NOTEXIST", req)
    assert exc.value.status_code == 404


# ─── get_vehicle_health ───────────────────────────────────────────────────────

def test_get_vehicle_health_success(db):
    c = _make_customer(db)
    v = _make_vehicle(db, customer_id=c.id)
    resp = customer_service.get_vehicle_health(db, v.plate)
    assert resp.plate == v.plate


def test_get_vehicle_health_not_found_raises_404(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        customer_service.get_vehicle_health(db, "NOTEXIST")
    assert exc.value.status_code == 404


# ─── _classify_segment ────────────────────────────────────────────────────────

def test_classify_segment_churned():
    last_visit = datetime.now(timezone.utc) - timedelta(days=200)
    seg = customer_service._classify_segment(50000, 10, last_visit)
    assert seg == "Churned"


def test_classify_segment_vip_by_spend():
    last_visit = datetime.now(timezone.utc) - timedelta(days=10)
    seg = customer_service._classify_segment(25000, 2, last_visit)
    assert seg == "VIP"


def test_classify_segment_vip_by_visits():
    last_visit = datetime.now(timezone.utc) - timedelta(days=10)
    seg = customer_service._classify_segment(5000, 6, last_visit)
    assert seg == "VIP"


def test_classify_segment_at_risk():
    last_visit = datetime.now(timezone.utc) - timedelta(days=100)
    seg = customer_service._classify_segment(5000, 2, last_visit)
    assert seg == "At Risk"


def test_classify_segment_regular():
    last_visit = datetime.now(timezone.utc) - timedelta(days=10)
    seg = customer_service._classify_segment(5000, 2, last_visit)
    assert seg == "Regular"


def test_classify_segment_new_no_visits():
    last_visit = datetime.now(timezone.utc) - timedelta(days=10)
    seg = customer_service._classify_segment(0, 0, last_visit)
    assert seg == "New"


# ─── get_customer_360 ─────────────────────────────────────────────────────────

def test_get_customer_360_not_found_raises_404(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        customer_service.get_customer_360(db, 99999)
    assert exc.value.status_code == 404


def test_get_customer_360_returns_profile(db):
    c = _make_customer(db)
    _make_vehicle(db, customer_id=c.id)
    profile = customer_service.get_customer_360(db, c.id)
    assert profile.customer.id == c.id
    assert isinstance(profile.vehicles, list)
    assert isinstance(profile.ticket_history, list)
    assert profile.total_visits == 0
