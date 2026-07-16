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
