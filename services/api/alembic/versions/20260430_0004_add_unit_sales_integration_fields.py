"""add unit sales integration fields

Revision ID: 20260430_0004
Revises: 20260430_0003
Create Date: 2026-04-30 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260430_0004"
down_revision = "20260430_0003"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE_NAME = "construction_units"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.add_column(
        TABLE_NAME,
        sa.Column("buyer_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("reservation_expires_at", sa.Date(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("external_contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("external_contract_status", sa.String(length=40), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("external_receivable_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("external_receivable_status", sa.String(length=40), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_units_external_contract_id",
        TABLE_NAME,
        ["external_contract_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index("ix_construction_units_external_contract_id", table_name=TABLE_NAME, schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "external_receivable_status", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "external_receivable_id", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "external_contract_status", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "external_contract_id", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "sold_at", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "reservation_expires_at", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "reserved_at", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "buyer_person_id", schema=SCHEMA_NAME)
