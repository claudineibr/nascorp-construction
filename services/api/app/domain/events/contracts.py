from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class EventEnvelope:
    event_id: UUID
    event_type: str
    event_version: int
    company_id: UUID
    aggregate_id: UUID
    aggregate_type: str
    occurred_at: datetime
    producer: str
    correlation_id: UUID
    causation_id: UUID | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class EventPublishResult:
    event_id: UUID
    broker_message_id: str | None = None


class EventPublisher(Protocol):
    async def publish(self, event: EventEnvelope) -> EventPublishResult:
        raise NotImplementedError


class EventConsumer(Protocol):
    async def receive(self, *, event_type: str | None = None, limit: int = 10) -> list[EventEnvelope]:
        raise NotImplementedError


class EventSerializer(Protocol):
    def serialize(self, event: EventEnvelope) -> str:
        raise NotImplementedError

    def deserialize(self, value: str) -> EventEnvelope:
        raise NotImplementedError


class OutboxRelay(Protocol):
    async def relay_pending(self, *, limit: int = 100) -> int:
        raise NotImplementedError


class ProcessedEventStore(Protocol):
    async def mark_processed(self, *, consumer_name: str, event: EventEnvelope) -> bool:
        raise NotImplementedError