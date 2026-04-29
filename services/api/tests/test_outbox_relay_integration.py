from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.events.constants import EventStatus
from app.infrastructure.database.models import DeadLetterEvent, OutboxEvent
from app.infrastructure.events import DatabaseOutboxRelay, InMemoryEventBus
from app.infrastructure.repository.event_repository import EventRepository
from tests.event_factory import make_event
from tests.integration_database import create_reachable_engine_or_skip


class FailingOncePublisher:
    def __init__(self) -> None:
        self.publish_attempts = 0
        self.successful_publisher = InMemoryEventBus()

    async def publish(self, event):
        self.publish_attempts += 1
        if self.publish_attempts == 1:
            raise RuntimeError("broker unavailable")

        return await self.successful_publisher.publish(event)


async def get_outbox_event(session, event_id):
    return (
        await session.execute(
            select(OutboxEvent).where(OutboxEvent.event_id == event_id)
        )
    ).scalar_one()


async def test_database_outbox_relay_commits_and_retries_with_real_repository() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    event = make_event()
    publisher = FailingOncePublisher()

    try:
        async with session_factory() as setup_session:
            setup_repository = EventRepository(session=setup_session)
            await setup_repository.add_outbox_event(event=event)
            await setup_session.commit()

        async with session_factory() as first_relay_session:
            first_relay = DatabaseOutboxRelay(
                repository=EventRepository(session=first_relay_session),
                publisher=publisher,
                max_attempts_before_dlq=3,
            )
            first_relayed_count = await first_relay.relay_pending()

        async with session_factory() as first_assertion_session:
            failed_outbox_event = await get_outbox_event(session=first_assertion_session, event_id=event.event_id)

            assert first_relayed_count == 0
            assert failed_outbox_event.status == EventStatus.FAILED
            assert failed_outbox_event.retry_count == 1

        async with session_factory() as second_relay_session:
            second_relay = DatabaseOutboxRelay(
                repository=EventRepository(session=second_relay_session),
                publisher=publisher,
                max_attempts_before_dlq=3,
            )
            second_relayed_count = await second_relay.relay_pending()

        async with session_factory() as second_assertion_session:
            published_outbox_event = await get_outbox_event(session=second_assertion_session, event_id=event.event_id)

            assert second_relayed_count == 1
            assert published_outbox_event.status == EventStatus.PUBLISHED
            assert published_outbox_event.retry_count == 1
            assert published_outbox_event.published_at is not None
            assert publisher.publish_attempts == 2
    finally:
        async with session_factory() as cleanup_session:
            await cleanup_session.execute(delete(DeadLetterEvent).where(DeadLetterEvent.event_id == event.event_id))
            await cleanup_session.execute(delete(OutboxEvent).where(OutboxEvent.event_id == event.event_id))
            await cleanup_session.commit()

        await engine.dispose()