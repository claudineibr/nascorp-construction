from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionInvalidValueError
from app.domain.services.unit_transfer_service import UnitTransferService


def confirmation():
    source, target, sale_id, company = uuid4(), uuid4(), uuid4(), uuid4()
    sale = SimpleNamespace(id=sale_id, unit_id=source, status='TRANSFERRED', transferred_to_unit_id=target,
                           paid_amount=Decimal('100'))
    request = SimpleNamespace(company_id=company, aggregate_id=source, event_id=uuid4(), payload={
        'source_sale_id': str(sale_id), 'target_unit_id': str(target),
    })
    response = SimpleNamespace(payload={'source_unit_id': str(source), 'paid_amount': '150.00'})
    service = SimpleNamespace(repository=SimpleNamespace(get_unit_sale=AsyncMock(return_value=sale)))
    return service, request, response, sale


@pytest.mark.asyncio
async def test_confirmation_preserves_payment_received_after_preview_on_replay():
    service, request, response, sale = confirmation()
    for _ in range(2):
        await UnitTransferService._confirm_unit_transfer_financial(service, request, response)
    assert sale.paid_amount == Decimal('150.00')
    service.repository.get_unit_sale.assert_awaited_with(
        company_id=request.company_id, sale_id=sale.id, lock=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-1', 'invalid'])
async def test_invalid_confirmation_does_not_replace_sale_snapshot(amount):
    service, request, response, sale = confirmation()
    response.payload['paid_amount'] = amount
    with pytest.raises(ConstructionInvalidValueError):
        await UnitTransferService._confirm_unit_transfer_financial(service, request, response)
    assert sale.paid_amount == Decimal('100')


@pytest.mark.asyncio
async def test_confirmation_refuses_another_sale_or_destination():
    service, request, response, sale = confirmation()
    sale.transferred_to_unit_id = uuid4()
    with pytest.raises(ConstructionInvalidValueError):
        await UnitTransferService._confirm_unit_transfer_financial(service, request, response)
    assert sale.paid_amount == Decimal('100')
