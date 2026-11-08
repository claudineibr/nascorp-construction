from alembic import op
import sqlalchemy as sa

revision = "20261108_0054"
down_revision = "20261108_0053"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_projects", sa.Column("nfse_receivable_due_days", sa.Integer()), schema="construction")
    op.create_check_constraint("ck_project_nfse_receivable_due_days", "construction_projects",
                               "nfse_receivable_due_days BETWEEN 0 AND 365", schema="construction")


def downgrade():
    op.drop_constraint("ck_project_nfse_receivable_due_days", "construction_projects", schema="construction", type_="check")
    op.drop_column("construction_projects", "nfse_receivable_due_days", schema="construction")
