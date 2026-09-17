"""guarda o status de qualificacao do fornecedor no momento do registro

Fase 04A do plano de migracao do MFCON. A qualificacao vive no core (ERP); o que
fica aqui e o status QUE VALIA quando a requisicao ou a medicao foi criada.

Guardar o status do momento e o que permite auditar depois sem reconstruir o
passado: a qualificacao pode ser renovada, cancelada ou vencer, e nenhuma dessas
coisas pode reescrever o que a obra sabia no dia em que comprou.

O Obras AVISA, nao bloqueia. Medido no legado: 69 fornecedores com 359 pedidos
de compra nunca foram qualificados, e mais 3 reprovados com 15 pedidos. Bloquear
de saida trancaria esses pedidos no dia do corte.

`none` e o default de proposito -- e tambem o que o codigo assume quando o core
ainda nao devolve o campo, entao deploy do ERP primeiro e do Obras depois nao
derruba a tela.

Revision ID: 20260916_0022
Revises: 20260916_0021
Create Date: 2026-09-16 19:00:00.000000
"""

from alembic import op


revision = "20260916_0022"
down_revision = "20260916_0021"
branch_labels = None
depends_on = None

SCHEMA_NAME = "construction"
TABLES = ("construction_procurement_requests", "construction_measurements")
COLUMN = "supplier_qualification_status"


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f'ALTER TABLE {SCHEMA_NAME}.{table} '
            f'ADD COLUMN IF NOT EXISTS "{COLUMN}" VARCHAR(20) NOT NULL DEFAULT \'none\''
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE {SCHEMA_NAME}.{table} DROP COLUMN IF EXISTS "{COLUMN}"')
