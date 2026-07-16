# Calendar Scheduling with Drag-and-Drop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a doctor a native calendar (Day/Week/Month) where they can drag a patient onto a time slot to book, drag an appointment to reschedule, resize to change duration, and hover for details — backed by a new FastAPI `Appointment` resource.

**Architecture:** New `Appointment` SQLAlchemy model + FastAPI CRUD routes (overlap-checked, tenant-scoped) mirroring the existing `followups`/`therapies` conventions. A new React calendar built entirely from the app's existing primitives (`@dnd-kit`, `date-fns`, shadcn/ui, Tailwind tokens) — **no FullCalendar, no new dependency**. All calendar logic (date math, positioning, overlap layout, drag resolution) lives in pure functions in `lib/calendar/utils.ts` so it is unit-tested without DOM.

**Tech Stack:** FastAPI · SQLAlchemy 2 async · Alembic · Pydantic 2 · pytest (async, real Postgres) · Next.js 16 App Router · React 19 · TypeScript · React Query · `@dnd-kit` · `date-fns` · shadcn/ui · Tailwind 4 · vitest.

## Global Constraints

- **Additive only.** Do not modify or restyle any existing page/component. The only edits to existing files are the exact ones named in tasks (NAV array, `client.ts`, `models/__init__.py`, `main.py`, `email.py`, `Patient`/`Practitioner` relationships).
- **No new dependencies.** Everything needed (`@dnd-kit/*`, `date-fns`) is already in `frontend/package.json`.
- **Enum wire format is lowercase values.** `appointment_type` ∈ `consultation | follow_up | therapy | panchakarma`; `status` ∈ `scheduled | confirmed | completed | cancelled | no_show`. Backend serializes via `.value`; SQLAlchemy columns use `values_callable` so the DB stores these exact lowercase strings.
- **Backend model IDs are integers.** FKs: `practitioner_id → practitioners.id`, `patient_id → patients.id`, `plan_id → consultation_plans.id` (nullable), `therapy_id → therapies.id` (nullable).
- **Tenant scoping.** Every appointment query filters `Appointment.practitioner_id == practitioner.id`.
- **Handlers `await db.flush()` — never commit** (the `get_db` dependency commits at request end).
- **Colors use existing tokens only** (`chart-1..5`, `primary`, `muted-foreground`, etc.). No raw hex for structural UI.
- **Time grid:** 06:00–20:00 window, 30-minute slots, 28px per slot (`SLOT_PX`). Week starts Monday.
- **Backend tests need Postgres** at `postgresql+asyncpg://postgres:postgres@localhost:5432/dhanvantari` (via `docker-compose up -d db`), or override `TEST_DATABASE_URL`.
- Run backend commands from `backend/`, frontend commands from `frontend/`.

---

## Canonical data shapes (used across tasks)

**Backend `_appt_dict(appt, patient_name)` returns:**
```json
{
  "id": 1, "patient_id": 3, "practitioner_id": 1, "patient_name": "Asha Patel",
  "start_at": "2026-07-16T09:00:00+00:00", "end_at": "2026-07-16T09:30:00+00:00",
  "appointment_type": "consultation", "status": "scheduled",
  "reason": null, "notes": null, "location": null,
  "plan_id": null, "therapy_id": null, "reminder_sent_at": null,
  "created_at": "2026-07-16T08:00:00+00:00", "updated_at": "2026-07-16T08:00:00+00:00"
}
```

**Frontend `Appointment` type (Task 5, `lib/calendar/types.ts`)** mirrors that object exactly.

---

## Task 1: Backend — `Appointment` model, enums, relationships, registration

**Files:**
- Create: `backend/app/models/appointment.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/patient.py` (add one relationship)
- Modify: `backend/app/models/practitioner.py` (add one relationship)
- Test: `backend/tests/unit/test_appointments_model.py`

**Interfaces:**
- Produces: `Appointment` model (table `appointments`); `AppointmentType` (`consultation|follow_up|therapy|panchakarma`); `AppointmentStatus` (`scheduled|confirmed|completed|cancelled|no_show`). Columns: `id, practitioner_id, patient_id, start_at, end_at, appointment_type, status, reason, notes, location, plan_id, therapy_id, reminder_sent_at, created_at, updated_at`. Relationships `Appointment.patient`, `Appointment.practitioner`, `Patient.appointments`, `Practitioner.appointments`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_appointments_model.py
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
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
    # relationships load
    assert (await db_session.get(Patient, patient.id)).appointments.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_appointments_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.appointment'`

- [ ] **Step 3: Create the model**

```python
# backend/app/models/appointment.py
"""
Appointment — a time-slot booking between a practitioner and a patient.
Adds the time-of-day scheduling the date-only FollowUp lacks.
"""
from datetime import datetime, timezone
import enum
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AppointmentType(str, enum.Enum):
    CONSULTATION = "consultation"
    FOLLOW_UP    = "follow_up"
    THERAPY      = "therapy"
    PANCHAKARMA  = "panchakarma"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW   = "no_show"


# Store the lowercase .value (not the member name) in the DB enum type,
# so the wire format and DB match the frontend union types.
def _enum_values(e):
    return [m.value for m in e]


class Appointment(Base):
    __tablename__ = "appointments"

    id:              Mapped[int] = mapped_column(primary_key=True)
    practitioner_id: Mapped[int] = mapped_column(ForeignKey("practitioners.id"), nullable=False, index=True)
    patient_id:      Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    appointment_type: Mapped[AppointmentType] = mapped_column(
        SAEnum(AppointmentType, name="appointmenttype", values_callable=_enum_values),
        default=AppointmentType.CONSULTATION, nullable=False,
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, name="appointmentstatus", values_callable=_enum_values),
        default=AppointmentStatus.SCHEDULED, nullable=False,
    )

    reason:   Mapped[str | None] = mapped_column(String(300))
    notes:    Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))

    plan_id:    Mapped[int | None] = mapped_column(ForeignKey("consultation_plans.id"))
    therapy_id: Mapped[int | None] = mapped_column(ForeignKey("therapies.id"))

    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    patient:      Mapped["Patient"]      = relationship(back_populates="appointments")  # noqa: F821
    practitioner: Mapped["Practitioner"] = relationship(back_populates="appointments")  # noqa: F821
```

- [ ] **Step 4: Register the model in `models/__init__.py`**

Add the import after the `therapy` import line and extend `__all__`:

```python
from app.models.appointment import Appointment, AppointmentType, AppointmentStatus
```
```python
    # add to __all__ list:
    "Appointment", "AppointmentType", "AppointmentStatus",
```

- [ ] **Step 5: Add the `appointments` relationship to `Patient`**

In `backend/app/models/patient.py`, after the `consultation_notes` relationship (around line 70), add:

```python
    appointments:        Mapped[list["Appointment"]]        = relationship(back_populates="patient", lazy="dynamic", cascade="all, delete-orphan")  # noqa: F821
```

- [ ] **Step 6: Add the `appointments` relationship to `Practitioner`**

In `backend/app/models/practitioner.py`, after the `consultation_notes` relationship (around line 67), add:

```python
    appointments:       Mapped[list["Appointment"]]       = relationship(back_populates="practitioner", lazy="dynamic")  # noqa: F821
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_appointments_model.py -v`
Expected: PASS (2 assertions; relationship count == 1)

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/appointment.py backend/app/models/__init__.py backend/app/models/patient.py backend/app/models/practitioner.py backend/tests/unit/test_appointments_model.py
git commit -m "feat(appointments): add Appointment model, enums, relationships"
```

---

## Task 2: Backend — Alembic migration `0011_appointments`

**Files:**
- Create: `backend/alembic/versions/0011_appointments.py`

**Interfaces:**
- Consumes: the `Appointment` model column set from Task 1.
- Produces: the `appointments` table + `appointmenttype`/`appointmentstatus` pg enums in a real migrated DB.

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0011_appointments.py
"""Add appointments table for calendar scheduling.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

appointment_type = sa.Enum(
    "consultation", "follow_up", "therapy", "panchakarma", name="appointmenttype"
)
appointment_status = sa.Enum(
    "scheduled", "confirmed", "completed", "cancelled", "no_show", name="appointmentstatus"
)


def upgrade() -> None:
    bind = op.get_bind()
    appointment_type.create(bind, checkfirst=True)
    appointment_status.create(bind, checkfirst=True)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("practitioner_id", sa.Integer, sa.ForeignKey("practitioners.id"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("appointment_type", appointment_type, nullable=False, server_default="consultation"),
        sa.Column("status", appointment_status, nullable=False, server_default="scheduled"),
        sa.Column("reason", sa.String(300)),
        sa.Column("notes", sa.Text),
        sa.Column("location", sa.String(200)),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("consultation_plans.id")),
        sa.Column("therapy_id", sa.Integer, sa.ForeignKey("therapies.id")),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("appointments")
    bind = op.get_bind()
    appointment_status.drop(bind, checkfirst=True)
    appointment_type.drop(bind, checkfirst=True)
```

