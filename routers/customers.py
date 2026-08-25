"""
Router: Module 3 — Customer & Vehicle 360° Data Hub
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import get_db
from models.schemas import (
    Customer360Profile, CustomerCreate, CustomerResponse, CustomerUpdate,
    VehicleCreate, VehicleMileageUpdate, VehicleResponse,
)
from services import customer_service

router = APIRouter()


# ── Customer CRUD ─────────────────────────────────────────────────────────────

@router.post(
    "/customers/",
    response_model=CustomerResponse,
    status_code=201,
    summary="Create a new customer",
)
def create_customer(req: CustomerCreate, db: Session = Depends(get_db)):
    return customer_service.create_customer(db, req)


@router.get(
    "/customers/",
    summary="List all customers",
    response_model=dict,
)
def list_customers(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return customer_service.list_customers(db, limit=limit, offset=offset)


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return customer_service.get_customer(db, customer_id)


@router.put(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer info",
)
def update_customer(
    customer_id: int,
    req: CustomerUpdate,
    db: Session = Depends(get_db),
):
    return customer_service.update_customer(db, customer_id, req)


# ── 360° Profile ──────────────────────────────────────────────────────────────

@router.get(
    "/customers/{customer_id}/profile",
    response_model=Customer360Profile,
    summary="Get Customer 360° Profile",
    description=(
        "Aggregates the complete **Customer 360° view**: "
        "customer info, all vehicles + health watchlist, full ticket/service history, "
        "total lifetime spend, visit count, customer segment classification "
        "(`VIP` / `Regular` / `At Risk` / `Churned`), and active health alerts."
    ),
)
def get_customer_360(customer_id: int, db: Session = Depends(get_db)):
    return customer_service.get_customer_360(db, customer_id)


# ── Vehicle management ────────────────────────────────────────────────────────

@router.post(
    "/customers/{customer_id}/vehicles",
    response_model=VehicleResponse,
    status_code=201,
    summary="Add a vehicle to a customer",
)
def add_vehicle(
    customer_id: int,
    req: VehicleCreate,
    db: Session = Depends(get_db),
):
    return customer_service.add_vehicle(db, customer_id, req)


@router.put(
    "/vehicles/{plate}/mileage",
    response_model=VehicleResponse,
    summary="Update vehicle mileage & service dates",
    description=(
        "Updates the vehicle's current mileage and optionally records "
        "last oil change, battery change, and tire change data. "
        "Used after each service visit to keep the maintenance calendar accurate."
    ),
)
def update_vehicle_mileage(
    plate: str,
    req: VehicleMileageUpdate,
    db: Session = Depends(get_db),
):
    return customer_service.update_vehicle_mileage(db, plate, req)


@router.get(
    "/vehicles/{plate}/health",
    response_model=VehicleResponse,
    summary="Get vehicle health watchlist",
    description="Returns the vehicle record including its full health watchlist (overdue components).",
)
def get_vehicle_health(plate: str, db: Session = Depends(get_db)):
    return customer_service.get_vehicle_health(db, plate)
