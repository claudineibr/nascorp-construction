import asyncio
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import httpx
from fastapi import FastAPI
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.exceptions import ConstructionDomainError, ConstructionNotFoundError
from app.domain.services.construction_project_service import ConstructionProjectService
from app.domain.services.project_document_parser import parse_service_stages
from app.domain.services.project_document_service import ProjectDocumentService
from app.domain.services.subcontract_service import SubcontractService
from app.infrastructure.database.models import ConstructionMeasurement, ConstructionProject
from app.infrastructure.database.models import ConstructionSchedulePhase
from app.infrastructure.database.models.subcontract import ConstructionSubcontract
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction.subcontract import SubcontractRequest
from tests.integration_database import create_reachable_engine_or_skip
from tests.test_subcontracts_integration import cleanup


@pytest.mark.asyncio
async def test_monthly_selection_api_filters_execution_month_and_phase_and_excludes_other_statuses():
    from app.core.context import ConstructionContext
    from app.core.security import get_construction_context
    from app.presentation.routes.construction_projects import get_project_service, router

    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id, supplier = uuid4(), uuid4()
    try:
        async with factory() as session:
            project = ConstructionProject(id=uuid4(), company_id=company_id, code=f"TEST-{uuid4().hex[:10]}",
                name="Monthly selection", status="active", project_type="condominium")
            session.add(project)
            await session.flush()
            phases = [ConstructionSchedulePhase(id=uuid4(), company_id=company_id, project_id=project.id,
                name=name, sequence_order=index + 1) for index, name in enumerate(["Terra", "Fundação"])]
            session.add_all(phases)
            contract = ConstructionSubcontract(id=uuid4(), company_id=company_id, project_id=project.id,
                supplier_person_id=supplier, code="CT", title="Measured", pricing_mode="MEASURED", global_amount=Decimal("1000"),
                valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31), status="RELEASED", released_version=1)
            session.add(contract)
            await session.flush()
            statuses = ["draft", "submitted", "in_approval", "approved", "rejected", "paid"]
            for status in statuses:
                session.add(ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project.id,
                    schedule_phase_id=phases[0].id, subcontract_id=contract.id, code=status,
                    competence_date=date(2026, 10, 31), due_date=date(2026, 11, 20), supplier_person_id=supplier,
                    gross_amount=Decimal("10"), net_amount=Decimal("10"), measured_amount=Decimal("10"), status=status))
            for code, measured_on, phase in [("NOV", date(2026, 11, 1), phases[0]), ("OTHER-PHASE", date(2026, 10, 1), phases[1])]:
                session.add(ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project.id,
                    schedule_phase_id=phase.id, subcontract_id=contract.id, code=code, competence_date=measured_on,
                    due_date=date(2026, 11, 20), supplier_person_id=supplier, gross_amount=Decimal("10"),
                    net_amount=Decimal("10"), measured_amount=Decimal("10"), status="approved"))
            await session.commit()
            project_id, contract_id, phase_id = project.id, contract.id, phases[0].id

        async def service():
            async with factory() as session:
                yield ConstructionProjectService(repository=ConstructionRepository(session))

        app = FastAPI()
        app.include_router(router, prefix="/v1")
        context = ConstructionContext(company_id=company_id, user_id=uuid4(), person_id=None,
            feature_permissions={"construction_measurements": 1})
        app.dependency_overrides[get_construction_context] = lambda: context
        app.dependency_overrides[get_project_service] = service
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = f"/v1/construction/projects/{project_id}/zero-value-measurements"
            params = {"subcontract_id": str(contract_id)}
            response = await client.get(path, params=params)
            assert response.status_code == 200 and response.json()["total"] == 3
            params.update(competence_from="2026-10-01", competence_to="2026-10-31", schedule_phase_id=str(phase_id))
            response = await client.get(path, params=params)
            assert response.status_code == 200
            assert [row["code"] for row in response.json()["items"]] == ["approved"]
            params.update(competence_from="2026-11-01", competence_to="2026-11-30")
            response = await client.get(path, params=params)
            assert [row["code"] for row in response.json()["items"]] == ["NOV"]
            params["schedule_phase_id"] = str(uuid4())
            assert (await client.get(path, params=params)).status_code == 404
            context = ConstructionContext(company_id=uuid4(), user_id=uuid4(), person_id=None,
                feature_permissions={"construction_measurements": 1})
            assert (await client.get(path, params={"subcontract_id": str(contract_id)})).status_code == 404
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.parametrize("offset", [0, 1])
def test_stage_import_accepts_both_workbook_layouts_without_reading_month_values(offset):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([None] * offset + ["ITEM", "DESCRIÇÃO", "UNID", "No mês"])
    sheet.append([None] * offset + [" 2 ", "SERVIÇOS EM TERRA", None, 500])
    sheet.append([None] * offset + [" 2.1 ", "Escavação manual", "m³", 100])
    sheet.append([None] * offset + [" 3 ", "FUNDAÇÃO", None, 800])
    data = BytesIO()
    workbook.save(data)
    assert parse_service_stages(data.getvalue()) == [{"name": "SERVIÇOS EM TERRA"}, {"name": "FUNDAÇÃO"}]


