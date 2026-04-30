from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.constants import ConstructionMeasurementStatus, ConstructionProcurementStatus, ConstructionProjectStatus
from app.domain.exceptions import (
    ConstructionDuplicateCodeError,
    ConstructionInvalidStatusTransitionError,
    ConstructionNotFoundError,
)
from app.domain.events.constants import ConstructionEventType, ErpEventType
from app.domain.events.contracts import EventEnvelope
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionMeasurement,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionUnit,
)
from app.schemas.construction import (
    ConstructionMeasurementCreate,
    ConstructionProcurementRequestCreate,
    ConstructionProjectCreate,
    ConstructionProjectUpdate,
    ConstructionUnitSaleConfirmRequest,
)


class FakeConstructionRepository:
    def __init__(self) -> None:
        self.projects: dict[tuple[object, object], ConstructionProject] = {}
        self.measurements: dict[tuple[object, object], ConstructionMeasurement] = {}
        self.units: dict[tuple[object, object], ConstructionUnit] = {}
        self.procurement_requests: dict[tuple[object, object], ConstructionProcurementRequest] = {}
        self.commits = 0

    async def add(
        self,
        entity: ConstructionProject | ConstructionMeasurement | ConstructionUnit | ConstructionProcurementRequest,
    ) -> None:
        if entity.id is None:
            entity.id = uuid4()
        if isinstance(entity, ConstructionProject):
            self.projects[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionUnit):
            self.units[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionProcurementRequest):
            self.procurement_requests[(entity.company_id, entity.id)] = entity
            return

        self.measurements[(entity.company_id, entity.id)] = entity

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(
        self,
        entity: ConstructionProject | ConstructionMeasurement | ConstructionUnit | ConstructionProcurementRequest,
    ) -> None:
        return None

    async def get_project(self, *, company_id, project_id):
        return self.projects.get((company_id, project_id))

    async def get_project_by_code(self, *, company_id, code):
        return next(
            (
                project
                for (stored_company_id, _), project in self.projects.items()
                if stored_company_id == company_id and project.code == code
            ),
            None,
        )

    async def list_projects(self, *, company_id, search, page, page_size):
        items = [project for (stored_company_id, _), project in self.projects.items() if stored_company_id == company_id]
        return items[(page - 1) * page_size : page * page_size], len(items)

    async def delete(
        self,
        entity: ConstructionProject | ConstructionMeasurement | ConstructionUnit | ConstructionProcurementRequest,
    ) -> None:
        if isinstance(entity, ConstructionProject):
            self.projects.pop((entity.company_id, entity.id), None)
            return

        if isinstance(entity, ConstructionUnit):
            self.units.pop((entity.company_id, entity.id), None)
            return

        if isinstance(entity, ConstructionProcurementRequest):
            self.procurement_requests.pop((entity.company_id, entity.id), None)
            return

        self.measurements.pop((entity.company_id, entity.id), None)

    async def get_measurement(self, *, company_id, measurement_id):
        return self.measurements.get((company_id, measurement_id))

    async def get_unit(self, *, company_id, unit_id):
        return self.units.get((company_id, unit_id))

    async def get_measurement_by_code(self, *, company_id, project_id, code):
        return next(
            (
                measurement
                for (stored_company_id, _), measurement in self.measurements.items()
                if (
                    stored_company_id == company_id
                    and measurement.project_id == project_id
                    and measurement.code == code
                )
            ),
            None,
        )

    async def get_measurement_by_external_accounts_payable_id(self, *, company_id, accounts_payable_id):
        return next(
            (
                measurement
                for (stored_company_id, _), measurement in self.measurements.items()
                if (
                    stored_company_id == company_id
                    and measurement.external_accounts_payable_id == accounts_payable_id
                )
            ),
            None,
        )

    async def list_measurements(self, *, company_id, project_id):
        return [
            measurement
            for (stored_company_id, _), measurement in self.measurements.items()
            if stored_company_id == company_id and measurement.project_id == project_id
        ]

    async def get_procurement_request(self, *, company_id, procurement_request_id):
        return self.procurement_requests.get((company_id, procurement_request_id))

    async def list_procurement_requests(self, *, company_id, project_id):
        return [
            procurement_request
            for (stored_company_id, _), procurement_request in self.procurement_requests.items()
            if stored_company_id == company_id and procurement_request.project_id == project_id
        ]


