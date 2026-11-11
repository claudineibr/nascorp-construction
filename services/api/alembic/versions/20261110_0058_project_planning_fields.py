from alembic import op
import sqlalchemy as sa

revision = "20261110_0058"
down_revision = "20261110_0057"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_projects", sa.Column("estimated_cost", sa.Numeric(14, 2)), schema="construction")
    op.add_column("construction_projects", sa.Column("planned_start_date", sa.Date()), schema="construction")


def downgrade():
    op.drop_column("construction_projects", "planned_start_date", schema="construction")
    op.drop_column("construction_projects", "estimated_cost", schema="construction")
