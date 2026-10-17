"""
Customer Service — Module 3 business logic (360° Data Hub)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.db_models import (
    Customer, ServiceTicket, TicketStatus, Vehicle, VehicleHealthWatchlist,
)
from models.schemas import (
    Customer360Profile, CustomerCreate, CustomerResponse, CustomerUpdate,
    DiagnosedIssueSchema, HealthWatchlistItemSchema, LineItemSchema,
    TicketResponse, VehicleCreate, VehicleMileageUpdate, VehicleResponse,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _customer_to_response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        line_id=customer.line_id,
        email=customer.email,
        created_at=customer.created_at,
    )


def _watchlist_to_schema(items: list) -> List[HealthWatchlistItemSchema]:
    return [
        HealthWatchlistItemSchema(
            id=w.id,
            component=w.component,
            condition=w.condition,
            next_due_mileage=w.next_due_mileage,
            next_due_date=w.next_due_date,
            is_overdue=w.is_overdue,
            notes=w.notes,
        )
        for w in items
    ]


def _vehicle_to_response(vehicle: Vehicle) -> VehicleResponse:
    return VehicleResponse(
        id=vehicle.id,
        plate=vehicle.plate,
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        current_mileage=vehicle.current_mileage,
        last_service_date=vehicle.last_service_date,
        last_oil_change_date=vehicle.last_oil_change_date,
        last_oil_change_mileage=vehicle.last_oil_change_mileage,
        last_battery_date=vehicle.last_battery_date,
        last_tire_change_mileage=vehicle.last_tire_change_mileage,
        customer_id=vehicle.customer_id,
        health_watchlist=_watchlist_to_schema(vehicle.health_watchlist),
    )


def _ticket_to_response_mini(ticket: ServiceTicket) -> TicketResponse:
    """Lightweight ticket → schema conversion for embedding in 360° profile."""
    vehicle = ticket.vehicle
    customer = ticket.customer
    symptoms = ticket.get_symptoms()
    raw_issues = ticket.get_diagnosed_issues()
    raw_items = ticket.get_line_items()

    return TicketResponse(
        id=ticket.id,
        vehicle_plate=vehicle.plate if vehicle else None,
        customer_name=customer.name if customer else None,
        car_model=f"{vehicle.brand} {vehicle.model}" if vehicle else None,
        raw_input=ticket.raw_input,
        extracted_symptoms=symptoms,
        diagnosed_issues=[DiagnosedIssueSchema(**i) for i in raw_issues],
        line_items=[LineItemSchema(**i) for i in raw_items],
        estimated_labor_cost=ticket.estimated_labor_cost,
        estimated_parts_cost=ticket.estimated_parts_cost,
        total_estimated_cost=ticket.total_estimated_cost,
        requires_heavy_repair=ticket.requires_heavy_repair,
        status=ticket.status,  # type: ignore[arg-type]
        mechanic_notes=ticket.mechanic_notes,
        approved_by=ticket.approved_by,
        approved_at=ticket.approved_at,
        final_cost=ticket.final_cost,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _classify_segment(total_spent: float, total_visits: int, last_visit: Optional[datetime]) -> str:
    now = datetime.now(timezone.utc)
    if last_visit:
        # SQLite stores naive datetimes; normalise so subtraction always works.
        lv = last_visit.replace(tzinfo=timezone.utc) if last_visit.tzinfo is None else last_visit
        if (now - lv).days > 180:
            return "Churned"
    if total_visits == 0:
        return "New"
    if total_spent >= 20000 or total_visits >= 5:
        return "VIP"
    if last_visit:
        lv = last_visit.replace(tzinfo=timezone.utc) if last_visit.tzinfo is None else last_visit
        if (now - lv).days > 90:
            return "At Risk"
    return "Regular"


# ── Service functions ─────────────────────────────────────────────────────────

def create_customer(db: Session, req: CustomerCreate) -> CustomerResponse:
    existing = db.query(Customer).filter(Customer.phone == req.phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"เบอร์โทร {req.phone} มีอยู่ในระบบแล้ว (ลูกค้า: {existing.name} ID: #{existing.id})",
        )
    customer = Customer(
        name=req.name,
        phone=req.phone,
        line_id=req.line_id.strip() if req.line_id else None,
        email=req.email.strip() if req.email else None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    # If initial plate was supplied, register the vehicle automatically
    plate = getattr(req, 'plate', None)
    if plate and plate.strip():
        plate_clean = plate.strip()
        v_exists = db.query(Vehicle).filter(Vehicle.plate == plate_clean).first()
        if not v_exists:
            brand = getattr(req, 'brand', None) or "Toyota"
            model = getattr(req, 'model', None) or getattr(req, 'car_model', None) or "รถยนต์"
            v = Vehicle(
                plate=plate_clean,
                brand=brand,
                model=model,
                year=getattr(req, 'year', None) or 2020,
                current_mileage=getattr(req, 'mileage', None) or 0,
                customer_id=customer.id,
            )
            db.add(v)
            db.commit()
        else:
            # If vehicle already existed, link to this customer
            v_exists.customer_id = customer.id
            db.commit()

    return _customer_to_response(customer)


def delete_customer(db: Session, customer_id: int) -> dict:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"ไม่พบข้อมูลลูกค้า #{customer_id}")

    # Unlink tickets so service history is preserved
    for t in db.query(ServiceTicket).filter(ServiceTicket.customer_id == customer_id).all():
        t.customer_id = None

    # Delete vehicles owned by this customer
    for v in db.query(Vehicle).filter(Vehicle.customer_id == customer_id).all():
        # Unlink tickets pointing to this vehicle
        for vt in db.query(ServiceTicket).filter(ServiceTicket.vehicle_id == v.id).all():
            vt.vehicle_id = None
        db.delete(v)

    db.delete(customer)
    db.commit()
    return {"status": "ok", "message": f"ลบข้อมูลลูกค้า #{customer_id} เรียบร้อยแล้ว"}


def get_customer(db: Session, customer_id: int) -> CustomerResponse:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer #{customer_id} not found.")
    return _customer_to_response(customer)


def list_customers(db: Session, limit: int = 50, offset: int = 0) -> dict:
    total = db.query(Customer).count()
    customers = db.query(Customer).offset(offset).limit(limit).all()
    return {"total": total, "items": [_customer_to_response(c) for c in customers]}


def update_customer(db: Session, customer_id: int, req: CustomerUpdate) -> CustomerResponse:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer #{customer_id} not found.")

    if req.name is not None:
        customer.name = req.name
    if req.phone is not None:
        dup = db.query(Customer).filter(Customer.phone == req.phone, Customer.id != customer_id).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Phone {req.phone} is already in use.")
        customer.phone = req.phone
    if req.line_id is not None:
        customer.line_id = req.line_id
    if req.email is not None:
        customer.email = req.email

    customer.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(customer)
    return _customer_to_response(customer)


def get_customer_360(db: Session, customer_id: int) -> Customer360Profile:
    """Aggregate full 360° view: customer + vehicles + ticket history + health alerts."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer #{customer_id} not found.")

    vehicles = customer.vehicles
    vehicle_responses = [_vehicle_to_response(v) for v in vehicles]

    # All tickets for this customer
    tickets = (
        db.query(ServiceTicket)
        .filter(ServiceTicket.customer_id == customer_id)
        .order_by(ServiceTicket.created_at.desc())
        .all()
    )
    ticket_responses = [_ticket_to_response_mini(t) for t in tickets]

    # Financial aggregation
    total_spent = sum(
        (t.final_cost or t.total_estimated_cost or 0.0)
        for t in tickets
        if t.status in (TicketStatus.APPROVED, TicketStatus.COMPLETED)
    )
    total_visits = len([t for t in tickets if t.status != TicketStatus.CANCELLED])

    last_visit = max((t.created_at for t in tickets), default=None)
    segment = _classify_segment(total_spent, total_visits, last_visit)

    # Aggregate overdue health alerts across all vehicles
    all_alerts: List[HealthWatchlistItemSchema] = []
    for v in vehicles:
        for w in v.health_watchlist:
            if w.is_overdue:
                all_alerts.append(HealthWatchlistItemSchema(
                    id=w.id,
                    component=w.component,
                    condition=w.condition,
                    next_due_mileage=w.next_due_mileage,
                    next_due_date=w.next_due_date,
                    is_overdue=w.is_overdue,
                    notes=w.notes,
                ))

    return Customer360Profile(
        customer=_customer_to_response(customer),
        vehicles=vehicle_responses,
        ticket_history=ticket_responses,
        total_spent=total_spent,
        total_visits=total_visits,
        last_visit_date=last_visit,
        customer_segment=segment,
        health_alerts=all_alerts,
    )


