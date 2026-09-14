"""audit every delete on unit commissions

Sinal lancado sumiu sem causa identificada: o log de acesso da API nao registrou
nenhum DELETE /commissions/{id}, a unidade nao foi recriada (o ON DELETE CASCADE
nao disparou), nao houve restore de dump nem migration no boot, e a tabela nao
tinha trigger. Sobrou a hipotese de DELETE por fora da aplicacao, que nenhum log
de aplicacao alcanca.

Este trigger grava uma linha por DELETE, venha de onde vier -- API, psql, script
-- junto de quem o emitiu (usuario do banco, application_name, endereco do
cliente, pid e a propria query). E instrumentacao de diagnostico: quando a causa
for identificada, o downgrade remove tudo sem deixar rastro no schema.

Revision ID: 20260907_0019
Revises: 20260907_0018
Create Date: 2026-09-13 23:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260907_0019"
down_revision = "20260907_0018"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
COMMISSION_TABLE = "construction_unit_commissions"
AUDIT_TABLE = "construction_unit_commission_deletions"
TRIGGER_NAME = "trg_audit_construction_unit_commission_delete"
FUNCTION_NAME = f"{SCHEMA_NAME}.audit_construction_unit_commission_delete"


def upgrade() -> None:
    op.create_table(
        AUDIT_TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("commission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("composes_sale_price", sa.Boolean(), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        # Quem emitiu o DELETE. application_name distingue a API (asyncpg) de um
        # psql ou script avulso, que e a hipotese que sobrou.
        sa.Column("db_user", sa.Text(), nullable=True),
        sa.Column("application_name", sa.Text(), nullable=True),
        sa.Column("client_addr", sa.Text(), nullable=True),
        sa.Column("backend_pid", sa.Integer(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        f"ix_{AUDIT_TABLE}_unit_id",
        AUDIT_TABLE,
        ["unit_id"],
        schema=SCHEMA_NAME,
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            INSERT INTO {SCHEMA_NAME}.{AUDIT_TABLE} (
                commission_id, unit_id, company_id, sequence_number, amount,
                composes_sale_price, payment_date, deleted_at, db_user,
                application_name, client_addr, backend_pid, statement
            )
            VALUES (
                OLD.id, OLD.unit_id, OLD.company_id, OLD.sequence_number, OLD.amount,
                OLD.composes_sale_price, OLD.payment_date, now(), session_user,
                current_setting('application_name', true),
                host(coalesce(inet_client_addr(), '0.0.0.0'::inet)),
                pg_backend_pid(), current_query()
            );
            RETURN OLD;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        AFTER DELETE ON {SCHEMA_NAME}.{COMMISSION_TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION {FUNCTION_NAME}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON {SCHEMA_NAME}.{COMMISSION_TABLE};")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}();")
    op.drop_index(f"ix_{AUDIT_TABLE}_unit_id", table_name=AUDIT_TABLE, schema=SCHEMA_NAME)
    op.drop_table(AUDIT_TABLE, schema=SCHEMA_NAME)
