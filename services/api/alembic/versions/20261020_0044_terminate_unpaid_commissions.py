"""Preserve unpaid commissions deleted on sale termination.

Revision ID: 20261020_0044
Revises: 20261018_0043
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261020_0044"
down_revision = "20261018_0043"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("construction_unit_commissions", sa.Column("deleted_at", sa.DateTime(timezone=True)), schema="construction")
    op.add_column("construction_unit_commissions", sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True)), schema="construction")
    op.execute("""
        CREATE TRIGGER preserve_deletion AFTER UPDATE ON construction.construction_unit_commissions
        FOR EACH ROW EXECUTE FUNCTION construction.record_preserved_deletion()
    """)
    op.execute("""
        UPDATE construction.construction_unit_commissions c
        SET deleted_at = now()
        FROM construction.construction_units u
        WHERE u.id = c.unit_id AND u.company_id = c.company_id
          AND c.payment_date IS NULL AND c.deleted_at IS NULL
          AND (u.status = 'terminated' OR upper(u.external_contract_status) = 'CANCELED')
    """)


def downgrade():
    op.execute("DROP TRIGGER preserve_deletion ON construction.construction_unit_commissions")
    op.drop_column("construction_unit_commissions", "deleted_by_user_id", schema="construction")
    op.drop_column("construction_unit_commissions", "deleted_at", schema="construction")