def add_vehicle(db: Session, customer_id: int, req: VehicleCreate) -> VehicleResponse:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer #{customer_id} not found.")

    existing = db.query(Vehicle).filter(Vehicle.plate == req.plate).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Vehicle with plate '{req.plate}' already exists (ID: {existing.id}).",
        )

    vehicle = Vehicle(
        plate=req.plate,
        brand=req.brand,
        model=req.model,
        year=req.year,
        color=req.color,
        current_mileage=req.current_mileage,
        customer_id=customer_id,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return _vehicle_to_response(vehicle)


def update_vehicle_mileage(db: Session, plate: str, req: VehicleMileageUpdate) -> VehicleResponse:
    vehicle = db.query(Vehicle).filter(Vehicle.plate == plate).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle with plate '{plate}' not found.")

    if req.current_mileage < vehicle.current_mileage:
        raise HTTPException(
            status_code=400,
            detail=f"New mileage ({req.current_mileage} km) cannot be less than current ({vehicle.current_mileage} km).",
        )

    vehicle.current_mileage = req.current_mileage
    if req.last_service_date:
        vehicle.last_service_date = req.last_service_date
    if req.last_oil_change_date:
        vehicle.last_oil_change_date = req.last_oil_change_date
    if req.last_oil_change_mileage is not None:
        vehicle.last_oil_change_mileage = req.last_oil_change_mileage
    if req.last_battery_date:
        vehicle.last_battery_date = req.last_battery_date
    if req.last_tire_change_mileage is not None:
        vehicle.last_tire_change_mileage = req.last_tire_change_mileage

    # Clear respective overdue alerts if they exist
    from datetime import datetime, timezone
    now_dt = datetime.now(timezone.utc)
    if req.last_oil_change_date or req.last_oil_change_mileage is not None:
        for w in vehicle.health_watchlist:
            if w.component == "น้ำมันเครื่อง":
                w.is_overdue = False
                w.condition = "ได้รับการอัปเดตประวัติ"
                w.notes = f"อัปเดตประวัติการบำรุงรักษาด้วยตนเอง เมื่อ {now_dt.strftime('%Y-%m-%d')}"
    if req.last_battery_date:
        for w in vehicle.health_watchlist:
            if w.component == "แบตเตอรี่":
                w.is_overdue = False
                w.condition = "ได้รับการอัปเดตประวัติ"
                w.notes = f"อัปเดตประวัติการบำรุงรักษาด้วยตนเอง เมื่อ {now_dt.strftime('%Y-%m-%d')}"
    if req.last_tire_change_mileage is not None:
        for w in vehicle.health_watchlist:
            if w.component == "ยางรถยนต์":
                w.is_overdue = False
                w.condition = "ได้รับการอัปเดตประวัติ"
                w.notes = f"อัปเดตประวัติการบำรุงรักษาด้วยตนเอง เมื่อ {now_dt.strftime('%Y-%m-%d')}"

    db.commit()
    db.refresh(vehicle)
    return _vehicle_to_response(vehicle)


def get_vehicle_health(db: Session, plate: str) -> VehicleResponse:
    vehicle = db.query(Vehicle).filter(Vehicle.plate == plate).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle with plate '{plate}' not found.")
    return _vehicle_to_response(vehicle)
