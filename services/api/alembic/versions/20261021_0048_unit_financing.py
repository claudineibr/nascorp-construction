from alembic import op
import sqlalchemy as sa

revision = "20261021_0048"
down_revision = "20261020_0047"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("construction_units", "construction_unit_sales"):
        op.add_column(
            name,
            sa.Column("financing_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            schema="construction",
        )
        op.add_column(name, sa.Column("financing_date", sa.Date(), nullable=True), schema="construction")


def downgrade():
    for name in ("construction_unit_sales", "construction_units"):
        op.drop_column(name, "financing_date", schema="construction")
        op.drop_column(name, "financing_completed", schema="construction")
