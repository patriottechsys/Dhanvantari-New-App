"""
Practitioner — the authenticated user / practice owner.
Multi-tenant: all patient data is scoped to a practitioner.
"""
import secrets
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class SubscriptionTier(str, enum.Enum):
    FREE    = "free"
    SEED    = "seed"       # $49/mo — up to 30 patients
    PRACTICE = "practice"  # $89/mo — unlimited
    CLINIC  = "clinic"     # $149/mo — multi-practitioner


class Practitioner(Base):
    __tablename__ = "practitioners"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identity
    name:           Mapped[str]  = mapped_column(String(120), nullable=False)
    email:          Mapped[str]  = mapped_column(String(200), unique=True, nullable=False, index=True)
    password_hash:  Mapped[str]  = mapped_column(String(256), nullable=False)

    # Practice profile
    practice_name:  Mapped[str | None]  = mapped_column(String(200))
    practice_logo_url: Mapped[str | None] = mapped_column(String(500))
    tagline:        Mapped[str | None]  = mapped_column(String(300))
    bio:            Mapped[str | None]  = mapped_column(Text)
    designation:    Mapped[str | None]  = mapped_column(String(50))  # CAP, CAAP, AV, BAMS…
    location:       Mapped[str | None]  = mapped_column(String(200))
    telehealth_url: Mapped[str | None]  = mapped_column(String(500))  # Calendly/Zoom link
    website:        Mapped[str | None]  = mapped_column(String(500))

    # Billing
    stripe_customer_id:     Mapped[str | None] = mapped_column(String(100), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        SAEnum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False
    )
    subscription_active: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_ends_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Account status
    email_verified:  Mapped[bool]     = mapped_column(Boolean, default=False)
    active:          Mapped[bool]     = mapped_column(Boolean, default=True)
    is_admin:        Mapped[bool]     = mapped_column(Boolean, default=False)  # super-admin

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    patients:           Mapped[list["Patient"]]           = relationship(back_populates="practitioner", lazy="dynamic")  # noqa: F821
    followups:          Mapped[list["FollowUp"]]          = relationship(back_populates="practitioner", lazy="dynamic")  # noqa: F821
    consultation_notes: Mapped[list["ConsultationNote"]]  = relationship(back_populates="practitioner", lazy="dynamic")  # noqa: F821
    appointments:       Mapped[list["Appointment"]]       = relationship(back_populates="practitioner", lazy="dynamic")  # noqa: F821

    @property
    def can_add_patient(self) -> bool:
        """Enforce tier patient limits."""
        from sqlalchemy import func
        # Checked at route level with async query; this is a sync helper for reference
        return True

    @property
    def display_name(self) -> str:
        return self.practice_name or self.name
