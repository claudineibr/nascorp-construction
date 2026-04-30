"""add construction procurement requests

Revision ID: 20260430_0005
Revises: 20260430_0004
Create Date: 2026-04-30 00:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260430_0005"
down_revision = "20260430_0004"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
PROCUREMENT_STATUS_DRAFT = "draft"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.create_table(
        "construction_procurement_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=PROCUREMENT_STATUS_DRAFT),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_procurement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_procurement_status", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], [f"{SCHEMA_NAME}.construction_projects.id"], ondelete="CASCADE"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_procurement_requests_company_id",
        "construction_procurement_requests",
        ["company_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_procurement_requests_project_id",
        "construction_procurement_requests",
        ["project_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_procurement_requests_external_procurement_id",
        "construction_procurement_requests",
        ["external_procurement_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_procurement_requests_external_procurement_id",
        table_name="construction_procurement_requests",
        schema=SCHEMA_NAME,
    )
    op.drop_index(
        "ix_construction_procurement_requests_project_id",
        table_name="construction_procurement_requests",
        schema=SCHEMA_NAME,
    )
    op.drop_index(
        "ix_construction_procurement_requests_company_id",
        table_name="construction_procurement_requests",
        schema=SCHEMA_NAME,
    )
    op.drop_table("construction_procurement_requests", schema=SCHEMA_NAME)
