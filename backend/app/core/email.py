"""
Email service using Resend.
All sends are fire-and-forget safe — errors are logged but never crash the caller.
"""
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_resend():
    import resend
    resend.api_key = settings.RESEND_API_KEY
    return resend


def send_welcome_email(name: str, email: str) -> None:
    """Send welcome email after registration."""
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping welcome email to %s", email)
        return

    try:
        resend = _get_resend()
        resend.Emails.send({
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
            "to": [email],
            "subject": f"Welcome to Dhanvantari, {name}!",
            "html": f"""
            <div style="font-family: Georgia, serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
                <h2 style="color: #8B6914; margin-bottom: 8px;">Namaste, {name}</h2>
                <p>Welcome to the <strong>Dhanvantari Ayurveda Care Platform</strong>.</p>
                <p>Your 14-day free trial has started. Here's what you can do:</p>
                <ul style="line-height: 1.8;">
                    <li>Add patients and build their health profiles</li>
                    <li>Create personalized Ayurvedic care plans</li>
                    <li>Share portal links so patients can check in daily</li>
                    <li>Track progress with habit and symptom trends</li>
                </ul>
                <p>
                    <a href="{settings.FRONTEND_URL}/dashboard"
                       style="display: inline-block; background: #8B6914; color: #fff; padding: 12px 24px;
                              border-radius: 8px; text-decoration: none; font-weight: bold;">
                        Open Your Dashboard
                    </a>
                </p>
                <p style="color: #888; font-size: 13px; margin-top: 32px;">
                    Rooted in tradition. Powered by intelligence.<br>
                    — The Dhanvantari Team
                </p>
            </div>
            """,
        })
        logger.info("Welcome email sent to %s", email)
    except Exception as e:
        logger.error("Failed to send welcome email to %s: %s", email, e)


def send_checkin_reminder(patient_name: str, email: str, portal_url: str) -> None:
    """Remind a patient to complete their daily check-in."""
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping reminder to %s", email)
        return

    try:
        resend = _get_resend()
        resend.Emails.send({
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
            "to": [email],
            "subject": f"{patient_name}, your daily check-in is waiting",
            "html": f"""
            <div style="font-family: Georgia, serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
                <h2 style="color: #8B6914; margin-bottom: 8px;">Namaste, {patient_name}</h2>
                <p>A quick reminder to log your daily habits and how you're feeling today.</p>
                <p>It takes less than a minute and helps your practitioner track your progress.</p>
                <p>
                    <a href="{portal_url}"
                       style="display: inline-block; background: #8B6914; color: #fff; padding: 12px 24px;
                              border-radius: 8px; text-decoration: none; font-weight: bold;">
                        Complete Check-in
                    </a>
                </p>
                <p style="color: #888; font-size: 13px; margin-top: 32px;">
                    Keep your streak going!<br>
                    — Dhanvantari Care
                </p>
            </div>
            """,
        })
        logger.info("Check-in reminder sent to %s", email)
    except Exception as e:
        logger.error("Failed to send reminder to %s: %s", email, e)


def send_followup_reminder(
    practitioner_name: str,
    patient_name: str,
    email: str,
    scheduled_date: str,
    reason: str | None,
) -> None:
    """Notify practitioner about an upcoming follow-up."""
    if not settings.RESEND_API_KEY:
        return

    try:
        resend = _get_resend()
        resend.Emails.send({
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
            "to": [email],
            "subject": f"Upcoming follow-up: {patient_name} on {scheduled_date}",
            "html": f"""
            <div style="font-family: Georgia, serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
                <h2 style="color: #8B6914;">Follow-up Reminder</h2>
                <p>Hi {practitioner_name},</p>
                <p>You have a follow-up scheduled with <strong>{patient_name}</strong> on <strong>{scheduled_date}</strong>.</p>
                {f'<p>Reason: {reason}</p>' if reason else ''}
                <p>
                    <a href="{settings.FRONTEND_URL}/dashboard"
                       style="display: inline-block; background: #8B6914; color: #fff; padding: 12px 24px;
                              border-radius: 8px; text-decoration: none; font-weight: bold;">
                        View Dashboard
                    </a>
                </p>
            </div>
            """,
        })
    except Exception as e:
        logger.error("Failed to send follow-up reminder: %s", e)


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
