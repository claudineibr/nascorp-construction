from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.events.contracts import EventEnvelope


class JsonEventSerializer:
    def serialize(self, event: EventEnvelope) -> str:
        return json.dumps(self._to_dict(event), separators=(",", ":"), sort_keys=True)

    def deserialize(self, value: str) -> EventEnvelope:
        data = json.loads(value)
        return EventEnvelope(
            event_id=UUID(data["event_id"]),
            event_type=data["event_type"],
            event_version=data["event_version"],
            company_id=UUID(data["company_id"]),
            aggregate_id=UUID(data["aggregate_id"]),
            aggregate_type=data["aggregate_type"],
            occurred_at=datetime.fromisoformat(data["occurred_at"].replace("Z", "+00:00")),
            producer=data["producer"],
            correlation_id=UUID(data["correlation_id"]),
            causation_id=UUID(data["causation_id"]) if data.get("causation_id") else None,
            payload=data["payload"],
        )

    def _to_dict(self, event: EventEnvelope) -> dict[str, Any]:
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "company_id": str(event.company_id),
            "aggregate_id": str(event.aggregate_id),
            "aggregate_type": event.aggregate_type,
            "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
            "producer": event.producer,
            "correlation_id": str(event.correlation_id),
            "causation_id": str(event.causation_id) if event.causation_id else None,
            "payload": event.payload,
        }