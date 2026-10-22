from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.constants import ConstructionMeasurementStatus, ConstructionProjectStatus
from app.domain.exceptions import ConstructionInvalidValueError, ConstructionNotFoundError
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionMeasurement, ConstructionProject
from tests.test_construction_project_service import FakeConstructionRepository, FakeEventRepository


class FakeErpSharedPayableClient:
    def __init__(self, person_id):
        self.person_id = person_id
        self.checked = []

    async def check_shared_payable(self, *, company_id, project_id, user_id, payable_document_id, supplier_person_id):
        self.checked.append((payable_document_id, supplier_person_id))
        return {
            "accounts_payable_document_id": str(payable_document_id),
            "accounts_payable_status": "PAID",
            "document_number": "15237",
            "person_id": str(self.person_id),
        }


def build_project(*, title_supplier=None):
    company_id = uuid4()
    supplier_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="EMP-000097",
        name="Obra da empreitada",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    repository.projects[(company_id, project.id)] = project
    erp = FakeErpSharedPayableClient(title_supplier or supplier_id)
    service = ConstructionProjectService(repository=repository, event_repository=FakeEventRepository(), erp_client=erp)
    return service, repository, erp, company_id, project, supplier_id


def add_measurement(repository, company_id, project, supplier_id, *, code, amount=Decimal("0.00"), **extra):
    measurement = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code=code,
        measured_amount=amount,
        net_amount=amount,
        due_date=date(2021, 3, 19),
        status=ConstructionMeasurementStatus.APPROVED,
        supplier_person_id=supplier_id,
        external_accounts_payable_shared=False,
        **extra,
    )
    repository.measurements[(company_id, measurement.id)] = measurement
    return measurement


@pytest.mark.asyncio
async def test_one_dnf_covers_several_zero_value_orders() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    orders = [add_measurement(repository, company_id, project, supplier_id, code=f"OS-00{n}") for n in range(3)]
    title_id = uuid4()

    linked = await service.link_shared_payable(
        company_id=company_id,
        project_id=project.id,
        payable_document_id=title_id,
        measurement_ids=[order.id for order in orders],
    )

    assert linked == 3
    assert erp.checked == [(title_id, supplier_id)]
    assert all(order.external_accounts_payable_id == title_id for order in orders)
    assert all(order.external_accounts_payable_shared for order in orders)
    assert all(order.external_accounts_payable_status == "PAID" for order in orders)
    assert repository.commits == 1

    again = await service.link_shared_payable(
        company_id=company_id,
        project_id=project.id,
        payable_document_id=title_id,
        measurement_ids=[orders[0].id],
    )
    assert again == 0


@pytest.mark.asyncio
async def test_order_with_value_is_not_covered_by_the_subcontract_dnf() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    valued = add_measurement(repository, company_id, project, supplier_id, code="OS-001", amount=Decimal("810.00"))

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.link_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=uuid4(), measurement_ids=[valued.id]
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_NOT_ZERO"
    assert erp.checked == []


@pytest.mark.asyncio
async def test_order_already_linked_elsewhere_is_refused() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    linked = add_measurement(
        repository, company_id, project, supplier_id, code="OS-001", external_accounts_payable_id=uuid4()
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.link_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=uuid4(), measurement_ids=[linked.id]
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_ALREADY_LINKED"


@pytest.mark.asyncio
async def test_orders_of_different_suppliers_or_title_of_another_supplier_are_refused() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    first = add_measurement(repository, company_id, project, supplier_id, code="OS-001")
    other = add_measurement(repository, company_id, project, uuid4(), code="OS-002")

    with pytest.raises(ConstructionInvalidValueError) as mixed:
        await service.link_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=uuid4(), measurement_ids=[first.id, other.id]
        )
    assert mixed.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_OTHER_SUPPLIER"

    service, repository, erp, company_id, project, supplier_id = build_project(title_supplier=uuid4())
    order = add_measurement(repository, company_id, project, supplier_id, code="OS-003")
    with pytest.raises(ConstructionInvalidValueError) as foreign_title:
        await service.link_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=uuid4(), measurement_ids=[order.id]
        )
    assert foreign_title.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_OTHER_SUPPLIER"
    assert order.external_accounts_payable_id is None


@pytest.mark.asyncio
async def test_dnf_of_a_contract_does_not_take_orders_without_contract() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    title_id = uuid4()
    contract_order = add_measurement(
        repository, company_id, project, supplier_id, code="OS-001", amount=Decimal("500.00"),
        external_accounts_payable_id=title_id, subcontract_id=uuid4(),
    )
    contract_order.external_accounts_payable_shared = True
    zero_order = add_measurement(repository, company_id, project, supplier_id, code="OS-002")

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.link_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=title_id, measurement_ids=[zero_order.id]
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_MIXED_CONTRACTS"
    assert zero_order.external_accounts_payable_id is None
    assert erp.checked == []


@pytest.mark.asyncio
async def test_contract_order_leaves_the_dnf_only_when_it_has_no_payment() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    title_id = uuid4()
    contract_order = add_measurement(
        repository, company_id, project, supplier_id, code="OS-001", amount=Decimal("500.00"),
        external_accounts_payable_id=title_id, subcontract_id=uuid4(),
    )
    contract_order.external_accounts_payable_shared = True

    with pytest.raises(ConstructionInvalidValueError) as paid:
        await service.unlink_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=title_id, measurement_ids=[contract_order.id]
        )
    assert paid.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_PAYABLE_PAID"
    assert contract_order.external_accounts_payable_id == title_id

    async def missing_title(**_):
        raise ConstructionNotFoundError(resource_name="o título")

    erp.check_shared_payable = missing_title
    removed = await service.unlink_shared_payable(
        company_id=company_id, project_id=project.id, payable_document_id=title_id, measurement_ids=[contract_order.id]
    )
    assert removed == 1
    assert contract_order.external_accounts_payable_id is None


@pytest.mark.asyncio
async def test_order_from_another_project_is_not_found() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()

    with pytest.raises(ConstructionNotFoundError):
        await service.link_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=uuid4(), measurement_ids=[uuid4()]
        )


@pytest.mark.asyncio
async def test_removing_orders_only_touches_the_ones_in_that_dnf() -> None:
    service, repository, erp, company_id, project, supplier_id = build_project()
    title_id = uuid4()
    covered = add_measurement(
        repository,
        company_id,
        project,
        supplier_id,
        code="OS-001",
        external_accounts_payable_id=title_id,
        external_accounts_payable_status="PAID",
    )
    covered.external_accounts_payable_shared = True
    own_title = add_measurement(
        repository, company_id, project, supplier_id, code="OS-002", external_accounts_payable_id=title_id
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.unlink_shared_payable(
            company_id=company_id, project_id=project.id, payable_document_id=title_id, measurement_ids=[own_title.id]
        )
    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_SHARED_NOT_IN_PAYABLE"

    removed = await service.unlink_shared_payable(
        company_id=company_id, project_id=project.id, payable_document_id=title_id, measurement_ids=[covered.id]
    )
    assert removed == 1
    assert covered.external_accounts_payable_id is None
    assert covered.external_accounts_payable_status is None
    assert covered.external_accounts_payable_shared is False
    assert own_title.external_accounts_payable_id == title_id
