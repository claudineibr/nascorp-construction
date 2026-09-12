"""persist the broker commission charged to the unit buyer

Revision ID: 20260907_0018
Revises: 20260907_0017
Create Date: 2026-09-12 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0018"
down_revision = "20260907_0017"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
COMMISSION_TABLE = "construction_unit_commissions"
PROJECT_TABLE = "construction_projects"
UNIT_TABLE = "construction_units"


def upgrade() -> None:
    op.create_table(
        COMMISSION_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("beneficiary_person_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column(
            "composes_sale_price",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("receipt_template_id", sa.UUID(), nullable=True),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            [f"{SCHEMA_NAME}.{UNIT_TABLE}.id"],
            name="fk_construction_unit_commissions_unit_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "unit_id",
            "sequence_number",
            name="uq_construction_unit_commissions_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_unit_commissions_unit_id",
        COMMISSION_TABLE,
        ["unit_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_unit_commissions_beneficiary_person_id",
        COMMISSION_TABLE,
        ["beneficiary_person_id"],
        schema=SCHEMA_NAME,
    )

    # Referencia ao modelo de recibo do ERP, sem FK: o schema construction nao
    # alcanca as tabelas do ERP, como ja acontece com company_id e
    # analytic_cost_center_id.
    op.add_column(
        PROJECT_TABLE,
        sa.Column("receipt_template_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        PROJECT_TABLE,
        sa.Column("commission_receipt_template_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column(PROJECT_TABLE, "commission_receipt_template_id", schema=SCHEMA_NAME)
    op.drop_column(PROJECT_TABLE, "receipt_template_id", schema=SCHEMA_NAME)
    op.drop_index(
        "ix_construction_unit_commissions_beneficiary_person_id",
        table_name=COMMISSION_TABLE,
        schema=SCHEMA_NAME,
    )
    op.drop_index(
        "ix_construction_unit_commissions_unit_id",
        table_name=COMMISSION_TABLE,
        schema=SCHEMA_NAME,
    )
    op.drop_table(COMMISSION_TABLE, schema=SCHEMA_NAME)
