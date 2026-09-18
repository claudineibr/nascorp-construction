from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionServiceTemplate,
    ConstructionServiceTemplateAudit,
    ConstructionServiceTemplateSection,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction import (
    ConstructionServiceTemplateCreate,
    ConstructionServiceTemplateReplace,
    ConstructionServiceTemplateUpdate,
)
from tests.integration_database import create_reachable_engine_or_skip


def section(name, items):
    return {
        "name": name,
        "items": [
            {"description": description, "verification_method": method}
            for description, method in items
        ],
    }


async def clean_up(session, *, company_id) -> None:
    await session.rollback()
    await session.execute(
        delete(ConstructionServiceTemplateAudit).where(
            ConstructionServiceTemplateAudit.company_id == company_id
        )
    )
    await session.execute(
        delete(ConstructionServiceTemplateSection).where(
            ConstructionServiceTemplateSection.company_id == company_id
        )
    )
    await session.execute(
        delete(ConstructionServiceTemplate).where(ConstructionServiceTemplate.company_id == company_id)
    )
    await session.commit()


async def test_the_replace_snapshot_holds_the_new_structure_not_the_old_one() -> None:
    """Esta e a razao do `populate_existing` no repositorio.

    A sessao roda com ``expire_on_commit=False``: reler o servico logo depois de
    trocar as secoes devolvia a instancia do identity map, com as secoes ANTIGAS
    ainda carregadas -- o `selectinload` nao sobrescreve colecao ja carregada. O
    snapshot da revisao saia afirmando a estrutura anterior, e so o banco de
    verdade mostra isso: o repositorio falso dos testes de unidade re-hidrata a
    cada leitura e nunca reproduz a falha.
    """
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = ConstructionProjectService(repository=ConstructionRepository(session=session))
        try:
            created = await service.create_service_template(
                company_id=company_id,
                request=ConstructionServiceTemplateCreate(
                    name=f"Auditoria {str(uuid4())[:8]}",
                    sections=[section("Preparo", [("Terreno limpo", "Visual"), ("Nivel", "Laser")])],
                ),
                actor_user_id=uuid4(),
            )

            await service.replace_service_template(
                company_id=company_id,
                service_template_id=created.id,
                request=ConstructionServiceTemplateReplace(
                    name=created.name,
                    sections=[
                        section("Preparo", [("Terreno limpo", "Visual")]),
                        section("Aceitacao", [("Recebido", "Vistoria")]),
                    ],
                ),
                actor_user_id=uuid4(),
            )

            audits = await service.list_service_template_audits(
                company_id=company_id,
                service_template_id=created.id,
            )

            assert [audit.event for audit in audits] == ["replaced", "created"]
            assert len(audits[0].snapshot["sections"]) == 2
            assert audits[0].summary == "2 seções, 2 itens."
            assert len(audits[1].snapshot["sections"]) == 1
            assert audits[1].summary == "1 seção, 2 itens."
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()


async def test_the_deleted_service_keeps_its_trail_and_frees_the_name() -> None:
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = ConstructionProjectService(repository=ConstructionRepository(session=session))
        name = f"Auditoria {str(uuid4())[:8]}"
        who_deleted = uuid4()
        try:
            created = await service.create_service_template(
                company_id=company_id,
                request=ConstructionServiceTemplateCreate(
                    name=name,
                    sections=[section("Preparo", [("Terreno limpo", "Visual")])],
                ),
                actor_user_id=uuid4(),
            )
            await service.update_service_template(
                company_id=company_id,
                service_template_id=created.id,
                request=ConstructionServiceTemplateUpdate(is_active=False),
                actor_user_id=uuid4(),
            )
            await service.delete_service_template(
                company_id=company_id,
                service_template_id=created.id,
                actor_user_id=who_deleted,
            )

            assert await service.list_service_templates(company_id=company_id, only_active=False) == []

            deleted = await service.list_service_templates(company_id=company_id, only_deleted=True)
            assert [item.id for item in deleted] == [created.id]
            assert deleted[0].deleted_by_user_id == who_deleted

            audits = await service.list_service_template_audits(
                company_id=company_id,
                service_template_id=created.id,
            )
            assert [audit.event for audit in audits] == ["deleted", "deactivated", "created"]
            assert [audit.sequence_number for audit in audits] == [3, 2, 1]
            assert audits[0].actor_user_id == who_deleted

            # O indice unico e parcial: o nome volta a ficar livre.
            recreated = await service.create_service_template(
                company_id=company_id,
                request=ConstructionServiceTemplateCreate(name=name, sections=[]),
                actor_user_id=uuid4(),
            )
            assert recreated.id != created.id
        finally:
            await clean_up(session, company_id=company_id)

    await engine.dispose()
