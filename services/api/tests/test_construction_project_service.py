from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.domain.constants import ConstructionProjectStatus
from app.domain.exceptions import (
    ConstructionDuplicateCodeError,
    ConstructionInvalidStatusTransitionError,
    ConstructionNotFoundError,
)
from app.domain.events.constants import ConstructionEventType, ErpEventType
from app.domain.events.contracts import EventEnvelope
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject
from app.schemas.construction import ConstructionProjectCreate, ConstructionProjectUpdate


class FakeConstructionRepository:
    def __init__(self) -> None:
        self.projects: dict[tuple[object, object], ConstructionProject] = {}
        self.commits = 0

    async def add(self, entity: ConstructionProject) -> None:
        if entity.id is None:
            entity.id = uuid4()
        self.projects[(entity.company_id, entity.id)] = entity

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, entity: ConstructionProject) -> None:
        return None

    async def get_project(self, *, company_id, project_id):
        return self.projects.get((company_id, project_id))

    async def get_project_by_code(self, *, company_id, code):
        return next(
            (
                project
                for (stored_company_id, _), project in self.projects.items()
                if stored_company_id == company_id and project.code == code
            ),
            None,
        )

    async def list_projects(self, *, company_id, search, page, page_size):
        items = [project for (stored_company_id, _), project in self.projects.items() if stored_company_id == company_id]
        return items[(page - 1) * page_size : page * page_size], len(items)

    async def delete(self, entity: ConstructionProject) -> None:
        self.projects.pop((entity.company_id, entity.id), None)


class FakeEventRepository:
    def __init__(self) -> None:
        self.outbox_events: list[EventEnvelope] = []
        self.processed_events: set[tuple[str, object]] = set()

    async def add_outbox_event(self, *, event: EventEnvelope):
        self.outbox_events.append(event)
        return event

    async def mark_processed(self, *, consumer_name: str, event: EventEnvelope) -> bool:
        processed_key = (consumer_name, event.event_id)
        if processed_key in self.processed_events:
            return False

        self.processed_events.add(processed_key)
        return True


def make_service(repository: FakeConstructionRepository | None = None) -> ConstructionProjectService:
    return ConstructionProjectService(repository=repository or FakeConstructionRepository())


def make_erp_cost_center_created_event(
    *,
    company_id,
    project_id,
    synthetic_cost_center_id,
    analytic_cost_center_id,
) -> EventEnvelope:
    event_id = uuid4()
    return EventEnvelope(
        event_id=event_id,
        event_type=ErpEventType.COST_CENTER_CREATED,
        event_version=1,
        company_id=company_id,
        aggregate_id=project_id,
        aggregate_type="construction_project",
        occurred_at=datetime.now(tz=UTC),
        producer="erp-api",
        correlation_id=event_id,
        causation_id=None,
        payload={
            "construction_project_id": str(project_id),
            "synthetic_cost_center_id": str(synthetic_cost_center_id),
            "analytic_cost_center_id": str(analytic_cost_center_id),
        },
    )


@pytest.mark.asyncio
async def test_create_project_rejects_duplicate_code() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    existing_project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-001",
        name="Existing project",
        status=ConstructionProjectStatus.DRAFT,
    )
    repository.projects[(company_id, existing_project.id)] = existing_project
    service = make_service(repository=repository)

    with pytest.raises(ConstructionDuplicateCodeError):
        await service.create_project(
            company_id=company_id,
            request=ConstructionProjectCreate(code="OBRA-001", name="New project"),
        )


@pytest.mark.asyncio
async def test_create_project_records_project_created_outbox_event() -> None:
    company_id = uuid4()
    user_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    service = ConstructionProjectService(repository=repository, event_repository=event_repository)

    project = await service.create_project(
        company_id=company_id,
        request=ConstructionProjectCreate(
            code="OBRA-010",
            name="Obra Outbox",
            start_date=date(2026, 4, 1),
            expected_end_date=date(2026, 12, 31),
        ),
        actor_user_id=user_id,
    )

    assert repository.commits == 1
    assert len(event_repository.outbox_events) == 1
    event = event_repository.outbox_events[0]
    assert event.event_type == ConstructionEventType.PROJECT_CREATED
    assert event.company_id == company_id
    assert event.aggregate_id == project.id
    assert event.payload["construction_project_id"] == str(project.id)
    assert event.payload["project_code"] == "OBRA-010"
    assert event.payload["project_name"] == "Obra Outbox"
    assert event.payload["start_date"] == "2026-04-01"
    assert event.payload["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_update_project_rejects_invalid_status_transition() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-002",
        name="Completed project",
        status=ConstructionProjectStatus.COMPLETED,
    )
    repository.projects[(company_id, project.id)] = project
    service = make_service(repository=repository)

    with pytest.raises(ConstructionInvalidStatusTransitionError):
        await service.update_project(
            company_id=company_id,
            project_id=project.id,
            request=ConstructionProjectUpdate(status=ConstructionProjectStatus.ACTIVE),
        )


@pytest.mark.asyncio
async def test_get_project_enforces_company_isolation() -> None:
    owner_company_id = uuid4()
    other_company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=owner_company_id,
        code="OBRA-003",
        name="Tenant project",
        status=ConstructionProjectStatus.DRAFT,
    )
    repository.projects[(owner_company_id, project.id)] = project
    service = make_service(repository=repository)

    with pytest.raises(ConstructionNotFoundError):
        await service.get_project(company_id=other_company_id, project_id=project.id)


@pytest.mark.asyncio
async def test_apply_cost_center_created_event_updates_project_once() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    synthetic_cost_center_id = uuid4()
    analytic_cost_center_id = uuid4()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-020",
        name="Cost center project",
        status=ConstructionProjectStatus.DRAFT,
    )
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(repository=repository, event_repository=event_repository)
    event = make_erp_cost_center_created_event(
        company_id=company_id,
        project_id=project.id,
        synthetic_cost_center_id=synthetic_cost_center_id,
        analytic_cost_center_id=analytic_cost_center_id,
    )

    first_result = await service.apply_cost_center_created_event(event=event)
    second_result = await service.apply_cost_center_created_event(event=event)

    assert first_result.synthetic_cost_center_id == synthetic_cost_center_id
    assert first_result.analytic_cost_center_id == analytic_cost_center_id
    assert second_result.synthetic_cost_center_id == synthetic_cost_center_id
    assert repository.commits == 1
