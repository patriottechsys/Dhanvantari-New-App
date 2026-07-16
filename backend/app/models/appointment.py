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
