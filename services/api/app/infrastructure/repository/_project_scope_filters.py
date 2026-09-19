"""O predicado que limita cada tabela de Obras às obras permitidas.

Escrito uma vez porque `ConstructionRepository` tem 58 métodos e 19 tabelas, e
copiar a condição à mão em cada consulta é a forma garantida de esquecer uma.
Esquecer uma não dá erro: a consulta continua devolvendo linhas, só que as
linhas de quem não devia.

**Só 5 das 19 tabelas têm `project_id`.** Bloco, unidade, fase, medição e
solicitação de compra. O resto chega na obra por um ou dois saltos -- parcela de
pagamento pende da unidade, inspeção pende do item, que pende da medição. Em vez
de repetir o caminho em cada consulta, o caminho está declarado uma vez em
`_CAMINHO` e a condição é montada por recursão.

**O registro é fechado de propósito.** Tabela que não aparece em `_CAMINHO` nem
em `_SEM_OBRA` faz `scope_conditions` levantar exceção, e o teste que percorre
os modelos quebra na hora. Uma tabela nova de Obras é justamente o caso em que o
filtro seria esquecido; aqui ela não passa calada.

**`_SEM_OBRA` não é a lista dos esquecidos** -- é a lista dos que não pertencem
a obra nenhuma: catálogo de serviço, tipo de documentação e a auditoria deles são
da EMPRESA. Restringi-los por obra esconderia o catálogo de quem tem acesso a
uma obra só, e não há nada de uma obra específica neles para vazar.
"""

from __future__ import annotations

from sqlalchemy import false as sa_false, select

from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionDocumentationType,
    ConstructionInspectionRound,
    ConstructionMeasurement,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionMeasurementItemOccurrence,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionServiceTemplate,
    ConstructionServiceTemplateAudit,
    ConstructionServiceTemplateItem,
    ConstructionServiceTemplateSection,
    ConstructionUnit,
    ConstructionUnitCommission,
    ConstructionUnitDocumentation,
    ConstructionUnitPaymentSource,
)

# Tabelas que chegam na obra por um salto de chave estrangeira: (pai, coluna).
# A recursão para nas cinco que têm `project_id` -- e em `ConstructionProject`,
# que é a própria obra.
_CAMINHO = {
    ConstructionUnitPaymentSource: (ConstructionUnit, "unit_id"),
    ConstructionUnitDocumentation: (ConstructionUnit, "unit_id"),
    ConstructionUnitCommission: (ConstructionUnit, "unit_id"),
    ConstructionMeasurementItem: (ConstructionMeasurement, "measurement_id"),
    # Inspeção, reinspeção e ocorrência penduram no ITEM, não na medição --
    # `inspection_id` existe em duas delas, mas leva à inspeção, não à obra.
    ConstructionMeasurementItemInspection: (ConstructionMeasurementItem, "measurement_item_id"),
    ConstructionMeasurementItemOccurrence: (ConstructionMeasurementItem, "measurement_item_id"),
    ConstructionInspectionRound: (ConstructionMeasurementItem, "measurement_item_id"),
}

# Tabelas com `project_id` próprio: um passo só.
_COM_OBRA = (
    ConstructionBlock,
    ConstructionUnit,
    ConstructionSchedulePhase,
    ConstructionMeasurement,
    ConstructionProcurementRequest,
)

# Catálogos da empresa: não pertencem a obra nenhuma.
_SEM_OBRA = (
    ConstructionServiceTemplate,
    ConstructionServiceTemplateSection,
    ConstructionServiceTemplateItem,
    ConstructionServiceTemplateAudit,
    ConstructionDocumentationType,
)


def _clause(model, scope):
    if model is ConstructionProject:
        return ConstructionProject.id.in_(scope.project_ids)

    if model in _COM_OBRA:
        return model.project_id.in_(scope.project_ids)

    caminho = _CAMINHO.get(model)
    if caminho is None:
        raise KeyError(
            f"{model.__name__} nao esta declarado em _project_scope_filters. "
            "Declare o caminho ate a obra, ou em _SEM_OBRA se a tabela for da empresa."
        )

    pai, coluna = caminho
    # EXISTS correlacionado, e não JOIN: entra como mais uma cláusula de `where`
    # sem alterar a forma da consulta de quem chama -- várias delas já fazem
    # `selectinload` e um JOIN extra mudaria a contagem.
    return (
        select(1)
        .select_from(pai)
        .where(pai.id == getattr(model, coluna), _clause(pai, scope))
        .exists()
    )


def scope_conditions(model, scope) -> tuple:
    """As condições que limitam `model` às obras permitidas, para dar splat em `where`.

    Devolve tupla vazia quando não há o que filtrar -- assim o chamador escreve
    `where(A, B, *scope_conditions(Model, self.scope))` e o caso irrestrito não
    paga nada.
    """
    if scope is None or scope.unrestricted:
        return ()

    if model in _SEM_OBRA:
        return ()

    if not scope.project_ids:
        # Escopo vazio nega tudo. `IN ()` em SQL não é falso em todo dialeto, e
        # contar com isso é justamente o tipo de detalhe que muda de versão.
        return (sa_false(),)

    return (_clause(model, scope),)
