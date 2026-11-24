from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.domain.exceptions import ConstructionDomainError
from app.domain.services import ConstructionProjectService
from app.schemas.construction import ConstructionUnitAdjustmentCreate, ConstructionUnitInstallmentCreateRequest
from tests.test_construction_project_service import FakeConstructionRepository
from tests.test_unit_commissions import RecordingAdjustmentErpClient, seed_project_and_unit


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["installment", "adjustment"])
async def test_delivered_unit_accepts_additional_charges_without_contract_or_balance(kind):
    company_id = uuid4()
    repository = FakeConstructionRepository()
    client = RecordingAdjustmentErpClient()
    client.create_unit_installments = AsyncMock(return_value=[])
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    unit.status = "delivered"
    unit.current_sale_id = uuid4()
    unit.buyer_person_id = uuid4()
    unit.external_receivable_id = uuid4()
    service = ConstructionProjectService(repository=repository, erp_client=client)
    service._has_balance_to_charge = AsyncMock(return_value=False)
    if kind == "installment":
        await service.create_unit_installments(
            company_id=company_id, unit_id=unit.id,
            request=ConstructionUnitInstallmentCreateRequest(
                starting_number=31, count=1, first_due_date=date(2026, 11, 20), amount=Decimal("2000"),
            ),
        )
        assert client.create_unit_installments.await_args.kwargs["amount"] == Decimal("2000")
    else:
        await service.create_unit_adjustment(
            company_id=company_id, unit_id=unit.id,
            request=ConstructionUnitAdjustmentCreate(
                amount=Decimal("2000"), installments=1, first_due_date=date(2026, 11, 20),
            ),
        )
        assert client.adjustments[0]["construction_sale_id"] == unit.current_sale_id
    service._has_balance_to_charge.assert_not_awaited()


@pytest.mark.asyncio
async def test_delivered_installment_timeout_keeps_the_result_unknown():
    company_id = uuid4()
    repository = FakeConstructionRepository()
    client = RecordingAdjustmentErpClient()
    client.create_unit_installments = AsyncMock(side_effect=httpx.ReadTimeout("ERP response delayed"))
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    unit.status = "delivered"
    unit.external_receivable_id = uuid4()
    service = ConstructionProjectService(repository=repository, erp_client=client)
    request = ConstructionUnitInstallmentCreateRequest(
        starting_number=37,
        count=2,
        first_due_date=date(2026, 12, 10),
        amount=Decimal("15237.72"),
    )

    with pytest.raises(ConstructionDomainError) as error:
        await service.create_unit_installments(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.status_code == 504
    assert error.value.error_code == "CONSTRUCTION_UNIT_INSTALLMENT_RESULT_UNKNOWN"
    client.create_unit_installments.assert_awaited_once()
