from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select, func
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentType, AppointmentStatus


@pytest.mark.asyncio
async def test_create_appointment_persists_with_enum_values(db_session, practitioner):
    patient = Patient(practitioner_id=practitioner.id, first_name="Asha", last_name="Patel")
    db_session.add(patient)
    await db_session.flush()

    start = datetime(2026, 7, 16, 9, 0, tzinfo=timezone.utc)
    appt = Appointment(
        practitioner_id=practitioner.id,
        patient_id=patient.id,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        appointment_type=AppointmentType.CONSULTATION,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appt)
    await db_session.commit()

    row = (await db_session.execute(select(Appointment))).scalars().first()
    assert row.appointment_type == AppointmentType.CONSULTATION
    assert row.appointment_type.value == "consultation"
    assert row.status.value == "scheduled"
    # appointment is linked to the patient (async-safe count — dynamic relations
    # can't be .count()'d directly inside an async session)
    count = await db_session.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.patient_id == patient.id)
    )
    assert count == 1
