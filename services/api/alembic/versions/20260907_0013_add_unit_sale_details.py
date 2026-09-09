"""add unit sale detail fields

Revision ID: 20260907_0013
Revises: 20260507_0012
Create Date: 2026-09-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0013"
down_revision = "20260507_0012"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE_NAME = "construction_units"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("secondary_buyer_person_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("broker_person_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("contract_signature_date", sa.Date(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TABLE_NAME,
        sa.Column("sale_notes", sa.Text(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_units_broker_person_id",
        TABLE_NAME,
        ["broker_person_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index("ix_construction_units_broker_person_id", table_name=TABLE_NAME, schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "sale_notes", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "contract_signature_date", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "discount_amount", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "broker_person_id", schema=SCHEMA_NAME)
    op.drop_column(TABLE_NAME, "secondary_buyer_person_id", schema=SCHEMA_NAME)
