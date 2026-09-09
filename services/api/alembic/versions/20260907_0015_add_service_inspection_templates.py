"""add service inspection templates imported from the caixa spreadsheet

Revision ID: 20260907_0015
Revises: 20260907_0014
Create Date: 2026-09-07 02:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0015"
down_revision = "20260907_0014"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TEMPLATE_TABLE = "construction_service_templates"
TEMPLATE_ITEM_TABLE = "construction_service_template_items"
MEASUREMENT_ITEM_TABLE = "construction_measurement_items"


def upgrade() -> None:
    op.create_table(
        TEMPLATE_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("source_file_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "name", name="uq_construction_service_templates_name"),
        schema=SCHEMA_NAME,
    )

    op.create_table(
        TEMPLATE_ITEM_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("service_template_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("verification_method", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["service_template_id"],
            [f"{SCHEMA_NAME}.{TEMPLATE_TABLE}.id"],
            name="fk_construction_service_template_items_template_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "service_template_id",
            "sequence_number",
            name="uq_construction_service_template_items_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_service_template_items_template_id",
        TEMPLATE_ITEM_TABLE,
        ["service_template_id"],
        schema=SCHEMA_NAME,
    )

    op.add_column(
        MEASUREMENT_ITEM_TABLE,
        sa.Column("service_template_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurement_items_service_template_id",
        MEASUREMENT_ITEM_TABLE,
        ["service_template_id"],
        schema=SCHEMA_NAME,
    )
    op.create_foreign_key(
        "fk_construction_measurement_items_service_template_id",
        MEASUREMENT_ITEM_TABLE,
        TEMPLATE_TABLE,
        ["service_template_id"],
        ["id"],
        source_schema=SCHEMA_NAME,
        referent_schema=SCHEMA_NAME,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_construction_measurement_items_service_template_id",
        MEASUREMENT_ITEM_TABLE,
        schema=SCHEMA_NAME,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_construction_measurement_items_service_template_id",
        table_name=MEASUREMENT_ITEM_TABLE,
        schema=SCHEMA_NAME,
    )
    op.drop_column(MEASUREMENT_ITEM_TABLE, "service_template_id", schema=SCHEMA_NAME)
    op.drop_index(
        "ix_construction_service_template_items_template_id",
        table_name=TEMPLATE_ITEM_TABLE,
        schema=SCHEMA_NAME,
    )
    op.drop_table(TEMPLATE_ITEM_TABLE, schema=SCHEMA_NAME)
    op.drop_table(TEMPLATE_TABLE, schema=SCHEMA_NAME)
