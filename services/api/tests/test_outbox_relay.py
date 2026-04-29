from dataclasses import dataclass

from app.infrastructure.events import DatabaseOutboxRelay, InMemoryEventBus
from tests.event_factory import make_event


@dataclass
class FakeOutboxEvent:
    event_id: object
    event_type: str
    event_version: int
    company_id: object
    aggregate_id: object
    aggregate_type: str
    occurred_at: object
    producer: str
    correlation_id: object
    causation_id: object
    payload: dict
    retry_count: int = 0
    status: str = "pending"


class FakeEventRepository:
    def __init__(self, outbox_event: FakeOutboxEvent) -> None:
        self.outbox_event = outbox_event
        self.dead_lettered = False
        self.commit_count = 0
        self.committed_statuses = []

    async def list_pending_outbox_events(self, *, limit: int = 100, max_attempts_before_dlq: int = 3):
        if self.outbox_event.status == "pending":
            return [self.outbox_event]

        if self.outbox_event.status == "failed" and self.outbox_event.retry_count < max_attempts_before_dlq:
            return [self.outbox_event]

        return []

    async def mark_published(self, outbox_event: FakeOutboxEvent) -> None:
        outbox_event.status = "published"

    async def mark_failed(self, outbox_event: FakeOutboxEvent, error: str) -> None:
        outbox_event.status = "failed"
        outbox_event.retry_count += 1

    async def move_to_dead_letter(self, outbox_event: FakeOutboxEvent, error: str) -> None:
        outbox_event.status = "dead_letter"
        self.dead_lettered = True

    async def commit(self) -> None:
        self.commit_count += 1
        self.committed_statuses.append(self.outbox_event.status)


class FailingEventPublisher:
    def __init__(self, *, failures_before_success: int = 1) -> None:
        self.failures_before_success = failures_before_success
        self.publish_attempts = 0
        self.successful_publisher = InMemoryEventBus()

    async def publish(self, event):
        self.publish_attempts += 1
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("broker unavailable")

        return await self.successful_publisher.publish(event)


def make_outbox_event(retry_count: int = 0) -> FakeOutboxEvent:
    event = make_event()
    return FakeOutboxEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        event_version=event.event_version,
        company_id=event.company_id,
        aggregate_id=event.aggregate_id,
        aggregate_type=event.aggregate_type,
        occurred_at=event.occurred_at,
        producer=event.producer,
        correlation_id=event.correlation_id,
        causation_id=event.causation_id,
        payload=event.payload,
        retry_count=retry_count,
    )


async def test_outbox_relay_marks_event_published_after_broker_ack() -> None:
    outbox_event = make_outbox_event()
    repository = FakeEventRepository(outbox_event)
    relay = DatabaseOutboxRelay(repository=repository, publisher=InMemoryEventBus())

    relayed_count = await relay.relay_pending()

    assert relayed_count == 1
    assert outbox_event.status == "published"
    assert repository.commit_count == 1
    assert repository.committed_statuses == ["published"]


async def test_outbox_relay_keeps_event_recoverable_when_broker_fails() -> None:
    outbox_event = make_outbox_event()
    repository = FakeEventRepository(outbox_event)
    publisher = FailingEventPublisher()
    relay = DatabaseOutboxRelay(repository=repository, publisher=publisher)

    relayed_count = await relay.relay_pending()

    assert relayed_count == 0
    assert outbox_event.status == "failed"
    assert outbox_event.retry_count == 1
    assert repository.commit_count == 1
    assert repository.committed_statuses == ["failed"]


async def test_outbox_relay_retries_failed_event_before_dead_letter_limit() -> None:
    outbox_event = make_outbox_event()
    repository = FakeEventRepository(outbox_event)
    publisher = FailingEventPublisher()
    relay = DatabaseOutboxRelay(repository=repository, publisher=publisher, max_attempts_before_dlq=3)

    first_relayed_count = await relay.relay_pending()
    second_relayed_count = await relay.relay_pending()

    assert first_relayed_count == 0
    assert second_relayed_count == 1
    assert outbox_event.status == "published"
    assert outbox_event.retry_count == 1
    assert publisher.publish_attempts == 2
    assert repository.commit_count == 2
    assert repository.committed_statuses == ["failed", "published"]


async def test_outbox_relay_moves_event_to_dead_letter_after_final_allowed_attempt_fails() -> None:
    outbox_event = make_outbox_event(retry_count=2)
    repository = FakeEventRepository(outbox_event)
    publisher = FailingEventPublisher()
    relay = DatabaseOutboxRelay(repository=repository, publisher=publisher, max_attempts_before_dlq=3)

    relayed_count = await relay.relay_pending()

    assert relayed_count == 0
    assert outbox_event.status == "dead_letter"
    assert repository.dead_lettered is True
    assert publisher.publish_attempts == 1
    assert repository.commit_count == 1
    assert repository.committed_statuses == ["dead_letter"]