- [ ] **Step 2: Apply the migration**

Run: `cd backend && alembic upgrade head`
Expected: `Running upgrade 0010 -> 0011, Add appointments table for calendar scheduling` and no error.

- [ ] **Step 3: Verify round-trip (down then up)**

Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: downgrade drops the table/enums cleanly, upgrade re-creates them. No error.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0011_appointments.py
git commit -m "feat(appointments): add 0011 migration for appointments table"
```

---

## Task 3: Backend — appointment reminder email helper

**Files:**
- Modify: `backend/app/core/email.py` (append one function)
- Test: `backend/tests/unit/test_appointment_email.py`

**Interfaces:**
- Produces: `send_appointment_reminder(practitioner_name: str, patient_name: str, email: str, when: str, appointment_type: str, location: str | None) -> None` — Resend-backed, no-ops (returns cleanly) when `RESEND_API_KEY` is unset. Never raises.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_appointment_email.py
from app.core import email


def test_send_appointment_reminder_noops_without_key():
    # RESEND_API_KEY is "" in the test env (see conftest) — must return without raising.
    email.send_appointment_reminder(
        practitioner_name="Dr. Test",
        patient_name="Asha Patel",
        email="asha@example.com",
        when="Thu, Jul 16, 2026 at 9:00 AM",
        appointment_type="consultation",
        location=None,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_appointment_email.py -v`
Expected: FAIL — `AttributeError: module 'app.core.email' has no attribute 'send_appointment_reminder'`

- [ ] **Step 3: Append the helper to `email.py`**

```python
def send_appointment_reminder(
    practitioner_name: str,
    patient_name: str,
    email: str,
    when: str,
    appointment_type: str,
    location: str | None,
) -> None:
    """Email a patient an appointment confirmation / reminder."""
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping appointment reminder to %s", email)
        return

    try:
        resend = _get_resend()
        resend.Emails.send({
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
            "to": [email],
            "subject": f"Appointment confirmation — {when}",
            "html": f"""
            <div style="font-family: Georgia, serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
                <h2 style="color: #8B6914; margin-bottom: 8px;">Namaste, {patient_name}</h2>
                <p>Your {appointment_type.replace('_', ' ')} appointment with
                   <strong>{practitioner_name}</strong> is confirmed for <strong>{when}</strong>.</p>
                {f'<p>Location: {location}</p>' if location else ''}
                <p style="color: #888; font-size: 13px; margin-top: 32px;">
                    Please reach out if you need to reschedule.<br>
                    — {practitioner_name}
                </p>
            </div>
            """,
        })
        logger.info("Appointment reminder sent to %s", email)
    except Exception as e:
        logger.error("Failed to send appointment reminder to %s: %s", email, e)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_appointment_email.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/email.py backend/tests/unit/test_appointment_email.py
git commit -m "feat(appointments): add appointment reminder email helper"
```

---

## Task 4: Backend — appointment routes (CRUD + overlap + reminder)

**Files:**
- Create: `backend/app/api/routes/appointments.py`
- Modify: `backend/app/main.py` (import + include_router)
- Test: `backend/tests/unit/test_appointments_api.py`

**Interfaces:**
- Consumes: `Appointment`, `AppointmentType`, `AppointmentStatus` (Task 1); `send_appointment_reminder` (Task 3); `get_current_practitioner`, `get_db`.
- Produces HTTP API at `/api/appointments`:
  - `GET ""` → `list[_appt_dict]`, params `start,end` (ISO), `status`, `type`, `patient_id`
  - `POST ""` (201) → `{id, message}`; body `{patient_id, start_at, end_at, appointment_type?, reason?, notes?, location?, plan_id?, therapy_id?}`; `409` on overlap; `404` if patient not owned; `400` if `end<=start`
  - `GET "/{id}"` → `_appt_dict` or 404
  - `PATCH "/{id}"` → `_appt_dict`; any of `{start_at,end_at,appointment_type,status,reason,notes,location,plan_id,therapy_id,patient_id}`; `409` on overlap (excluding self)
  - `DELETE "/{id}"` (204)
  - `POST "/{id}/send-reminder"` → `{message}`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_appointments_api.py
from datetime import datetime, timedelta, timezone
import pytest_asyncio
import pytest
from app.models.patient import Patient
from app.core.security import hash_password, create_access_token
from app.models.practitioner import Practitioner, SubscriptionTier


