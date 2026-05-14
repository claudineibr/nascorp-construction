"""add unit cost center snapshot

Revision ID: 20260507_0011
Revises: 20260507_0010
Create Date: 2026-05-07 00:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0011"
down_revision = "20260507_0010"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE_NAME = "construction_units"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("analytic_cost_center_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column(TABLE_NAME, "analytic_cost_center_id", schema=SCHEMA_NAME)