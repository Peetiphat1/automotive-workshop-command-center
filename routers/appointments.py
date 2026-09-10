"""
Router: Appointments — Calendar management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from core.dependencies import get_db
from models.db_models import Appointment

router = APIRouter()


class AppointmentCreate(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_info: Optional[str] = None
    appointment_date: datetime
    time_slot: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    status: str = "confirmed"


@router.get("/")
def list_appointments(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    if year and month:
        from sqlalchemy import extract
        query = query.filter(
            extract('year', Appointment.appointment_date) == year,
            extract('month', Appointment.appointment_date) == month,
        )
    appointments = query.order_by(Appointment.appointment_date).all()
    return [{
        "id": a.id,
        "customer_name": a.customer_name,
        "customer_phone": a.customer_phone,
        "vehicle_plate": a.vehicle_plate,
        "vehicle_info": a.vehicle_info,
        "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
        "time_slot": a.time_slot,
        "service_type": a.service_type,
        "notes": a.notes,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in appointments]


@router.post("/")
def create_appointment(req: AppointmentCreate, db: Session = Depends(get_db)):
    appt = Appointment(**req.model_dump())
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return {
        "id": appt.id,
        "customer_name": appt.customer_name,
        "appointment_date": appt.appointment_date.isoformat(),
        "time_slot": appt.time_slot,
        "service_type": appt.service_type,
        "status": appt.status,
    }


@router.put("/{appointment_id}")
def update_appointment(appointment_id: int, req: AppointmentCreate, db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(appt, k, v)
    db.commit()
    db.refresh(appt)
    return {"status": "updated", "id": appt.id}


@router.delete("/{appointment_id}")
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    db.delete(appt)
    db.commit()
    return {"status": "deleted"}
