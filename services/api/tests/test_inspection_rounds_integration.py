import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionInspectionRound,
    ConstructionMeasurement,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionMeasurementItemOccurrence,
    ConstructionProject,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction import (
    ConstructionMeasurementInspectionVerifyRequest,
    ConstructionMeasurementItemOccurrenceCreate,
)
from tests.integration_database import create_reachable_engine_or_skip


async def seed_line(session, *, company_id):
    """Uma obra, uma medicao, um item e uma linha de FVS."""
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code=f"OBRA-FVS-{str(uuid4())[:8]}",
        name="Rounds integration project",
        status="active",
    )
    measurement = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code=f"MED-{str(uuid4())[:8]}",
        measured_amount=Decimal("1000.00"),
        due_date=date(2026, 12, 31),
        status="draft",
    )
    item = ConstructionMeasurementItem(
        id=uuid4(),
        company_id=company_id,
        measurement_id=measurement.id,
        sequence_number=1,
        description="Aterro",
        amount=Decimal("1000.00"),
        inspection_status="pending",
    )
    inspection = ConstructionMeasurementItemInspection(
        id=uuid4(),
        company_id=company_id,
        measurement_item_id=item.id,
        sequence_number=1,
        description="Compactacao das camadas",
        status="pending",
        rounds_count=0,
    )
    session.add_all([project, measurement, item, inspection])
    await session.flush()
    return project, measurement, item, inspection


async def clean_up(session, *, company_id) -> None:
    """Apaga o que o cenario criou, escopado ao company_id proprio do teste."""
    await session.rollback()
    await session.execute(
        delete(ConstructionMeasurement).where(ConstructionMeasurement.company_id == company_id)
    )
    await session.execute(delete(ConstructionProject).where(ConstructionProject.company_id == company_id))
    await session.commit()


