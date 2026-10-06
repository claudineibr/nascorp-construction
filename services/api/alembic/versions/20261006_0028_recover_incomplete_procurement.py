"""Devolve para correção os envios antigos que só receberam confirmação fictícia."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_0028"
down_revision = "20261006_0027"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        UPDATE construction.construction_procurement_requests r
        SET status = 'rejected', external_procurement_id = NULL, external_procurement_status = NULL,
            rejection_reason = 'Envio anterior sem itens gravados. Complete os produtos, quantidades, unidades e valores e envie novamente para aprovação na central de compras.',
            updated_at = now()
        WHERE r.status = 'sent_to_erp' AND r.external_procurement_status = 'PENDING_REVIEW'
          AND NOT EXISTS (SELECT 1 FROM construction.construction_procurement_items i WHERE i.procurement_request_id = r.id)
    """))


def downgrade():
    # Não restaurar confirmações de integração que nunca criaram um pedido.
    pass
