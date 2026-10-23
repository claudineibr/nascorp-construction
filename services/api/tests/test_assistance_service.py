import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.record_scope import ProjectScope
from app.domain.exceptions import ConstructionDomainError
from app.domain.services.assistance_service import pending_stage, AssistanceRequestService
from app.infrastructure.database.models.assistance import (
    AssistanceRequest,
    AssistanceContact,
    AssistanceComplaint,
    AssistanceService,
    AssistanceHistory,
    AssistanceMigrationState,
)
from app.infrastructure.database.models.construction import ConstructionProject, ConstructionUnit
from app.infrastructure.repository.assistance_repository import AssistanceRepository
from app.schemas.construction.assistance import AssistanceInput
from tests.integration_database import create_reachable_engine_or_skip


def complaint(provenance="invalid", analyzed=True):
    return SimpleNamespace(
        id=uuid4(),
        deleted_at=None,
        provenance=provenance,
        analyzed_by_person_id=uuid4() if analyzed else None,
        analyzed_at=datetime.now(UTC) if analyzed else None,
    )


def service(complaint_id, executed=True, inspected=True):
    return SimpleNamespace(
        deleted_at=None,
        complaint_id=complaint_id,
        due_date=datetime.now(UTC).date(),
        executed_at=datetime.now(UTC) if executed else None,
        executed_by_person_id=uuid4() if executed else None,
        inspected_at=datetime.now(UTC) if inspected else None,
        inspected_by_person_id=uuid4() if inspected else None,
    )


@pytest.mark.parametrize(
    "provenance,analyzed,expected",
    [
        ("pending", False, "analysis"),
        ("invalid", False, "analysis"),
        ("invalid", True, "completion"),
        ("valid", True, "planning"),
    ],
)
def test_complaint_analysis_controls_completion(provenance, analyzed, expected):
    row = SimpleNamespace(status="open", complaints=[complaint(provenance, analyzed)], services=[])
    assert pending_stage(row) == expected


def test_mixed_complaints_and_each_service_must_finish():
    valid = complaint("valid")
    invalid = complaint("invalid")
    row = SimpleNamespace(
        status="open",
        complaints=[valid, invalid],
        services=[service(valid.id), service(None, executed=False, inspected=False)],
    )
    assert pending_stage(row) == "execution"
    row.services[1] = service(None, inspected=False)
    assert pending_stage(row) == "inspection"
    row.services[1] = service(None)
    assert pending_stage(row) == "completion"
    row.services[0].complaint_id = None
    assert pending_stage(row) == "planning"
    invalid.analyzed_at = None
    assert pending_stage(row) == "analysis"


def test_empty_requests_and_historical_completions():
    row = SimpleNamespace(status="open", complaints=[], services=[])
    assert pending_stage(row) == "analysis"
    row.status = "completed"
    assert pending_stage(row) == "completed"


