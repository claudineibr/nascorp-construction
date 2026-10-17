import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import ConstructionContext
from app.core.security import get_construction_context
from app.domain.record_scope import ProjectScope
from app.infrastructure.database.session import engine, get_session
from app.infrastructure.database.models.assistance import AssistanceRequest
from app.main import create_app


async def main():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        row = await session.scalar(select(AssistanceRequest).where(AssistanceRequest.status == "open").limit(1))
        assert row is not None
        company = row.company_id
        person = row.attendant_person_id
        ctx = ConstructionContext(
            company_id=company, user_id=uuid4(), person_id=person, feature_permissions={"construction_units": 15}
        )
        current = {"ctx": ctx}
        app = create_app()
        app.dependency_overrides[get_construction_context] = lambda: current["ctx"]

        async def db():
            yield session

        app.dependency_overrides[get_session] = db
        checks = []
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            base = "/v1/construction/assistance-requests"
            for status in (None, "open", "completed"):
                result = await client.get(base, params={"status": status, "page_size": 1} if status else {"page_size": 1})
                assert result.status_code == 200, result.text
                expected = await session.scalar(
                    select(func.count())
                    .select_from(AssistanceRequest)
                    .where(
                        AssistanceRequest.company_id == company,
                        AssistanceRequest.deleted_at.is_(None),
                        *([AssistanceRequest.status == status] if status else []),
                    )
                )
                assert result.json()["total"] == expected
                checks.append({"status": status or "all", "total": expected})
            assert (await client.get(base, params={"status": "unknown"})).status_code == 422
            detail = await client.get(f"{base}/{row.id}")
            assert detail.status_code == 200
            for filters in (
                {"project_id": str(row.project_id)},
                {"unit_id": str(row.unit_id)},
                {"customer_person_id": str(row.customer_person_id)},
                {"responsible_person_id": str(person)},
                {"overdue": "true"},
                {"overdue": "false"},
                {"opened_from": row.opened_at.isoformat()},
                {"opened_to": row.opened_at.isoformat()},
                {"page": 2, "page_size": 1},
            ):
                result = await client.get(base, params=filters)
                assert result.status_code == 200, result.text
            assert (await client.post(f"{base}/{row.id}/complete")).status_code == 422
            current["ctx"] = ConstructionContext(
                company_id=company,
                user_id=ctx.user_id,
                person_id=person,
                feature_permissions={"construction_units": 15},
                project_scope=ProjectScope.nothing(),
            )
            assert (await client.get(base)).json()["total"] == 0
            for method, suffix, body in (
                ("GET", "", None),
                ("POST", "/complete", None),
                ("POST", "/reopen", {"justification": "Conferência de escopo"}),
                ("DELETE", "", None),
            ):
                assert (await client.request(method, f"{base}/{row.id}{suffix}", json=body)).status_code == 404
            current["ctx"] = ConstructionContext(
                company_id=uuid4(), user_id=ctx.user_id, person_id=person, feature_permissions={"construction_units": 15}
            )
            assert (await client.get(f"{base}/{row.id}")).status_code == 404
            current["ctx"] = ConstructionContext(
                company_id=company, user_id=ctx.user_id, person_id=person, feature_permissions={"construction_units": 1}
            )
            assert (await client.post(f"{base}/{row.id}/complete")).status_code == 403
            current["ctx"] = ctx
            opened = datetime.now(UTC) - timedelta(days=2)
            request = dict(
                project_id=str(row.project_id),
                unit_id=str(row.unit_id),
                customer_person_id=str(row.customer_person_id),
                attendant_person_id=str(person),
                opened_at=opened.isoformat(),
                complaints=[{"description": "Verificação SAT", "provenance": "pending"}],
                contacts=[],
                services=[],
            )
            created = await client.post(base, json=request)
            assert created.status_code == 201, created.text
            saved = created.json()
            sat_id = saved["id"]
            request["complaints"] = [
                {
                    "id": saved["complaints"][0]["id"],
                    "description": "Verificação SAT",
                    "provenance": "invalid",
                    "analyzed_by_person_id": str(person),
                    "analyzed_at": (opened + timedelta(hours=1)).isoformat(),
                }
            ]
            updated = await client.put(f"{base}/{sat_id}", json=request)
            assert updated.status_code == 200, updated.text
            concluded = await client.post(f"{base}/{sat_id}/complete")
            assert concluded.status_code == 200, concluded.text
            assert concluded.json()["status"] == "completed"
            assert (await client.put(f"{base}/{sat_id}", json=request)).status_code == 422
            assert (await client.post(f"{base}/{sat_id}/reopen", json={"justification": "Curta"})).status_code == 422
            reopened = await client.post(
                f"{base}/{sat_id}/reopen", json={"justification": "Revisar nova evidência do cliente"}
            )
            assert reopened.status_code == 200, reopened.text
            assert any(
                event["action"] == "reopened" and event["payload"]["completed_at"] for event in reopened.json()["history"]
            )
            request["complaints"][0]["provenance"] = "valid"
            assert (await client.put(f"{base}/{sat_id}", json=request)).status_code == 200
            assert (await client.post(f"{base}/{sat_id}/complete")).status_code == 422
            request["services"] = [
                {
                    "description": "Reparo",
                    "complaint_id": request["complaints"][0]["id"],
                    "due_date": opened.date().isoformat(),
                }
            ]
            service_result = await client.put(f"{base}/{sat_id}", json=request)
            assert service_result.status_code == 200, service_result.text
            assert service_result.json()["overdue"] is True
            assert (await client.post(f"{base}/{sat_id}/complete")).status_code == 422
            service = request["services"][0]
            service.update(
                id=service_result.json()["services"][0]["id"],
                executed_by_person_id=str(person),
                executed_at=(opened + timedelta(hours=2)).isoformat(),
            )
            assert (await client.put(f"{base}/{sat_id}", json=request)).status_code == 200
            assert (await client.post(f"{base}/{sat_id}/complete")).status_code == 422
            service.update(inspected_by_person_id=str(person), inspected_at=(opened + timedelta(hours=3)).isoformat())
            assert (await client.put(f"{base}/{sat_id}", json=request)).status_code == 200
            assert (await client.post(f"{base}/{sat_id}/complete")).status_code == 200
            assert (await client.delete(f"{base}/{sat_id}")).status_code == 204
            assert (await client.get(f"{base}/{sat_id}")).status_code == 404
            checks.append(
                {"workflow": "create/analysis/complete/reopen/service/execution/inspection/delete", "result": "passed"}
            )
        await session.close()
        await transaction.rollback()
        print(json.dumps({"checks": checks, "writes": "rolled_back"}))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
