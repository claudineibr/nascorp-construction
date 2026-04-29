import asyncio
from typing import Any

from app.domain.events.contracts import EventEnvelope, EventPublishResult, EventSerializer


class SqsEventBus:
    def __init__(self, *, client: Any, queue_url: str, serializer: EventSerializer) -> None:
        self.client = client
        self.queue_url = queue_url
        self.serializer = serializer

    async def publish(self, event: EventEnvelope) -> EventPublishResult:
        response = await asyncio.to_thread(
            self.client.send_message,
            QueueUrl=self.queue_url,
            MessageBody=self.serializer.serialize(event),
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": event.event_type},
                "event_version": {"DataType": "Number", "StringValue": str(event.event_version)},
                "company_id": {"DataType": "String", "StringValue": str(event.company_id)},
                "correlation_id": {"DataType": "String", "StringValue": str(event.correlation_id)},
            },
        )
        return EventPublishResult(event_id=event.event_id, broker_message_id=response.get("MessageId"))