async def test_reading_the_line_back_holds_the_round_that_was_just_written() -> None:
    """Esta e a razao do `populate_existing` no repositorio.

    A sessao roda com ``expire_on_commit=False``, entao a inspecao ja esta no
    identity map com a colecao de rodadas carregada -- e `selectinload` NAO
    sobrescreve colecao ja carregada. Sem `populate_existing`, a releitura logo
    depois de gravar devolveria o historico SEM a rodada recem-criada, e o
    status derivado da resposta contradiria as proprias rodadas.

    O repositorio falso dos testes de unidade re-hidrata a cada leitura e nunca
    reproduz isso: so a sessao de verdade expoe.
    """
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = ConstructionProjectService(repository=ConstructionRepository(session=session))
        try:
            _, _, item, inspection = await seed_line(session, company_id=company_id)
            await session.commit()

            first = await service.verify_measurement_item_inspection(
                company_id=company_id,
                inspection_id=inspection.id,
                request=ConstructionMeasurementInspectionVerifyRequest(
                    status="non_compliant",
                    comment="camada 3 solta",
                ),
                actor_user_id=uuid4(),
            )
            assert first.rounds_count == 1
            assert [round_.sequence_number for round_ in first.rounds] == [1]

            second = await service.verify_measurement_item_inspection(
                company_id=company_id,
                inspection_id=inspection.id,
                request=ConstructionMeasurementInspectionVerifyRequest(status="compliant"),
                actor_user_id=uuid4(),
            )

            assert second.rounds_count == 2
            assert [round_.sequence_number for round_ in second.rounds] == [1, 2]
            assert [round_.status for round_ in second.rounds] == ["non_compliant", "compliant"]
            assert second.status == "compliant"
            assert second.approved_after_reinspection is True
            # Os campos de compatibilidade derivam das rodadas, nao de coluna.
            assert second.first_status == "non_compliant"
            assert second.second_status == "compliant"

            refreshed_item = await service.get_measurement_item(company_id=company_id, item_id=item.id)
            assert refreshed_item.inspection_status == "compliant"
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_two_simultaneous_reinspections_do_not_collide_on_the_round_number() -> None:
    """O advisory lock e primitiva do Postgres: o `max()+1` do fake nao prova nada.

    Sem ele, duas requisicoes concorrentes leem o mesmo numero, o segundo INSERT
    estoura a UNIQUE e o usuario ve um 500 num botao que ele so apertou duas
    vezes ao mesmo tempo.
    """
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as setup_session:
        _, _, _, inspection = await seed_line(setup_session, company_id=company_id)
        await setup_session.commit()
        inspection_id = inspection.id

    async def record(status: str, comment: str) -> None:
        async with session_factory() as session:
            service = ConstructionProjectService(repository=ConstructionRepository(session=session))
            await service.verify_measurement_item_inspection(
                company_id=company_id,
                inspection_id=inspection_id,
                request=ConstructionMeasurementInspectionVerifyRequest(status=status, comment=comment),
                actor_user_id=uuid4(),
            )

    try:
        await asyncio.gather(
            record("non_compliant", "primeira concorrente"),
            record("non_compliant", "segunda concorrente"),
        )

        async with session_factory() as session:
            rounds = (
                (
                    await session.execute(
                        select(ConstructionInspectionRound)
                        .where(ConstructionInspectionRound.inspection_id == inspection_id)
                        .order_by(ConstructionInspectionRound.sequence_number)
                    )
                )
                .scalars()
                .all()
            )
            assert [round_.sequence_number for round_ in rounds] == [1, 2]
    finally:
        async with session_factory() as session:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_a_pending_round_is_refused_by_the_database() -> None:
    """`pending` deixou de ser veredito e virou a AUSENCIA de rodada.

    A guarda e do banco, nao so do schema: antes o cliente podia postar
    status="pending" e gravar uma "verificacao pendente".
    """
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        try:
            _, _, item, inspection = await seed_line(session, company_id=company_id)
            await session.commit()

            session.add(
                ConstructionInspectionRound(
                    id=uuid4(),
                    company_id=company_id,
                    inspection_id=inspection.id,
                    measurement_item_id=item.id,
                    sequence_number=1,
                    status="pending",
                    verified_at=datetime.now(tz=UTC),
                )
            )
            try:
                await session.commit()
                raise AssertionError("o banco aceitou uma rodada pendente")
            except IntegrityError:
                pass
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_deleting_the_item_takes_its_rounds_with_it() -> None:
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = ConstructionProjectService(repository=ConstructionRepository(session=session))
        try:
            _, _, item, inspection = await seed_line(session, company_id=company_id)
            await session.commit()
            await service.verify_measurement_item_inspection(
                company_id=company_id,
                inspection_id=inspection.id,
                request=ConstructionMeasurementInspectionVerifyRequest(status="compliant"),
                actor_user_id=uuid4(),
            )

            await session.execute(delete(ConstructionMeasurementItem).where(ConstructionMeasurementItem.id == item.id))
            await session.commit()

            remaining = (
                await session.execute(
                    select(ConstructionInspectionRound).where(
                        ConstructionInspectionRound.company_id == company_id
                    )
                )
            ).scalars().all()
            assert remaining == []
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_the_occurrence_survives_the_deletion_of_its_inspection() -> None:
    """SET NULL e nao CASCADE, de proposito.

    Apagar a linha da ficha nao pode apagar o registro do problema que ela
    encontrou -- e justamente o que a FVS existe para provar.
    """
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = ConstructionProjectService(repository=ConstructionRepository(session=session))
        try:
            _, _, item, inspection = await seed_line(session, company_id=company_id)
            await session.commit()

            occurrence = await service.create_measurement_item_occurrence(
                company_id=company_id,
                item_id=item.id,
                request=ConstructionMeasurementItemOccurrenceCreate(problem="camada 3 solta"),
                actor_user_id=uuid4(),
            )
            occurrence.inspection_id = inspection.id
            await session.commit()

            await session.execute(
                delete(ConstructionMeasurementItemInspection).where(
                    ConstructionMeasurementItemInspection.id == inspection.id
                )
            )
            await session.commit()

            # populate_existing porque o DELETE foi statement: o banco zerou a
            # coluna, mas a instancia no identity map ainda carrega o id antigo
            # (expire_on_commit=False).
            survivor = (
                await session.execute(
                    select(ConstructionMeasurementItemOccurrence)
                    .where(ConstructionMeasurementItemOccurrence.id == occurrence.id)
                    .execution_options(populate_existing=True)
                )
            ).scalars().first()
            assert survivor is not None
            assert survivor.inspection_id is None
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()
