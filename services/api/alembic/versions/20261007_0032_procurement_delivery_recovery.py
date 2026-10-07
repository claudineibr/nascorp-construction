from alembic import op

revision = "20261007_0032"
down_revision = "20261007_0031"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE construction.construction_procurement_requests r
        SET delivery_status='failed'
        WHERE r.status='pending_approval' AND r.external_procurement_id IS NULL
            AND r.delivery_status='sending'
            AND NOT EXISTS (
                SELECT 1 FROM construction.outbox_events e
                WHERE e.company_id=r.company_id AND e.aggregate_id=r.id
                    AND e.event_type='construction.procurement.requested.v2'
            )
    """)


def downgrade():
    pass
