"""O escopo por obra, contra o Postgres de verdade.

O teste sem banco prova que o SQL *diz* a coisa certa. Este prova que o banco
*faz* a coisa certa -- e é onde aparece o erro que a compilação não pega: um
EXISTS correlacionado com a coluna errada compila liso e não filtra nada.

Dois saltos é o caso perigoso. Inspeção pende do item, que pende da medição, que
tem a obra. Se a correlação escapar em qualquer nível, a subconsulta vira um
EXISTS sempre verdadeiro e **toda inspeção de toda obra volta** -- sem erro, sem
aviso, só a FVS da obra do vizinho na tela.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.record_scope import ProjectScope
from app.infrastructure.database.models import (
    ConstructionMeasurement,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionProject,
    ConstructionUnit,
    ConstructionUnitPaymentSource,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from tests.integration_database import create_reachable_engine_or_skip


async def _semear_obra(session, *, company_id, sufixo):
    """Uma obra completa: unidade com fonte de pagamento, medição com item e FVS."""
    obra = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code=f"ESC-{sufixo}",
        name=f"Obra {sufixo}",
        status="active",
        start_date=date(2024, 1, 1),
    )
    unidade = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=obra.id,
        code=f"UN-{sufixo}",
        unit_type="apartamento",
    )
    fonte = ConstructionUnitPaymentSource(
        id=uuid4(),
        company_id=company_id,
        unit_id=unidade.id,
        source_type="recursos_proprios",
        amount=Decimal("1000.00"),
    )
    medicao = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=obra.id,
        code=f"OS-{sufixo}",
        measured_amount=Decimal("500.00"),
        due_date=date(2024, 6, 1),
    )
    item = ConstructionMeasurementItem(
        id=uuid4(),
        company_id=company_id,
        measurement_id=medicao.id,
        sequence_number=1,
        description=f"Servico {sufixo}",
        amount=Decimal("500.00"),
    )
    inspecao = ConstructionMeasurementItemInspection(
        id=uuid4(),
        company_id=company_id,
        measurement_item_id=item.id,
        sequence_number=1,
        description=f"Verificacao {sufixo}",
    )
    session.add_all([obra, unidade, fonte, medicao, item, inspecao])
    await session.flush()
    return {
        "obra": obra,
        "unidade": unidade,
        "fonte": fonte,
        "medicao": medicao,
        "item": item,
        "inspecao": inspecao,
    }


async def _limpar(session, *, company_id) -> None:
    await session.rollback()
    # As filhas saem por ON DELETE CASCADE a partir da obra.
    await session.execute(delete(ConstructionProject).where(ConstructionProject.company_id == company_id))
    await session.commit()


async def test_escopo_esconde_a_obra_e_tudo_que_pende_dela() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        permitida = await _semear_obra(session, company_id=company_id, sufixo="PERMITIDA")
        proibida = await _semear_obra(session, company_id=company_id, sufixo="PROIBIDA")
        repositorio = ConstructionRepository(
            session=session,
            scope=ProjectScope.limited_to([permitida["obra"].id]),
        )

        try:
            obras, total = await repositorio.list_projects(
                company_id=company_id, search=None, page=1, page_size=50
            )
            assert total == 1, "o total conta a empresa inteira, e tem de contar so o permitido"
            assert [obra.code for obra in obras] == ["ESC-PERMITIDA"]

            assert await repositorio.get_project(company_id=company_id, project_id=permitida["obra"].id)
            assert await repositorio.get_project(company_id=company_id, project_id=proibida["obra"].id) is None

            # Um salto: unidade tem `project_id` proprio.
            assert await repositorio.get_unit(company_id=company_id, unit_id=permitida["unidade"].id)
            assert await repositorio.get_unit(company_id=company_id, unit_id=proibida["unidade"].id) is None

            # Pedir a unidade pelo id da obra proibida tambem nao devolve nada,
            # mesmo com o `project_id` correto na mao.
            assert await repositorio.list_units(company_id=company_id, project_id=proibida["obra"].id) == []

            # Dois saltos: fonte de pagamento chega na obra pela unidade.
            permitidas = await repositorio.list_unit_payment_sources(
                company_id=company_id, unit_id=permitida["unidade"].id
            )
            assert len(permitidas) == 1
            assert (
                await repositorio.list_unit_payment_sources(
                    company_id=company_id, unit_id=proibida["unidade"].id
                )
                == []
            )

            # Tres niveis: inspecao -> item -> medicao -> obra. Se a correlacao
            # escapar em qualquer nivel, este assert e o que quebra.
            assert await repositorio.get_measurement_inspection(
                company_id=company_id, inspection_id=permitida["inspecao"].id
            )
            assert (
                await repositorio.get_measurement_inspection(
                    company_id=company_id, inspection_id=proibida["inspecao"].id
                )
                is None
            )
            assert (
                await repositorio.list_measurement_items(
                    company_id=company_id, measurement_id=proibida["medicao"].id
                )
                == []
            )
        finally:
            await _limpar(session, company_id=company_id)

    await engine.dispose()


async def test_sem_concessao_nenhuma_nao_ve_obra_nenhuma() -> None:
    """`frozenset()` é falsy: quem testar a verdade do conjunto em vez de
    `unrestricted` transforma "não pode nada" em "pode tudo"."""
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        dados = await _semear_obra(session, company_id=company_id, sufixo="SOZINHA")
        repositorio = ConstructionRepository(session=session, scope=ProjectScope.nothing())

        try:
            obras, total = await repositorio.list_projects(
                company_id=company_id, search=None, page=1, page_size=50
            )
            assert obras == []
            assert total == 0
            assert await repositorio.get_unit(company_id=company_id, unit_id=dados["unidade"].id) is None
            assert (
                await repositorio.get_measurement_inspection(
                    company_id=company_id, inspection_id=dados["inspecao"].id
                )
                is None
            )
        finally:
            await _limpar(session, company_id=company_id)

    await engine.dispose()


async def test_repositorio_sem_escopo_continua_enxergando_tudo() -> None:
    """O handler de evento interno usa este caminho: evento do ERP não tem
    pessoa a quem restringir, e a obra recém-criada não foi concedida a
    ninguém ainda."""
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        await _semear_obra(session, company_id=company_id, sufixo="UMA")
        await _semear_obra(session, company_id=company_id, sufixo="OUTRA")
        repositorio = ConstructionRepository(session=session)

        try:
            _, total = await repositorio.list_projects(
                company_id=company_id, search=None, page=1, page_size=50
            )
            assert total == 2
        finally:
            await _limpar(session, company_id=company_id)

    await engine.dispose()


async def test_guarda_de_unicidade_enxerga_o_codigo_fora_do_escopo() -> None:
    """Deliberado: `get_project_by_code` não é leitura, é guarda de unicidade.

    Escondendo a obra de código já usado, o serviço seguiria em frente e o
    INSERT estouraria no índice único -- um 500 no lugar de "código já existe".
    """
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        await _semear_obra(session, company_id=company_id, sufixo="ALHEIA")
        repositorio = ConstructionRepository(session=session, scope=ProjectScope.nothing())

        try:
            achada = await repositorio.get_project_by_code(company_id=company_id, code="ESC-ALHEIA")
            assert achada is not None
        finally:
            await _limpar(session, company_id=company_id)

    await engine.dispose()
