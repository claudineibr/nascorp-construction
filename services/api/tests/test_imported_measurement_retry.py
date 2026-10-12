from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.constants import ConstructionMeasurementStatus, ConstructionProjectStatus
from app.domain.exceptions import ConstructionInvalidValueError
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionMeasurement, ConstructionProject
from tests.test_construction_project_service import FakeConstructionRepository, FakeEventRepository


class FakeErpPayableLinkClient:
    def __init__(self):
        self.linked = []

    async def list_measurement_payable_candidates(self, *, company_id, measurement_id, user_id, search=None):
        return {"items": [{"id": "title-1", "document_number": "10275", "total_amount": "135.00"}]}

    async def link_measurement_payable(self, *, company_id, measurement_id, user_id, payable_document_id):
        self.linked.append((measurement_id, payable_document_id))
        return {"accounts_payable_document_id": str(payable_document_id), "accounts_payable_status": "PAID"}


def build_approved_measurement(*, approved_at, erp_client=None, supplier_person_id=None, amount=Decimal("1200.00")):
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="EMP-000067",
        name="Obra importada",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    measurement = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="OS-000401",
        measured_amount=amount,
        net_amount=amount,
        due_date=date(2026, 5, 25),
        status=ConstructionMeasurementStatus.APPROVED,
        approved_at=approved_at,
        supplier_person_id=supplier_person_id,
    )
    repository.projects[(company_id, project.id)] = project
    repository.measurements[(company_id, measurement.id)] = measurement
    service = ConstructionProjectService(
        repository=repository, event_repository=FakeEventRepository(), erp_client=erp_client
    )
    return service, company_id, measurement


@pytest.mark.asyncio
async def test_imported_approved_measurement_is_not_resent_to_the_erp() -> None:
    service, company_id, measurement = build_approved_measurement(approved_at=None)

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.approve_measurement(company_id=company_id, measurement_id=measurement.id)

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_IMPORTED_NOT_SENT"


@pytest.mark.asyncio
async def test_measurement_approved_in_the_system_still_reaches_the_phase_check_on_resend() -> None:
    service, company_id, measurement = build_approved_measurement(approved_at=datetime(2026, 9, 1, tzinfo=UTC))

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.approve_measurement(company_id=company_id, measurement_id=measurement.id)

    assert error.value.error_code != "CONSTRUCTION_MEASUREMENT_IMPORTED_NOT_SENT"


@pytest.mark.asyncio
async def test_imported_measurement_links_the_chosen_erp_title() -> None:
    erp = FakeErpPayableLinkClient()
    service, company_id, measurement = build_approved_measurement(
        approved_at=None, erp_client=erp, supplier_person_id=uuid4()
    )
    title_id = uuid4()

    candidates = await service.list_measurement_payable_candidates(company_id=company_id, measurement_id=measurement.id)
    linked = await service.link_measurement_payable(
        company_id=company_id, measurement_id=measurement.id, payable_document_id=title_id
    )

    assert candidates[0]["document_number"] == "10275"
    assert linked.external_accounts_payable_id == title_id
    assert linked.external_accounts_payable_status == "PAID"
    with pytest.raises(ConstructionInvalidValueError) as again:
        await service.link_measurement_payable(
            company_id=company_id, measurement_id=measurement.id, payable_document_id=uuid4()
        )
    assert again.value.error_code == "CONSTRUCTION_MEASUREMENT_ALREADY_LINKED"
    assert len(erp.linked) == 1


@pytest.mark.asyncio
async def test_measurement_without_supplier_cannot_look_for_a_title() -> None:
    service, company_id, measurement = build_approved_measurement(
        approved_at=None, erp_client=FakeErpPayableLinkClient()
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.list_measurement_payable_candidates(company_id=company_id, measurement_id=measurement.id)

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_SUPPLIER_REQUIRED"


@pytest.mark.asyncio
async def test_zero_value_measurement_has_no_title_of_its_own() -> None:
    erp = FakeErpPayableLinkClient()
    service, company_id, measurement = build_approved_measurement(
        approved_at=None, erp_client=erp, supplier_person_id=uuid4(), amount=Decimal("0.00")
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.link_measurement_payable(
            company_id=company_id, measurement_id=measurement.id, payable_document_id=uuid4()
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_ZERO_VALUE_NO_TITLE"
    assert erp.linked == []
