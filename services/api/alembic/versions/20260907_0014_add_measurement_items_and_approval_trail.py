"""add measurement items, inspections, occurrences and approval trail

Revision ID: 20260907_0014
Revises: 20260907_0013
Create Date: 2026-09-07 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0014"
down_revision = "20260907_0013"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
MEASUREMENT_TABLE = "construction_measurements"
ITEM_TABLE = "construction_measurement_items"
INSPECTION_TABLE = "construction_measurement_item_inspections"
OCCURRENCE_TABLE = "construction_measurement_item_occurrences"


def upgrade() -> None:
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("rejected_by_user_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA_NAME,
    )

    op.create_table(
        ITEM_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("measurement_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("product_description", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("inspector_person_id", sa.UUID(), nullable=True),
        sa.Column("inspection_status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["measurement_id"],
            [f"{SCHEMA_NAME}.{MEASUREMENT_TABLE}.id"],
            name="fk_construction_measurement_items_measurement_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "measurement_id",
            "sequence_number",
            name="uq_construction_measurement_items_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurement_items_measurement_id",
        ITEM_TABLE,
        ["measurement_id"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        INSPECTION_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("measurement_item_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("verification_method", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("inspector_person_id", sa.UUID(), nullable=True),
        sa.Column("first_status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("first_status_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_status_by_user_id", sa.UUID(), nullable=True),
        sa.Column("second_status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("second_status_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("second_status_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["measurement_item_id"],
            [f"{SCHEMA_NAME}.{ITEM_TABLE}.id"],
            name="fk_construction_measurement_inspections_item_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "measurement_item_id",
            "sequence_number",
            name="uq_construction_measurement_inspections_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurement_inspections_item_id",
        INSPECTION_TABLE,
        ["measurement_item_id"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        OCCURRENCE_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("measurement_item_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'open'")),
        sa.Column("opened_at", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.Date(), nullable=True),
        sa.Column("inspector_person_id", sa.UUID(), nullable=True),
        sa.Column("registered_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["measurement_item_id"],
            [f"{SCHEMA_NAME}.{ITEM_TABLE}.id"],
            name="fk_construction_measurement_occurrences_item_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "measurement_item_id",
            "sequence_number",
            name="uq_construction_measurement_occurrences_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurement_occurrences_item_id",
        OCCURRENCE_TABLE,
        ["measurement_item_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index("ix_construction_measurement_occurrences_item_id", table_name=OCCURRENCE_TABLE, schema=SCHEMA_NAME)
    op.drop_table(OCCURRENCE_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_measurement_inspections_item_id", table_name=INSPECTION_TABLE, schema=SCHEMA_NAME)
    op.drop_table(INSPECTION_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_measurement_items_measurement_id", table_name=ITEM_TABLE, schema=SCHEMA_NAME)
    op.drop_table(ITEM_TABLE, schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "rejected_at", schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "rejected_by_user_id", schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "approved_by_user_id", schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "submitted_at", schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "submitted_by_user_id", schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "created_by_user_id", schema=SCHEMA_NAME)
