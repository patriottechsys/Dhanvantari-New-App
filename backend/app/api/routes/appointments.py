"""
Appointment routes — calendar scheduling with overlap prevention.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.email import send_appointment_reminder
from app.api.deps import get_current_practitioner
from app.models.practitioner import Practitioner
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentType, AppointmentStatus

router = APIRouter()

BLOCKING_STATUSES = [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]


class AppointmentCreate(BaseModel):
    patient_id: int
    start_at: str
    end_at: str
    appointment_type: str = "consultation"
    reason: str | None = None
    notes: str | None = None
    location: str | None = None
    plan_id: int | None = None
    therapy_id: int | None = None


class AppointmentUpdate(BaseModel):
    patient_id: int | None = None
    start_at: str | None = None
    end_at: str | None = None
    appointment_type: str | None = None
    status: str | None = None
    reason: str | None = None
    notes: str | None = None
    location: str | None = None
    plan_id: int | None = None
    therapy_id: int | None = None


def _appt_dict(a: Appointment, patient_name: str | None = None) -> dict:
    return {
        "id": a.id,
        "patient_id": a.patient_id,
        "practitioner_id": a.practitioner_id,
        "patient_name": patient_name,
        "start_at": a.start_at.isoformat(),
        "end_at": a.end_at.isoformat(),
        "appointment_type": a.appointment_type.value,
        "status": a.status.value,
        "reason": a.reason,
        "notes": a.notes,
        "location": a.location,
        "plan_id": a.plan_id,
        "therapy_id": a.therapy_id,
        "reminder_sent_at": a.reminder_sent_at.isoformat() if a.reminder_sent_at else None,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")


async def _has_conflict(db, practitioner_id, start, end, exclude_id=None) -> bool:
    q = select(Appointment.id).where(
        Appointment.practitioner_id == practitioner_id,
        Appointment.status.notin_(BLOCKING_STATUSES),
        Appointment.start_at < end,
        Appointment.end_at > start,
    )
    if exclude_id is not None:
        q = q.where(Appointment.id != exclude_id)
    return (await db.execute(q)).scalars().first() is not None


async def _require_owned_patient(db, practitioner_id, patient_id) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.practitioner_id == practitioner_id)
    )
    patient = result.scalars().first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("")
async def list_appointments(
    start: str | None = Query(None),
    end: str | None = Query(None),
    status: str | None = Query(None),
    type: str | None = Query(None),
    patient_id: int | None = Query(None),
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db),
):
    q = select(Appointment).options(selectinload(Appointment.patient)).where(
        Appointment.practitioner_id == practitioner.id
    )
    if start:
        q = q.where(Appointment.end_at > _parse_dt(start))
    if end:
        q = q.where(Appointment.start_at < _parse_dt(end))
    if status:
        q = q.where(Appointment.status == AppointmentStatus(status))
    if type:
        q = q.where(Appointment.appointment_type == AppointmentType(type))
    if patient_id:
        q = q.where(Appointment.patient_id == patient_id)
    q = q.order_by(Appointment.start_at)
    result = await db.execute(q)
    return [_appt_dict(a, patient_name=a.patient.full_name if a.patient else None) for a in result.scalars().all()]


@router.post("", status_code=201)
async def create_appointment(
    body: AppointmentCreate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db),
):
    patient = await _require_owned_patient(db, practitioner.id, body.patient_id)
    start, end = _parse_dt(body.start_at), _parse_dt(body.end_at)
    if end <= start:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    if await _has_conflict(db, practitioner.id, start, end):
        raise HTTPException(status_code=409, detail="This time slot overlaps an existing appointment")

    appt = Appointment(
        practitioner_id=practitioner.id,
        patient_id=body.patient_id,
        start_at=start,
        end_at=end,
        appointment_type=AppointmentType(body.appointment_type),
        reason=body.reason,
        notes=body.notes,
        location=body.location,
        plan_id=body.plan_id,
        therapy_id=body.therapy_id,
    )
    db.add(appt)
    await db.flush()

    if patient.email:
        send_appointment_reminder(
            practitioner_name=practitioner.display_name,
            patient_name=patient.full_name,
            email=patient.email,
            when=start.strftime("%a, %b %d, %Y at %I:%M %p"),
            appointment_type=appt.appointment_type.value,
            location=appt.location,
        )
        appt.reminder_sent_at = datetime.now(timezone.utc)

    return {"id": appt.id, "message": "Appointment booked"}


async def _get_owned(db, practitioner_id, appointment_id) -> Appointment:
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.patient))
        .where(Appointment.id == appointment_id, Appointment.practitioner_id == practitioner_id)
    )
    appt = result.scalars().first()
    if not appt:
        raise HTTPException(status_code=404, detail="Not found")
    return appt


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: int,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db),
):
    appt = await _get_owned(db, practitioner.id, appointment_id)
    return _appt_dict(appt, patient_name=appt.patient.full_name if appt.patient else None)


@router.patch("/{appointment_id}")
async def update_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db),
):
    appt = await _get_owned(db, practitioner.id, appointment_id)

    if body.patient_id is not None:
        await _require_owned_patient(db, practitioner.id, body.patient_id)
        appt.patient_id = body.patient_id

    new_start = _parse_dt(body.start_at) if body.start_at else appt.start_at
    new_end = _parse_dt(body.end_at) if body.end_at else appt.end_at
    if body.start_at or body.end_at:
        if new_end <= new_start:
            raise HTTPException(status_code=400, detail="End time must be after start time")
        if await _has_conflict(db, practitioner.id, new_start, new_end, exclude_id=appt.id):
            raise HTTPException(status_code=409, detail="This time slot overlaps an existing appointment")
        appt.start_at, appt.end_at = new_start, new_end

    if body.appointment_type is not None:
        appt.appointment_type = AppointmentType(body.appointment_type)
    if body.status is not None:
        appt.status = AppointmentStatus(body.status)
    if body.reason is not None:
        appt.reason = body.reason
    if body.notes is not None:
        appt.notes = body.notes
    if body.location is not None:
        appt.location = body.location
    if body.plan_id is not None:
        appt.plan_id = body.plan_id
    if body.therapy_id is not None:
        appt.therapy_id = body.therapy_id

    await db.flush()
    await db.refresh(appt, ["patient"])
    return _appt_dict(appt, patient_name=appt.patient.full_name if appt.patient else None)


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db),
):
    appt = await _get_owned(db, practitioner.id, appointment_id)
    await db.delete(appt)


@router.post("/{appointment_id}/send-reminder")
async def send_reminder(
    appointment_id: int,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db),
):
    appt = await _get_owned(db, practitioner.id, appointment_id)
    if not appt.patient or not appt.patient.email:
        raise HTTPException(status_code=400, detail="Patient has no email on file")
    send_appointment_reminder(
        practitioner_name=practitioner.display_name,
        patient_name=appt.patient.full_name,
        email=appt.patient.email,
        when=appt.start_at.strftime("%a, %b %d, %Y at %I:%M %p"),
        appointment_type=appt.appointment_type.value,
        location=appt.location,
    )
    appt.reminder_sent_at = datetime.now(timezone.utc)
    await db.flush()
    return {"message": "Reminder sent"}
