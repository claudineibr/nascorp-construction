from alembic import op
import sqlalchemy as sa

revision = "20261020_0046"
down_revision = "20261020_0045"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_measurements", sa.Column("purpose", sa.String(20), nullable=True), schema="construction")
    op.create_check_constraint("ck_measurement_purpose", "construction_measurements", "purpose IS NULL OR purpose IN ('CONTRACT', 'SERVICE', 'CONTROL')", schema="construction")


def downgrade():
    op.drop_constraint("ck_measurement_purpose", "construction_measurements", schema="construction", type_="check")
    op.drop_column("construction_measurements", "purpose", schema="construction")
