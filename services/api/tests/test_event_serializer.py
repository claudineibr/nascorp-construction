from uuid import uuid4

from app.infrastructure.events import JsonEventSerializer
from tests.event_factory import make_event


def test_json_event_serializer_round_trips_envelope() -> None:
    serializer = JsonEventSerializer()
    event = make_event()

    serialized_event = serializer.serialize(event)
    deserialized_event = serializer.deserialize(serialized_event)

    assert deserialized_event == event


def test_json_event_serializer_round_trips_populated_causation_id() -> None:
    serializer = JsonEventSerializer()
    event = make_event(causation_id=uuid4())

    serialized_event = serializer.serialize(event)
    deserialized_event = serializer.deserialize(serialized_event)

    assert deserialized_event == event