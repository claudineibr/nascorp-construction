from app.domain.events.contracts import EventEnvelope, EventPublisher


class DatabaseOutboxRelay:
    def __init__(self, *, repository, publisher: EventPublisher, max_attempts_before_dlq: int = 3) -> None:
        self.repository = repository
        self.publisher = publisher
        self.max_attempts_before_dlq = max_attempts_before_dlq

    async def relay_pending(self, *, limit: int = 100) -> int:
        relayed_count = 0
        outbox_events = await self.repository.list_pending_outbox_events(
            limit=limit,
            max_attempts_before_dlq=self.max_attempts_before_dlq,
        )
        for outbox_event in outbox_events:
            envelope = self._to_envelope(outbox_event)
            try:
                await self.publisher.publish(envelope)
            except Exception as exc:
                if outbox_event.retry_count + 1 >= self.max_attempts_before_dlq:
                    await self.repository.move_to_dead_letter(outbox_event, str(exc))
                else:
                    await self.repository.mark_failed(outbox_event, str(exc))

                await self.repository.commit()
                continue

            await self.repository.mark_published(outbox_event)
            await self.repository.commit()
            relayed_count += 1

        return relayed_count

    def _to_envelope(self, outbox_event) -> EventEnvelope:
        return EventEnvelope(
            event_id=outbox_event.event_id,
            event_type=outbox_event.event_type,
            event_version=outbox_event.event_version,
            company_id=outbox_event.company_id,
            aggregate_id=outbox_event.aggregate_id,
            aggregate_type=outbox_event.aggregate_type,
            occurred_at=outbox_event.occurred_at,
            producer=outbox_event.producer,
            correlation_id=outbox_event.correlation_id,
            causation_id=outbox_event.causation_id,
            payload=outbox_event.payload,
        )