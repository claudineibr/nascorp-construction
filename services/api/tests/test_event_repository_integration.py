from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.events.constants import EventStatus
from app.infrastructure.database.models import DeadLetterEvent, OutboxEvent, ProcessedEvent
from app.infrastructure.repository.event_repository import EventRepository
from tests.event_factory import make_event
from tests.integration_database import create_reachable_engine_or_skip


async def delete_event_rows(session, event_id) -> None:
    await session.execute(delete(DeadLetterEvent).where(DeadLetterEvent.event_id == event_id))
    await session.execute(delete(ProcessedEvent).where(ProcessedEvent.event_id == event_id))
    await session.execute(delete(OutboxEvent).where(OutboxEvent.event_id == event_id))


async def test_event_repository_persists_and_reads_real_outbox_mapping() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    event = make_event()

    try:
        async with session_factory() as session:
            repository = EventRepository(session=session)

            outbox_event = await repository.add_outbox_event(event=event)
            await session.flush()
            pending_events = await repository.list_pending_outbox_events(limit=10)

            assert outbox_event in pending_events
            assert outbox_event.event_id == event.event_id
            assert outbox_event.company_id == event.company_id
            assert outbox_event.payload == event.payload
            assert outbox_event.status == EventStatus.PENDING
            assert outbox_event.occurred_at == event.occurred_at

            await session.rollback()
    finally:
        await engine.dispose()


async def test_event_repository_updates_real_outbox_processed_and_dead_letter_rows() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    event = make_event()

    try:
        async with session_factory() as session:
            repository = EventRepository(session=session)

            outbox_event = await repository.add_outbox_event(event=event)
            await session.flush()

            await repository.mark_failed(outbox_event=outbox_event, error="broker unavailable")
            await session.flush()
            retriable_events = await repository.list_pending_outbox_events(limit=10, max_attempts_before_dlq=3)

            assert outbox_event in retriable_events
            assert outbox_event.status == EventStatus.FAILED
            assert outbox_event.retry_count == 1
            assert outbox_event.last_error == "broker unavailable"

            await repository.mark_published(outbox_event=outbox_event)
            await session.flush()
            pending_events = await repository.list_pending_outbox_events(limit=10, max_attempts_before_dlq=3)

            assert outbox_event not in pending_events
            assert outbox_event.status == EventStatus.PUBLISHED
            assert outbox_event.published_at is not None
            assert outbox_event.last_error is None

            first_processed_result = await repository.mark_processed(consumer_name="construction-worker", event=event)
            second_processed_result = await repository.mark_processed(consumer_name="construction-worker", event=event)
            processed_count = len(
                (
                    await session.execute(
                        select(ProcessedEvent).where(ProcessedEvent.event_id == event.event_id)
                    )
                )
                .scalars()
                .all()
            )

            assert first_processed_result is True
            assert second_processed_result is False
            assert processed_count == 1

            dead_letter_event = await repository.move_to_dead_letter(outbox_event=outbox_event, error="final failure")
            await session.flush()

            assert outbox_event.status == EventStatus.DEAD_LETTER
            assert dead_letter_event.payload == event.payload
            assert dead_letter_event.failure_reason == "final failure"

            await session.rollback()
    finally:
        async with session_factory() as cleanup_session:
            await delete_event_rows(session=cleanup_session, event_id=event.event_id)
            await cleanup_session.commit()

        await engine.dispose()