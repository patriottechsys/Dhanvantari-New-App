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


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("practitioner_id", sa.Integer, sa.ForeignKey("practitioners.id"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("appointment_type", sa.Enum("consultation", "follow_up", "therapy", "panchakarma", name="appointmenttype"), nullable=False, server_default="consultation"),
        sa.Column("status", sa.Enum("scheduled", "confirmed", "completed", "cancelled", "no_show", name="appointmentstatus"), nullable=False, server_default="scheduled"),
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
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.execute("DROP TYPE IF EXISTS appointmenttype")
