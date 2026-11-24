from alembic import op
import sqlalchemy as sa

revision = "20261124_0063"
down_revision = "20261118_0062"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "construction_projects",
        sa.Column("cost_appropriation_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="construction",
    )


def downgrade():
    op.drop_column("construction_projects", "cost_appropriation_paused", schema="construction")
