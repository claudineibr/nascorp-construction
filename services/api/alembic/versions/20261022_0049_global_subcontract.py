from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261022_0049"
down_revision = "20261021_0048"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "construction_subcontracts",
        sa.Column("pricing_mode", sa.String(20), nullable=False, server_default=sa.text("'ITEMIZED'")),
        schema="construction",
    )
    op.add_column("construction_subcontracts", sa.Column("global_amount", sa.Numeric(14, 2), nullable=True), schema="construction")
    op.create_check_constraint(
        "ck_subcontract_pricing_mode", "construction_subcontracts", "pricing_mode IN ('ITEMIZED','GLOBAL')", schema="construction"
    )
    op.create_check_constraint(
        "ck_subcontract_global_amount",
        "construction_subcontracts",
        "pricing_mode <> 'GLOBAL' OR global_amount > 0",
        schema="construction",
    )
    op.add_column(
        "construction_measurements",
        sa.Column(
            "global_contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("construction.construction_subcontracts.id"),
            nullable=True,
        ),
        schema="construction",
    )
    op.create_index(
        "ix_construction_construction_measurements_global_contract_id",
        "construction_measurements",
        ["global_contract_id"],
        schema="construction",
    )
    op.create_table(
        "construction_subcontract_payables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("construction.construction_subcontracts.id"), nullable=False),
        sa.Column("payable_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("document_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("linked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0 AND status IN ('ACTIVE','REMOVED')", name="ck_subcontract_payable"),
        schema="construction",
    )
    op.create_index(
        "ix_construction_construction_subcontract_payables_company_id",
        "construction_subcontract_payables",
        ["company_id"],
        schema="construction",
    )
    op.create_index(
        "ix_construction_construction_subcontract_payables_contract_id",
        "construction_subcontract_payables",
        ["contract_id"],
        schema="construction",
    )
    op.create_index(
        "uq_subcontract_payable_document",
        "construction_subcontract_payables",
        ["company_id", "payable_document_id"],
        unique=True,
        schema="construction",
        postgresql_where=sa.text("status='ACTIVE'"),
    )


def downgrade():
    op.drop_index("uq_subcontract_payable_document", table_name="construction_subcontract_payables", schema="construction")
    op.drop_index(
        "ix_construction_construction_subcontract_payables_contract_id",
        table_name="construction_subcontract_payables",
        schema="construction",
    )
    op.drop_index(
        "ix_construction_construction_subcontract_payables_company_id",
        table_name="construction_subcontract_payables",
        schema="construction",
    )
    op.drop_table("construction_subcontract_payables", schema="construction")
    op.drop_index(
        "ix_construction_construction_measurements_global_contract_id",
        table_name="construction_measurements",
        schema="construction",
    )
    op.drop_column("construction_measurements", "global_contract_id", schema="construction")
    op.drop_constraint("ck_subcontract_global_amount", "construction_subcontracts", schema="construction", type_="check")
    op.drop_constraint("ck_subcontract_pricing_mode", "construction_subcontracts", schema="construction", type_="check")
    op.drop_column("construction_subcontracts", "global_amount", schema="construction")
    op.drop_column("construction_subcontracts", "pricing_mode", schema="construction")
