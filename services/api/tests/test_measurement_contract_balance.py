from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionDomainError
from app.domain.services.subcontract_service import SubcontractService


@pytest.mark.asyncio
@pytest.mark.parametrize("quantities,allowed", [
    ([], False),
    ([("1", "1", True)], False),
    ([("1", "1", True), ("2", "0", False)], False),
    ([("1", "1", True), ("2", "1.5", True)], True),
    ([("1", "0", True)], True),
    ([("0", "0", True)], False),
])
async def test_new_measurement_requires_active_remaining_quantity(quantities, allowed):
    service = SubcontractService(SimpleNamespace(repository=SimpleNamespace(session=MagicMock(), scope=None)))
    contract = SimpleNamespace(id=uuid4(), company_id=uuid4(), code="C-0002")
    items = [SimpleNamespace(quantity=Decimal(quantity), consumed_quantity=Decimal(consumed), active=active)
        for quantity, consumed, active in quantities]
    service.repository.items = AsyncMock(return_value=items)
    if allowed:
        await service.ensure_measurement_balance(contract)
    else:
        with pytest.raises(ConstructionDomainError, match="não possui saldo disponível para nova medição"):
            await service.ensure_measurement_balance(contract)
    service.repository.items.assert_awaited_once_with(contract.company_id, contract.id)
