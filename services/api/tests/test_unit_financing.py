from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject, ConstructionUnit
from app.schemas.construction import ConstructionUnitSaleConfirmRequest
from .test_construction_project_service import FakeConstructionRepository, FakeEventRepository, FakeErpMeasurementClient


@pytest.mark.asyncio
async def test_financing_fields_are_written_snapshotted_and_cleared():
    company = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(id=uuid4(), company_id=company, code="F-1", name="Obra", status="active")
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company,
        project_id=project.id,
        code="1",
        unit_type="house",
        sale_price=Decimal("200000"),
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    repository.projects[(company, project.id)] = project
    repository.units[(company, unit.id)] = unit
    service = ConstructionProjectService(
        repository=repository, event_repository=FakeEventRepository(), erp_client=FakeErpMeasurementClient()
    )
    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("200000"),
        first_due_date=date(2026, 10, 1),
        installments=1,
        financing_completed=True,
        financing_date=date(2020, 1, 1),
        payment_sources=[dict(source_type="financing", amount="100000", installments=1)],
    )
    result = await service.confirm_unit_sale(company_id=company, unit_id=unit.id, request=request)
    assert result.financing_completed is True and result.financing_date == date(2020, 1, 1)
    sale = service._build_current_sale(unit=unit, project=project, actor_user_id=None, sequence=2)
    assert sale.financing_completed is True and sale.financing_date == date(2020, 1, 1)
    await service._release_terminated_unit(unit)
    assert unit.financing_completed is False and unit.financing_date is None
    assert sale.financing_completed is True and sale.financing_date == date(2020, 1, 1)


@pytest.mark.asyncio
async def test_financing_snapshot_is_restored_when_termination_is_reactivated():
    from .test_construction_project_service import _sold_unit_with_sale, _termination_request, FakeSaleTerminationClient
    from app.schemas.construction.project import ConstructionUnitTerminationReactivateRequest

    company = uuid4()
    repository = FakeConstructionRepository()
    _, unit = _sold_unit_with_sale(repository, company_id=company)
    unit.financing_completed = True
    unit.financing_date = date(2020, 1, 1)
    service = ConstructionProjectService(
        repository=repository, event_repository=FakeEventRepository(), erp_client=FakeSaleTerminationClient()
    )
    await service.terminate_unit(company_id=company, unit_id=unit.id, request=_termination_request())
    assert unit.financing_completed is False and unit.financing_date is None
    await service.reactivate_unit_termination(
        company_id=company, unit_id=unit.id, request=ConstructionUnitTerminationReactivateRequest(reason="Retomar venda")
    )
    assert unit.financing_completed is True and unit.financing_date == date(2020, 1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "financing_date, sources, error",
    [
        (date(2100, 1, 1), [dict(source_type="financing", amount="100000")], "CONSTRUCTION_FINANCING_FUTURE_DATE"),
        (date(2020, 1, 1), [], "CONSTRUCTION_FINANCING_REQUIRED"),
    ],
)
async def test_financing_date_rejects_future_and_missing_financing(financing_date, sources, error):
    from app.domain.exceptions import ConstructionInvalidValueError
    from .test_construction_project_service import _available_unit_for_sale

    company = uuid4()
    repository = FakeConstructionRepository()
    _, unit = _available_unit_for_sale(repository, company_id=company)
    service = ConstructionProjectService(
        repository=repository, event_repository=FakeEventRepository(), erp_client=FakeErpMeasurementClient()
    )
    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("200000"),
        first_due_date=date(2026, 10, 1),
        financing_date=financing_date,
        payment_sources=sources,
    )
    with pytest.raises(ConstructionInvalidValueError) as raised:
        await service.confirm_unit_sale(company_id=company, unit_id=unit.id, request=request)
    assert raised.value.error_code == error