@pytest.mark.asyncio
async def test_concurrent_numbers_and_reimport_gate_and_no_measurement_side_effects(monkeypatch):
    from unittest.mock import AsyncMock

    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id = uuid4()
    project_id, unit_id = uuid4(), uuid4()
    try:
        async with factory() as session:
            person_id = await session.scalar(text("SELECT id FROM persons WHERE deleted_at IS NULL LIMIT 1"))
            assert person_id is not None
            await session.execute(
                text(
                    "INSERT INTO companies (id, legal_name, is_active) VALUES (:id, 'SAT concurrency', true)"
                ),
                {"id": company_id},
            )
            await session.execute(
                text("INSERT INTO person_company_profiles (id, person_id, company_id) VALUES (:id, :person_id, :company_id)"),
                {"id": uuid4(), "person_id": person_id, "company_id": company_id},
            )
            before = (
                await session.execute(
                    text(
                        "SELECT (SELECT count(*) FROM construction.construction_measurements), (SELECT count(*) FROM construction.construction_inspection_rounds)"
                    )
                )
            ).one()
            session.add(
                ConstructionProject(
                    id=project_id,
                    company_id=company_id,
                    code=f"SAT-{company_id}",
                    name="SAT concurrency",
                    project_type="residential_vertical",
                    status="active",
                )
            )
            await session.flush()
            session.add(
                ConstructionUnit(
                    id=unit_id,
                    company_id=company_id,
                    project_id=project_id,
                    code="SAT-1",
                    unit_type="moradia",
                    status="available",
                )
            )
            await session.commit()

        async def create():
            async with factory() as session:
                sat_service = AssistanceRequestService(AssistanceRepository(session, ProjectScope.unlimited()))
                row = await sat_service.save(
                    company_id,
                    AssistanceInput(
                        project_id=project_id,
                        unit_id=unit_id,
                        customer_person_id=person_id,
                        attendant_person_id=person_id,
                        opened_at=datetime.now(UTC) - timedelta(hours=1),
                        complaints=[{"description": "Reparo"}],
                    ),
                    uuid4(),
                    actor_person_id=person_id,
                )
                return row.number

        numbers = await asyncio.gather(create(), create())
        assert sorted(numbers) == [1, 2]
        async with factory() as session:
            assert (
                await session.scalar(
                    select(AssistanceMigrationState.released_at).where(AssistanceMigrationState.company_id == company_id)
                )
                is not None
            )
            after = (
                await session.execute(
                    text(
                        "SELECT (SELECT count(*) FROM construction.construction_measurements), (SELECT count(*) FROM construction.construction_inspection_rounds)"
                    )
                )
            ).one()
            assert before == after
    finally:
        async with factory() as session:
            ids = select(AssistanceRequest.id).where(AssistanceRequest.company_id == company_id)
            for model in (AssistanceHistory, AssistanceService, AssistanceContact, AssistanceComplaint):
                await session.execute(delete(model).where(model.request_id.in_(ids)))
            await session.execute(delete(AssistanceRequest).where(AssistanceRequest.company_id == company_id))
            await session.execute(delete(AssistanceMigrationState).where(AssistanceMigrationState.company_id == company_id))
            await session.execute(delete(ConstructionUnit).where(ConstructionUnit.id == unit_id))
            await session.execute(delete(ConstructionProject).where(ConstructionProject.id == project_id))
            await session.execute(text("DELETE FROM person_company_profiles WHERE company_id = :id"), {"id": company_id})
            await session.execute(text("DELETE FROM companies WHERE id = :id"), {"id": company_id})
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("description", ["", "   "])
async def test_unchanged_legacy_blank_description_is_preserved(description):
    from unittest.mock import AsyncMock

    old_service = AssistanceService(id=uuid4(), source_id=17, description=description, deleted_at=None)
    row = AssistanceRequest(
        id=uuid4(),
        project_id=uuid4(),
        unit_id=uuid4(),
        opened_at=datetime.now(UTC) - timedelta(days=1),
        contacts=[],
        complaints=[],
        services=[old_service],
        history=[],
    )
    person_id = uuid4()
    row.attendant_person_id = person_id
    repository = SimpleNamespace(
        project=AsyncMock(return_value=object()),
        unit=AsyncMock(return_value=object()),
        valid_people=AsyncMock(side_effect=lambda company_id, ids: set(ids)),
    )
    data = AssistanceInput(
        project_id=row.project_id,
        unit_id=row.unit_id,
        customer_person_id=person_id,
        attendant_person_id=person_id,
        opened_at=row.opened_at,
        services=[{"id": old_service.id, "description": description}],
    )
    assert data.services[0].description == description
    await AssistanceRequestService(repository).validate(uuid4(), data, row)
    old_service.source_id = None
    with pytest.raises(ConstructionDomainError, match="descrição"):
        await AssistanceRequestService(repository).validate(uuid4(), data, row)


@pytest.mark.asyncio
async def test_unit_with_sat_is_protected_without_financial_history():
    from unittest.mock import AsyncMock
    from app.infrastructure.repository._history import protected_history

    unit = ConstructionUnit(
        id=uuid4(), company_id=uuid4(), project_id=uuid4(), external_contract_id=None, external_receivable_id=None
    )
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(return_value=uuid4()))

    class Rows:
        def __iter__(self):
            return iter([])

        def all(self):
            return [unit]

    session.scalars = AsyncMock(return_value=Rows())
    assert await protected_history(session, unit) is True


@pytest.mark.asyncio
async def test_person_without_link_to_the_company_is_refused():
    from unittest.mock import AsyncMock

    company_id, attendant_id, outsider_id = uuid4(), uuid4(), uuid4()
    repository = SimpleNamespace(
        project=AsyncMock(return_value=object()),
        unit=AsyncMock(return_value=object()),
        valid_people=AsyncMock(return_value={attendant_id}),
    )
    data = AssistanceInput(
        project_id=uuid4(),
        unit_id=uuid4(),
        customer_person_id=outsider_id,
        attendant_person_id=attendant_id,
        opened_at=datetime.now(UTC) - timedelta(hours=1),
    )
    with pytest.raises(ConstructionDomainError, match="sem vínculo ativo com esta empresa"):
        await AssistanceRequestService(repository).validate(company_id, data)
    repository.valid_people.assert_awaited_once_with(company_id, {attendant_id, outsider_id})


