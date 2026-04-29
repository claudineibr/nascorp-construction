from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repository.event_repository import EventRepository
from tests.event_factory import make_event


class FakeScalarResult:
    def all(self):
        return []


class FakeResult:
    def scalars(self):
        return FakeScalarResult()


class CapturingSession:
    def __init__(self) -> None:
        self.statement: Any | None = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult()


class FakeNestedTransaction:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        self.session.nested_transaction_started = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool:
        self.session.nested_transaction_exit_type = exc_type
        return False


class DuplicateProcessedSession:
    def __init__(self) -> None:
        self.added_items = []
        self.rollback_called = False
        self.nested_transaction_started = False
        self.nested_transaction_exit_type = None

    def begin_nested(self):
        return FakeNestedTransaction(session=self)

    def add(self, item) -> None:
        self.added_items.append(item)

    async def flush(self) -> None:
        raise IntegrityError("insert processed event", {}, Exception("duplicate"))

    async def rollback(self) -> None:
        self.rollback_called = True


async def test_list_pending_outbox_events_includes_retriable_failed_events() -> None:
    session = CapturingSession()
    repository = EventRepository(session=cast(AsyncSession, session))

    await repository.list_pending_outbox_events(limit=10, max_attempts_before_dlq=3)

    assert session.statement is not None
    compiled_statement = str(
        session.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "outbox_events.status = 'pending'" in compiled_statement
    assert "outbox_events.status = 'failed'" in compiled_statement
    assert "outbox_events.retry_count < 3" in compiled_statement


async def test_mark_processed_duplicate_uses_savepoint_without_rolling_back_caller_transaction() -> None:
    session = DuplicateProcessedSession()
    repository = EventRepository(session=cast(AsyncSession, session))

    result = await repository.mark_processed(consumer_name="erp-api", event=make_event())

    assert result is False
    assert session.nested_transaction_started is True
    assert session.nested_transaction_exit_type is IntegrityError
    assert session.rollback_called is False
    assert len(session.added_items) == 1