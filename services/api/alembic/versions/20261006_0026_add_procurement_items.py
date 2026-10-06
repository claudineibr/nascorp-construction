"""add items and discounts to construction procurement requests

Revision ID: 20261006_0026
Revises: 20260917_0025
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261006_0026"
down_revision = "20260917_0025"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.add_column(
        "construction_procurement_requests",
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        schema=SCHEMA_NAME,
    )
    op.create_table(
        "construction_procurement_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procurement_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_code", sa.String(40), nullable=False),
        sa.Column("product_description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_of_measure", sa.String(10), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["procurement_request_id"],
            [f"{SCHEMA_NAME}.construction_procurement_requests.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "procurement_request_id", "sequence_number", name="uq_construction_procurement_items_sequence"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_construction_procurement_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_construction_procurement_items_unit_price_nonnegative"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_procurement_items_company_id",
        "construction_procurement_items",
        ["company_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_procurement_items_procurement_request_id",
        "construction_procurement_items",
        ["procurement_request_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_procurement_items_procurement_request_id",
        table_name="construction_procurement_items",
        schema=SCHEMA_NAME,
    )
    op.drop_index(
        "ix_construction_procurement_items_company_id",
        table_name="construction_procurement_items",
        schema=SCHEMA_NAME,
    )
    op.drop_table("construction_procurement_items", schema=SCHEMA_NAME)
    op.drop_column("construction_procurement_requests", "discount_amount", schema=SCHEMA_NAME)
