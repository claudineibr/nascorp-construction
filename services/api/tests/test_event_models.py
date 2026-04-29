from app.infrastructure.database.models import DeadLetterEvent, OutboxEvent, ProcessedEvent


def test_outbox_occurred_at_has_no_server_default() -> None:
    assert OutboxEvent.__table__.c.occurred_at.nullable is False
    assert OutboxEvent.__table__.c.occurred_at.server_default is None


def test_technical_timestamps_keep_server_defaults() -> None:
    assert ProcessedEvent.__table__.c.processed_at.server_default is not None
    assert DeadLetterEvent.__table__.c.dead_lettered_at.server_default is not None