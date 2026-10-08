from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.events.constants import ConstructionEventType, ConstructionIntegrationMode
from app.domain.events.contracts import EventEnvelope


@dataclass(frozen=True)
class ConstructionIntegrationDispatchResult:
    event: EventEnvelope
    response_event: EventEnvelope | None
    integration_mode: str

    @property
    def delivered_synchronously(self) -> bool:
        return self.response_event is not None


class ConstructionEventRepository(Protocol):
    async def add_outbox_event(self, *, event: EventEnvelope):
        raise NotImplementedError


class ConstructionEventTransport(Protocol):
    async def deliver_event(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError


class ConstructionIntegrationDispatcher:
    def __init__(
        self,
        *,
        event_repository: ConstructionEventRepository | None,
        event_transport: ConstructionEventTransport | None,
        integration_mode: str,
    ) -> None:
        self.event_repository = event_repository
        self.event_transport = event_transport
        self.integration_mode = integration_mode

    async def dispatch(self, *, event: EventEnvelope) -> ConstructionIntegrationDispatchResult:
        deferred = event.event_type == ConstructionEventType.PROCUREMENT_REQUESTED or (
            event.event_type == ConstructionEventType.MEASUREMENT_APPROVED and event.payload.get("subcontract_id"))
        if deferred and self.event_repository is None:
            raise ValueError("O envio de compras exige um outbox persistente.")
        if self.event_repository is not None:
            await self.event_repository.add_outbox_event(event=event)

        response_event = None
        if not deferred and self.integration_mode == ConstructionIntegrationMode.SYNC_HTTP and self.event_transport is not None:
            response_event = await self.event_transport.deliver_event(event=event)

        return ConstructionIntegrationDispatchResult(
            event=event,
            response_event=response_event,
            integration_mode=self.integration_mode,
        )
