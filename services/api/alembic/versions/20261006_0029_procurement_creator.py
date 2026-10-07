"""Registra o criador de novas requisições de compra."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_0029"
down_revision = "20261006_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_procurement_requests", sa.Column("created_by_user_id", sa.UUID(), nullable=True), schema="construction")


def downgrade():
    op.drop_column("construction_procurement_requests", "created_by_user_id", schema="construction")
