"""Add source revisions and optional, construction-aware procurement items."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261006_0030"
down_revision = "20261006_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("construction_procurement_requests", sa.Column("submission_revision", sa.Integer(), nullable=False, server_default="0"), schema="construction")
    op.add_column("construction_procurement_requests", sa.Column("external_order_numbers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), schema="construction")
    op.execute("""
        UPDATE construction.construction_procurement_requests
        SET external_order_numbers = CASE WHEN external_order_number IS NULL THEN '[]'::jsonb
            ELSE jsonb_build_array(external_order_number) END
    """)
    op.add_column("construction_procurement_items", sa.Column("schedule_phase_id", postgresql.UUID(as_uuid=True), nullable=True), schema="construction")
    op.add_column("construction_procurement_items", sa.Column("construction_unit_id", postgresql.UUID(as_uuid=True), nullable=True), schema="construction")
    op.alter_column("construction_procurement_items", "unit_price", existing_type=sa.Numeric(14, 2), type_=sa.Numeric(15, 4), nullable=True, schema="construction")
    op.alter_column("construction_procurement_items", "line_total", existing_type=sa.Numeric(14, 2), nullable=True, schema="construction")


def downgrade() -> None:
    bind = op.get_bind()
    null_prices = bind.scalar(sa.text("SELECT count(*) FROM construction.construction_procurement_items WHERE unit_price IS NULL OR line_total IS NULL"))
    if null_prices:
        raise RuntimeError("Não é possível voltar para v1 enquanto houver preço estimado ausente nos itens.")
    op.alter_column("construction_procurement_items", "line_total", existing_type=sa.Numeric(14, 2), nullable=False, schema="construction")
    op.alter_column("construction_procurement_items", "unit_price", existing_type=sa.Numeric(15, 4), type_=sa.Numeric(14, 2), nullable=False, schema="construction")
    op.drop_column("construction_procurement_items", "construction_unit_id", schema="construction")
    op.drop_column("construction_procurement_items", "schedule_phase_id", schema="construction")
    op.drop_column("construction_procurement_requests", "external_order_numbers", schema="construction")
    op.drop_column("construction_procurement_requests", "submission_revision", schema="construction")
