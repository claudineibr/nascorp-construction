"""link catalog services to the projects that will execute them

Revision ID: 20261011_0034
Revises: 20261008_0033
Create Date: 2026-10-11 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261011_0034"
down_revision = "20261008_0033"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE = "construction_project_service_templates"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("service_template_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("deleted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["project_id"],
            [f"{SCHEMA_NAME}.construction_projects.id"],
            name="fk_construction_project_service_templates_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_template_id"],
            [f"{SCHEMA_NAME}.construction_service_templates.id"],
            name="fk_construction_project_service_templates_template_id",
            ondelete="CASCADE",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_project_service_templates_company_project",
        TABLE,
        ["company_id", "project_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_construction_project_service_templates_template_id",
        TABLE,
        ["service_template_id"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "uq_construction_project_service_templates_live",
        TABLE,
        ["project_id", "service_template_id"],
        unique=True,
        schema=SCHEMA_NAME,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_construction_project_service_templates_live", table_name=TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_project_service_templates_template_id", table_name=TABLE, schema=SCHEMA_NAME)
    op.drop_index("ix_construction_project_service_templates_company_project", table_name=TABLE, schema=SCHEMA_NAME)
    op.drop_table(TABLE, schema=SCHEMA_NAME)
