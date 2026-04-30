from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.events.constants import ConstructionEventType, ErpEventType
from app.domain.events.contracts import EventEnvelope
from app.domain.services import ConstructionCostCenterIntegrationService


class FakeErpClient:
    def __init__(self, *, confirmation_event: EventEnvelope) -> None:
        self.confirmation_event = confirmation_event
        self.received_event = None

    async def create_cost_center_hierarchy(self, *, event: EventEnvelope) -> EventEnvelope:
        self.received_event = event
        return self.confirmation_event


class FakeProjectService:
    def __init__(self) -> None:
        self.applied_event = None

    async def apply_cost_center_created_event(self, *, event: EventEnvelope):
        self.applied_event = event
        return SimpleNamespace(id=event.aggregate_id)


def make_event(*, event_type: str, project_id, company_id) -> EventEnvelope:
    event_id = uuid4()
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        event_version=1,
        company_id=company_id,
        aggregate_id=project_id,
        aggregate_type="construction_project",
        occurred_at=datetime.now(tz=UTC),
        producer="test",
        correlation_id=event_id,
        causation_id=None,
        payload={"construction_project_id": str(project_id)},
    )


@pytest.mark.asyncio
async def test_sync_project_created_event_sends_to_erp_and_applies_confirmation() -> None:
    project_id = uuid4()
    company_id = uuid4()
    project_created_event = make_event(
        event_type=ConstructionEventType.PROJECT_CREATED,
        project_id=project_id,
        company_id=company_id,
    )
    confirmation_event = make_event(
        event_type=ErpEventType.COST_CENTER_CREATED,
        project_id=project_id,
        company_id=company_id,
    )
    project_service = FakeProjectService()
    erp_client = FakeErpClient(confirmation_event=confirmation_event)
    service = ConstructionCostCenterIntegrationService(project_service=project_service, erp_client=erp_client)

    result = await service.sync_project_created_event(event=project_created_event)

    assert result.id == project_id
    assert erp_client.received_event == project_created_event
    assert project_service.applied_event == confirmation_event
