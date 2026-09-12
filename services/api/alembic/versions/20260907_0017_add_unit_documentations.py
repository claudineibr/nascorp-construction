"""persist the documentation charged to the unit buyer

Revision ID: 20260907_0017
Revises: 20260907_0016
Create Date: 2026-09-10 03:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0017"
down_revision = "20260907_0016"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TYPE_TABLE = "construction_documentation_types"
ITEM_TABLE = "construction_unit_documentations"
UNIT_TABLE = "construction_units"

SEED_STATEMENT = f"""
INSERT INTO {SCHEMA_NAME}.{TYPE_TABLE}
       (id, company_id, name, normalized_name, system_code, is_active, created_at, updated_at)
SELECT gen_random_uuid(), c.company_id, d.name, d.normalized_name, d.system_code, true, now(), now()
  FROM (SELECT DISTINCT company_id FROM {SCHEMA_NAME}.construction_projects) c
 CROSS JOIN (VALUES ('Avaliação', 'AVALIAÇÃO', 'APPRAISAL'),
                    ('Prefeitura', 'PREFEITURA', 'CITY_HALL'),
                    ('Cartório', 'CARTÓRIO', 'NOTARY'),
                    ('IPTU', 'IPTU', 'IPTU')) AS d(name, normalized_name, system_code)
    ON CONFLICT DO NOTHING
"""


def upgrade() -> None:
    op.create_table(
        TYPE_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("system_code", sa.String(40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_id",
            "normalized_name",
            name="uq_construction_documentation_types_normalized_name",
        ),
        sa.UniqueConstraint(
            "company_id",
            "system_code",
            name="uq_construction_documentation_types_system_code",
        ),
        schema=SCHEMA_NAME,
    )

    op.create_table(
        ITEM_TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("documentation_type_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            [f"{SCHEMA_NAME}.{UNIT_TABLE}.id"],
            name="fk_construction_unit_documentations_unit_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["documentation_type_id"],
            [f"{SCHEMA_NAME}.{TYPE_TABLE}.id"],
            name="fk_construction_unit_documentations_type_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("unit_id", "documentation_type_id", name="uq_construction_unit_documentations_type"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_unit_documentations_unit_id",
        ITEM_TABLE,
        ["unit_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_unit_documentations_type_id",
        ITEM_TABLE,
        ["documentation_type_id"],
        schema=SCHEMA_NAME,
    )

    op.execute(SEED_STATEMENT)


def downgrade() -> None:
    op.drop_index("ix_construction_unit_documentations_type_id", table_name=ITEM_TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_unit_documentations_unit_id", table_name=ITEM_TABLE, schema=SCHEMA_NAME)
    op.drop_table(ITEM_TABLE, schema=SCHEMA_NAME)
    op.drop_table(TYPE_TABLE, schema=SCHEMA_NAME)
