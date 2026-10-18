from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261018_0043"
down_revision = "20261018_0042"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_units", sa.Column("cost_sale_history", JSONB(), nullable=True), schema="construction")


def downgrade():
    op.drop_column("construction_units", "cost_sale_history", schema="construction")
