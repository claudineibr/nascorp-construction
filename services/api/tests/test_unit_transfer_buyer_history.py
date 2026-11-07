from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.constants import ConstructionUnitStatus
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionUnit, ConstructionUnitSale
from app.infrastructure.database.models.unit_buyer_history import ConstructionUnitBuyerHistory


def transfer(existing=False, sold_at=None):
    company, buyer, actor = uuid4(), uuid4(), uuid4()
    source = ConstructionUnit(id=uuid4(), company_id=company, project_id=uuid4(), code='SOURCE',
                              description='Source', status=ConstructionUnitStatus.SOLD, buyer_person_id=buyer,
                              sold_at=sold_at, sale_price=Decimal('1000'), analytic_cost_center_id=uuid4())
    target = ConstructionUnit(id=uuid4(), company_id=company, project_id=uuid4(), code='TARGET',
                              description='Target', status=ConstructionUnitStatus.AVAILABLE,
                              analytic_cost_center_id=uuid4())
    sale = ConstructionUnitSale(id=uuid4(), company_id=company, unit_id=source.id, status='ACTIVE', source='NATIVE')
    source.current_sale_id = sale.id
    rows = []
    if existing:
        rows.append(ConstructionUnitBuyerHistory(company_id=company, unit_id=source.id, buyer_person_id=buyer,
                                                 buyer_name='Buyer', included_at=sold_at, source_id='native:existing'))

    async def history(company_id, unit_id, open_only=False):
        return [row for row in rows if row.company_id == company_id and row.unit_id == unit_id
                and (not open_only or row.excluded_at is None)]

    async def add(entity):
        if isinstance(entity, ConstructionUnitBuyerHistory):
            rows.append(entity)

    repository = SimpleNamespace(session=SimpleNamespace(info={}), unit_buyer_history=history,
                                 add=add, flush=AsyncMock(), commit=AsyncMock(),
                                 next_unit_sale_sequence=AsyncMock(return_value=1),
                                 transfer_unit_children=AsyncMock(return_value=[]))
    service = ConstructionProjectService(repository, event_repository=SimpleNamespace(add_outbox_event=AsyncMock()))
    service._transfer_units = AsyncMock(return_value=(source, target, sale, False))
    service._preview_transfer_financial = AsyncMock(return_value={'paid_amount': '100.00'})
    service._sync_unit_buyer_description = AsyncMock(side_effect=lambda unit, buyer_id, *args: 'Buyer' if buyer_id else None)
    service._resolve_actor_name = AsyncMock(return_value='Transfer operator')
    request = SimpleNamespace(target_unit_id=target.id, reason='Transfer requested by buyer')
    return service, source, target, rows, actor, request


@pytest.mark.asyncio
@pytest.mark.parametrize('existing', [False, True])
async def test_transfer_closes_source_history_at_sale_date_without_duplicate_or_invented_author(existing):
    sold_at = datetime(2024, 3, 19, 19, 47, 14, tzinfo=UTC)
    service, source, target, rows, actor, request = transfer(existing, sold_at)
    result = await service.transfer_unit(source.company_id, source.id, request, actor)
    origin = [row for row in rows if row.unit_id == source.id]
    destination = [row for row in rows if row.unit_id == target.id]
    assert len(origin) == 1 and len(destination) == 1
    assert origin[0].included_at == sold_at
    assert origin[0].included_by_user_id is None and origin[0].included_by_name is None
    assert origin[0].excluded_at == result['occurred_at'] == destination[0].included_at
    assert origin[0].excluded_by_user_id == actor
    assert destination[0].excluded_at is None
    assert source.buyer_person_id is None and target.buyer_person_id == origin[0].buyer_person_id
    service.repository.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('future', [False, True])
async def test_transfer_does_not_invent_source_period_without_valid_sale_date(future):
    sold_at = datetime.now(UTC) + timedelta(days=1) if future else None
    service, source, target, rows, actor, request = transfer(sold_at=sold_at)
    await service.transfer_unit(source.company_id, source.id, request, actor)
    assert not [row for row in rows if row.unit_id == source.id]
    assert len([row for row in rows if row.unit_id == target.id]) == 1
