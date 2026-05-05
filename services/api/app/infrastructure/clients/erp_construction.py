from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.core.config import settings
from app.domain.events.constants import ConstructionAggregateType, ErpEventType, EventProducer
from app.domain.events.contracts import EventEnvelope


class ErpConstructionClient:
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
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction cost center integration.")

        headers = {
            "X-Service-Key": settings.erp_service_key,
            "X-Company-ID": str(event.company_id),
        }
        if event.payload.get("user_id"):
            headers["X-User-ID"] = str(event.payload["user_id"])

        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.post(
                "/v1/internal/construction/events/project-created",
                headers=headers,
                json=self._build_project_created_payload(event=event),
            )
            response.raise_for_status()
            payload = response.json()

        return EventEnvelope(
            event_id=UUID(payload["event_id"]),
            event_type=payload.get("event_type", ErpEventType.COST_CENTER_CREATED),
            event_version=int(payload["event_version"]),
            company_id=event.company_id,
            aggregate_id=UUID(payload["construction_project_id"]),
            aggregate_type=ConstructionAggregateType.PROJECT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.ERP_API,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload=payload["payload"],
        )

    async def create_accounts_payable_from_measurement(self, *, event: EventEnvelope) -> EventEnvelope:
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction accounts payable integration.")

        headers = {
            "X-Service-Key": settings.erp_service_key,
            "X-Company-ID": str(event.company_id),
        }
        if event.payload.get("user_id"):
            headers["X-User-ID"] = str(event.payload["user_id"])

        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.post(
                "/v1/internal/construction/events/measurement-approved",
                headers=headers,
                json=self._build_project_created_payload(event=event),
            )
            response.raise_for_status()
            payload = response.json()

        return EventEnvelope(
            event_id=UUID(payload["event_id"]),
            event_type=payload.get("event_type", ErpEventType.ACCOUNTS_PAYABLE_CREATED),
            event_version=int(payload["event_version"]),
            company_id=event.company_id,
            aggregate_id=UUID(payload["construction_measurement_id"]),
            aggregate_type=ConstructionAggregateType.MEASUREMENT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.ERP_API,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload=payload["payload"],
        )

    async def create_contract_and_receivables_from_unit_sale(self, *, event: EventEnvelope) -> EventEnvelope:
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction contract integration.")

        headers = {
            "X-Service-Key": settings.erp_service_key,
            "X-Company-ID": str(event.company_id),
        }
        if event.payload.get("user_id"):
            headers["X-User-ID"] = str(event.payload["user_id"])

        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.post(
                "/v1/internal/construction/events/unit-sold",
                headers=headers,
                json=self._build_project_created_payload(event=event),
            )
            response.raise_for_status()
            payload = response.json()

        return EventEnvelope(
            event_id=UUID(payload["event_id"]),
            event_type=payload.get("event_type", ErpEventType.CONTRACT_RECEIVABLE_CREATED),
            event_version=int(payload["event_version"]),
            company_id=event.company_id,
            aggregate_id=UUID(payload["construction_unit_id"]),
            aggregate_type=ConstructionAggregateType.UNIT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.ERP_API,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload=payload["payload"],
        )

    async def create_procurement_demand_from_request(self, *, event: EventEnvelope) -> EventEnvelope:
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction procurement integration.")

        headers = {
            "X-Service-Key": settings.erp_service_key,
            "X-Company-ID": str(event.company_id),
        }
        if event.payload.get("user_id"):
            headers["X-User-ID"] = str(event.payload["user_id"])

        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.post(
                "/v1/internal/construction/events/procurement-requested",
                headers=headers,
                json=self._build_project_created_payload(event=event),
            )
            response.raise_for_status()
            payload = response.json()

        return EventEnvelope(
            event_id=UUID(payload["event_id"]),
            event_type=payload.get("event_type", ErpEventType.PROCUREMENT_REQUEST_ACCEPTED),
            event_version=int(payload["event_version"]),
            company_id=event.company_id,
            aggregate_id=UUID(payload["construction_procurement_request_id"]),
            aggregate_type=ConstructionAggregateType.PROCUREMENT_REQUEST,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.ERP_API,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload=payload["payload"],
        )

    @staticmethod
    def _build_project_created_payload(*, event: EventEnvelope) -> dict[str, object]:
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "company_id": str(event.company_id),
            "aggregate_id": str(event.aggregate_id),
            "aggregate_type": event.aggregate_type,
            "producer": event.producer,
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "occurred_at": event.occurred_at.isoformat(),
            "payload": event.payload,
        }