@pytest.mark.asyncio
async def test_attendant_with_company_link_does_not_require_employee_role():
    from unittest.mock import AsyncMock

    company_id, person_id = uuid4(), uuid4()
    repository = SimpleNamespace(
        project=AsyncMock(return_value=object()),
        unit=AsyncMock(return_value=object()),
        valid_people=AsyncMock(return_value={person_id}),
    )
    data = AssistanceInput(
        project_id=uuid4(),
        unit_id=uuid4(),
        customer_person_id=person_id,
        attendant_person_id=person_id,
        opened_at=datetime.now(UTC) - timedelta(hours=1),
    )
    await AssistanceRequestService(repository).validate(company_id, data)
    repository.valid_people.assert_awaited_once_with(company_id, {person_id})


@pytest.mark.parametrize("existing", [False, True])
async def test_save_resolves_attendant_from_actor_or_preserves_existing(existing):
    from unittest.mock import AsyncMock

    company_id, actor_id, actor_person_id, stored_person_id = uuid4(), uuid4(), uuid4(), uuid4()
    request_id = uuid4() if existing else None
    repository = SimpleNamespace(release_operation=AsyncMock())
    service = AssistanceRequestService(repository)
    service.get = AsyncMock(return_value=SimpleNamespace(status="open", attendant_person_id=stored_person_id))
    service.validate = AsyncMock(side_effect=ConstructionDomainError(message="Stop before writing", status_code=422))
    request = AssistanceInput(
        project_id=uuid4(),
        unit_id=uuid4(),
        customer_person_id=uuid4(),
        attendant_person_id=uuid4(),
        opened_at=datetime.now(UTC) - timedelta(hours=1),
    )
    with pytest.raises(ConstructionDomainError, match="Stop before writing"):
        await service.save(company_id, request, actor_id, request_id, actor_person_id=actor_person_id)
    resolved = service.validate.await_args.args[1]
    assert resolved.attendant_person_id == (stored_person_id if existing else actor_person_id)


async def _seed_sat_company(factory, company_id, project_id, unit_ids):
    async with factory() as session:
        person_id = await session.scalar(text("SELECT id FROM persons WHERE deleted_at IS NULL LIMIT 1"))
        assert person_id is not None
        await session.execute(
            text("INSERT INTO companies (id, legal_name, is_active) VALUES (:id, 'SAT header', true)"),
            {"id": company_id},
        )
        await session.execute(
            text("INSERT INTO person_company_profiles (id, person_id, company_id) VALUES (:id, :person_id, :company_id)"),
            {"id": uuid4(), "person_id": person_id, "company_id": company_id},
        )
        session.add(
            ConstructionProject(
                id=project_id,
                company_id=company_id,
                code=f"SAT-{company_id}",
                name="SAT header",
                project_type="residential_vertical",
                status="active",
            )
        )
        await session.flush()
        for index, unit_id in enumerate(unit_ids, start=1):
            session.add(
                ConstructionUnit(
                    id=unit_id,
                    company_id=company_id,
                    project_id=project_id,
                    code=f"SAT-{index}",
                    unit_type="moradia",
                    status="available",
                )
            )
        await session.commit()
        return person_id


async def _cleanup_sat_company(factory, company_id, project_id, unit_ids):
    async with factory() as session:
        ids = select(AssistanceRequest.id).where(AssistanceRequest.company_id == company_id)
        for model in (AssistanceHistory, AssistanceService, AssistanceContact, AssistanceComplaint):
            await session.execute(delete(model).where(model.request_id.in_(ids)))
        await session.execute(delete(AssistanceRequest).where(AssistanceRequest.company_id == company_id))
        await session.execute(delete(AssistanceMigrationState).where(AssistanceMigrationState.company_id == company_id))
        await session.execute(delete(ConstructionUnit).where(ConstructionUnit.id.in_(unit_ids)))
        await session.execute(delete(ConstructionProject).where(ConstructionProject.id == project_id))
        await session.execute(text("DELETE FROM person_company_profiles WHERE company_id = :id"), {"id": company_id})
        await session.execute(text("DELETE FROM companies WHERE id = :id"), {"id": company_id})
        await session.commit()


@pytest.mark.asyncio
async def test_editing_the_header_of_an_existing_sat_saves_the_notes(monkeypatch):
    from unittest.mock import AsyncMock

    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id, project_id, unit_id = uuid4(), uuid4(), uuid4()
    try:
        person_id = await _seed_sat_company(factory, company_id, project_id, [unit_id])
        payload = {
            "project_id": project_id,
            "unit_id": unit_id,
            "customer_person_id": person_id,
            "attendant_person_id": person_id,
            "opened_at": datetime.now(UTC) - timedelta(hours=1),
            "complaints": [{"description": "Infiltração"}],
        }
        async with factory() as session:
            created = await AssistanceRequestService(AssistanceRepository(session, ProjectScope.unlimited())).save(
                company_id, AssistanceInput(**payload), uuid4(), actor_person_id=person_id
            )
            complaint_id = created.complaints[0].id
        async with factory() as session:
            edited = await AssistanceRequestService(AssistanceRepository(session, ProjectScope.unlimited())).save(
                company_id,
                AssistanceInput(
                    **{**payload, "notes": "Cliente pediu retorno à tarde",
                       "complaints": [{"id": complaint_id, "description": "Infiltração"}]}
                ),
                uuid4(),
                created.id,
            )
            assert edited.notes == "Cliente pediu retorno à tarde"
            assert edited.updated_at is not None
    finally:
        await _cleanup_sat_company(factory, company_id, project_id, [unit_id])
        await engine.dispose()


