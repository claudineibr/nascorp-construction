from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261007_0031"
down_revision = "20261006_0030"
branch_labels = None
depends_on = None


def upgrade():
    table = "construction_procurement_requests"
    op.add_column(table, sa.Column("delivery_status", sa.String(20), nullable=False, server_default="not_sent"), schema="construction")
    op.add_column(table, sa.Column("external_snapshot_at", sa.DateTime(timezone=True)), schema="construction")
    for name in ["external_items", "external_orders"]:
        op.add_column(table, sa.Column(name, postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), schema="construction")
    op.execute("UPDATE construction.construction_procurement_requests SET delivery_status = CASE WHEN external_procurement_id IS NOT NULL THEN 'sent' WHEN status='pending_approval' THEN 'sending' ELSE 'not_sent' END")


def downgrade():
    for name in ["external_orders", "external_items", "external_snapshot_at", "delivery_status"]:
        op.drop_column("construction_procurement_requests", name, schema="construction")