def test_stage_import_rejects_invalid_file():
    with pytest.raises(ConstructionDomainError, match="XLSX"):
        parse_service_stages(b"invalid")


@pytest.mark.asyncio
async def test_stage_import_preserves_existing_phases_and_is_idempotent():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    try:
        async with factory() as session:
            project = ConstructionProject(id=uuid4(), company_id=company_id, code=f"TEST-{uuid4().hex[:10]}",
                name="Stage import", status="planning", project_type="condominium")
            session.add(project)
            await session.commit()
            workbook = Workbook()
            workbook.active.append(["ITEM", "DESCRIÇÃO"])
            workbook.active.append(["2", "SERVIÇOS EM TERRA"])
            workbook.active.append(["3", "FUNDAÇÃO"])
            content = BytesIO()
            workbook.save(content)
            projects = ConstructionProjectService(repository=ConstructionRepository(session))
            documents = ProjectDocumentService(projects, None, company_id, uuid4(), "America/Campo_Grande")
            assert await documents.import_stages(project.id, content.getvalue()) == {"created": 2, "matched": 0, "total": 2}
            assert await documents.import_stages(project.id, content.getvalue()) == {"created": 0, "matched": 2, "total": 2}
            another_company = ProjectDocumentService(projects, None, uuid4(), uuid4(), "America/Campo_Grande")
            with pytest.raises(ConstructionNotFoundError):
                await another_company.import_stages(project.id, content.getvalue())
            await session.rollback()
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_measured_contract_reserves_drafts_under_lock_and_does_not_consume_twice_on_approval():
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id, supplier = uuid4(), uuid4()
    try:
        async with factory() as session:
            project = ConstructionProject(id=uuid4(), company_id=company_id, code=f"TEST-{uuid4().hex[:10]}",
                name="Measured contract", status="planning", project_type="condominium")
            session.add(project)
            await session.commit()
            client = AsyncMock()
            client.list_person_summaries.return_value = {"items": [{"id": str(supplier)}]}
            service = SubcontractService(ConstructionProjectService(repository=ConstructionRepository(session), erp_client=client))
            contract = await service.save(company_id, project.id, SubcontractRequest(code="CT", title="Serviços medidos",
                pricing_mode="MEASURED", global_amount="100", supplier_person_id=supplier,
                valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31)), uuid4())
            contract = await service.release(company_id, contract["id"], uuid4())
            parents = [ConstructionMeasurement(id=uuid4(), company_id=company_id, project_id=project.id, code=f"M{i}",
                subcontract_id=contract["id"], competence_date=date(2026, 10, 1), measured_amount=Decimal("0"),
                gross_amount=Decimal("0"), retentions_amount=Decimal("0"), due_date=date(2026, 11, 1),
                supplier_person_id=supplier, status="draft", retention_details=[]) for i in range(2)]
            session.add_all(parents)
            await session.commit()

        async def reserve(measurement_id):
            async with factory() as session:
                service = SubcontractService(ConstructionProjectService(repository=ConstructionRepository(session)))
                row = await service.repository.measurement(company_id, measurement_id, True)
                try:
                    await service.reserve_measured(row, Decimal("60"))
                    row.gross_amount = row.net_amount = row.measured_amount = Decimal("60")
                    await session.commit()
                    return row.id
                except ConstructionDomainError:
                    await session.rollback()
                    return None

        results = await asyncio.gather(*(reserve(parent.id) for parent in parents))
        assert sum(result is not None for result in results) == 1
        successful = next(result for result in results if result is not None)
        async with factory() as session:
            service = SubcontractService(ConstructionProjectService(repository=ConstructionRepository(session)))
            row = await service.repository.measurement(company_id, successful, True)
            await service.consume(row)
            row.status = "approved"
            await session.commit()
            detail = await service.detail(company_id, contract["id"])
            assert Decimal(detail["remaining_amount"]) == Decimal("40")
            row.status = "paid"
            await session.commit()
            assert Decimal((await service.detail(company_id, contract["id"]))["remaining_amount"]) == Decimal("40")
            with pytest.raises(ConstructionNotFoundError):
                await service.get(uuid4(), contract["id"])
            await session.rollback()
    finally:
        await cleanup(factory, company_id)
        await engine.dispose()
