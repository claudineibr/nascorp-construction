"""identify recoverable outbox deliveries

Revision ID: 20261015_0040
Revises: 20261015_0039
"""

from alembic import op
import sqlalchemy as sa


revision = '20261015_0040'
down_revision = '20261015_0039'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('outbox_events', sa.Column('delivery_mode', sa.String(30), nullable=False,
        server_default=sa.text("'legacy'")), schema='construction')


def downgrade():
    op.drop_column('outbox_events', 'delivery_mode', schema='construction')
