"""add procurement detail fields

Revision ID: 20260505_0009
Revises: 20260505_0008
Create Date: 2026-05-05 00:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260505_0009"
down_revision = "20260505_0008"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE_NAME = "construction_procurement_requests"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("code", sa.String(length=50), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("needed_by_date", sa.Date(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("supplier_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        schema=SCHEMA_NAME,
    )

    op.execute(
        f"""
        UPDATE {SCHEMA_NAME}.{TABLE_NAME}
        SET code = 'REQ-' || UPPER(SUBSTRING(REPLACE(id::text, '-', '') FROM 1 FOR 8))
        WHERE code IS NULL
        """
    )

    op.alter_column(
        TABLE_NAME,
        "code",
        existing_type=sa.String(length=50),
        nullable=False,
        schema=SCHEMA_NAME,
    )

    op.create_index(
        "uq_construction_procurement_requests_company_project_code",
        TABLE_NAME,
        ["company_id", "project_id", "code"],
        unique=True,
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_construction_procurement_requests_company_project_code",
        table_name=TABLE_NAME,
        schema=SCHEMA_NAME,
    )
    op.drop_column(TABLE_NAME, "rejection_reason", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "supplier_person_id", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "needed_by_date", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "code", schema=SCHEMA_NAME)
