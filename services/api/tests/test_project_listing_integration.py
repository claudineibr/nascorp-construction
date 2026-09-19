"""A listagem de obras: paginacao estavel e filtro no servidor.

Existe por causa de um defeito que so aparece com dado real. A carga do MFCON
gravou 77 obras numa unica transacao, e no Postgres `now()` e o mesmo para a
transacao inteira: as 77 ficaram com `created_at` IDENTICO. `ORDER BY created_at
DESC` sozinho deixa o banco livre para devolver qualquer ordem a cada consulta,
e com OFFSET/LIMIT isso significa a mesma obra na pagina 1 e ausente na 2 --
silenciosamente, sem erro nenhum.
"""

from datetime import date
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.infrastructure.database.models import ConstructionProject
from app.infrastructure.repository.construction_repository import ConstructionRepository
from tests.integration_database import create_reachable_engine_or_skip


async def seed_projects(session, *, company_id, quantidade):
    """Todas com o mesmo `created_at`, como a carga do MFCON produziu."""
    projetos = [
        ConstructionProject(
            id=uuid4(),
            company_id=company_id,
            code=f"EMP-{indice:06d}",
            name=f"Obra {indice:06d}",
            status="active" if indice % 2 else "completed",
            start_date=date(2020 + (indice % 5), 1, 1),
        )
        for indice in range(1, quantidade + 1)
    ]
    session.add_all(projetos)
    await session.flush()
    return projetos


async def clean_up(session, *, company_id) -> None:
    await session.rollback()
    await session.execute(delete(ConstructionProject).where(ConstructionProject.company_id == company_id))
    await session.commit()


async def test_paginar_nao_repete_nem_perde_obra_com_created_at_identico() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        await seed_projects(session, company_id=company_id, quantidade=25)
        repository = ConstructionRepository(session=session)

        try:
            vistos = []
            for pagina in (1, 2, 3):
                itens, total = await repository.list_projects(
                    company_id=company_id,
                    search=None,
                    page=pagina,
                    page_size=10,
                )
                vistos.extend(item.code for item in itens)
                assert total == 25

            assert len(vistos) == 25
            assert len(set(vistos)) == 25, "obra repetida entre paginas"
            assert vistos == sorted(vistos), "o desempate por `code` nao esta ordenando"
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_filtro_de_status_conta_a_empresa_inteira_e_nao_a_pagina_aberta() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        await seed_projects(session, company_id=company_id, quantidade=25)
        repository = ConstructionRepository(session=session)

        try:
            itens, total = await repository.list_projects(
                company_id=company_id,
                search=None,
                status="active",
                page=1,
                page_size=5,
            )

            # 13 dos 25 indices sao impares. O `total` tem de ser o do filtro, nao
            # o das 5 linhas devolvidas -- e nem o das 25 sem filtro.
            assert total == 13
            assert len(itens) == 5
            assert all(item.status == "active" for item in itens)
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_janela_de_data_filtra_pelo_inicio_da_obra() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        await seed_projects(session, company_id=company_id, quantidade=25)
        repository = ConstructionRepository(session=session)

        try:
            itens, total = await repository.list_projects(
                company_id=company_id,
                search=None,
                start_date_from=date(2022, 1, 1),
                start_date_to=date(2023, 12, 31),
                page=1,
                page_size=100,
            )

            assert total == len(itens)
            assert total > 0
            assert all(date(2022, 1, 1) <= item.start_date <= date(2023, 12, 31) for item in itens)
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()
