from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import httpx

from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.clients import erp_construction
from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.schemas.construction.project import ConstructionUnitUpdate


@pytest.mark.asyncio
@pytest.mark.parametrize("previous,status", [("sold", "delivered"), ("delivered", "sold")])
async def test_status_transition_persists_event_before_unit_commit(previous, status, monkeypatch):
    unit = SimpleNamespace(
        id=uuid4(), company_id=uuid4(), project_id=uuid4(), status=previous, description="", analytic_cost_center_id=None
    )
    repository, events = AsyncMock(), AsyncMock()
    repository.get_unit.return_value = unit
    repository.lock_unit.return_value = unit
    calls = []
    events.add_outbox_event.side_effect = lambda **kwargs: calls.append(("event", kwargs["event"]))
    repository.commit.side_effect = lambda: calls.append(("commit", None))
    service = ConstructionProjectService(repository=repository, event_repository=events)
    user = uuid4()
    await service.update_unit(
        company_id=unit.company_id, unit_id=unit.id, request=ConstructionUnitUpdate(status=status), actor_user_id=user
    )
    assert [call[0] for call in calls] == ["event", "commit"]
    event = calls[0][1]
    assert event.event_type == "construction.unit.status_changed.v1"
    assert event.payload["status"] == status
    assert event.payload["previous_status"] == previous
    assert event.payload["user_id"] == str(user)

    async def respond(request):
        assert request.url.path == "/v1/internal/construction/events/unit-status-changed"
        assert request.headers["X-User-ID"] == str(user)
        return httpx.Response(
            200,
            json={
                "event_id": str(event.event_id),
                "event_type": "erp.unit.reclassified.v1",
                "event_version": 1,
                "construction_unit_id": str(unit.id),
                "payload": {"entries": 1},
            },
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(erp_construction.settings, "erp_service_key", "test-service-key")
    monkeypatch.setattr(erp_construction.settings, "erp_api_url", "http://erp.local")
    monkeypatch.setattr(
        erp_construction.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(**kwargs, transport=httpx.MockTransport(respond)),
    )
    response = await ErpConstructionClient().deliver_event(event=event)
    await service.apply_integration_response(request_event=event, response_event=response)
    assert response.causation_id == event.event_id