class FakeEventRepository:
    def __init__(self) -> None:
        self.outbox_events: list[EventEnvelope] = []
        self.processed_events: set[tuple[str, object]] = set()

    async def add_outbox_event(self, *, event: EventEnvelope):
        self.outbox_events.append(event)
        return event

    async def mark_processed(self, *, consumer_name: str, event: EventEnvelope) -> bool:
        processed_key = (consumer_name, event.event_id)
        if processed_key in self.processed_events:
            return False

        self.processed_events.add(processed_key)
        return True


class FakeErpMeasurementClient:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    async def create_accounts_payable_from_measurement(self, *, event: EventEnvelope) -> EventEnvelope:
        self.events.append(event)
        event_id = uuid4()
        return EventEnvelope(
            event_id=event_id,
            event_type=ErpEventType.ACCOUNTS_PAYABLE_CREATED,
            event_version=1,
            company_id=event.company_id,
            aggregate_id=event.aggregate_id,
            aggregate_type="construction_measurement",
            occurred_at=datetime.now(tz=UTC),
            producer="erp-api",
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload={
                "construction_measurement_id": str(event.aggregate_id),
                "accounts_payable_document_id": str(uuid4()),
                "accounts_payable_status": "OPEN",
            },
        )

    async def create_contract_and_receivables_from_unit_sale(self, *, event: EventEnvelope) -> EventEnvelope:
        self.events.append(event)
        event_id = uuid4()
        return EventEnvelope(
            event_id=event_id,
            event_type=ErpEventType.CONTRACT_RECEIVABLE_CREATED,
            event_version=1,
            company_id=event.company_id,
            aggregate_id=event.aggregate_id,
            aggregate_type="construction_unit",
            occurred_at=datetime.now(tz=UTC),
            producer="erp-api",
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload={
                "construction_unit_id": str(event.aggregate_id),
                "external_contract_id": str(uuid4()),
                "contract_status": "ACTIVE",
                "external_receivable_id": str(uuid4()),
                "receivable_status": "OPEN",
            },
        )

    async def create_procurement_demand_from_request(self, *, event: EventEnvelope) -> EventEnvelope:
        self.events.append(event)
        event_id = uuid4()
        return EventEnvelope(
            event_id=event_id,
            event_type=ErpEventType.PROCUREMENT_REQUEST_ACCEPTED,
            event_version=1,
            company_id=event.company_id,
            aggregate_id=event.aggregate_id,
            aggregate_type="construction_procurement_request",
            occurred_at=datetime.now(tz=UTC),
            producer="erp-api",
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload={
                "construction_procurement_request_id": str(event.aggregate_id),
                "external_procurement_id": str(event.aggregate_id),
                "external_procurement_status": "PENDING_REVIEW",
            },
        )


def make_service(repository: FakeConstructionRepository | None = None) -> ConstructionProjectService:
    return ConstructionProjectService(repository=repository or FakeConstructionRepository())


def make_erp_cost_center_created_event(
    *,
    company_id,
    project_id,
    synthetic_cost_center_id,
    analytic_cost_center_id,
) -> EventEnvelope:
    event_id = uuid4()
    return EventEnvelope(
        event_id=event_id,
        event_type=ErpEventType.COST_CENTER_CREATED,
        event_version=1,
        company_id=company_id,
        aggregate_id=project_id,
        aggregate_type="construction_project",
        occurred_at=datetime.now(tz=UTC),
        producer="erp-api",
        correlation_id=event_id,
        causation_id=None,
        payload={
            "construction_project_id": str(project_id),
            "synthetic_cost_center_id": str(synthetic_cost_center_id),
            "analytic_cost_center_id": str(analytic_cost_center_id),
        },
    )


