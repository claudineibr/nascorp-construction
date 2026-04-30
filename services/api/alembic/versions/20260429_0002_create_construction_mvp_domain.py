"""create construction mvp domain

Revision ID: 20260429_0002
Revises: 20260428_0001
Create Date: 2026-04-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_0002"
down_revision = "20260428_0001"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
PROJECT_STATUS_DRAFT = "draft"
BLOCK_STATUS_ACTIVE = "active"
UNIT_STATUS_AVAILABLE = "available"
SCHEDULE_STATUS_PLANNED = "planned"
DEFAULT_PROGRESS_PERCENT = "0"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))

    op.create_table(
        "construction_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=PROJECT_STATUS_DRAFT),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("expected_end_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("synthetic_cost_center_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analytic_cost_center_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "code", name="uq_construction_projects_company_code"),
        schema=SCHEMA_NAME,
    )
    op.create_index("ix_construction_projects_company_id", "construction_projects", ["company_id"], schema=SCHEMA_NAME)

    op.create_table(
        "construction_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=BLOCK_STATUS_ACTIVE),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], [f"{SCHEMA_NAME}.construction_projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "code", name="uq_construction_blocks_project_code"),
        schema=SCHEMA_NAME,
    )
    op.create_index("ix_construction_blocks_company_id", "construction_blocks", ["company_id"], schema=SCHEMA_NAME)
    op.create_index("ix_construction_blocks_project_id", "construction_blocks", ["project_id"], schema=SCHEMA_NAME)

    op.create_table(
        "construction_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("unit_type", sa.String(length=80), nullable=False),
        sa.Column("floor", sa.String(length=30), nullable=True),
        sa.Column("private_area", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_area", sa.Numeric(12, 2), nullable=True),
        sa.Column("sale_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=UNIT_STATUS_AVAILABLE),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], [f"{SCHEMA_NAME}.construction_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["block_id"], [f"{SCHEMA_NAME}.construction_blocks.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "code", name="uq_construction_units_project_code"),
        schema=SCHEMA_NAME,
    )
    op.create_index("ix_construction_units_company_id", "construction_units", ["company_id"], schema=SCHEMA_NAME)
    op.create_index("ix_construction_units_project_id", "construction_units", ["project_id"], schema=SCHEMA_NAME)
    op.create_index("ix_construction_units_block_id", "construction_units", ["block_id"], schema=SCHEMA_NAME)

    op.create_table(
        "construction_schedule_phases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=SCHEDULE_STATUS_PLANNED),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("planned_end_date", sa.Date(), nullable=True),
        sa.Column("actual_start_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("progress_percent", sa.Numeric(5, 2), nullable=False, server_default=DEFAULT_PROGRESS_PERCENT),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], [f"{SCHEMA_NAME}.construction_projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "sequence_order", name="uq_construction_schedule_project_sequence"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_schedule_phases_company_id",
        "construction_schedule_phases",
        ["company_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_schedule_phases_project_id",
        "construction_schedule_phases",
        ["project_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index("ix_construction_schedule_phases_project_id", table_name="construction_schedule_phases", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_schedule_phases_company_id", table_name="construction_schedule_phases", schema=SCHEMA_NAME)
    op.drop_table("construction_schedule_phases", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_units_block_id", table_name="construction_units", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_units_project_id", table_name="construction_units", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_units_company_id", table_name="construction_units", schema=SCHEMA_NAME)
    op.drop_table("construction_units", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_blocks_project_id", table_name="construction_blocks", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_blocks_company_id", table_name="construction_blocks", schema=SCHEMA_NAME)
    op.drop_table("construction_blocks", schema=SCHEMA_NAME)
    op.drop_index("ix_construction_projects_company_id", table_name="construction_projects", schema=SCHEMA_NAME)
    op.drop_table("construction_projects", schema=SCHEMA_NAME)
