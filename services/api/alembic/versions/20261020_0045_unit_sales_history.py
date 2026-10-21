"""Unit sales history and termination terms.

Revision ID: 20261020_0045
Revises: 20261020_0044
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261020_0045"
down_revision = "20261020_0044"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "construction_projects",
        sa.Column("termination_defaults", postgresql.JSONB(), nullable=True),
        schema="construction",
    )
    op.add_column(
        "construction_projects",
        sa.Column("has_segregated_assets", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="construction",
    )
    op.create_table(
        "construction_unit_sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("construction.construction_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'NATIVE'")),
        sa.Column("buyer_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("secondary_buyer_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("broker_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sale_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("payment_sources", postgresql.JSONB(), nullable=True),
        sa.Column("documentations", postgresql.JSONB(), nullable=True),
        sa.Column("sale_notes", sa.Text(), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contract_signature_date", sa.Date(), nullable=True),
        sa.Column("external_contract_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_receivable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("termination_terms", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("termination_notes", sa.Text(), nullable=True),
        sa.Column("external_termination_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refund_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("terminated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('ACTIVE', 'TERMINATED')", name="ck_unit_sales_status"),
        sa.CheckConstraint("source IN ('NATIVE', 'LEGACY')", name="ck_unit_sales_source"),
        sa.UniqueConstraint("unit_id", "sequence", name="uq_construction_unit_sales_sequence"),
        schema="construction",
    )
    op.create_index("ix_construction_unit_sales_company_id", "construction_unit_sales", ["company_id"], schema="construction")
    op.create_index("ix_construction_unit_sales_unit_id", "construction_unit_sales", ["unit_id"], schema="construction")
    op.create_index(
        "uq_construction_unit_sales_active",
        "construction_unit_sales",
        ["unit_id"],
        unique=True,
        schema="construction",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.add_column(
        "construction_units",
        sa.Column("current_sale_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="construction",
    )
    op.create_index("ix_construction_units_current_sale_id", "construction_units", ["current_sale_id"], schema="construction")
    op.execute(
        """
        INSERT INTO construction.construction_unit_sales (
            id, company_id, unit_id, sequence, status, source, buyer_person_id, secondary_buyer_person_id,
            broker_person_id, sale_price, discount_amount, payment_sources, documentations, sale_notes, sold_at,
            contract_signature_date, external_contract_id, external_receivable_id, termination_terms
        )
        SELECT gen_random_uuid(), u.company_id, u.id, 1, 'ACTIVE', 'NATIVE', u.buyer_person_id,
               u.secondary_buyer_person_id, u.broker_person_id, u.sale_price, u.discount_amount,
               (SELECT jsonb_agg(jsonb_build_object('id', s.id, 'source_type', s.source_type,
                        'amount', s.amount::text, 'due_date', s.due_date, 'installments', s.installments,
                        'generates_installments', s.generates_installments))
                  FROM construction.construction_unit_payment_sources s WHERE s.unit_id = u.id),
               (SELECT jsonb_agg(jsonb_build_object('documentation_type_id', d.documentation_type_id,
                        'amount', d.amount))
                  FROM construction.construction_unit_documentations d WHERE d.unit_id = u.id),
               u.sale_notes, u.sold_at, u.contract_signature_date, u.external_contract_id,
               u.external_receivable_id, COALESCE(p.termination_defaults, '{}'::jsonb)
          FROM construction.construction_units u
          JOIN construction.construction_projects p ON p.id = u.project_id
         WHERE u.status IN ('sold', 'delivered') AND u.deleted_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE construction.construction_units u
           SET current_sale_id = s.id
          FROM construction.construction_unit_sales s
         WHERE s.unit_id = u.id AND s.status = 'ACTIVE'
        """
    )


def downgrade():
    op.drop_index("ix_construction_units_current_sale_id", table_name="construction_units", schema="construction")
    op.drop_column("construction_units", "current_sale_id", schema="construction")
    op.drop_table("construction_unit_sales", schema="construction")
    op.drop_column("construction_projects", "has_segregated_assets", schema="construction")
    op.drop_column("construction_projects", "termination_defaults", schema="construction")
