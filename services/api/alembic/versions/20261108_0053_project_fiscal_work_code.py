from alembic import op
import sqlalchemy as sa

revision = "20261108_0053"
down_revision = "20261105_0052"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_projects", sa.Column("fiscal_work_code", sa.String(50)), schema="construction")
    op.create_unique_constraint(
        "uq_construction_projects_fiscal_work_code",
        "construction_projects",
        ["company_id", "fiscal_work_code"],
        schema="construction",
    )


def downgrade():
    op.drop_constraint(
        "uq_construction_projects_fiscal_work_code", "construction_projects", schema="construction", type_="unique",
    )
    op.drop_column("construction_projects", "fiscal_work_code", schema="construction")
