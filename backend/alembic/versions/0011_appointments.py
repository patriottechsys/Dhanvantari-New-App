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
