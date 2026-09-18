"""group FVS items into sections and flag required comment/photo

The Caixa FVS arrives as one file per service, with no grouping. Manual entry
needs sections because a real sheet separates blocks ("Materiais", "Execucao",
"Aceitacao") and an item only makes sense inside its block.

Item numbering becomes PER SECTION. The backfill creates one GERAL section per
template -- including templates with no items, otherwise the edit screen would
open empty -- and since every item lands in the same section, the old uniqueness
(template, sequence) already guarantees the new (section, sequence): there is
nothing to renumber on the way up.

The downgrade renumbers back per template BEFORE recreating the old constraint.
Without that, any template with two sections has a repeated sequence and the
constraint refuses. Section names and the flags are lost -- the old schema has
nowhere to keep them.

The three columns on construction_measurement_item_inspections are a snapshot,
in the same spirit as description/verification_method, which are already copied
rather than read from the catalog. Deliberately no backfill: NULL/false is what
those inspections actually knew when they were created.

Revision ID: 20260917_0023
Revises: 20260916_0022
Create Date: 2026-09-17 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260917_0023"
down_revision = "20260916_0022"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TEMPLATE_TABLE = "construction_service_templates"
SECTION_TABLE = "construction_service_template_sections"
TEMPLATE_ITEM_TABLE = "construction_service_template_items"
INSPECTION_TABLE = "construction_measurement_item_inspections"

DEFAULT_SECTION_NAME = "GERAL"


def upgrade() -> None:
    op.create_table(
        SECTION_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("service_template_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["service_template_id"],
            [f"{SCHEMA_NAME}.{TEMPLATE_TABLE}.id"],
            name="fk_construction_service_template_sections_template_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "service_template_id",
            "sequence_number",
            name="uq_construction_service_template_sections_sequence",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_service_template_sections_template_id",
        SECTION_TABLE,
        ["service_template_id"],
        schema=SCHEMA_NAME,
    )

    op.add_column(
        TEMPLATE_ITEM_TABLE,
        sa.Column("section_id", sa.UUID(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TEMPLATE_ITEM_TABLE,
        sa.Column("requires_comment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        TEMPLATE_ITEM_TABLE,
        sa.Column("requires_photo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA_NAME,
    )

    op.execute(
        f"""
        INSERT INTO {SCHEMA_NAME}.{SECTION_TABLE}
            (id, company_id, service_template_id, sequence_number, name, created_at, updated_at)
        SELECT gen_random_uuid(), t.company_id, t.id, 1, '{DEFAULT_SECTION_NAME}', now(), now()
        FROM {SCHEMA_NAME}.{TEMPLATE_TABLE} t
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_NAME}.{TEMPLATE_ITEM_TABLE} i
        SET section_id = s.id
        FROM {SCHEMA_NAME}.{SECTION_TABLE} s
        WHERE s.service_template_id = i.service_template_id
        """
    )

    op.alter_column(
        TEMPLATE_ITEM_TABLE,
        "section_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema=SCHEMA_NAME,
    )
    op.create_foreign_key(
        "fk_construction_service_template_items_section_id",
        TEMPLATE_ITEM_TABLE,
        SECTION_TABLE,
        ["section_id"],
        ["id"],
        source_schema=SCHEMA_NAME,
        referent_schema=SCHEMA_NAME,
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_construction_service_template_items_section_id",
        TEMPLATE_ITEM_TABLE,
        ["section_id"],
        schema=SCHEMA_NAME,
    )

    op.drop_constraint(
        "uq_construction_service_template_items_sequence",
        TEMPLATE_ITEM_TABLE,
        schema=SCHEMA_NAME,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_construction_service_template_items_section_sequence",
        TEMPLATE_ITEM_TABLE,
        ["section_id", "sequence_number"],
        schema=SCHEMA_NAME,
    )

    op.add_column(
        INSPECTION_TABLE,
        sa.Column("section_name", sa.String(255), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("requires_comment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        INSPECTION_TABLE,
        sa.Column("requires_photo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column(INSPECTION_TABLE, "requires_photo", schema=SCHEMA_NAME)
    op.drop_column(INSPECTION_TABLE, "requires_comment", schema=SCHEMA_NAME)
    op.drop_column(INSPECTION_TABLE, "section_name", schema=SCHEMA_NAME)

    op.drop_constraint(
        "uq_construction_service_template_items_section_sequence",
        TEMPLATE_ITEM_TABLE,
        schema=SCHEMA_NAME,
        type_="unique",
    )

    op.execute(
        f"""
        UPDATE {SCHEMA_NAME}.{TEMPLATE_ITEM_TABLE} i
        SET sequence_number = r.rn
        FROM (
            SELECT i2.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY i2.service_template_id
                       ORDER BY s.sequence_number, i2.sequence_number
                   ) AS rn
            FROM {SCHEMA_NAME}.{TEMPLATE_ITEM_TABLE} i2
            JOIN {SCHEMA_NAME}.{SECTION_TABLE} s ON s.id = i2.section_id
        ) r
        WHERE r.id = i.id
        """
    )

    op.create_unique_constraint(
        "uq_construction_service_template_items_sequence",
        TEMPLATE_ITEM_TABLE,
        ["service_template_id", "sequence_number"],
        schema=SCHEMA_NAME,
    )

    op.drop_index(
        "ix_construction_service_template_items_section_id",
        table_name=TEMPLATE_ITEM_TABLE,
        schema=SCHEMA_NAME,
    )
    op.drop_constraint(
        "fk_construction_service_template_items_section_id",
        TEMPLATE_ITEM_TABLE,
        schema=SCHEMA_NAME,
        type_="foreignkey",
    )
    op.drop_column(TEMPLATE_ITEM_TABLE, "requires_photo", schema=SCHEMA_NAME)
    op.drop_column(TEMPLATE_ITEM_TABLE, "requires_comment", schema=SCHEMA_NAME)
    op.drop_column(TEMPLATE_ITEM_TABLE, "section_id", schema=SCHEMA_NAME)

    op.drop_index(
        "ix_construction_service_template_sections_template_id",
        table_name=SECTION_TABLE,
        schema=SCHEMA_NAME,
    )
    op.drop_table(SECTION_TABLE, schema=SCHEMA_NAME)
