from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.events.constants import EventStatus
from app.domain.events.contracts import EventEnvelope
from app.infrastructure.database.models import DeadLetterEvent, OutboxEvent, ProcessedEvent


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_outbox_event(self, event: EventEnvelope) -> OutboxEvent:
        outbox_event = OutboxEvent(
            id=uuid4(),
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_id=event.aggregate_id,
            aggregate_type=event.aggregate_type,
            company_id=event.company_id,
            producer=event.producer,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            payload=event.payload,
            status=EventStatus.PENDING,
            retry_count=0,
            occurred_at=event.occurred_at,
        )
        self.session.add(outbox_event)
        return outbox_event

    async def list_pending_outbox_events(
        self,
        *,
        limit: int = 100,
        max_attempts_before_dlq: int = 3,
    ) -> list[OutboxEvent]:
        result = await self.session.execute(
            select(OutboxEvent)
            .where(
                or_(
                    OutboxEvent.status == EventStatus.PENDING,
                    and_(
                        OutboxEvent.status == EventStatus.FAILED,
                        OutboxEvent.retry_count < max_attempts_before_dlq,
                    ),
                )
            )
            .order_by(OutboxEvent.occurred_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_published(self, outbox_event: OutboxEvent) -> None:
        outbox_event.status = EventStatus.PUBLISHED
        outbox_event.published_at = datetime.now(UTC)
        outbox_event.last_error = None

    async def mark_failed(self, outbox_event: OutboxEvent, error: str) -> None:
        outbox_event.status = EventStatus.FAILED
        outbox_event.retry_count += 1
        outbox_event.last_error = error

    async def move_to_dead_letter(self, outbox_event: OutboxEvent, error: str) -> DeadLetterEvent:
        dead_letter_event = DeadLetterEvent(
            id=uuid4(),
            event_id=outbox_event.event_id,
            event_type=outbox_event.event_type,
            event_version=outbox_event.event_version,
            aggregate_id=outbox_event.aggregate_id,
            aggregate_type=outbox_event.aggregate_type,
            company_id=outbox_event.company_id,
            producer=outbox_event.producer,
            correlation_id=outbox_event.correlation_id,
            causation_id=outbox_event.causation_id,
            payload=outbox_event.payload,
            failure_reason=error,
            retry_count=outbox_event.retry_count,
            occurred_at=outbox_event.occurred_at,
        )
        outbox_event.status = EventStatus.DEAD_LETTER
        outbox_event.last_error = error
        self.session.add(dead_letter_event)
        return dead_letter_event

    async def commit(self) -> None:
        await self.session.commit()

    async def mark_processed(self, *, consumer_name: str, event: EventEnvelope) -> bool:
        processed_event = ProcessedEvent(
            id=uuid4(),
            consumer_name=consumer_name,
            event_id=event.event_id,
            event_type=event.event_type,
            company_id=event.company_id,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(processed_event)
                await self.session.flush()
        except IntegrityError:
            return False

        return True