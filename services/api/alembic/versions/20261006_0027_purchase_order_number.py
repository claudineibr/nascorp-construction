"""Número do pedido gerado na central de compras."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_0027"
down_revision = "20261006_0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_procurement_requests", sa.Column("external_order_number", sa.String(50)), schema="construction")


def downgrade():
    op.drop_column("construction_procurement_requests", "external_order_number", schema="construction")
