"""add project and block fields

Revision ID: 20260505_0006
Revises: 20260430_0005
Create Date: 2026-05-05 09:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260505_0006"
down_revision = "20260430_0005"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
PROJECT_TYPE_DEFAULT = "residential_vertical"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Construction API migrations require PostgreSQL.")

    op.add_column(
        "construction_projects",
        sa.Column(
            "project_type",
            sa.String(length=40),
            nullable=False,
            server_default=PROJECT_TYPE_DEFAULT,
        ),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_projects",
        sa.Column("customer_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_projects",
        sa.Column("cnpj_spe", sa.String(length=18), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_projects",
        sa.Column("address_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "construction_blocks",
        sa.Column("floors_count", sa.Integer(), nullable=True),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_column("construction_blocks", "floors_count", schema=SCHEMA_NAME)
    op.drop_column("construction_projects", "address_json", schema=SCHEMA_NAME)
    op.drop_column("construction_projects", "cnpj_spe", schema=SCHEMA_NAME)
    op.drop_column("construction_projects", "customer_person_id", schema=SCHEMA_NAME)
    op.drop_column("construction_projects", "project_type", schema=SCHEMA_NAME)
