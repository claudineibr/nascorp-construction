from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261105_0050'
down_revision = '20261022_0049'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f('ck_construction_unit_sales_ck_unit_sales_status'), 'construction_unit_sales', schema='construction')
    op.create_check_constraint(op.f('ck_construction_unit_sales_ck_unit_sales_status'), 'construction_unit_sales',
                               "status IN ('ACTIVE', 'TERMINATED', 'TRANSFERRED')", schema='construction')
    op.add_column('construction_unit_sales', sa.Column('transferred_at', sa.DateTime(timezone=True)), schema='construction')
    op.add_column('construction_unit_sales', sa.Column('transferred_to_unit_id', postgresql.UUID(as_uuid=True)), schema='construction')
    op.add_column('construction_unit_sales', sa.Column('transferred_from_sale_id', postgresql.UUID(as_uuid=True)), schema='construction')
    op.create_foreign_key('fk_sale_transfer_target', 'construction_unit_sales', 'construction_units',
                          ['transferred_to_unit_id'], ['id'], source_schema='construction', referent_schema='construction', ondelete='SET NULL')
    op.create_foreign_key('fk_sale_transfer_source', 'construction_unit_sales', 'construction_unit_sales',
                          ['transferred_from_sale_id'], ['id'], source_schema='construction', referent_schema='construction', ondelete='SET NULL')
    op.create_index(op.f('ix_construction_construction_unit_sales_transferred_to_unit_id'), 'construction_unit_sales', ['transferred_to_unit_id'], schema='construction')
    op.create_index(op.f('ix_construction_construction_unit_sales_transferred_from_sale_id'), 'construction_unit_sales', ['transferred_from_sale_id'], schema='construction')


def downgrade():
    op.drop_index(op.f('ix_construction_construction_unit_sales_transferred_from_sale_id'), table_name='construction_unit_sales', schema='construction')
    op.drop_index(op.f('ix_construction_construction_unit_sales_transferred_to_unit_id'), table_name='construction_unit_sales', schema='construction')
    op.drop_constraint('fk_sale_transfer_source', 'construction_unit_sales', schema='construction', type_='foreignkey')
    op.drop_constraint('fk_sale_transfer_target', 'construction_unit_sales', schema='construction', type_='foreignkey')
    op.drop_column('construction_unit_sales', 'transferred_from_sale_id', schema='construction')
    op.drop_column('construction_unit_sales', 'transferred_to_unit_id', schema='construction')
    op.drop_column('construction_unit_sales', 'transferred_at', schema='construction')
    op.drop_constraint(op.f('ck_construction_unit_sales_ck_unit_sales_status'), 'construction_unit_sales', schema='construction')
    op.create_check_constraint(op.f('ck_construction_unit_sales_ck_unit_sales_status'), 'construction_unit_sales',
                               "status IN ('ACTIVE', 'TERMINATED')", schema='construction')
