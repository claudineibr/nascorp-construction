from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.core.config import settings
from app.domain.events.constants import ConstructionAggregateType, ConstructionEventType, ErpEventType, EventProducer
from app.domain.events.contracts import EventEnvelope
from app.infrastructure.events.json_event_serializer import JsonEventSerializer


class ErpConstructionClient:
    EVENT_ENDPOINTS = {
        ConstructionEventType.PROJECT_CREATED: "/v1/internal/construction/events/project-created",
        ConstructionEventType.UNIT_CREATED: "/v1/internal/construction/events/unit-created",
        ConstructionEventType.MEASUREMENT_APPROVED: "/v1/internal/construction/events/measurement-approved",
        ConstructionEventType.UNIT_SOLD: "/v1/internal/construction/events/unit-sold",
        ConstructionEventType.PROCUREMENT_REQUESTED: "/v1/internal/construction/events/procurement-requested",
    }
    RESPONSE_EVENT_TYPES = {
        ConstructionEventType.PROJECT_CREATED: ErpEventType.COST_CENTER_CREATED,
        ConstructionEventType.UNIT_CREATED: ErpEventType.COST_CENTER_CREATED,
        ConstructionEventType.MEASUREMENT_APPROVED: ErpEventType.ACCOUNTS_PAYABLE_CREATED,
        ConstructionEventType.UNIT_SOLD: ErpEventType.CONTRACT_RECEIVABLE_CREATED,
        ConstructionEventType.PROCUREMENT_REQUESTED: ErpEventType.PROCUREMENT_REQUEST_ACCEPTED,
    }
    RESPONSE_AGGREGATES = {
        ConstructionEventType.PROJECT_CREATED: ("construction_project_id", ConstructionAggregateType.PROJECT),
        ConstructionEventType.UNIT_CREATED: ("construction_unit_id", ConstructionAggregateType.UNIT),
        ConstructionEventType.MEASUREMENT_APPROVED: ("construction_measurement_id", ConstructionAggregateType.MEASUREMENT),
        ConstructionEventType.UNIT_SOLD: ("construction_unit_id", ConstructionAggregateType.UNIT),
        ConstructionEventType.PROCUREMENT_REQUESTED: (
            "construction_procurement_request_id",
            ConstructionAggregateType.PROCUREMENT_REQUEST,
        ),
    }

    def __init__(self) -> None:
        self.serializer = JsonEventSerializer()

    async def list_person_summaries(
        self,
        *,
        company_id: UUID,
        user_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction person lookup integration.")

        headers = {
            "X-Service-Key": settings.erp_service_key,
            "X-Company-ID": str(company_id),
        }
        if user_id is not None:
            headers["X-User-ID"] = str(user_id)

        params: dict[str, object] = {
            "page": page,
            "page_size": page_size,
        }
        if search:
            params["search"] = search

        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.get(
                "/v1/internal/construction/person-summaries",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def create_cost_center_hierarchy(self, *, event: EventEnvelope) -> EventEnvelope:
        return await self.deliver_event(event=event)

    async def create_accounts_payable_from_measurement(self, *, event: EventEnvelope) -> EventEnvelope:
        return await self.deliver_event(event=event)

    async def create_contract_and_receivables_from_unit_sale(self, *, event: EventEnvelope) -> EventEnvelope:
        return await self.deliver_event(event=event)

    async def create_procurement_demand_from_request(self, *, event: EventEnvelope) -> EventEnvelope:
        return await self.deliver_event(event=event)

    async def deliver_event(self, *, event: EventEnvelope) -> EventEnvelope:
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction ERP integration.")

        endpoint = self.EVENT_ENDPOINTS.get(event.event_type)
        if endpoint is None:
            raise RuntimeError(f"Unsupported Construction ERP event type: {event.event_type}.")

        headers = self._build_headers(event=event)
        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=self.serializer.to_dict(event=event),
            )
            response.raise_for_status()
            payload = response.json()

        return self._build_response_event(request_event=event, response_payload=payload)

    def _build_headers(self, *, event: EventEnvelope) -> dict[str, str]:
        headers = {
            "X-Service-Key": settings.erp_service_key or "",
            "X-Company-ID": str(event.company_id),
        }
        if event.payload.get("user_id"):
            headers["X-User-ID"] = str(event.payload["user_id"])

        return headers

    def _build_response_event(self, *, request_event: EventEnvelope, response_payload: dict[str, object]) -> EventEnvelope:
        aggregate_id_field_name, aggregate_type = self.RESPONSE_AGGREGATES[request_event.event_type]
        return EventEnvelope(
            event_id=UUID(str(response_payload["event_id"])),
            event_type=str(response_payload.get("event_type") or self.RESPONSE_EVENT_TYPES[request_event.event_type]),
            event_version=int(response_payload["event_version"]),
            company_id=request_event.company_id,
            aggregate_id=UUID(str(response_payload[aggregate_id_field_name])),
            aggregate_type=aggregate_type,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.ERP_API,
            correlation_id=request_event.correlation_id,
            causation_id=request_event.event_id,
            payload=response_payload["payload"],
        )
