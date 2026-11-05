from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261105_0051'
down_revision = '20261105_0050'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('unit_buyer_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('buyer_person_id', postgresql.UUID(as_uuid=True)),
        sa.Column('buyer_name', sa.String(255)),
        sa.Column('included_at', sa.DateTime(timezone=True)), sa.Column('excluded_at', sa.DateTime(timezone=True)),
        sa.Column('included_by_user_id', postgresql.UUID(as_uuid=True)),
        sa.Column('excluded_by_user_id', postgresql.UUID(as_uuid=True)),
        sa.Column('included_by_name', sa.String(255)), sa.Column('excluded_by_name', sa.String(255)),
        sa.Column('source_id', sa.String(120), nullable=False), sa.Column('reason', sa.String(1000)),
        sa.Column('source_payload', postgresql.JSONB()),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by_user_id', postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(['unit_id'], ['construction.construction_units.id'], ondelete='RESTRICT'),
        schema='construction',
    )
    op.create_index('uq_unit_buyer_history_source', 'unit_buyer_history', ['company_id', 'source_id'],
                    unique=True, schema='construction')
    op.create_index('ix_unit_buyer_history_unit', 'unit_buyer_history',
                    ['company_id', 'unit_id', 'included_at'], schema='construction')
    op.create_index(op.f('ix_construction_unit_buyer_history_unit_id'), 'unit_buyer_history', ['unit_id'], schema='construction')
    op.create_index(op.f('ix_construction_unit_buyer_history_buyer_person_id'), 'unit_buyer_history', ['buyer_person_id'], schema='construction')


def downgrade():
    op.drop_table('unit_buyer_history', schema='construction')
