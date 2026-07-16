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
