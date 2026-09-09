"""persist the unit sale payment composition

Revision ID: 20260907_0016
Revises: 20260907_0015
Create Date: 2026-09-07 03:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0016"
down_revision = "20260907_0015"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE_NAME = "construction_unit_payment_sources"
UNIT_TABLE = "construction_units"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("installments", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("generates_installments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            [f"{SCHEMA_NAME}.{UNIT_TABLE}.id"],
            name="fk_construction_unit_payment_sources_unit_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("unit_id", "source_type", name="uq_construction_unit_payment_sources_type"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_unit_payment_sources_unit_id",
        TABLE_NAME,
        ["unit_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index("ix_construction_unit_payment_sources_unit_id", table_name=TABLE_NAME, schema=SCHEMA_NAME)
    op.drop_table(TABLE_NAME, schema=SCHEMA_NAME)
