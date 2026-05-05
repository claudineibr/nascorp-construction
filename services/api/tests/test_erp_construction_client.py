from uuid import uuid4

import pytest

from app.domain.events.constants import ErpEventType
from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.infrastructure.clients import erp_construction
from tests.event_factory import make_event


class FakeResponse:
    def __init__(self, *, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class FakeAsyncClient:
    instances = []

    def __init__(self, *, base_url: str, timeout: int) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.posts = []
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def post(self, endpoint: str, *, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        self.posts.append({"endpoint": endpoint, "headers": headers, "json": json})
        return FakeResponse(
            payload={
                "event_id": str(uuid4()),
                "event_type": ErpEventType.COST_CENTER_CREATED,
                "event_version": 1,
                "construction_project_id": str(json["aggregate_id"]),
                "payload": {
                    "construction_project_id": str(json["aggregate_id"]),
                    "synthetic_cost_center_id": str(uuid4()),
                    "analytic_cost_center_id": str(uuid4()),
                },
            }
        )


@pytest.mark.asyncio
async def test_erp_construction_client_delivers_serialized_event_envelope(monkeypatch) -> None:
    monkeypatch.setattr(erp_construction.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(erp_construction.settings, "erp_api_url", "http://erp.local")
    monkeypatch.setattr(erp_construction.settings, "erp_service_key", "service-key")
    FakeAsyncClient.instances = []
    event = make_event()

    response_event = await ErpConstructionClient().deliver_event(event=event)

    sent_request = FakeAsyncClient.instances[0].posts[0]
    assert sent_request["endpoint"] == "/v1/internal/construction/events/project-created"
    assert sent_request["headers"]["X-Service-Key"] == "service-key"
    assert sent_request["headers"]["X-Company-ID"] == str(event.company_id)
    assert sent_request["json"]["event_id"] == str(event.event_id)
    assert sent_request["json"]["occurred_at"] == "2026-04-28T12:00:00Z"
    assert sent_request["json"]["payload"] == event.payload
    assert response_event.event_type == ErpEventType.COST_CENTER_CREATED
    assert response_event.causation_id == event.event_id