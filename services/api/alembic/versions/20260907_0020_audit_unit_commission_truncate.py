"""also audit TRUNCATE on unit commissions

O trigger de DELETE nao cobre TRUNCATE: o Postgres nao dispara trigger de linha
para ele. Como a causa do sumico ainda nao foi identificada, deixar esse caminho
sem rastro manteria de pe justamente a hipotese mais dificil de provar.

Trigger de TRUNCATE e por statement (nao existe FOR EACH ROW), entao ele grava
uma unica linha marcadora com commission_id nulo -- e por isso a coluna deixa de
ser NOT NULL aqui.

Revision ID: 20260907_0020
Revises: 20260907_0019
Create Date: 2026-09-13 23:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_0020"
down_revision = "20260907_0019"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
COMMISSION_TABLE = "construction_unit_commissions"
AUDIT_TABLE = "construction_unit_commission_deletions"
TRIGGER_NAME = "trg_audit_construction_unit_commission_truncate"
FUNCTION_NAME = f"{SCHEMA_NAME}.audit_construction_unit_commission_truncate"


def upgrade() -> None:
    for column in ("commission_id", "unit_id", "company_id"):
        op.alter_column(
            AUDIT_TABLE,
            column,
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
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
                deleted_at, db_user, application_name, client_addr, backend_pid, statement
            )
            VALUES (
                now(), session_user,
                current_setting('application_name', true),
                host(coalesce(inet_client_addr(), '0.0.0.0'::inet)),
                pg_backend_pid(),
                'TRUNCATE -- ' || current_query()
            );
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        AFTER TRUNCATE ON {SCHEMA_NAME}.{COMMISSION_TABLE}
        FOR EACH STATEMENT
        EXECUTE FUNCTION {FUNCTION_NAME}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON {SCHEMA_NAME}.{COMMISSION_TABLE};")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}();")
    for column in ("commission_id", "unit_id", "company_id"):
        op.alter_column(
            AUDIT_TABLE,
            column,
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            schema=SCHEMA_NAME,
        )
