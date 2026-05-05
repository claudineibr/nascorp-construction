"""add unit typology field

Revision ID: 20260505_0007
Revises: 20260505_0006
Create Date: 2026-05-05 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260505_0007"
down_revision = "20260505_0006"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.add_column(
        "construction_units",
        sa.Column("typology", sa.String(length=80), nullable=True),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column("construction_units", "typology", schema=SCHEMA_NAME)
