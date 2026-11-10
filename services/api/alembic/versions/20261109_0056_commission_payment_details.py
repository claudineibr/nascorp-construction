from alembic import op
import sqlalchemy as sa

revision = "20261109_0056"
down_revision = "20261108_0055"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_unit_commissions", sa.Column("payment_method", sa.String(30)), schema="construction")
    op.add_column("construction_unit_commissions", sa.Column("payment_recorded_by_user_id", sa.Uuid()), schema="construction")


def downgrade():
    op.drop_column("construction_unit_commissions", "payment_recorded_by_user_id", schema="construction")
    op.drop_column("construction_unit_commissions", "payment_method", schema="construction")
