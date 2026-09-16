"""repair project receipt template columns

A 0018 entrou pela metade em bancos que ja existiam: as tabelas e indices de
comissao ficaram de pe, mas as duas colunas de recibo em construction_projects
nao. O sintoma e a API subir e quebrar na primeira listagem de obras com
UndefinedColumnError em receipt_template_id -- o modulo inteiro para.

Esta revisao repete as duas colunas da 0018 de forma idempotente, para nao
falhar em ambiente que ja as tem.

Revision ID: 20260916_0021
Revises: 20260907_0020
Create Date: 2026-09-16 18:30:00.000000
"""

from alembic import op


revision = "20260916_0021"
down_revision = "20260907_0020"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
PROJECT_TABLE = "construction_projects"
COLUMNS = ("receipt_template_id", "commission_receipt_template_id")


def upgrade() -> None:
    for column in COLUMNS:
        op.execute(
            f'ALTER TABLE {SCHEMA_NAME}.{PROJECT_TABLE} ADD COLUMN IF NOT EXISTS "{column}" UUID'
        )


def downgrade() -> None:
    # A 0018 ja e dona dessas colunas; aqui o downgrade so desfaz o reparo em
    # quem nunca as teve, e por isso nao derruba nada incondicionalmente.
    pass