def make_erp_accounts_payable_updated_event(
    *,
    company_id,
    measurement_id,
    accounts_payable_document_id,
    accounts_payable_status,
) -> EventEnvelope:
    event_id = uuid4()
    return EventEnvelope(
        event_id=event_id,
        event_type=ErpEventType.ACCOUNTS_PAYABLE_UPDATED,
        event_version=1,
        company_id=company_id,
        aggregate_id=measurement_id,
        aggregate_type="construction_measurement",
        occurred_at=datetime.now(tz=UTC),
        producer="erp-api",
        correlation_id=event_id,
        causation_id=None,
        payload={
            "construction_measurement_id": str(measurement_id),
            "accounts_payable_document_id": str(accounts_payable_document_id),
            "accounts_payable_status": accounts_payable_status,
        },
    )


def make_erp_contract_status_updated_event(
    *,
    company_id,
    unit_id,
    contract_status,
) -> EventEnvelope:
    event_id = uuid4()
    return EventEnvelope(
        event_id=event_id,
        event_type=ErpEventType.CONTRACT_STATUS_UPDATED,
        event_version=1,
        company_id=company_id,
        aggregate_id=unit_id,
        aggregate_type="construction_unit",
        occurred_at=datetime.now(tz=UTC),
        producer="erp-api",
        correlation_id=event_id,
        causation_id=None,
        payload={
            "construction_unit_id": str(unit_id),
            "external_contract_id": str(uuid4()),
            "contract_status": contract_status,
            "external_receivable_id": str(uuid4()),
            "receivable_status": "CANCELED" if contract_status == "CANCELED" else "OPEN",
        },
    )


@pytest.mark.asyncio
async def test_create_project_rejects_duplicate_code() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    existing_project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-001",
        name="Existing project",
        status=ConstructionProjectStatus.DRAFT,
    )
    repository.projects[(company_id, existing_project.id)] = existing_project
    service = make_service(repository=repository)

    with pytest.raises(ConstructionDuplicateCodeError):
        await service.create_project(
            company_id=company_id,
            request=ConstructionProjectCreate(code="OBRA-001", name="New project"),
        )


@pytest.mark.asyncio
async def test_create_project_records_project_created_outbox_event() -> None:
    company_id = uuid4()
    user_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    service = ConstructionProjectService(repository=repository, event_repository=event_repository)

    project = await service.create_project(
        company_id=company_id,
        request=ConstructionProjectCreate(
            code="OBRA-010",
            name="Obra Outbox",
            start_date=date(2026, 4, 1),
            expected_end_date=date(2026, 12, 31),
        ),
        actor_user_id=user_id,
    )

    assert repository.commits == 1
    assert len(event_repository.outbox_events) == 1
    event = event_repository.outbox_events[0]
    assert event.event_type == ConstructionEventType.PROJECT_CREATED
    assert event.company_id == company_id
    assert event.aggregate_id == project.id
    assert event.payload["construction_project_id"] == str(project.id)
    assert event.payload["project_code"] == "OBRA-010"
    assert event.payload["project_name"] == "Obra Outbox"
    assert event.payload["start_date"] == "2026-04-01"
    assert event.payload["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_update_project_rejects_invalid_status_transition() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-002",
        name="Completed project",
        status=ConstructionProjectStatus.COMPLETED,
    )
    repository.projects[(company_id, project.id)] = project
    service = make_service(repository=repository)

    with pytest.raises(ConstructionInvalidStatusTransitionError):
        await service.update_project(
            company_id=company_id,
            project_id=project.id,
            request=ConstructionProjectUpdate(status=ConstructionProjectStatus.ACTIVE),
        )


