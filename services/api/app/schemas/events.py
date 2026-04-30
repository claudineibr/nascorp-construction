from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.domain.events.contracts import EventEnvelope


class EventEnvelopeRequest(BaseModel):
    event_id: UUID
    event_type: str
    event_version: int
    company_id: UUID
    aggregate_id: UUID
    aggregate_type: str
    occurred_at: datetime
    producer: str
    correlation_id: UUID
    causation_id: UUID | None = None
    payload: dict[str, Any]

    def to_event_envelope(self) -> EventEnvelope:
        return EventEnvelope(
            event_id=self.event_id,
            event_type=self.event_type,
            event_version=self.event_version,
            company_id=self.company_id,
            aggregate_id=self.aggregate_id,
            aggregate_type=self.aggregate_type,
            occurred_at=self.occurred_at,
            producer=self.producer,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            payload=self.payload,
        )
