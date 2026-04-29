from app.domain.events.contracts import EventEnvelope, EventPublishResult


class InMemoryEventBus:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> EventPublishResult:
        self.events.append(event)
        return EventPublishResult(event_id=event.event_id, broker_message_id=str(event.event_id))

    async def receive(self, *, event_type: str | None = None, limit: int = 10) -> list[EventEnvelope]:
        events = self.events
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]

        return events[:limit]


class InMemoryProcessedEventStore:
    def __init__(self) -> None:
        self.processed_keys: set[tuple[str, str]] = set()

    async def mark_processed(self, *, consumer_name: str, event: EventEnvelope) -> bool:
        key = (consumer_name, str(event.event_id))
        if key in self.processed_keys:
            return False

        self.processed_keys.add(key)
        return True