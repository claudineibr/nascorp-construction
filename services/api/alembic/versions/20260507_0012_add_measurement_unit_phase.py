"""add measurement unit and phase links

Revision ID: 20260507_0012
Revises: 20260507_0011
Create Date: 2026-05-07 00:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0012"
down_revision = "20260507_0011"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
MEASUREMENT_TABLE = "construction_measurements"


def upgrade() -> None:
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("unit_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        MEASUREMENT_TABLE,
        sa.Column("schedule_phase_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurements_unit_id",
        MEASUREMENT_TABLE,
        ["unit_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_measurements_schedule_phase_id",
        MEASUREMENT_TABLE,
        ["schedule_phase_id"],
        schema=SCHEMA_NAME,
    )
    op.create_foreign_key(
        "fk_construction_measurements_unit_id",
        MEASUREMENT_TABLE,
        "construction_units",
        ["unit_id"],
        ["id"],
        source_schema=SCHEMA_NAME,
        referent_schema=SCHEMA_NAME,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_construction_measurements_schedule_phase_id",
        MEASUREMENT_TABLE,
        "construction_schedule_phases",
        ["schedule_phase_id"],
        ["id"],
        source_schema=SCHEMA_NAME,
        referent_schema=SCHEMA_NAME,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_construction_measurements_schedule_phase_id",
        MEASUREMENT_TABLE,
        schema=SCHEMA_NAME,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_construction_measurements_unit_id",
        MEASUREMENT_TABLE,
        schema=SCHEMA_NAME,
        type_="foreignkey",
    )
    op.drop_index("ix_construction_measurements_schedule_phase_id", table_name=MEASUREMENT_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_measurements_unit_id", table_name=MEASUREMENT_TABLE, schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "schedule_phase_id", schema=SCHEMA_NAME)
    op.drop_column(MEASUREMENT_TABLE, "unit_id", schema=SCHEMA_NAME)