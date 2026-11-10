from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261110_0057"
down_revision = "20261109_0056"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_projects", sa.Column("completion_history", JSONB()), schema="construction")


def downgrade():
    op.drop_column("construction_projects", "completion_history", schema="construction")
