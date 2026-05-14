"""add unit description field

Revision ID: 20260507_0010
Revises: 20260505_0009
Create Date: 2026-05-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0010"
down_revision = "20260505_0009"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE_NAME = "construction_units"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("description", sa.Text(), nullable=True),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column(TABLE_NAME, "description", schema=SCHEMA_NAME)