"""Add therapies, service packages, and plan assignment tables.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "therapies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("practitioner_id", sa.Integer, sa.ForeignKey("practitioners.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_sanskrit", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(80)),
        sa.Column("default_duration_minutes", sa.Integer),
        sa.Column("default_price_cents", sa.Integer),
        sa.Column("benefits", sa.JSON),
        sa.Column("contraindications", sa.JSON),
        sa.Column("dosha_effect", sa.String(200)),
        sa.Column("image_url", sa.String(500)),
        sa.Column("is_community", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "service_packages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("practitioner_id", sa.Integer, sa.ForeignKey("practitioners.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(80)),
        sa.Column("total_duration_minutes", sa.Integer),
        sa.Column("total_price_cents", sa.Integer),
        sa.Column("includes_extras", sa.JSON),
        sa.Column("panchakarma_days", sa.Integer),
        sa.Column("image_url", sa.String(500)),
        sa.Column("is_community", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "package_therapies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("package_id", sa.Integer, sa.ForeignKey("service_packages.id"), nullable=False),
        sa.Column("therapy_id", sa.Integer, sa.ForeignKey("therapies.id"), nullable=False),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("override_duration_minutes", sa.Integer),
        sa.Column("notes", sa.String(500)),
    )

    op.create_table(
        "plan_therapies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("consultation_plans.id"), nullable=False, index=True),
        sa.Column("therapy_id", sa.Integer, sa.ForeignKey("therapies.id"), nullable=False),
        sa.Column("frequency", sa.String(100)),
        sa.Column("duration_minutes", sa.Integer),
        sa.Column("price_cents", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("scheduled_date", sa.Date),
    )

    op.create_table(
        "plan_service_packages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("consultation_plans.id"), nullable=False, index=True),
        sa.Column("package_id", sa.Integer, sa.ForeignKey("service_packages.id"), nullable=False),
        sa.Column("price_cents", sa.Integer),
        sa.Column("start_date", sa.Date),
        sa.Column("notes", sa.Text),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_table("plan_service_packages")
    op.drop_table("plan_therapies")
    op.drop_table("package_therapies")
    op.drop_table("service_packages")
    op.drop_table("therapies")
