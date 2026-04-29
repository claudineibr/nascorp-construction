import threading

from app.infrastructure.events import InMemoryEventBus, InMemoryProcessedEventStore, JsonEventSerializer, SqsEventBus
from tests.event_factory import make_event


class FakeSqsClient:
    def __init__(self) -> None:
        self.messages = []
        self.send_message_thread_id = None

    def send_message(self, **message):
        self.send_message_thread_id = threading.get_ident()
        self.messages.append(message)
        return {"MessageId": "message-1"}


async def test_in_memory_event_bus_publish_and_receive() -> None:
    bus = InMemoryEventBus()
    event = make_event()

    result = await bus.publish(event)
    received_events = await bus.receive(event_type=event.event_type)

    assert result.event_id == event.event_id
    assert received_events == [event]


async def test_processed_event_store_rejects_duplicate_consumer_event() -> None:
    store = InMemoryProcessedEventStore()
    event = make_event()

    first_result = await store.mark_processed(consumer_name="erp-api", event=event)
    second_result = await store.mark_processed(consumer_name="erp-api", event=event)

    assert first_result is True
    assert second_result is False


async def test_sqs_event_bus_publishes_envelope_with_message_attributes() -> None:
    client = FakeSqsClient()
    serializer = JsonEventSerializer()
    bus = SqsEventBus(client=client, queue_url="https://sqs.local/queue", serializer=serializer)
    event = make_event()
    event_loop_thread_id = threading.get_ident()

    result = await bus.publish(event)

    assert result.broker_message_id == "message-1"
    assert client.send_message_thread_id != event_loop_thread_id
    assert client.messages[0]["QueueUrl"] == "https://sqs.local/queue"
    assert client.messages[0]["MessageAttributes"]["event_type"]["StringValue"] == event.event_type
    assert serializer.deserialize(client.messages[0]["MessageBody"]) == event