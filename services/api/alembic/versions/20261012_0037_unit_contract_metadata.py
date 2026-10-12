from alembic import op
import sqlalchemy as sa

revision = "20261012_0037"
down_revision = "20261012_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_projects", sa.Column("contract_template_id", sa.UUID(), nullable=True), schema="construction")
    op.create_index("ix_construction_projects_contract_template_id", "construction_projects", ["contract_template_id"], schema="construction")
    op.add_column("construction_projects", sa.Column("lot", sa.String(120), nullable=True), schema="construction")
    op.add_column("construction_projects", sa.Column("registration", sa.String(120), nullable=True), schema="construction")
    op.add_column("construction_projects", sa.Column("land_area", sa.Numeric(14, 2), nullable=True), schema="construction")


def downgrade():
    for column in ("land_area", "registration", "lot"):
        op.drop_column("construction_projects", column, schema="construction")
    op.drop_index("ix_construction_projects_contract_template_id", table_name="construction_projects", schema="construction")
    op.drop_column("construction_projects", "contract_template_id", schema="construction")
