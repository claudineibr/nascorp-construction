"""O predicado que limita cada tabela de Obras às obras permitidas.

Estes testes existem porque as falhas aqui **não dão erro** -- a consulta segue
devolvendo linhas, só que as linhas de quem não devia ver:

1. **Escopo vazio tem de negar.** `frozenset()` é falsy em Python, e quem
   escrever `if scope.project_ids:` transforma "não pode nada" em "pode tudo".
2. **Ausência de escopo não é escopo vazio.** `None` é o handler de evento
   interno, que não tem a quem restringir; `nothing()` é a pessoa sem concessão.
3. **Tabela nova não pode passar calada.** O registro é fechado justamente
   porque uma tabela nova é o caso em que o filtro seria esquecido.
"""

from uuid import uuid4

import pytest

from app.domain.record_scope import ProjectScope
from app.infrastructure.database import models
from app.infrastructure.database.models import (
    ConstructionInspectionRound,
    ConstructionMeasurement,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionProject,
    ConstructionServiceTemplate,
    ConstructionUnit,
    ConstructionUnitPaymentSource,
)
from app.infrastructure.repository import _project_scope_filters as filtros
from app.infrastructure.repository._project_scope_filters import scope_conditions


def _sql(condicoes) -> str:
    return " ".join(str(condicao.compile()).lower() for condicao in condicoes)


def test_escopo_irrestrito_nao_filtra_nada():
    """MASTER não paga o custo de um EXISTS por consulta."""
    assert scope_conditions(ConstructionProject, ProjectScope.unlimited()) == ()
    assert scope_conditions(ConstructionUnit, ProjectScope.unlimited()) == ()


def test_ausencia_de_escopo_nao_e_tratada_como_escopo_vazio():
    """`None` é o evento interno, sem pessoa a quem restringir. `nothing()` é a
    pessoa sem concessão nenhuma. Confundir os dois esconde tudo de todos, ou
    libera tudo para todos."""
    assert scope_conditions(ConstructionProject, None) == ()
    assert scope_conditions(ConstructionProject, ProjectScope.nothing()) != ()


def test_escopo_vazio_nega_em_vez_de_virar_in_vazio():
    condicoes = scope_conditions(ConstructionProject, ProjectScope.nothing())

    assert "false" in _sql(condicoes)


def test_tabela_com_project_id_filtra_pela_propria_coluna():
    condicoes = scope_conditions(ConstructionUnit, ProjectScope.limited_to([uuid4()]))
    sql = _sql(condicoes)

    assert "project_id" in sql
    assert "exists" not in sql, "unidade tem `project_id`: um salto seria desperdicio"


def test_tabela_a_um_salto_chega_na_obra_por_exists():
    condicoes = scope_conditions(ConstructionUnitPaymentSource, ProjectScope.limited_to([uuid4()]))
    sql = _sql(condicoes)

    assert "exists" in sql
    assert "construction_units" in sql
    assert "project_id" in sql


def test_tabela_a_dois_saltos_atravessa_a_medicao():
    """Inspeção pende do item, que pende da medição, que tem a obra. Parar no
    item deixaria o filtro sem efeito nenhum."""
    condicoes = scope_conditions(ConstructionMeasurementItemInspection, ProjectScope.limited_to([uuid4()]))
    sql = _sql(condicoes)

    assert sql.count("exists") == 2
    assert "construction_measurement_items" in sql
    assert "construction_measurements" in sql
    assert "project_id" in sql


def test_reinspecao_chega_na_obra_pelo_item_e_nao_pela_inspecao():
    """`ConstructionInspectionRound` tem `inspection_id` E `measurement_item_id`.
    Seguir por `inspection_id` acrescentaria um salto que não leva a lugar
    nenhum -- inspeção não tem obra."""
    condicoes = scope_conditions(ConstructionInspectionRound, ProjectScope.limited_to([uuid4()]))
    sql = _sql(condicoes)

    assert "construction_measurement_items" in sql
    assert "construction_measurement_item_inspections" not in sql


def test_catalogo_da_empresa_nao_e_restringido_por_obra():
    """Serviço e tipo de documentação são da EMPRESA. Restringi-los esconderia o
    catálogo de quem tem acesso a uma obra só, e não há nada de uma obra
    específica dentro deles para vazar."""
    assert scope_conditions(ConstructionServiceTemplate, ProjectScope.nothing()) == ()


def test_tabela_nao_declarada_estoura_em_vez_de_passar_sem_filtro():
    class ConstructionTabelaNova:
        __name__ = "ConstructionTabelaNova"

    with pytest.raises(KeyError):
        scope_conditions(ConstructionTabelaNova, ProjectScope.limited_to([uuid4()]))


def test_todo_modelo_de_obras_esta_declarado():
    """A guarda que faz a próxima tabela aparecer aqui, e não em produção.

    Percorre os modelos de verdade: quem criar uma tabela nova e não declarar o
    caminho até a obra quebra este teste, não um relatório meses depois.
    """
    declarados = set(filtros._CAMINHO) | set(filtros._COM_OBRA) | set(filtros._SEM_OBRA) | {ConstructionProject}
    do_modulo = {
        getattr(models, nome)
        for nome in models.__all__
        if nome.startswith("Construction")
    }

    assert do_modulo - declarados == set()


def test_medicao_e_item_estao_em_niveis_diferentes():
    """Medição tem `project_id`; item não. Tratar os dois igual é o erro que
    deixaria todo item de toda obra visível."""
    sql_medicao = _sql(scope_conditions(ConstructionMeasurement, ProjectScope.limited_to([uuid4()])))
    sql_item = _sql(scope_conditions(ConstructionMeasurementItem, ProjectScope.limited_to([uuid4()])))

    assert "exists" not in sql_medicao
    assert "exists" in sql_item
