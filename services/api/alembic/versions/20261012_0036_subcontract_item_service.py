"""link subcontract items to the service catalog instead of an ERP product

Revision ID: 20261012_0036
Revises: 20261012_0035
Create Date: 2026-10-12 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20261012_0036"
down_revision = "20261012_0035"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLE = "construction_subcontract_items"
COLUMN = "service_template_id"
FOREIGN_KEY = "fk_construction_subcontract_items_service_template_id"
INDEX = "ix_construction_subcontract_items_service_template_id"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column(COLUMN, UUID(as_uuid=True), nullable=True), schema=SCHEMA_NAME)
    op.create_foreign_key(
        FOREIGN_KEY,
        TABLE,
        "construction_service_templates",
        [COLUMN],
        ["id"],
        source_schema=SCHEMA_NAME,
        referent_schema=SCHEMA_NAME,
    )
    op.create_index(INDEX, TABLE, [COLUMN], schema=SCHEMA_NAME)


def downgrade() -> None:
    op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA_NAME)
    op.drop_constraint(FOREIGN_KEY, TABLE, schema=SCHEMA_NAME, type_="foreignkey")
    op.drop_column(TABLE, COLUMN, schema=SCHEMA_NAME)