@pytest.mark.asyncio
async def test_get_project_enforces_company_isolation() -> None:
    owner_company_id = uuid4()
    other_company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=owner_company_id,
        code="OBRA-003",
        name="Tenant project",
        status=ConstructionProjectStatus.DRAFT,
    )
    repository.projects[(owner_company_id, project.id)] = project
    service = make_service(repository=repository)

    with pytest.raises(ConstructionNotFoundError):
        await service.get_project(company_id=other_company_id, project_id=project.id)


@pytest.mark.asyncio
async def test_apply_cost_center_created_event_updates_project_once() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    synthetic_cost_center_id = uuid4()
    analytic_cost_center_id = uuid4()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-020",
        name="Cost center project",
        status=ConstructionProjectStatus.DRAFT,
    )
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(repository=repository, event_repository=event_repository)
    event = make_erp_cost_center_created_event(
        company_id=company_id,
        project_id=project.id,
        synthetic_cost_center_id=synthetic_cost_center_id,
        analytic_cost_center_id=analytic_cost_center_id,
    )

    first_result = await service.apply_cost_center_created_event(event=event)
    second_result = await service.apply_cost_center_created_event(event=event)

    assert first_result.synthetic_cost_center_id == synthetic_cost_center_id
    assert first_result.analytic_cost_center_id == analytic_cost_center_id
    assert second_result.synthetic_cost_center_id == synthetic_cost_center_id
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_approve_measurement_creates_accounts_payable_once() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-030",
        name="Measurement project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(
        repository=repository,
        event_repository=event_repository,
        erp_client=erp_client,
    )

    measurement = await service.create_measurement(
        company_id=company_id,
        project_id=project.id,
        request=ConstructionMeasurementCreate(
            code="MED-001",
            measured_amount=Decimal("12500.50"),
            due_date=date(2026, 5, 15),
        ),
    )

    approved_first = await service.approve_measurement(company_id=company_id, measurement_id=measurement.id)
    approved_second = await service.approve_measurement(company_id=company_id, measurement_id=measurement.id)

    assert approved_first.status == ConstructionMeasurementStatus.APPROVED
    assert approved_first.external_accounts_payable_id is not None
    assert approved_first.external_accounts_payable_status == "OPEN"
    assert approved_second.external_accounts_payable_id == approved_first.external_accounts_payable_id
    assert len(erp_client.events) == 1
    assert any(event.event_type == ConstructionEventType.MEASUREMENT_APPROVED for event in event_repository.outbox_events)


@pytest.mark.asyncio
async def test_rejected_or_draft_measurement_does_not_create_accounts_payable() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-031",
        name="Rejected measurement project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)

    measurement = await service.create_measurement(
        company_id=company_id,
        project_id=project.id,
        request=ConstructionMeasurementCreate(
            code="MED-002",
            measured_amount=Decimal("1000.00"),
            due_date=date(2026, 5, 20),
        ),
    )
    await service.reject_measurement(company_id=company_id, measurement_id=measurement.id)

    assert len(erp_client.events) == 0
    stored_measurement = await service.get_measurement(company_id=company_id, measurement_id=measurement.id)
    assert stored_measurement.status == ConstructionMeasurementStatus.REJECTED


