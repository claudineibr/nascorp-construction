from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionInvalidValueError, ConstructionResourceInUseError
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionUnit, ConstructionUnitPaymentSource, ConstructionUnitSale
from app.infrastructure.database.models.unit_sale_value_audit import ConstructionUnitSaleValueAudit
from app.schemas.construction.project import ConstructionDeliveredSaleUpdateRequest


def scenario():
    company, unit_id, sale_id = uuid4(), uuid4(), uuid4()
    unit = ConstructionUnit(id=unit_id, company_id=company, project_id=uuid4(), code="QA-AUDIT",
        status="delivered", current_sale_id=sale_id, sale_price=Decimal("167275.05"),
        discount_amount=Decimal("0"), financing_date=None, external_contract_id=uuid4(), updated_at=datetime.now(UTC),
        external_receivable_id=uuid4())
    sale = ConstructionUnitSale(id=sale_id, company_id=company, unit_id=unit_id, sequence=1,
                               status="ACTIVE", termination_terms={})
    sources = [ConstructionUnitPaymentSource(source_type=key, amount=Decimal(amount),
               due_date=None, installments=1, generates_installments=False)
               for key, amount in (("financing", "150000.00"), ("balance", "17275.05"))]
    repository = AsyncMock()
    repository.list_unit_documentations.return_value = []
    repository.list_unit_payment_sources.return_value = sources
    repository.list_unit_commissions.return_value = []
    client = AsyncMock()
    service = ConstructionProjectService(repository=repository, erp_client=client)
    service._get_active_current_sale = AsyncMock(return_value=sale)
    return service, unit, sale, repository, client


@pytest.mark.asyncio
@pytest.mark.parametrize("amount,balance,difference", [
    ("160000.00", "7275.05", "0.00"),
    ("140000.00", "27275.05", "0.00"),
    ("167275.05", "0.00", "0.00"),
    ("168000.00", "0.00", "724.95"),
    ("169000.00", "0.00", "1724.95"),
])
async def test_delivered_value_update_preserves_financial_links_and_records_before_after(amount, balance, difference):
    service, unit, sale, repository, client = scenario()
    contract, receivable = unit.external_contract_id, unit.external_receivable_id
    request = ConstructionDeliveredSaleUpdateRequest(sale_id=sale.id, expected_updated_at=unit.updated_at, documentations=[],
        bank_sources=[{"source_type": "financing", "amount": amount}], change_reason="Contrato do banco")
    await service._update_delivered_sale(unit, request, uuid4(), None)
    audit = repository.add.call_args.args[0]
    assert isinstance(audit, ConstructionUnitSaleValueAudit)
    assert audit.old_data["financing"] == "150000.00"
    assert audit.new_data["financing"] == amount
    assert audit.new_data["balance"] == balance
    assert audit.new_data["composition_difference"] == difference
    assert audit.reason == "Contrato do banco"
    assert (unit.external_contract_id, unit.external_receivable_id) == (contract, receivable)
    assert unit.status == "delivered" and unit.sale_price == Decimal("167275.05")
    stored_balance = [row for row in sale.payment_sources if row["source_type"] == "balance"]
    assert bool(stored_balance) == (Decimal(balance) > 0)
    if stored_balance:
        assert stored_balance[0]["amount"] == balance
    repository.commit.assert_awaited_once()
    client.deliver_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [None, "", "   "])
async def test_changed_values_without_reason_are_rejected_before_writing(reason):
    service, unit, sale, repository, _ = scenario()
    request = ConstructionDeliveredSaleUpdateRequest(sale_id=sale.id, expected_updated_at=unit.updated_at, documentations=[],
        bank_sources=[{"source_type": "financing", "amount": "168000.00"}], change_reason=reason)
    with pytest.raises(ConstructionInvalidValueError) as error:
        await service._update_delivered_sale(unit, request, uuid4(), None)
    assert error.value.error_code == "CONSTRUCTION_SALE_VALUE_CHANGE_REASON_REQUIRED"
    repository.add.assert_not_awaited()
    repository.replace_unit_children.assert_not_awaited()
    repository.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unchanged_save_needs_no_reason_or_audit_or_commit():
    service, unit, sale, repository, _ = scenario()
    request = ConstructionDeliveredSaleUpdateRequest(sale_id=sale.id, expected_updated_at=unit.updated_at, documentations=[],
        bank_sources=[{"source_type": "financing", "amount": "150000.00"}])
    await service._update_delivered_sale(unit, request, uuid4(), None)
    repository.add.assert_not_awaited()
    repository.replace_unit_children.assert_not_awaited()
    repository.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_audit_failure_prevents_value_changes_and_commit():
    service, unit, sale, repository, _ = scenario()
    repository.add.side_effect = RuntimeError("Auditoria indisponível")
    request = ConstructionDeliveredSaleUpdateRequest(sale_id=sale.id, expected_updated_at=unit.updated_at, documentations=[],
        bank_sources=[{"source_type": "financing", "amount": "168000.00"}], change_reason="Contrato")
    with pytest.raises(RuntimeError):
        await service._update_delivered_sale(unit, request, uuid4(), None)
    repository.replace_unit_children.assert_not_awaited()
    repository.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"sale_price": "170000.00"}, {"sale_id": str(uuid4())},
                                    {"financing_date": date(2100, 1, 1)}])
async def test_existing_guards_still_reject_invalid_changes(change):
    service, unit, sale, repository, _ = scenario()
    data = dict(sale_id=sale.id, expected_updated_at=unit.updated_at, documentations=[], bank_sources=[{"source_type": "financing", "amount": "168000.00"}],
                change_reason="Contrato")
    data.update(change)
    with pytest.raises(ConstructionInvalidValueError):
        await service._update_delivered_sale(unit, ConstructionDeliveredSaleUpdateRequest(**data), uuid4(), None)
    repository.add.assert_not_awaited()
    repository.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_editor_cannot_overwrite_the_last_saved_values():
    service, unit, sale, repository, _ = scenario()
    stale_version = unit.updated_at
    first = ConstructionDeliveredSaleUpdateRequest(sale_id=sale.id, expected_updated_at=stale_version,
        documentations=[], bank_sources=[{"source_type": "financing", "amount": "168000.00"}],
        change_reason="Primeiro contrato")
    await service._update_delivered_sale(unit, first, uuid4(), None)
    assert unit.updated_at != stale_version
    repository.reset_mock()
    second = ConstructionDeliveredSaleUpdateRequest(sale_id=sale.id, expected_updated_at=stale_version,
        documentations=[], bank_sources=[{"source_type": "financing", "amount": "140000.00"}],
        change_reason="Tela antiga")
    with pytest.raises(ConstructionResourceInUseError):
        await service._update_delivered_sale(unit, second, uuid4(), None)
    repository.add.assert_not_awaited()
    repository.commit.assert_not_awaited()
    assert next(row for row in sale.payment_sources if row["source_type"] == "financing")["amount"] == "168000.00"
