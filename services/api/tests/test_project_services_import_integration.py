from datetime import date
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject, ConstructionServiceTemplate
from app.infrastructure.repository.construction_repository import ConstructionRepository
from tests.integration_database import create_reachable_engine_or_skip
from tests.test_service_templates import build_caixa_spreadsheet


async def test_fvs_enviada_na_aba_da_obra_fica_marcada_para_a_obra() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        obra = ConstructionProject(
            id=uuid4(),
            company_id=company_id,
            code="FVS-OBRA",
            name="Obra FVS",
            status="active",
            start_date=date(2024, 1, 1),
        )
        session.add(obra)
        await session.commit()
        service = ConstructionProjectService(repository=ConstructionRepository(session=session))

        try:
            await service.import_service_templates(
                company_id=company_id,
                files=[("alvenaria.xlsx", build_caixa_spreadsheet(service_name="Alvenaria", items=[("Prumo", "Régua")]))],
            )
            results = await service.import_project_services(
                company_id=company_id,
                project_id=obra.id,
                files=[
                    ("alvenaria.xlsx", build_caixa_spreadsheet(service_name="Alvenaria", items=[("Prumo", "Régua")])),
                    ("pintura.xlsx", build_caixa_spreadsheet(service_name="Pintura", items=[("Demãos", "Visual")])),
                ],
            )

            assert [(result["status"], result["linked"]) for result in results] == [
                ("skipped", True),
                ("created", True),
            ]
            linked = await service.list_project_services(company_id=company_id, project_id=obra.id)
            assert [template.name for template in linked] == ["ALVENARIA", "PINTURA"]
            templates, restricted = await service.list_service_templates_for_project(
                company_id=company_id, project_id=obra.id
            )
            assert restricted is True
            assert {template.name for template in templates} == {"ALVENARIA", "PINTURA"}
        finally:
            await session.rollback()
            await session.execute(
                delete(ConstructionServiceTemplate).where(ConstructionServiceTemplate.company_id == company_id)
            )
            await session.execute(delete(ConstructionProject).where(ConstructionProject.company_id == company_id))
            await session.commit()

    await engine.dispose()
