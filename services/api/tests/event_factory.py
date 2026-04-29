from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.events.contracts import EventEnvelope


def make_event(*, causation_id: UUID | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type="construction.project.created.v1",
        event_version=1,
        company_id=uuid4(),
        aggregate_id=uuid4(),
        aggregate_type="construction_project",
        occurred_at=datetime(2026, 4, 28, 12, 0, tzinfo=UTC),
        producer="construction-api",
        correlation_id=uuid4(),
        causation_id=causation_id,
        payload={"project_name": "Residencial Jardim Norte"},
    )