from alembic import op
import sqlalchemy as sa

revision = "20261018_0042"
down_revision = "20261016_0041"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_projects", sa.Column("development_type", sa.String(20), nullable=True), schema="construction")
    op.create_check_constraint("ck_project_development_type", "construction_projects", "development_type IN ('INCORPORATION', 'CONTRACT_WORK')", schema="construction")
    op.create_table("construction_inventory_backfill", sa.Column("project_id", sa.UUID(), primary_key=True), sa.Column("company_id", sa.UUID(), nullable=False), sa.Column("development_type", sa.String(20), nullable=False), sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()), schema="construction")
    op.execute("""INSERT INTO construction.construction_inventory_backfill (project_id, company_id, development_type)
        SELECT p.id, p.company_id, CASE WHEN EXISTS (
            SELECT 1 FROM construction.construction_units u
            WHERE u.project_id=p.id AND u.company_id=p.company_id AND u.deleted_at IS NULL
        ) THEN 'INCORPORATION' ELSE 'CONTRACT_WORK' END
        FROM construction.construction_projects p
        WHERE p.deleted_at IS NULL AND (p.customer_person_id IS NOT NULL OR EXISTS (
            SELECT 1 FROM construction.construction_units u
            WHERE u.project_id=p.id AND u.company_id=p.company_id AND u.deleted_at IS NULL))""")
    op.execute("""UPDATE construction.construction_projects p SET development_type=b.development_type
        FROM construction.construction_inventory_backfill b WHERE b.project_id=p.id AND b.company_id=p.company_id""")
    op.add_column("construction_units", sa.Column("ideal_fraction", sa.Numeric(12, 10), nullable=True), schema="construction")
    op.add_column("construction_units", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True), schema="construction")
    op.add_column("construction_units", sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True), schema="construction")
    op.create_check_constraint("ck_unit_ideal_fraction", "construction_units", "ideal_fraction > 0 AND ideal_fraction <= 1", schema="construction")


def downgrade():
    op.drop_constraint("ck_unit_ideal_fraction", "construction_units", schema="construction")
    for column in ("terminated_at", "delivered_at", "ideal_fraction"):
        op.drop_column("construction_units", column, schema="construction")
    op.drop_table("construction_inventory_backfill", schema="construction")
    op.drop_constraint("ck_project_development_type", "construction_projects", schema="construction")
    op.drop_column("construction_projects", "development_type", schema="construction")
