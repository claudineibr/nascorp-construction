from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261116_0061"
down_revision = "20261112_0060"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "construction_unit_sale_value_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_sequence", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("old_data", postgresql.JSONB(), nullable=False),
        sa.Column("new_data", postgresql.JSONB(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="construction",
    )
    op.create_index("ix_unit_sale_value_audit_history", "construction_unit_sale_value_audits",
                    ["company_id", "unit_id", "changed_at", "id"], schema="construction")


def downgrade():
    op.drop_index("ix_unit_sale_value_audit_history", table_name="construction_unit_sale_value_audits", schema="construction")
    op.drop_table("construction_unit_sale_value_audits", schema="construction")
