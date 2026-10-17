"""
Router: Appointments — Calendar management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from core.dependencies import get_db
from models.db_models import Appointment, to_local_naive

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
    allow_overlap: bool = False  # set after the user confirms a double booking


def _appt_dict(a: Appointment) -> dict:
    return {
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
    }


def _check_slot_free(db: Session, when: datetime, time_slot: Optional[str], exclude_id: Optional[int] = None) -> None:
    """409 when another active appointment has the same day + time slot (or the exact same time)."""
    day_start = when.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)
    q = db.query(Appointment).filter(
        Appointment.appointment_date >= day_start,
        Appointment.appointment_date <= day_end,
        Appointment.status != "cancelled",
    )
    if exclude_id:
        q = q.filter(Appointment.id != exclude_id)
    for other in q.all():
        same_slot = time_slot and other.time_slot and other.time_slot.strip() == time_slot.strip()
        same_time = not time_slot and other.appointment_date == when
        if same_slot or same_time:
            raise HTTPException(
                status_code=409,
                detail=f"ช่วงเวลานี้มีนัดแล้ว: {other.customer_name} ({other.time_slot or other.appointment_date.strftime('%H:%M')})",
            )


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
    data = req.model_dump(exclude={"allow_overlap"})
    data["appointment_date"] = to_local_naive(req.appointment_date)
    if not req.allow_overlap and data["status"] != "cancelled":
        _check_slot_free(db, data["appointment_date"], req.time_slot)
    appt = Appointment(**data)
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
    data = req.model_dump(exclude_unset=True, exclude={"allow_overlap"})
    if "appointment_date" in data:
        data["appointment_date"] = to_local_naive(data["appointment_date"])
    new_date = data.get("appointment_date", appt.appointment_date)
    new_slot = data.get("time_slot", appt.time_slot)
    if not req.allow_overlap and data.get("status", appt.status) != "cancelled":
        _check_slot_free(db, new_date, new_slot, exclude_id=appt.id)
    for k, v in data.items():
        setattr(appt, k, v)
    db.commit()
    db.refresh(appt)
    return {"status": "updated", **_appt_dict(appt)}


@router.delete("/{appointment_id}")
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    db.delete(appt)
    db.commit()
    return {"status": "deleted"}
