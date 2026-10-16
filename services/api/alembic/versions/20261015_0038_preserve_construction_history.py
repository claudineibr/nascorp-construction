"""preserve construction history

Revision ID: 20261015_0038
Revises: 20261012_0037
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261015_0038"
down_revision = "20261012_0037"
branch_labels = None
depends_on = None

TABLES = (
    'construction_projects', 'construction_units', 'construction_measurements',
    'construction_measurement_items', 'construction_measurement_item_inspections',
    'construction_measurement_item_occurrences',
)


def upgrade():
    op.create_table('construction_deletion_audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_table', sa.String(100), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True)),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('snapshot', postgresql.JSONB(), nullable=False), schema='construction')
    op.create_index('ix_construction_deletion_audits_company_entity', 'construction_deletion_audits',
        ['company_id', 'entity_table', 'entity_id'], schema='construction')
    op.execute("""
        CREATE FUNCTION construction.record_preserved_deletion() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
                INSERT INTO construction.construction_deletion_audits
                    (company_id, entity_table, entity_id, actor_user_id, deleted_at, snapshot)
                VALUES (OLD.company_id, TG_TABLE_NAME, OLD.id, NEW.deleted_by_user_id, NEW.deleted_at, to_jsonb(OLD));
            END IF;
            RETURN NEW;
        END $$
    """)
    for table in TABLES:
        op.add_column(table, sa.Column('deleted_at', sa.DateTime(timezone=True)), schema='construction')
        op.add_column(table, sa.Column('deleted_by_user_id', postgresql.UUID(as_uuid=True)), schema='construction')
        op.create_index(f'ix_{table}_active_company', table, ['company_id'], schema='construction',
            postgresql_where=sa.text('deleted_at IS NULL'))
        op.execute(f"CREATE TRIGGER preserve_deletion AFTER UPDATE ON construction.{table} "
                   "FOR EACH ROW EXECUTE FUNCTION construction.record_preserved_deletion()")


def downgrade():
    for table in reversed(TABLES):
        op.execute(f'DROP TRIGGER preserve_deletion ON construction.{table}')
        op.drop_index(f'ix_{table}_active_company', table_name=table, schema='construction')
        op.drop_column(table, 'deleted_by_user_id', schema='construction')
        op.drop_column(table, 'deleted_at', schema='construction')
    op.execute('DROP FUNCTION construction.record_preserved_deletion()')
    op.drop_table('construction_deletion_audits', schema='construction')
