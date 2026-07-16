"""
Patient and HealthProfile models.
All fields from the vaidya-care MVP, extended for production.
"""
from datetime import datetime, date, timezone
from sqlalchemy import String, Boolean, DateTime, Date, Float, Text, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class DoshaType(str, enum.Enum):
    VATA  = "Vata"
    PITTA = "Pitta"
    KAPHA = "Kapha"
    VATA_PITTA  = "Vata-Pitta"
    PITTA_KAPHA = "Pitta-Kapha"
    VATA_KAPHA  = "Vata-Kapha"
    TRIDOSHIC   = "Tridoshic"


class StressLevel(str, enum.Enum):
    LOW       = "Low"
    MODERATE  = "Moderate"
    HIGH      = "High"
    VERY_HIGH = "Very High"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    practitioner_id: Mapped[int] = mapped_column(ForeignKey("practitioners.id"), nullable=False, index=True)

    # Demographics
    first_name:  Mapped[str]       = mapped_column(String(80), nullable=False)
    last_name:   Mapped[str]       = mapped_column(String(80), nullable=False)
    dob:         Mapped[date | None] = mapped_column(Date)
    sex:         Mapped[str | None]  = mapped_column(String(10))
    location:    Mapped[str | None]  = mapped_column(String(200))
    occupation:  Mapped[str | None]  = mapped_column(String(200))
    phone:       Mapped[str | None]  = mapped_column(String(30))
    email:       Mapped[str | None]  = mapped_column(String(200))

    # Physical
    weight_lbs:  Mapped[float | None] = mapped_column(Float)
    weight_note: Mapped[str | None]   = mapped_column(String(200))
    height_in:   Mapped[float | None] = mapped_column(Float)

    # Lifestyle
    exercise_notes:  Mapped[str | None] = mapped_column(Text)
    diet_pattern:    Mapped[str | None] = mapped_column(Text)
    alcohol_notes:   Mapped[str | None] = mapped_column(String(200))
    caffeine_notes:  Mapped[str | None] = mapped_column(String(200))
    sleep_notes:     Mapped[str | None] = mapped_column(String(200))
    stress_level:    Mapped[str | None] = mapped_column(String(20))

    # Status
    active:     Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    practitioner:   Mapped["Practitioner"]    = relationship(back_populates="patients")  # noqa: F821
    health_profile: Mapped["HealthProfile | None"] = relationship(back_populates="patient", uselist=False, cascade="all, delete-orphan")
    plans:          Mapped[list["ConsultationPlan"]] = relationship(back_populates="patient", lazy="dynamic", cascade="all, delete-orphan")  # noqa: F821
    checkins:       Mapped[list["DailyCheckIn"]]     = relationship(back_populates="patient", lazy="dynamic", cascade="all, delete-orphan")  # noqa: F821
    checkin_token:  Mapped["CheckInToken | None"]    = relationship(back_populates="patient", uselist=False, cascade="all, delete-orphan")  # noqa: F821
    followups:           Mapped[list["FollowUp"]]           = relationship(back_populates="patient", lazy="dynamic", cascade="all, delete-orphan")  # noqa: F821
    consultation_notes:  Mapped[list["ConsultationNote"]]  = relationship(back_populates="patient", lazy="dynamic", cascade="all, delete-orphan")  # noqa: F821
    appointments:        Mapped[list["Appointment"]]        = relationship(back_populates="patient", lazy="dynamic", cascade="all, delete-orphan")  # noqa: F821

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def active_plan(self):
        return next((p for p in self.plans if p.active), None)


class HealthProfile(Base):
    __tablename__ = "health_profiles"

    id:         Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, unique=True)

    # Labs — Lipid
    cholesterol_total: Mapped[float | None] = mapped_column(Float)
    hdl:               Mapped[float | None] = mapped_column(Float)
    ldl:               Mapped[float | None] = mapped_column(Float)
    triglycerides:     Mapped[float | None] = mapped_column(Float)

    # Labs — Blood
    hemoglobin:    Mapped[float | None] = mapped_column(Float)
    hematocrit:    Mapped[float | None] = mapped_column(Float)
    eosinophils_pct: Mapped[float | None] = mapped_column(Float)

    # Labs — Metabolic
    glucose:     Mapped[float | None] = mapped_column(Float)
    hba1c:       Mapped[float | None] = mapped_column(Float)
    creatinine:  Mapped[float | None] = mapped_column(Float)
    egfr:        Mapped[float | None] = mapped_column(Float)

    # Labs — Hormonal
    testosterone: Mapped[float | None] = mapped_column(Float)
    tsh:          Mapped[float | None] = mapped_column(Float)
    psa:          Mapped[float | None] = mapped_column(Float)

    lab_date:  Mapped[date | None] = mapped_column(Date)
    lab_notes: Mapped[str | None]  = mapped_column(Text)

    # Clinical
    chief_complaints:     Mapped[str | None] = mapped_column(Text)
    medical_history:      Mapped[str | None] = mapped_column(Text)
    current_medications:  Mapped[str | None] = mapped_column(Text)
    allergies:            Mapped[str | None] = mapped_column(String(500))

    # Ayurvedic Assessment
    dosha_primary:    Mapped[str | None] = mapped_column(String(20))
    dosha_secondary:  Mapped[str | None] = mapped_column(String(20))
    dosha_imbalances: Mapped[str | None] = mapped_column(Text)
    agni_assessment:  Mapped[str | None] = mapped_column(Text)
    ama_assessment:   Mapped[str | None] = mapped_column(Text)
    prakriti_notes:   Mapped[str | None] = mapped_column(Text)
    vikriti_notes:    Mapped[str | None] = mapped_column(Text)

    # Nadi / Ashtavidha Pareeksha (pulse + 8-fold examination)
    nadi_notes:   Mapped[str | None] = mapped_column(Text)   # Pulse diagnosis notes
    jihwa_notes:  Mapped[str | None] = mapped_column(Text)   # Tongue examination
    mutra_notes:  Mapped[str | None] = mapped_column(Text)   # Urine examination
    mala_notes:   Mapped[str | None] = mapped_column(Text)   # Stool examination
    shabda_notes: Mapped[str | None] = mapped_column(Text)   # Voice / sound
    sparsha_notes: Mapped[str | None] = mapped_column(Text)  # Touch / skin texture
    drika_notes:  Mapped[str | None] = mapped_column(Text)   # Eyes
    akriti_notes: Mapped[str | None] = mapped_column(Text)   # General appearance

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    patient: Mapped["Patient"] = relationship(back_populates="health_profile")
