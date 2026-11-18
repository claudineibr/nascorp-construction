from datetime import UTC, datetime
from uuid import uuid4

import pytest
import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.context import ConstructionContext
from app.core.security import get_construction_context
from app.domain.record_scope import ProjectScope
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionMeasurement, ConstructionServiceTemplate
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.presentation.routes.construction_projects import create_measurement_item, get_project_service
from tests.integration_database import create_reachable_engine_or_skip
from tests.test_project_scope_integration import _semear_obra


@pytest.mark.parametrize("use_template", [True, False])
@pytest.mark.parametrize("status", ["draft", "submitted", "in_approval", "approved", "rejected", "paid", "cancelled"])
async def test_duplicate_service_query_preserves_company_and_project_scope(use_template, status):
    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()
    other_company_id = uuid4()
    suffix = uuid4().hex[:8]

    try:
        async with factory() as session:
            assert engine.url.database == "test"
            allowed = await _semear_obra(session, company_id=company_id, sufixo=f"A-{suffix}")
            forbidden = await _semear_obra(session, company_id=company_id, sufixo=f"B-{suffix}")
            foreign = await _semear_obra(session, company_id=other_company_id, sufixo=f"C-{suffix}")
            template_id = None
            if use_template:
                template = ConstructionServiceTemplate(company_id=company_id, name=f"Servico {suffix}")
                session.add(template)
                await session.flush()
                template_id = template.id

            for row in (allowed, forbidden, foreign):
                row["medicao"].unit_id = row["unidade"].id
                row["medicao"].status = "rejected" if status == "cancelled" else status
                row["medicao"].rejected_at = datetime(2024, 1, 1, tzinfo=UTC) if status == "rejected" else None
                row["item"].description = "Servico repetido"
                if row is not foreign:
                    row["item"].service_template_id = template_id
            await session.flush()

            async def find(scope, row, requested_company_id=company_id, exclude_id=None):
                return await ConstructionRepository(session=session, scope=scope).find_unit_order_with_service(
                    company_id=requested_company_id,
                    unit_id=row["unidade"].id,
                    exclude_measurement_id=exclude_id or uuid4(),
                    service_template_id=template_id,
                    description="  SERVICO REPETIDO  ",
                )

            limited = ProjectScope.limited_to([allowed["obra"].id])
            expected = None if status == "cancelled" else allowed["medicao"]
            assert await find(limited, allowed) is expected
            assert await find(ProjectScope.unlimited(), allowed) is expected
            assert await find(None, allowed) is expected
            assert await find(ProjectScope.nothing(), allowed) is None
            assert await find(limited, forbidden) is None
            assert await find(limited, foreign) is None
            assert await find(ProjectScope.unlimited(), foreign) is None
            assert await find(ProjectScope.unlimited(), allowed, requested_company_id=other_company_id) is None
            assert await find(limited, allowed, exclude_id=allowed["medicao"].id) is None
            await session.rollback()
    finally:
        await engine.dispose()


async def test_create_service_http_with_limited_scope_and_duplicate_confirmation():
    engine = await create_reachable_engine_or_skip()
    company_id = uuid4()
    suffix = uuid4().hex[:8]
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            async with factory() as session:
                assert engine.url.database == "test"
                seeded = await _semear_obra(session, company_id=company_id, sufixo=f"HTTP-{suffix}")
                seeded["medicao"].unit_id = seeded["unidade"].id
                measurement = ConstructionMeasurement(
                    company_id=company_id,
                    project_id=seeded["obra"].id,
                    unit_id=seeded["unidade"].id,
                    code=f"OS-NEW-{suffix}",
                    purpose="CONTROL",
                    measured_amount=0,
                    due_date=seeded["medicao"].due_date,
                )
                session.add(measurement)
                await session.flush()
                measurement_id = measurement.id
                repeated_description = seeded["item"].description
                scope = ProjectScope.limited_to([seeded["obra"].id])
                context = ConstructionContext(company_id, uuid4(), None, {"construction_measurements": 15}, scope)
                service = ConstructionProjectService(ConstructionRepository(session=session, scope=scope))
                app = FastAPI()
                app.add_api_route("/measurements/{measurement_id}/items", create_measurement_item, methods=["POST"], status_code=201)
                app.dependency_overrides[get_construction_context] = lambda: context
                app.dependency_overrides[get_project_service] = lambda: service
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    path = f"/measurements/{measurement_id}/items"
                    response = await client.post(path, json={"description": "Servico novo"})
                    assert response.status_code == 201, response.text
                    response = await client.post(path, json={"description": repeated_description})
                    assert response.status_code == 400, response.text
                    assert "Confirme para incluir mesmo assim" in response.text
                    response = await client.post(path, json={
                        "description": repeated_description,
                        "confirm_unit_duplicate": True,
                    })
                    assert response.status_code == 201, response.text
                    response = await client.post(path, json={"description": "Servico novo"})
                    assert response.status_code == 400, response.text
                    assert "já faz parte desta medição" in response.text
            await outer.rollback()
    finally:
        await engine.dispose()
