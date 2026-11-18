from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.services import ConstructionProjectService
from app.schemas.construction import ConstructionUnitSaleConfirmRequest
from tests.test_construction_project_service import FakeConstructionRepository, FakeErpMeasurementClient
from tests.test_unit_commissions import seed_project_and_unit


@pytest.mark.asyncio
async def test_adriano_sold_unit_saves_financing_above_price_without_new_installments():
    company = uuid4()
    repository = FakeConstructionRepository()
    _, unit = seed_project_and_unit(repository, company_id=company, sale_price=Decimal("174900"))
    unit.status = "sold"
    unit.buyer_person_id = uuid4()
    unit.current_sale_id = uuid4()
    unit.external_receivable_id = uuid4()
    service = ConstructionProjectService(repository=repository, erp_client=FakeErpMeasurementClient())
    sale = SimpleNamespace(id=unit.current_sale_id, sequence=1)
    service._ensure_current_sale = AsyncMock(return_value=sale)
    service._dispatch_integration_event = AsyncMock(return_value=None)
    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=unit.buyer_person_id, sale_price=Decimal("174900"),
        first_due_date=date(2026, 11, 17), installments=1,
        payment_sources=[{"source_type": "financing", "amount": "180000",
                          "due_date": "2026-11-17", "installments": 1}],
    )
    result = await service.confirm_unit_sale(company_id=company, unit_id=unit.id, request=request)
    assert result.sale_price == Decimal("174900")
    event = service._dispatch_integration_event.await_args.kwargs["event"]
    assert event.payload["update_existing_sale"] is True
    assert event.payload["receivable_amount"] == "0.00"
    assert event.payload["payment_sources"][0]["amount"] == "180000.00"
    assert event.payload["payment_sources"][0]["generates_installments"] is False
    assert sale.payment_sources == event.payload["payment_sources"]
