"""Link commissions to the unit sale and keep the termination snapshot.

Revision ID: 20261020_0047
Revises: 20261020_0046
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261020_0047"
down_revision = "20261020_0046"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "construction_unit_sales",
        sa.Column("external_contract_status", sa.String(40), nullable=True),
        schema="construction",
    )
    op.add_column(
        "construction_unit_sales",
        sa.Column("external_receivable_status", sa.String(40), nullable=True),
        schema="construction",
    )
    op.add_column(
        "construction_unit_sales",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        schema="construction",
    )
    op.add_column(
        "construction_unit_sales",
        sa.Column("termination_snapshot", postgresql.JSONB(), nullable=True),
        schema="construction",
    )
    op.add_column(
        "construction_unit_commissions",
        sa.Column(
            "sale_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("construction.construction_unit_sales.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="construction",
    )
    op.create_index(
        "ix_construction_unit_commissions_sale_id",
        "construction_unit_commissions",
        ["sale_id"],
        schema="construction",
    )
    op.execute(
        """
        UPDATE construction.construction_unit_commissions c
           SET sale_id = (
               SELECT s.id
                 FROM construction.construction_unit_sales s
                WHERE s.unit_id = c.unit_id
                  AND s.company_id = c.company_id
                  AND (s.status = 'ACTIVE'
                       OR (s.status = 'TERMINATED' AND s.source = 'NATIVE' AND s.terminated_at >= c.created_at))
                ORDER BY (s.status = 'ACTIVE'), s.terminated_at ASC NULLS LAST, s.sequence ASC
                LIMIT 1
           )
         WHERE c.sale_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE construction.construction_unit_sales s
           SET payment_sources = (
               SELECT jsonb_agg(jsonb_build_object('id', p.id, 'source_type', p.source_type,
                        'amount', p.amount::text, 'due_date', p.due_date, 'installments', p.installments,
                        'generates_installments', p.generates_installments) ORDER BY p.source_type)
                 FROM construction.construction_unit_payment_sources p
                WHERE p.unit_id = s.unit_id AND p.company_id = s.company_id
           )
          FROM construction.construction_units u
         WHERE u.current_sale_id = s.id
           AND s.status = 'ACTIVE'
           AND s.payment_sources IS NOT NULL
           AND EXISTS (
               SELECT 1 FROM jsonb_array_elements(s.payment_sources) e
                WHERE e->'generates_installments' IS NULL
           )
           AND EXISTS (
               SELECT 1 FROM construction.construction_unit_payment_sources p
                WHERE p.unit_id = s.unit_id AND p.company_id = s.company_id
           )
        """
    )
    op.execute(
        """
        UPDATE construction.construction_unit_sales s
           SET payment_sources = (
               SELECT jsonb_agg(
                        CASE WHEN e->'generates_installments' IS NULL
                             THEN e || jsonb_build_object('generates_installments', e->>'source_type' = 'down_payment')
                             ELSE e END
                        ORDER BY ordinality)
                 FROM jsonb_array_elements(s.payment_sources) WITH ORDINALITY AS rows(e, ordinality)
           )
         WHERE s.payment_sources IS NOT NULL
           AND jsonb_typeof(s.payment_sources) = 'array'
           AND EXISTS (
               SELECT 1 FROM jsonb_array_elements(s.payment_sources) e
                WHERE e->'generates_installments' IS NULL
           )
        """
    )


def downgrade():
    op.drop_index(
        "ix_construction_unit_commissions_sale_id",
        table_name="construction_unit_commissions",
        schema="construction",
    )
    op.drop_column("construction_unit_commissions", "sale_id", schema="construction")
    op.drop_column("construction_unit_sales", "termination_snapshot", schema="construction")
    op.drop_column("construction_unit_sales", "delivered_at", schema="construction")
    op.drop_column("construction_unit_sales", "external_receivable_status", schema="construction")
    op.drop_column("construction_unit_sales", "external_contract_status", schema="construction")