def _iso(dt): return dt.isoformat()
BASE = datetime(2026, 7, 16, 9, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def patient(db_session, practitioner):
    p = Patient(practitioner_id=practitioner.id, first_name="Asha", last_name="Patel", email="asha@example.com")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


async def _create(client, headers, patient_id, start, minutes=30, **extra):
    body = {"patient_id": patient_id, "start_at": _iso(start),
            "end_at": _iso(start + timedelta(minutes=minutes)), **extra}
    return await client.post("/api/appointments", json=body, headers=headers)


@pytest.mark.asyncio
async def test_create_and_list(client, auth_headers, patient):
    r = await _create(client, auth_headers, patient.id, BASE, appointment_type="therapy")
    assert r.status_code == 201
    appt_id = r.json()["id"]

    r2 = await client.get("/api/appointments",
                          params={"start": _iso(BASE - timedelta(days=1)), "end": _iso(BASE + timedelta(days=1))},
                          headers=auth_headers)
    assert r2.status_code == 200
    rows = r2.json()
    assert len(rows) == 1
    assert rows[0]["id"] == appt_id
    assert rows[0]["appointment_type"] == "therapy"
    assert rows[0]["status"] == "scheduled"
    assert rows[0]["patient_name"] == "Asha Patel"


@pytest.mark.asyncio
async def test_overlap_returns_409(client, auth_headers, patient):
    assert (await _create(client, auth_headers, patient.id, BASE, 60)).status_code == 201
    # overlaps the 9:00-10:00 booking
    r = await _create(client, auth_headers, patient.id, BASE + timedelta(minutes=30), 60)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_cancelled_does_not_block(client, auth_headers, patient):
    r = await _create(client, auth_headers, patient.id, BASE, 60)
    appt_id = r.json()["id"]
    await client.patch(f"/api/appointments/{appt_id}", json={"status": "cancelled"}, headers=auth_headers)
    # same slot is now free
    r2 = await _create(client, auth_headers, patient.id, BASE, 60)
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_reschedule_via_patch(client, auth_headers, patient):
    r = await _create(client, auth_headers, patient.id, BASE, 30)
    appt_id = r.json()["id"]
    new_start = BASE + timedelta(hours=2)
    r2 = await client.patch(f"/api/appointments/{appt_id}",
                            json={"start_at": _iso(new_start), "end_at": _iso(new_start + timedelta(minutes=30))},
                            headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["start_at"].startswith("2026-07-16T11:00")


@pytest.mark.asyncio
async def test_end_before_start_rejected(client, auth_headers, patient):
    body = {"patient_id": patient.id, "start_at": _iso(BASE), "end_at": _iso(BASE - timedelta(minutes=30))}
    r = await client.post("/api/appointments", json=body, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_tenant_isolation(client, auth_headers, patient, db_session):
    r = await _create(client, auth_headers, patient.id, BASE)
    appt_id = r.json()["id"]
    # second practitioner
    other = Practitioner(name="Dr. Other", email="other@example.com",
                         password_hash=hash_password("x"), subscription_tier=SubscriptionTier.PRACTICE,
                         subscription_active=True)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}
    # other cannot see or fetch it
    assert (await client.get("/api/appointments",
            params={"start": _iso(BASE - timedelta(days=1)), "end": _iso(BASE + timedelta(days=1))},
            headers=other_headers)).json() == []
    assert (await client.get(f"/api/appointments/{appt_id}", headers=other_headers)).status_code == 404


@pytest.mark.asyncio
async def test_delete(client, auth_headers, patient):
    r = await _create(client, auth_headers, patient.id, BASE)
    appt_id = r.json()["id"]
    assert (await client.delete(f"/api/appointments/{appt_id}", headers=auth_headers)).status_code == 204
    assert (await client.get(f"/api/appointments/{appt_id}", headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_send_reminder_ok_without_key(client, auth_headers, patient):
    r = await _create(client, auth_headers, patient.id, BASE)
    appt_id = r.json()["id"]
    r2 = await client.post(f"/api/appointments/{appt_id}/send-reminder", headers=auth_headers)
    assert r2.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_appointments_api.py -v`
Expected: FAIL — 404s / `no attribute` because the router does not exist yet.

- [ ] **Step 3: Create the routes**

```python
# backend/app/api/routes/appointments.py
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
```

- [ ] **Step 4: Register the router in `main.py`**

Append `, appointments` to the combined `from app.api.routes import ...` line (line 13), and add after the `therapies` include_router lines:

```python
app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_appointments_api.py -v`
Expected: PASS (8 tests: create/list, overlap 409, cancelled-frees-slot, reschedule, end<start 400, tenant isolation, delete, reminder).

- [ ] **Step 6: Run the whole backend suite (no regressions)**

Run: `cd backend && python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/appointments.py backend/app/main.py backend/tests/unit/test_appointments_api.py
git commit -m "feat(appointments): add CRUD API with overlap prevention and reminders"
```

---

## Task 5: Frontend — types, calendar utils (pure logic + tests), API client, nav

**Files:**
- Create: `frontend/src/lib/calendar/types.ts`
- Create: `frontend/src/lib/calendar/utils.ts`
- Create: `frontend/src/lib/calendar/utils.test.ts`
- Modify: `frontend/src/lib/api/client.ts` (add `appointmentsApi`)
- Modify: `frontend/src/app/(dashboard)/layout.tsx` (add nav item)

**Interfaces:**
- Produces (`types.ts`): `AppointmentType`, `AppointmentStatus`, `Appointment`, `Patient`, `DragResolution`, `NewAppointmentDraft`.
- Produces (`utils.ts`): constants `SLOT_MIN_MINUTES=360`, `SLOT_MAX_MINUTES=1200`, `SLOT_MINUTES=30`, `SLOT_PX=28`; functions `buildWeekDays`, `buildTimeSlots`, `minutesSinceMidnight`, `positionForRange`, `layoutDay`, `snapToSlot`, `slotId`, `parseSlotId`, `draggableId`, `parseDraggableId`, `resolveDragEnd`, `typeColor`, `statusBlockClass`, `typeLabel`, `statusLabel`, `formatTimeRange`.
- Produces (`client.ts`): `appointmentsApi { list, get, create, update, remove, sendReminder }`.

- [ ] **Step 1: Create `types.ts`**

```typescript
// frontend/src/lib/calendar/types.ts
export type AppointmentType = "consultation" | "follow_up" | "therapy" | "panchakarma";
export type AppointmentStatus = "scheduled" | "confirmed" | "completed" | "cancelled" | "no_show";

export interface Appointment {
  id: number;
  patient_id: number;
  practitioner_id: number;
  patient_name?: string | null;
  start_at: string;   // ISO
  end_at: string;     // ISO
  appointment_type: AppointmentType;
  status: AppointmentStatus;
  reason?: string | null;
  notes?: string | null;
  location?: string | null;
  plan_id?: number | null;
  therapy_id?: number | null;
  reminder_sent_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Patient {
  id: number;
  full_name: string;
}

export type DragResolution =
  | { kind: "book"; patientId: number; start: Date }
  | { kind: "reschedule"; appointmentId: number; start: Date; end: Date };

export interface NewAppointmentDraft {
  patientId?: number;
  start: Date;
  end: Date;
}
```

- [ ] **Step 2: Write the failing utils tests**

```typescript
// frontend/src/lib/calendar/utils.test.ts
import { describe, it, expect } from "vitest";
import {
  buildWeekDays, buildTimeSlots, positionForRange, layoutDay,
  snapToSlot, slotId, parseSlotId, draggableId, parseDraggableId,
  resolveDragEnd, SLOT_PX,
} from "./utils";
import type { Appointment } from "./types";

function appt(id: number, start: string, end: string): Appointment {
  return {
    id, patient_id: 1, practitioner_id: 1, start_at: start, end_at: end,
    appointment_type: "consultation", status: "scheduled",
    created_at: start, updated_at: start,
  };
}

describe("buildWeekDays", () => {
  it("returns 7 days starting Monday", () => {
    const days = buildWeekDays(new Date("2026-07-16T12:00:00")); // Thursday
    expect(days).toHaveLength(7);
    expect(days[0].getDay()).toBe(1); // Monday
    expect(days[0].getDate()).toBe(13);
    expect(days[6].getDate()).toBe(19);
  });
});

describe("buildTimeSlots", () => {
  it("spans 06:00 to 19:30 in 30-min steps", () => {
    const slots = buildTimeSlots();
    expect(slots[0].minutes).toBe(360);
    expect(slots[slots.length - 1].minutes).toBe(1170);
    expect(slots).toHaveLength(28);
  });
});

describe("positionForRange", () => {
  it("puts a 9:00-9:30 block one hour (2 slots) below the top", () => {
    const pos = positionForRange(new Date("2026-07-16T07:00:00"), new Date("2026-07-16T07:30:00"));
    expect(pos.top).toBe(2 * SLOT_PX);   // 06:00->07:00 == 2 slots
    expect(pos.height).toBe(SLOT_PX);    // 30 min == 1 slot
  });
});

describe("layoutDay", () => {
  it("splits two overlapping appointments into two columns", () => {
    const a = appt(1, "2026-07-16T09:00:00", "2026-07-16T10:00:00");
    const b = appt(2, "2026-07-16T09:30:00", "2026-07-16T10:30:00");
    const laid = layoutDay([a, b]);
    expect(laid).toHaveLength(2);
    expect(laid.every((x) => x.columns === 2)).toBe(true);
    expect(new Set(laid.map((x) => x.column))).toEqual(new Set([0, 1]));
  });

  it("keeps non-overlapping appointments in a single column", () => {
    const a = appt(1, "2026-07-16T09:00:00", "2026-07-16T09:30:00");
    const b = appt(2, "2026-07-16T10:00:00", "2026-07-16T10:30:00");
    const laid = layoutDay([a, b]);
    expect(laid.every((x) => x.columns === 1 && x.column === 0)).toBe(true);
  });
});

describe("slot id round-trip", () => {
  it("parses what it serializes", () => {
    const d = new Date("2026-07-16T09:30:00");
    const parsed = parseSlotId(slotId(d));
    expect(parsed?.getTime()).toBe(d.getTime());
  });
  it("returns null for non-slot ids", () => {
    expect(parseSlotId("patient:5")).toBeNull();
  });
});

describe("draggable id round-trip", () => {
  it("parses patient and appt ids", () => {
    expect(parseDraggableId(draggableId("patient", 5))).toEqual({ kind: "patient", id: 5 });
    expect(parseDraggableId(draggableId("appt", 9))).toEqual({ kind: "appt", id: 9 });
  });
});

describe("snapToSlot", () => {
  it("snaps 09:47 down to 09:30", () => {
    const snapped = snapToSlot(new Date("2026-07-16T09:47:00"));
    expect(snapped.getMinutes()).toBe(30);
    expect(snapped.getHours()).toBe(9);
  });
});

describe("resolveDragEnd", () => {
  const target = "2026-07-16T11:00:00";
  it("resolves patient -> slot as a booking", () => {
    const res = resolveDragEnd(draggableId("patient", 3), slotId(new Date(target)), []);
    expect(res).toEqual({ kind: "book", patientId: 3, start: new Date(target) });
  });
  it("resolves appt -> slot as a reschedule preserving duration", () => {
    const a = appt(7, "2026-07-16T09:00:00", "2026-07-16T10:00:00"); // 60 min
    const res = resolveDragEnd(draggableId("appt", 7), slotId(new Date(target)), [a]);
    expect(res).toEqual({
      kind: "reschedule", appointmentId: 7,
      start: new Date(target), end: new Date("2026-07-16T12:00:00"),
    });
  });
  it("returns null when dropped outside any slot", () => {
    expect(resolveDragEnd(draggableId("appt", 7), null, [])).toBeNull();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/calendar/utils.test.ts`
Expected: FAIL — cannot resolve `./utils`.

- [ ] **Step 4: Implement `utils.ts`**

```typescript
// frontend/src/lib/calendar/utils.ts
import { addDays, startOfWeek } from "date-fns";
import type { Appointment, AppointmentType, AppointmentStatus, DragResolution } from "./types";

export const SLOT_MIN_MINUTES = 6 * 60;   // 06:00
export const SLOT_MAX_MINUTES = 20 * 60;  // 20:00
export const SLOT_MINUTES = 30;
export const SLOT_PX = 28;                // height of one 30-min slot

export function buildWeekDays(anchor: Date): Date[] {
  const monday = startOfWeek(anchor, { weekStartsOn: 1 });
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

export function buildTimeSlots(): { minutes: number; label: string }[] {
  const slots: { minutes: number; label: string }[] = [];
  for (let m = SLOT_MIN_MINUTES; m < SLOT_MAX_MINUTES; m += SLOT_MINUTES) {
    const h = Math.floor(m / 60);
    const min = m % 60;
    const ampm = h < 12 ? "am" : "pm";
    const h12 = h % 12 === 0 ? 12 : h % 12;
    slots.push({ minutes: m, label: min === 0 ? `${h12}${ampm}` : `${h12}:${String(min).padStart(2, "0")}` });
  }
  return slots;
}

export function minutesSinceMidnight(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

export function positionForRange(start: Date, end: Date): { top: number; height: number } {
  const startMin = Math.max(minutesSinceMidnight(start), SLOT_MIN_MINUTES);
  const endMin = Math.min(minutesSinceMidnight(end), SLOT_MAX_MINUTES);
  const top = ((startMin - SLOT_MIN_MINUTES) / SLOT_MINUTES) * SLOT_PX;
  const height = Math.max(((endMin - startMin) / SLOT_MINUTES) * SLOT_PX, SLOT_PX * 0.6);
  return { top, height };
}

export interface LaidOutAppointment {
  appt: Appointment;
  column: number;
  columns: number;
}

// Greedy interval-graph column assignment for a single day's appointments.
export function layoutDay(appts: Appointment[]): LaidOutAppointment[] {
  const sorted = [...appts].sort(
    (a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()
  );
  const result: LaidOutAppointment[] = [];
  let cluster: Appointment[] = [];
  let clusterEnd = -Infinity;

  const flush = () => {
    if (cluster.length === 0) return;
    const colEnd: number[] = []; // last end-time per column
    const assign = new Map<number, number>();
    for (const a of cluster) {
      const s = new Date(a.start_at).getTime();
      let col = colEnd.findIndex((e) => e <= s);
      if (col === -1) { col = colEnd.length; colEnd.push(0); }
      colEnd[col] = new Date(a.end_at).getTime();
      assign.set(a.id, col);
    }
    const columns = colEnd.length;
    for (const a of cluster) result.push({ appt: a, column: assign.get(a.id)!, columns });
    cluster = [];
    clusterEnd = -Infinity;
  };

  for (const a of sorted) {
    const s = new Date(a.start_at).getTime();
    if (s >= clusterEnd && cluster.length > 0) flush();
    cluster.push(a);
    clusterEnd = Math.max(clusterEnd, new Date(a.end_at).getTime());
  }
  flush();
  return result;
}

export function snapToSlot(date: Date): Date {
  const snapped = new Date(date);
  snapped.setMinutes(Math.floor(snapped.getMinutes() / SLOT_MINUTES) * SLOT_MINUTES, 0, 0);
  return snapped;
}

export function slotId(date: Date): string {
  return `slot:${date.toISOString()}`;
}

export function parseSlotId(id: string): Date | null {
  if (!id.startsWith("slot:")) return null;
  const d = new Date(id.slice(5));
  return isNaN(d.getTime()) ? null : d;
}

export function draggableId(kind: "patient" | "appt", id: number): string {
  return `${kind}:${id}`;
}

export function parseDraggableId(id: string): { kind: "patient" | "appt"; id: number } | null {
  const [kind, raw] = id.split(":");
  if ((kind === "patient" || kind === "appt") && raw) return { kind, id: Number(raw) };
  return null;
}

export function resolveDragEnd(
  activeId: string,
  overId: string | null,
  appts: Appointment[]
): DragResolution | null {
  if (!overId) return null;
  const slot = parseSlotId(overId);
  const active = parseDraggableId(activeId);
  if (!slot || !active) return null;

  if (active.kind === "patient") {
    return { kind: "book", patientId: active.id, start: slot };
  }
  const appt = appts.find((a) => a.id === active.id);
  if (!appt) return null;
  const durationMs = new Date(appt.end_at).getTime() - new Date(appt.start_at).getTime();
  return { kind: "reschedule", appointmentId: appt.id, start: slot, end: new Date(slot.getTime() + durationMs) };
}

// ── Presentation helpers ────────────────────────────────────────────────────

export function typeColor(type: AppointmentType): { block: string; accent: string; dot: string } {
  switch (type) {
    case "consultation": return { block: "bg-chart-1/15 text-foreground", accent: "border-l-chart-1", dot: "bg-chart-1" };
    case "follow_up":    return { block: "bg-chart-2/15 text-foreground", accent: "border-l-chart-2", dot: "bg-chart-2" };
    case "therapy":      return { block: "bg-chart-4/15 text-foreground", accent: "border-l-chart-4", dot: "bg-chart-4" };
    case "panchakarma":  return { block: "bg-chart-3/15 text-foreground", accent: "border-l-chart-3", dot: "bg-chart-3" };
  }
}

export function statusBlockClass(status: AppointmentStatus): string {
  switch (status) {
    case "cancelled": return "opacity-50 line-through";
    case "no_show":   return "opacity-60 border-dashed";
    case "completed": return "opacity-75";
    default:          return "";
  }
}

export function typeLabel(type: AppointmentType): string {
  return { consultation: "Consultation", follow_up: "Follow-up", therapy: "Therapy", panchakarma: "Panchakarma" }[type];
}

export function statusLabel(status: AppointmentStatus): string {
  return { scheduled: "Scheduled", confirmed: "Confirmed", completed: "Completed", cancelled: "Cancelled", no_show: "No-show" }[status];
}

export function formatTimeRange(start: Date, end: Date): string {
  const fmt = (d: Date) => d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${fmt(start)} – ${fmt(end)}`;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/calendar/utils.test.ts`
Expected: PASS (all describe blocks green).

- [ ] **Step 6: Add `appointmentsApi` to `client.ts`**

Insert after the `followupsApi` block:

```typescript
export const appointmentsApi = {
  list:         (params?: { start?: string; end?: string; status?: string; type?: string; patient_id?: number }) =>
    api.get("/api/appointments", { params }),
  get:          (id: number)                => api.get(`/api/appointments/${id}`),
  create:       (data: unknown)             => api.post("/api/appointments", data),
  update:       (id: number, data: unknown) => api.patch(`/api/appointments/${id}`, data),
  remove:       (id: number)                => api.delete(`/api/appointments/${id}`),
  sendReminder: (id: number)                => api.post(`/api/appointments/${id}/send-reminder`),
};
```

- [ ] **Step 7: Add the nav item in `layout.tsx`**

Add `CalendarDays` to the `lucide-react` import block, then add this entry to the `NAV` array immediately after the Follow-ups line:

```typescript
  { href: "/calendar",    label: "Appointments", icon: CalendarDays },
```

- [ ] **Step 8: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

```bash
git add frontend/src/lib/calendar/types.ts frontend/src/lib/calendar/utils.ts frontend/src/lib/calendar/utils.test.ts frontend/src/lib/api/client.ts "frontend/src/app/(dashboard)/layout.tsx"
git commit -m "feat(calendar): add appointment types, calendar utils, api client, nav"
```

---

## Task 6: Frontend — presentational components (tooltip, patient panel, header, block, dialog)

**Files:**
- Create: `frontend/src/components/calendar/appointment-tooltip.tsx`
- Create: `frontend/src/components/calendar/patient-panel.tsx`
- Create: `frontend/src/components/calendar/calendar-header.tsx`
- Create: `frontend/src/components/calendar/appointment-block.tsx`
- Create: `frontend/src/components/calendar/appointment-dialog.tsx`

**Interfaces:**
- Consumes: `Appointment`, `Patient`, `AppointmentType`, `AppointmentStatus`, `NewAppointmentDraft` (Task 5); `typeColor`, `statusBlockClass`, `typeLabel`, `statusLabel`, `formatTimeRange`, `draggableId`, `SLOT_PX` (Task 5); `appointmentsApi` unused here.
- Produces:
  - `AppointmentTooltip({ appt, x, y })`
  - `PatientPanel({ patients, search, onSearch })` (renders `@dnd-kit` `useDraggable` cards `patient:<id>`)
  - `CalendarHeader({ view, onView, label, onPrev, onNext, onToday, onNew, typeFilter, onTypeFilter })`
  - `AppointmentBlock({ appt, style, onOpen, onResizeEnd })` (draggable `appt:<id>`, bottom resize handle, hover→tooltip)
  - `AppointmentDialog({ open, onClose, patients, draft, editing, onSubmit, isPending, error })`

- [ ] **Step 1: Create `appointment-tooltip.tsx`**

```tsx
// frontend/src/components/calendar/appointment-tooltip.tsx
"use client";

import { User, Stethoscope, MapPin, ArrowUpRight } from "lucide-react";
import type { Appointment } from "@/lib/calendar/types";
import { typeLabel, statusLabel, formatTimeRange } from "@/lib/calendar/utils";

export function AppointmentTooltip({ appt, x, y }: { appt: Appointment; x: number; y: number }) {
  return (
    <div
      className="fixed z-[9999] max-w-[280px] rounded-lg border bg-card p-3 text-xs shadow-xl pointer-events-none"
      style={{ top: y, left: x }}
    >
      <p className="font-semibold text-sm mb-1.5">
        {formatTimeRange(new Date(appt.start_at), new Date(appt.end_at))}
      </p>
      <p className="flex items-center gap-1.5 text-foreground">
        <User className="size-3 text-muted-foreground" /> {appt.patient_name ?? "Patient"}
      </p>
      <p className="flex items-center gap-1.5 text-muted-foreground mt-0.5">
        <Stethoscope className="size-3" /> {typeLabel(appt.appointment_type)} · {statusLabel(appt.status)}
      </p>
      {appt.location && (
        <p className="flex items-center gap-1.5 text-muted-foreground mt-0.5">
          <MapPin className="size-3" /> {appt.location}
        </p>
      )}
      {appt.reason && <p className="text-muted-foreground mt-1 italic">{appt.reason}</p>}
      <span className="mt-2 inline-flex items-center gap-1 text-primary">
        Open details <ArrowUpRight className="size-3" />
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Create `patient-panel.tsx`**

```tsx
// frontend/src/components/calendar/patient-panel.tsx
"use client";

import { useDraggable } from "@dnd-kit/core";
import { GripVertical, Search } from "lucide-react";
import type { Patient } from "@/lib/calendar/types";
import { draggableId } from "@/lib/calendar/utils";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

function PatientCard({ patient }: { patient: Patient }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: draggableId("patient", patient.id),
  });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={cn(
        "flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm cursor-grab active:cursor-grabbing touch-none select-none",
        isDragging && "opacity-50 shadow-lg ring-2 ring-primary/20"
      )}
    >
      <GripVertical className="size-3.5 text-muted-foreground shrink-0" />
      <span className="truncate">{patient.full_name}</span>
    </div>
  );
}

export function PatientPanel({
  patients,
  search,
  onSearch,
}: {
  patients: Patient[];
  search: string;
  onSearch: (v: string) => void;
}) {
  const filtered = patients.filter((p) => p.full_name.toLowerCase().includes(search.toLowerCase()));
  return (
    <div className="w-56 shrink-0 border-r flex flex-col">
      <div className="p-3 border-b">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Patients</p>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
          <Input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search…"
            className="pl-8 h-8"
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        <p className="text-[11px] text-muted-foreground mb-1">Drag a patient onto a time slot →</p>
        {filtered.map((p) => <PatientCard key={p.id} patient={p} />)}
        {filtered.length === 0 && <p className="text-xs text-muted-foreground py-4 text-center">No patients.</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `calendar-header.tsx`**

```tsx
// frontend/src/components/calendar/calendar-header.tsx
"use client";

import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AppointmentType } from "@/lib/calendar/types";
import { typeLabel } from "@/lib/calendar/utils";

export type CalendarView = "day" | "week" | "month";
const VIEWS: CalendarView[] = ["day", "week", "month"];
const TYPES: AppointmentType[] = ["consultation", "follow_up", "therapy", "panchakarma"];

export function CalendarHeader({
  view, onView, label, onPrev, onNext, onToday, onNew, typeFilter, onTypeFilter,
}: {
  view: CalendarView;
  onView: (v: CalendarView) => void;
  label: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  onNew: () => void;
  typeFilter: AppointmentType | null;
  onTypeFilter: (t: AppointmentType | null) => void;
}) {
  return (
    <div className="space-y-3 p-6 pb-3 border-b">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Appointments</h1>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={onPrev}><ChevronLeft className="size-4" /></Button>
            <Button variant="outline" size="sm" onClick={onToday}>Today</Button>
            <Button variant="ghost" size="icon-sm" onClick={onNext}><ChevronRight className="size-4" /></Button>
          </div>
          <span className="text-sm text-muted-foreground">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1 rounded-lg border p-0.5">
            {VIEWS.map((v) => (
              <button
                key={v}
                onClick={() => onView(v)}
                className={cn(
                  "text-sm px-3 py-1 rounded-md capitalize transition-colors",
                  view === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {v}
              </button>
            ))}
          </div>
          <Button size="sm" className="gap-1.5" onClick={onNew}><Plus className="size-4" /> New appointment</Button>
        </div>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        <button
          onClick={() => onTypeFilter(null)}
          className={cn("text-xs px-2.5 py-1 rounded-full border transition-colors",
            typeFilter === null ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground")}
        >
          All
        </button>
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => onTypeFilter(typeFilter === t ? null : t)}
            className={cn("text-xs px-2.5 py-1 rounded-full border transition-colors",
              typeFilter === t ? "bg-primary text-primary-foreground border-primary" : "text-muted-foreground hover:text-foreground")}
          >
            {typeLabel(t)}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `appointment-block.tsx`**

```tsx
// frontend/src/components/calendar/appointment-block.tsx
"use client";

import { useRef, useState } from "react";
import { useDraggable } from "@dnd-kit/core";
import type { Appointment } from "@/lib/calendar/types";
import {
  typeColor, statusBlockClass, typeLabel, draggableId,
  SLOT_PX, SLOT_MINUTES,
} from "@/lib/calendar/utils";
import { AppointmentTooltip } from "./appointment-tooltip";
import { cn } from "@/lib/utils";

export function AppointmentBlock({
  appt, style, onOpen, onResizeEnd,
}: {
  appt: Appointment;
  style: { top: number; height: number; left: string; width: string };
  onOpen: (appt: Appointment) => void;
  onResizeEnd: (appt: Appointment, newEnd: Date) => void;
}) {
  const color = typeColor(appt.appointment_type);
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: draggableId("appt", appt.id) });
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null);
  const [resizeDelta, setResizeDelta] = useState(0);
  const resizing = useRef(false);

  function onResizePointerDown(e: React.PointerEvent) {
    e.stopPropagation();
    e.preventDefault();
    resizing.current = true;
    const startY = e.clientY;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);

    const move = (ev: PointerEvent) => {
      if (!resizing.current) return;
      const slots = Math.round((ev.clientY - startY) / SLOT_PX);
      setResizeDelta(slots * SLOT_PX);
    };
    const up = (ev: PointerEvent) => {
      resizing.current = false;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      const slots = Math.round((ev.clientY - startY) / SLOT_PX);
      setResizeDelta(0);
      if (slots !== 0) {
        const newEnd = new Date(new Date(appt.end_at).getTime() + slots * SLOT_MINUTES * 60_000);
        if (newEnd.getTime() > new Date(appt.start_at).getTime()) onResizeEnd(appt, newEnd);
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  return (
    <>
      <div
        ref={setNodeRef}
        {...attributes}
        {...listeners}
        onClick={() => onOpen(appt)}
        onMouseEnter={(e) => {
          const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
          setTip({ x: r.right + 8, y: r.top });
        }}
        onMouseLeave={() => setTip(null)}
        style={{
          top: style.top, height: style.height + resizeDelta, left: style.left, width: style.width,
        }}
        className={cn(
          "absolute rounded-md border border-l-4 px-1.5 py-1 text-[11px] leading-tight overflow-hidden cursor-grab active:cursor-grabbing touch-none",
          color.block, color.accent, statusBlockClass(appt.status),
          isDragging && "opacity-60 shadow-lg z-20"
        )}
      >
        <p className="font-semibold truncate">{appt.patient_name ?? "Patient"}</p>
        <p className="truncate text-muted-foreground">{typeLabel(appt.appointment_type)}</p>
        <div
          onPointerDown={onResizePointerDown}
          onClick={(e) => e.stopPropagation()}
          className="absolute inset-x-0 bottom-0 h-2 cursor-ns-resize"
        />
      </div>
      {tip && !isDragging && <AppointmentTooltip appt={appt} x={tip.x} y={tip.y} />}
    </>
  );
}
```

- [ ] **Step 5: Create `appointment-dialog.tsx`**

```tsx
// frontend/src/components/calendar/appointment-dialog.tsx
"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { therapiesApi, plansApi } from "@/lib/api/client";
import type { Appointment, AppointmentType, AppointmentStatus, Patient, NewAppointmentDraft } from "@/lib/calendar/types";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const TYPES: AppointmentType[] = ["consultation", "follow_up", "therapy", "panchakarma"];
const STATUSES: AppointmentStatus[] = ["scheduled", "confirmed", "completed", "cancelled", "no_show"];

function toDateInput(d: Date) { return d.toLocaleDateString("en-CA"); }              // yyyy-mm-dd (local)
function toTimeInput(d: Date) { return d.toTimeString().slice(0, 5); }               // HH:MM (local)
function combine(dateStr: string, timeStr: string): Date { return new Date(`${dateStr}T${timeStr}`); }

export interface AppointmentSubmit {
  patient_id: number;
  start_at: string;
  end_at: string;
  appointment_type: AppointmentType;
  status?: AppointmentStatus;
  reason?: string;
  location?: string;
  notes?: string;
  therapy_id?: number | null;
  plan_id?: number | null;
}

export function AppointmentDialog({
  open, onClose, patients, draft, editing, onSubmit, isPending, error,
}: {
  open: boolean;
  onClose: () => void;
  patients: Patient[];
  draft: NewAppointmentDraft | null;
  editing: Appointment | null;
  onSubmit: (payload: AppointmentSubmit) => void;
  isPending: boolean;
  error: string | null;
}) {
  const initialStart = editing ? new Date(editing.start_at) : draft?.start ?? new Date();
  const initialEnd = editing ? new Date(editing.end_at) : draft?.end ?? new Date();

  const [patientId, setPatientId] = useState("");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [type, setType] = useState<AppointmentType>("consultation");
  const [status, setStatus] = useState<AppointmentStatus>("scheduled");
  const [reason, setReason] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [therapyId, setTherapyId] = useState("");
  const [attachPlan, setAttachPlan] = useState(false);

  // Reset fields whenever the dialog opens for a new draft/edit.
  useEffect(() => {
    if (!open) return;
    setPatientId(editing ? String(editing.patient_id) : draft?.patientId ? String(draft.patientId) : "");
    setDate(toDateInput(initialStart));
    setStartTime(toTimeInput(initialStart));
    setEndTime(toTimeInput(initialEnd));
    setType(editing?.appointment_type ?? "consultation");
    setStatus(editing?.status ?? "scheduled");
    setReason(editing?.reason ?? "");
    setLocation(editing?.location ?? "");
    setNotes(editing?.notes ?? "");
    setTherapyId(editing?.therapy_id ? String(editing.therapy_id) : "");
    setAttachPlan(Boolean(editing?.plan_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing, draft]);

  const { data: therapies = [] } = useQuery<{ id: number; name: string }[]>({
    queryKey: ["therapies"],
    queryFn: () => therapiesApi.list().then((r) => r.data),
    enabled: open,
  });

  const { data: activePlan } = useQuery<{ id: number } | null>({
    queryKey: ["active-plan", patientId],
    queryFn: () => plansApi.get(Number(patientId)).then((r) => r.data).catch(() => null),
    enabled: open && !!patientId,
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      patient_id: Number(patientId),
      start_at: combine(date, startTime).toISOString(),
      end_at: combine(date, endTime).toISOString(),
      appointment_type: type,
      status: editing ? status : undefined,
      reason: reason || undefined,
      location: location || undefined,
      notes: notes || undefined,
      therapy_id: therapyId ? Number(therapyId) : null,
      plan_id: attachPlan && activePlan?.id ? activePlan.id : null,
    });
  }

  return (
    <Dialog open={open} onClose={onClose} title={editing ? "Edit appointment" : "New appointment"}>
      <form onSubmit={submit} className="space-y-4">
        {error && <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>}

        <div className="space-y-1.5">
          <Label>Patient *</Label>
          <Select required value={patientId} onChange={(e) => setPatientId(e.target.value)}>
            <option value="">Select patient…</option>
            {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </Select>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5 col-span-1">
            <Label>Date *</Label>
            <Input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Start *</Label>
            <Input type="time" required step={1800} value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>End *</Label>
            <Input type="time" required step={1800} value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label>Type</Label>
            <Select value={type} onChange={(e) => setType(e.target.value as AppointmentType)}>
              {TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
            </Select>
          </div>
          {editing && (
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={status} onChange={(e) => setStatus(e.target.value as AppointmentStatus)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </Select>
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <Label>Reason</Label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Panchakarma consult" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label>Location</Label>
            <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Clinic / Telehealth" />
          </div>
          <div className="space-y-1.5">
            <Label>Link therapy</Label>
            <Select value={therapyId} onChange={(e) => setTherapyId(e.target.value)}>
              <option value="">None</option>
              {therapies.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </div>
        </div>

        {activePlan?.id && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={attachPlan} onChange={(e) => setAttachPlan(e.target.checked)} />
            Attach to patient&apos;s active care plan
          </label>
        )}

        <div className="space-y-1.5">
          <Label>Notes</Label>
          <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={isPending}>{isPending ? "Saving…" : editing ? "Save" : "Book"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 6: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

```bash
git add frontend/src/components/calendar/
git commit -m "feat(calendar): add tooltip, patient panel, header, block, dialog components"
```

---

## Task 7: Frontend — week/day + month view components

**Files:**
- Create: `frontend/src/components/calendar/calendar-week-view.tsx`
- Create: `frontend/src/components/calendar/calendar-month-view.tsx`

**Interfaces:**
- Consumes: `Appointment` (Task 5); `buildWeekDays`, `buildTimeSlots`, `positionForRange`, `layoutDay`, `slotId`, `SLOT_PX`, `SLOT_MINUTES`, `SLOT_MIN_MINUTES`, `typeColor`, `typeLabel` (Task 5); `AppointmentBlock` (Task 6).
- Produces:
  - `CalendarWeekView({ days, appointments, onOpen, onResizeEnd })` (days is 7 for week, 1 for day)
  - `CalendarMonthView({ anchor, appointments, onOpen })`

- [ ] **Step 1: Create `calendar-week-view.tsx`**

```tsx
// frontend/src/components/calendar/calendar-week-view.tsx
"use client";

import { useDroppable } from "@dnd-kit/core";
import { isSameDay } from "date-fns";
import type { Appointment } from "@/lib/calendar/types";
import {
  buildTimeSlots, positionForRange, layoutDay, slotId,
  SLOT_PX, SLOT_MINUTES, SLOT_MIN_MINUTES,
} from "@/lib/calendar/utils";
import { AppointmentBlock } from "./appointment-block";
import { cn } from "@/lib/utils";

function DroppableSlot({ day, minutes }: { day: Date; minutes: number }) {
  const slotDate = new Date(day);
  slotDate.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
  const { setNodeRef, isOver } = useDroppable({ id: slotId(slotDate) });
  return (
    <div
      ref={setNodeRef}
      style={{ height: SLOT_PX }}
      className={cn("border-b border-r border-border/50", isOver && "bg-primary/10")}
    />
  );
}

export function CalendarWeekView({
  days, appointments, onOpen, onResizeEnd,
}: {
  days: Date[];
  appointments: Appointment[];
  onOpen: (a: Appointment) => void;
  onResizeEnd: (a: Appointment, newEnd: Date) => void;
}) {
  const slots = buildTimeSlots();
  const now = new Date();

  return (
    <div className="flex-1 overflow-auto">
      <div className="grid" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(120px, 1fr))` }}>
        {/* Header row */}
        <div className="sticky top-0 z-10 bg-background border-b h-12" />
        {days.map((d) => (
          <div key={d.toISOString()} className="sticky top-0 z-10 bg-background border-b border-l h-12 flex flex-col items-center justify-center">
            <span className="text-xs text-muted-foreground">{d.toLocaleDateString("en-US", { weekday: "short" })}</span>
            <span className={cn("text-sm font-semibold", isSameDay(d, now) && "text-primary")}>{d.getDate()}</span>
          </div>
        ))}

        {/* Time gutter */}
        <div>
          {slots.map((s) => (
            <div key={s.minutes} style={{ height: SLOT_PX }} className="text-[10px] text-muted-foreground text-right pr-1.5 -translate-y-1.5">
              {s.label}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((day) => {
          const dayAppts = appointments.filter((a) => isSameDay(new Date(a.start_at), day));
          const laid = layoutDay(dayAppts);
          const isBusinessDay = day.getDay() >= 1 && day.getDay() <= 5;
          return (
            <div key={day.toISOString()} className={cn("relative", isBusinessDay && "bg-accent/20")}>
              {slots.map((s) => <DroppableSlot key={s.minutes} day={day} minutes={s.minutes} />)}

              {/* now-indicator */}
              {isSameDay(day, now) && (() => {
                const mins = now.getHours() * 60 + now.getMinutes();
                if (mins < SLOT_MIN_MINUTES) return null;
                const top = ((mins - SLOT_MIN_MINUTES) / SLOT_MINUTES) * SLOT_PX;
                return <div className="absolute inset-x-0 z-10 border-t-2 border-primary" style={{ top }} />;
              })()}

              {laid.map(({ appt, column, columns }) => {
                const pos = positionForRange(new Date(appt.start_at), new Date(appt.end_at));
                const width = 100 / columns;
                return (
                  <AppointmentBlock
                    key={appt.id}
                    appt={appt}
                    style={{ top: pos.top, height: pos.height, left: `${column * width}%`, width: `calc(${width}% - 2px)` }}
                    onOpen={onOpen}
                    onResizeEnd={onResizeEnd}
                  />
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `calendar-month-view.tsx`**

```tsx
// frontend/src/components/calendar/calendar-month-view.tsx
"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  startOfMonth, endOfMonth, startOfWeek, endOfWeek, addDays, isSameMonth, isSameDay,
} from "date-fns";
import type { Appointment } from "@/lib/calendar/types";
import { slotId, typeColor, typeLabel } from "@/lib/calendar/utils";
import { cn } from "@/lib/utils";

function DayCell({
  day, anchor, appts, onOpen,
}: {
  day: Date;
  anchor: Date;
  appts: Appointment[];
  onOpen: (a: Appointment) => void;
}) {
  // Dropping on a month cell books at 9:00am that day.
  const slotDate = new Date(day);
  slotDate.setHours(9, 0, 0, 0);
  const { setNodeRef, isOver } = useDroppable({ id: slotId(slotDate) });
  const now = new Date();
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "min-h-24 border-b border-r p-1.5 space-y-1 overflow-hidden",
        !isSameMonth(day, anchor) && "bg-muted/30 text-muted-foreground",
        isOver && "bg-primary/10"
      )}
    >
      <span className={cn("text-xs font-medium", isSameDay(day, now) && "text-primary font-semibold")}>{day.getDate()}</span>
      {appts.slice(0, 3).map((a) => {
        const color = typeColor(a.appointment_type);
        return (
          <button
            key={a.id}
            onClick={() => onOpen(a)}
            className={cn("block w-full text-left rounded px-1.5 py-0.5 text-[10px] truncate border-l-2", color.block, color.accent)}
          >
            {new Date(a.start_at).toLocaleTimeString("en-US", { hour: "numeric" })} {a.patient_name ?? typeLabel(a.appointment_type)}
          </button>
        );
      })}
      {appts.length > 3 && <span className="text-[10px] text-muted-foreground">+{appts.length - 3} more</span>}
    </div>
  );
}

export function CalendarMonthView({
  anchor, appointments, onOpen,
}: {
  anchor: Date;
  appointments: Appointment[];
  onOpen: (a: Appointment) => void;
}) {
  const gridStart = startOfWeek(startOfMonth(anchor), { weekStartsOn: 1 });
  const gridEnd = endOfWeek(endOfMonth(anchor), { weekStartsOn: 1 });
  const days: Date[] = [];
  for (let d = gridStart; d <= gridEnd; d = addDays(d, 1)) days.push(d);

  return (
    <div className="flex-1 overflow-auto">
      <div className="grid grid-cols-7 border-t border-l">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="border-b border-r px-2 py-1.5 text-xs font-medium text-muted-foreground">{d}</div>
        ))}
        {days.map((day) => (
          <DayCell
            key={day.toISOString()}
            day={day}
            anchor={anchor}
            appts={appointments.filter((a) => isSameDay(new Date(a.start_at), day))}
            onOpen={onOpen}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck + commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

```bash
git add frontend/src/components/calendar/calendar-week-view.tsx frontend/src/components/calendar/calendar-month-view.tsx
git commit -m "feat(calendar): add week/day and month view grids"
```

---

## Task 8: Frontend — calendar page container (DndContext + queries + mutations)

**Files:**
- Create: `frontend/src/app/(dashboard)/calendar/page.tsx`
- Test: `frontend/src/app/(dashboard)/calendar/page.test.tsx`

**Interfaces:**
- Consumes: everything above; `appointmentsApi`, `patientsApi`.
- Produces: the `/calendar` route — a client page composing header + patient panel + week/day/month views inside one `DndContext`, wired to React Query.

- [ ] **Step 1: Write a render smoke test**

```tsx
// frontend/src/app/(dashboard)/calendar/page.test.tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi } from "vitest";
import CalendarPage from "./page";

vi.mock("@/lib/api/client", () => ({
  appointmentsApi: { list: () => Promise.resolve({ data: [] }) },
  patientsApi: { list: () => Promise.resolve({ data: [] }) },
  therapiesApi: { list: () => Promise.resolve({ data: [] }) },
  plansApi: { get: () => Promise.resolve({ data: null }) },
}));

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("CalendarPage", () => {
  it("renders the header and patient panel", async () => {
    wrap(<CalendarPage />);
    expect(await screen.findByText("Appointments")).toBeInTheDocument();
    expect(screen.getByText("New appointment")).toBeInTheDocument();
    expect(screen.getByText("Patients")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run "src/app/(dashboard)/calendar/page.test.tsx"`
Expected: FAIL — cannot resolve `./page`.

- [ ] **Step 3: Implement the page**

```tsx
// frontend/src/app/(dashboard)/calendar/page.tsx
"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext, PointerSensor, KeyboardSensor, useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core";
import { addDays, addMonths, startOfWeek, endOfWeek, startOfMonth, endOfMonth, format } from "date-fns";
import { appointmentsApi, patientsApi } from "@/lib/api/client";
import type { Appointment, Patient, NewAppointmentDraft, AppointmentType } from "@/lib/calendar/types";
import { buildWeekDays, resolveDragEnd, SLOT_MINUTES } from "@/lib/calendar/utils";
import { CalendarHeader, type CalendarView } from "@/components/calendar/calendar-header";
import { PatientPanel } from "@/components/calendar/patient-panel";
import { CalendarWeekView } from "@/components/calendar/calendar-week-view";
import { CalendarMonthView } from "@/components/calendar/calendar-month-view";
import { AppointmentDialog, type AppointmentSubmit } from "@/components/calendar/appointment-dialog";

function extractError(err: unknown): string {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Something went wrong";
}

export default function CalendarPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<CalendarView>("week");
  const [anchor, setAnchor] = useState<Date>(new Date());
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<AppointmentType | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [draft, setDraft] = useState<NewAppointmentDraft | null>(null);
  const [editing, setEditing] = useState<Appointment | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Visible date range for the query.
  const [rangeStart, rangeEnd] = useMemo(() => {
    if (view === "month") return [startOfWeek(startOfMonth(anchor), { weekStartsOn: 1 }), endOfWeek(endOfMonth(anchor), { weekStartsOn: 1 })];
    if (view === "day") return [anchor, addDays(anchor, 1)];
    return [startOfWeek(anchor, { weekStartsOn: 1 }), addDays(startOfWeek(anchor, { weekStartsOn: 1 }), 7)];
  }, [view, anchor]);

  const rangeKey = `${rangeStart.toISOString()}_${rangeEnd.toISOString()}`;

  const { data: appointments = [] } = useQuery<Appointment[]>({
    queryKey: ["appointments", rangeKey, typeFilter],
    queryFn: () =>
      appointmentsApi
        .list({ start: rangeStart.toISOString(), end: rangeEnd.toISOString(), type: typeFilter ?? undefined })
        .then((r) => r.data),
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["patients"],
    queryFn: () => patientsApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (payload: AppointmentSubmit) => appointmentsApi.create(payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["appointments"] }); closeDialog(); },
    onError: (err) => setFormError(extractError(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<AppointmentSubmit> }) => appointmentsApi.update(id, payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["appointments"] }); closeDialog(); },
    onError: (err) => setFormError(extractError(err)),
  });

  const rescheduleMutation = useMutation({
    mutationFn: ({ id, start, end }: { id: number; start: Date; end: Date }) =>
      appointmentsApi.update(id, { start_at: start.toISOString(), end_at: end.toISOString() }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["appointments"] }),
    onError: (err) => { alert(extractError(err)); qc.invalidateQueries({ queryKey: ["appointments"] }); },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  );

  function handleDragEnd(event: DragEndEvent) {
    const res = resolveDragEnd(String(event.active.id), event.over ? String(event.over.id) : null, appointments);
    if (!res) return;
    if (res.kind === "reschedule") {
      rescheduleMutation.mutate({ id: res.appointmentId, start: res.start, end: res.end });
    } else {
      setEditing(null);
      setDraft({ patientId: res.patientId, start: res.start, end: new Date(res.start.getTime() + SLOT_MINUTES * 60_000) });
      setFormError(null);
      setDialogOpen(true);
    }
  }

  function openNew() {
    const start = new Date(anchor); start.setHours(9, 0, 0, 0);
    setEditing(null);
    setDraft({ start, end: new Date(start.getTime() + SLOT_MINUTES * 60_000) });
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(appt: Appointment) {
    setDraft(null);
    setEditing(appt);
    setFormError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setDraft(null);
    setFormError(null);
  }

  function onResizeEnd(appt: Appointment, newEnd: Date) {
    rescheduleMutation.mutate({ id: appt.id, start: new Date(appt.start_at), end: newEnd });
  }

  const step = (dir: 1 | -1) => {
    if (view === "month") setAnchor((a) => addMonths(a, dir));
    else if (view === "day") setAnchor((a) => addDays(a, dir));
    else setAnchor((a) => addDays(a, dir * 7));
  };

  const label =
    view === "month" ? format(anchor, "MMMM yyyy")
    : view === "day" ? format(anchor, "EEEE, MMM d, yyyy")
    : `${format(rangeStart, "MMM d")} – ${format(addDays(rangeStart, 6), "MMM d, yyyy")}`;

  const days = view === "day" ? [anchor] : buildWeekDays(anchor);

  return (
    <div className="flex flex-col h-full">
      <CalendarHeader
        view={view} onView={setView} label={label}
        onPrev={() => step(-1)} onNext={() => step(1)} onToday={() => setAnchor(new Date())}
        onNew={openNew} typeFilter={typeFilter} onTypeFilter={setTypeFilter}
      />
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="flex flex-1 min-h-0">
          <PatientPanel patients={patients} search={search} onSearch={setSearch} />
          {view === "month" ? (
            <CalendarMonthView anchor={anchor} appointments={appointments} onOpen={openEdit} />
          ) : (
            <CalendarWeekView days={days} appointments={appointments} onOpen={openEdit} onResizeEnd={onResizeEnd} />
          )}
        </div>
      </DndContext>

      <AppointmentDialog
        open={dialogOpen}
        onClose={closeDialog}
        patients={patients}
        draft={draft}
        editing={editing}
        isPending={createMutation.isPending || updateMutation.isPending}
        error={formError}
        onSubmit={(payload) => {
          setFormError(null);
          if (editing) updateMutation.mutate({ id: editing.id, payload });
          else createMutation.mutate(payload);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run: `cd frontend && npx vitest run "src/app/(dashboard)/calendar/page.test.tsx"`
Expected: PASS (header + "New appointment" + "Patients" found).

- [ ] **Step 5: Full frontend gate (typecheck + all tests + lint)**

Run: `cd frontend && npx tsc --noEmit && npx vitest run && npm run lint`
Expected: typecheck clean, all vitest suites pass, lint clean.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/app/(dashboard)/calendar/"
git commit -m "feat(calendar): add calendar page with drag-drop scheduling"
```

---

## Task 9: End-to-end verification in the running app

**Files:** none (manual verification).

- [ ] **Step 1: Start the stack**

Run (from repo root): `docker-compose up -d db` (Postgres), then backend `cd backend && alembic upgrade head && uvicorn app.main:app --reload --port 8747`, then frontend `cd frontend && npm run dev`.
Expected: backend healthy on :8747, frontend on :3000.

- [ ] **Step 2: Drive the feature (use the `verify` or `run` skill / browser automation)**

Log in, click **Appointments** in the sidebar, then verify each behavior:
1. The calendar renders in Week view with the 6am–8pm grid, Mon–Fri shaded, red now-line on today.
2. Drag a patient card from the left panel onto a slot → the New-appointment dialog opens prefilled with that patient + dropped time. Book it → the block appears colored by type.
3. Drag the block to another slot → it reschedules (persists after refresh).
4. Drag the block's bottom edge → duration changes.
5. Hover a block → tooltip shows patient · type · status · time.
6. Try to book an overlapping slot → inline 409 error ("overlaps an existing appointment").
7. Open a block → change status to Confirmed/Cancelled → cancelled renders muted/struck.
8. Switch to Day and Month views → data persists; month chips show; dropping on a month cell books at 9am.

Expected: all behaviors work; the page visually matches the app (saffron primary, forest sidebar, shadcn cards) with no layout breakage.

- [ ] **Step 3: Final commit / branch wrap-up**

If any fixes were needed in Step 2, commit them. Then the branch `feature/calendar-scheduling-dragdrop` is ready for PR (use `superpowers:finishing-a-development-branch`).

---

## Self-Review

**Spec coverage:**
- Domain mapping (Appointment/Patient/type-color/patient-panel) → Tasks 1, 5, 6, 8 ✓
- Backend model + enums + relationships + migration → Tasks 1, 2 ✓
- Routes (list/create/get/patch/delete/reminder) + overlap 409 + tenant scope + registration → Task 4 ✓
- Email reminder helper + confirmation-on-create → Tasks 3, 4 ✓
- Link plan/therapy → model (Task 1) + route fields (Task 4) + dialog (Task 6) ✓
- Frontend: types/utils/api/nav → Task 5; components → Tasks 6, 7; page + DndContext + queries/mutations → Task 8 ✓
- Drag-to-book, drag-to-reschedule, resize, hover → Tasks 6, 7, 8 (`resolveDragEnd`, `AppointmentBlock`, `CalendarWeekView`) ✓
- Views Day/Week/Month → Tasks 7, 8 ✓
- Double-booking prevention, status workflow, reminders, plan/therapy links (all four enhancements) → covered ✓
- Tests: backend overlap/tenant/CRUD (Task 4), utils pure-logic (Task 5), page smoke (Task 8) ✓
- UI-sameness (additive-only edits) → enforced by Global Constraints; existing-file edits limited to NAV, client.ts, models/__init__, main.py, email.py, Patient/Practitioner relationships ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `Appointment` shape identical in `_appt_dict` (Task 4) and `types.ts` (Task 5). `resolveDragEnd`/`DragResolution`/`NewAppointmentDraft`/`AppointmentSubmit` names consistent across Tasks 5–8. Enum wire values lowercase everywhere (model `values_callable`, `_appt_dict` `.value`, TS unions, migration labels). `slotId`/`draggableId` used identically by droppables (Task 7), draggables (Task 6), and `resolveDragEnd` (Tasks 5, 8).