@pytest.mark.asyncio
async def test_apply_accounts_payable_updated_event_updates_measurement_once() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-032",
        name="AP sync project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    measurement = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="MED-003",
        measured_amount=Decimal("3500.00"),
        due_date=date(2026, 5, 25),
        status=ConstructionMeasurementStatus.APPROVED,
    )
    repository.projects[(company_id, project.id)] = project
    repository.measurements[(company_id, measurement.id)] = measurement
    service = ConstructionProjectService(repository=repository, event_repository=event_repository)
    accounts_payable_document_id = uuid4()
    event = make_erp_accounts_payable_updated_event(
        company_id=company_id,
        measurement_id=measurement.id,
        accounts_payable_document_id=accounts_payable_document_id,
        accounts_payable_status="PAID",
    )

    first_result = await service.apply_accounts_payable_updated_event(event=event)
    second_result = await service.apply_accounts_payable_updated_event(event=event)

    assert first_result.external_accounts_payable_id == accounts_payable_document_id
    assert first_result.external_accounts_payable_status == "PAID"
    assert second_result.external_accounts_payable_id == accounts_payable_document_id
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_confirm_unit_sale_creates_contract_snapshot_once() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-040",
        name="Unit sales project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="A-101",
        unit_type="apartment",
        sale_price=Decimal("450000.00"),
        status="available",
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    service = ConstructionProjectService(
        repository=repository,
        event_repository=event_repository,
        erp_client=erp_client,
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("450000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
    )
    first_result = await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=request,
    )
    second_result = await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=request,
    )

    assert first_result.status == "sold"
    assert first_result.external_contract_id is not None
    assert first_result.external_receivable_id is not None
    assert second_result.external_contract_id == first_result.external_contract_id
    assert len(erp_client.events) == 1
    assert any(event.event_type == ConstructionEventType.UNIT_SOLD for event in event_repository.outbox_events)


@pytest.mark.asyncio
async def test_apply_contract_status_updated_event_cancellation_reverts_unit_to_available() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-041",
        name="Contract status sync",
        status=ConstructionProjectStatus.ACTIVE,
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="B-202",
        unit_type="apartment",
        status="sold",
        sold_at=datetime.now(tz=UTC),
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    service = ConstructionProjectService(repository=repository, event_repository=event_repository)
    event = make_erp_contract_status_updated_event(
        company_id=company_id,
        unit_id=unit.id,
        contract_status="CANCELED",
    )

    first_result = await service.apply_contract_status_updated_event(event=event)
    second_result = await service.apply_contract_status_updated_event(event=event)

    assert first_result.status == "available"
    assert first_result.external_contract_status == "CANCELED"
    assert second_result.status == "available"
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_submit_procurement_request_over_threshold_requires_approval() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-050",
        name="Procurement project",
        status=ConstructionProjectStatus.ACTIVE,
    )
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(repository=repository)

    procurement_request = await service.create_procurement_request(
        company_id=company_id,
        project_id=project.id,
        request=ConstructionProcurementRequestCreate(
            title="Elevator package",
            estimated_amount=Decimal("75000.00"),
        ),
    )
    submitted = await service.submit_procurement_request(
        company_id=company_id,
        procurement_request_id=procurement_request.id,
        actor_user_id=uuid4(),
    )

    assert submitted.status == ConstructionProcurementStatus.PENDING_APPROVAL
    assert submitted.external_procurement_id is None


@pytest.mark.asyncio
async def test_approve_procurement_request_sends_demand_once() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-051",
        name="Procurement integration",
        status=ConstructionProjectStatus.ACTIVE,
    )
    repository.projects[(company_id, project.id)] = project
    service = ConstructionProjectService(
        repository=repository,
        event_repository=event_repository,
        erp_client=erp_client,
    )

    procurement_request = await service.create_procurement_request(
        company_id=company_id,
        project_id=project.id,
        request=ConstructionProcurementRequestCreate(
            title="Facade structure",
            estimated_amount=Decimal("80000.00"),
        ),
    )
    await service.submit_procurement_request(
        company_id=company_id,
        procurement_request_id=procurement_request.id,
        actor_user_id=uuid4(),
    )
    approved = await service.approve_procurement_request(
        company_id=company_id,
        procurement_request_id=procurement_request.id,
        actor_user_id=uuid4(),
    )

    assert approved.status == ConstructionProcurementStatus.SENT_TO_ERP
    assert approved.external_procurement_id == procurement_request.id
    assert approved.external_procurement_status == "PENDING_REVIEW"
    assert any(event.event_type == ConstructionEventType.PROCUREMENT_REQUESTED for event in event_repository.outbox_events)
    assert len([event for event in erp_client.events if event.event_type == ConstructionEventType.PROCUREMENT_REQUESTED]) == 1
