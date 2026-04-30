"""add construction measurements

Revision ID: 20260430_0003
Revises: 20260429_0002
Create Date: 2026-04-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260430_0003"
down_revision = "20260429_0002"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
MEASUREMENT_STATUS_DRAFT = "draft"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.create_table(
        "construction_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("measured_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("supplier_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=MEASUREMENT_STATUS_DRAFT),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_accounts_payable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_accounts_payable_status", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], [f"{SCHEMA_NAME}.construction_projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "code", name="uq_construction_measurements_project_code"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurements_company_id",
        "construction_measurements",
        ["company_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurements_project_id",
        "construction_measurements",
        ["project_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurements_external_accounts_payable_id",
        "construction_measurements",
        ["external_accounts_payable_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_measurements_external_accounts_payable_id",
        table_name="construction_measurements",
        schema=SCHEMA_NAME,
    )
    op.drop_index("ix_construction_measurements_project_id", table_name="construction_measurements", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_measurements_company_id", table_name="construction_measurements", schema=SCHEMA_NAME)
    op.drop_table("construction_measurements", schema=SCHEMA_NAME)
