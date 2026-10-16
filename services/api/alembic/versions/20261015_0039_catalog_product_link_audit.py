"""audit catalog product links

Revision ID: 20261015_0039
Revises: 20261015_0038
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20261015_0039'
down_revision = '20261015_0038'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('construction_product_link_audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', sa.String(100), nullable=False),
        sa.Column('previous_product_id', postgresql.UUID(as_uuid=True)),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='construction')
    op.create_index('ix_construction_product_link_audits_company', 'construction_product_link_audits',
        ['company_id', 'template_id'], schema='construction')


def downgrade():
    op.drop_table('construction_product_link_audits', schema='construction')