@pytest.mark.asyncio
async def test_next_number_counts_sats_hidden_by_the_history_filter(monkeypatch):
    from unittest.mock import AsyncMock

    engine = await create_reachable_engine_or_skip()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    company_id, project_id, hidden_unit_id, unit_id = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        person_id = await _seed_sat_company(factory, company_id, project_id, [hidden_unit_id, unit_id])
        async with factory() as session:
            session.add(
                AssistanceRequest(
                    id=uuid4(),
                    company_id=company_id,
                    project_id=project_id,
                    unit_id=hidden_unit_id,
                    customer_person_id=person_id,
                    attendant_person_id=person_id,
                    number=1,
                    status="open",
                    opened_at=datetime.now(UTC) - timedelta(days=2),
                    deleted_at=datetime.now(UTC),
                )
            )
            await session.flush()
            await session.execute(
                text("UPDATE construction.construction_units SET deleted_at = now() WHERE id = :id"),
                {"id": hidden_unit_id},
            )
            await session.commit()
        async with factory() as session:
            row = await AssistanceRequestService(AssistanceRepository(session, ProjectScope.unlimited())).save(
                company_id,
                AssistanceInput(
                    project_id=project_id,
                    unit_id=unit_id,
                    customer_person_id=person_id,
                    attendant_person_id=person_id,
                    opened_at=datetime.now(UTC) - timedelta(hours=1),
                    complaints=[{"description": "Trinca"}],
                ),
                uuid4(),
                actor_person_id=person_id,
            )
            assert row.number == 2
    finally:
        await _cleanup_sat_company(factory, company_id, project_id, [hidden_unit_id, unit_id])
        await engine.dispose()


@pytest.mark.asyncio
async def test_unlinked_service_does_not_block_a_new_complaint():
    from unittest.mock import AsyncMock

    analyzed_at = datetime.now(UTC) - timedelta(days=2)
    executed_at = datetime.now(UTC) - timedelta(days=1)
    person_id = uuid4()
    old_complaint = AssistanceComplaint(
        id=uuid4(), description="Porta", provenance="valid", analyzed_by_person_id=person_id,
        analyzed_at=analyzed_at, deleted_at=None,
    )
    old_service = AssistanceService(
        id=uuid4(), complaint_id=None, description="Revisão geral", due_date=None,
        executed_by_person_id=person_id, executed_at=executed_at, inspected_by_person_id=None,
        inspected_at=None, deleted_at=None, source_id=None,
    )
    row = AssistanceRequest(
        id=uuid4(), project_id=uuid4(), unit_id=uuid4(), attendant_person_id=person_id,
        opened_at=datetime.now(UTC) - timedelta(days=3), contacts=[], complaints=[old_complaint],
        services=[old_service], history=[],
    )
    repository = SimpleNamespace(
        project=AsyncMock(return_value=object()),
        unit=AsyncMock(return_value=object()),
        valid_people=AsyncMock(side_effect=lambda company_id, ids: set(ids)),
    )
    data = AssistanceInput(
        project_id=row.project_id,
        unit_id=row.unit_id,
        customer_person_id=person_id,
        attendant_person_id=person_id,
        opened_at=row.opened_at,
        complaints=[
            {"id": old_complaint.id, "description": "Porta", "provenance": "valid",
             "analyzed_by_person_id": person_id, "analyzed_at": analyzed_at},
            {"description": "Janela emperrada"},
        ],
        services=[
            {"id": old_service.id, "description": "Revisão geral", "executed_by_person_id": person_id,
             "executed_at": executed_at},
            {"description": "Limpeza final", "executed_by_person_id": person_id, "executed_at": executed_at},
        ],
    )
    await AssistanceRequestService(repository).validate(uuid4(), data, row)


@pytest.mark.asyncio
async def test_print_context_enforces_request_scope():
    from unittest.mock import AsyncMock
    from app.domain.exceptions import ConstructionNotFoundError

    repository = SimpleNamespace(get=AsyncMock(return_value=None), print_people=AsyncMock())
    with pytest.raises(ConstructionNotFoundError):
        await AssistanceRequestService(repository).print_context(uuid4(), uuid4())
    repository.print_people.assert_not_awaited()
