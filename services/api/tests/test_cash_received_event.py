from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionNotFoundError
from app.domain.services import ConstructionProjectService


async def test_replayed_cash_event_is_acknowledged_without_financial_side_effect():
    unit_id, company_id = uuid4(), uuid4()
    repository, events = AsyncMock(), AsyncMock()
    repository.get_unit.return_value = SimpleNamespace(id=unit_id)
    events.mark_processed.return_value = False
    service = ConstructionProjectService(repository=repository, event_repository=events)
    event = SimpleNamespace(
        event_type="construction.unit.installment.cash_received.v1",
        event_version=1,
        company_id=company_id,
        aggregate_id=unit_id,
        payload={"unit_id": str(unit_id)},
    )
    result = await service.apply_cash_received_event(event=event)
    assert result == {"accepted": True, "duplicate": True, "unit_id": str(unit_id)}
    repository.get_unit.assert_awaited_once_with(company_id=company_id, unit_id=unit_id)
    events.add_outbox_event.assert_not_awaited()


async def test_cash_event_of_another_company_does_not_mark_processed():
    unit_id = uuid4()
    repository, events = AsyncMock(), AsyncMock()
    repository.get_unit.return_value = None
    service = ConstructionProjectService(repository=repository, event_repository=events)
    event = SimpleNamespace(
        event_type="construction.unit.installment.cash_received.v1",
        event_version=1,
        company_id=uuid4(),
        aggregate_id=unit_id,
        payload={"unit_id": str(unit_id)},
    )
    with pytest.raises(ConstructionNotFoundError):
        await service.apply_cash_received_event(event=event)
    events.mark_processed.assert_not_awaited()
