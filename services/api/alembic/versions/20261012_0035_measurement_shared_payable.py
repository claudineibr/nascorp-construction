"""mark measurements covered by a shared subcontract payable (one DNF paying many zero-value orders)

Revision ID: 20261012_0035
Revises: 20261011_0034
Create Date: 2026-10-12 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261012_0035"
down_revision = "20261011_0034"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE = "construction_measurements"
COLUMN = "external_accounts_payable_shared"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column(TABLE, COLUMN, schema=SCHEMA_NAME)
