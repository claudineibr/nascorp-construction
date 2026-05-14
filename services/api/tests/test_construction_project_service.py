from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.domain.constants import ConstructionMeasurementStatus, ConstructionProcurementStatus, ConstructionProjectStatus
from app.domain.exceptions import (
    ConstructionDuplicateCodeError,
    ConstructionInvalidStatusTransitionError,
    ConstructionNotFoundError,
)
from app.domain.events.constants import ConstructionEventType, ConstructionIntegrationMode, ErpEventType
from app.domain.events.contracts import EventEnvelope
from app.domain.services import ConstructionIntegrationDispatcher, ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionMeasurement,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionUnit,
)
from app.schemas.construction import (
    ConstructionMeasurementCreate,
    ConstructionProcurementRequestCreate,
    ConstructionProjectCreate,
    ConstructionProjectUpdate,
    ConstructionUnitCreate,
    ConstructionUnitSaleConfirmRequest,
)


class FakeConstructionRepository:
    def __init__(self) -> None:
        self.projects: dict[tuple[object, object], ConstructionProject] = {}
        self.measurements: dict[tuple[object, object], ConstructionMeasurement] = {}
        self.units: dict[tuple[object, object], ConstructionUnit] = {}
        self.schedule_phases: dict[tuple[object, object], ConstructionSchedulePhase] = {}
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

    async def get_schedule_phase(self, *, company_id, phase_id):
        return self.schedule_phases.get((company_id, phase_id))

    async def get_unit_by_code(self, *, company_id, project_id, code):
        return next(
            (
                unit
                for (stored_company_id, _), unit in self.units.items()
                if stored_company_id == company_id and unit.project_id == project_id and unit.code == code
            ),
            None,
        )

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

    async def get_next_measurement_sequence(self, *, company_id, project_id):
        sequences = [
            int(measurement.sequence_number)
            for (stored_company_id, _), measurement in self.measurements.items()
            if stored_company_id == company_id
            and measurement.project_id == project_id
            and measurement.sequence_number is not None
        ]
        if not sequences:
            return 1

        return max(sequences) + 1

    async def list_measurements(self, *, company_id, project_id):
        return [
            measurement
            for (stored_company_id, _), measurement in self.measurements.items()
            if stored_company_id == company_id and measurement.project_id == project_id
        ]

    async def get_procurement_request(self, *, company_id, procurement_request_id):
        return self.procurement_requests.get((company_id, procurement_request_id))

    async def get_procurement_request_by_code(self, *, company_id, project_id, code):
        return next(
            (
                procurement_request
                for (stored_company_id, _), procurement_request in self.procurement_requests.items()
                if (
                    stored_company_id == company_id
                    and procurement_request.project_id == project_id
                    and procurement_request.code == code
                )
            ),
            None,
        )

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
        self.confirmation_events: list[EventEnvelope] = []

    async def create_cost_center_hierarchy(self, *, event: EventEnvelope) -> EventEnvelope:
        self.events.append(event)
        event_id = uuid4()
        confirmation_event = EventEnvelope(
            event_id=event_id,
            event_type=ErpEventType.COST_CENTER_CREATED,
            event_version=1,
            company_id=event.company_id,
            aggregate_id=event.aggregate_id,
            aggregate_type="construction_project",
            occurred_at=datetime.now(tz=UTC),
            producer="erp-api",
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload={
                "construction_project_id": str(event.aggregate_id),
                "synthetic_cost_center_id": str(uuid4()),
                "analytic_cost_center_id": str(uuid4()),
            },
        )
        self.confirmation_events.append(confirmation_event)
        return confirmation_event

    async def create_unit_cost_center(self, *, event: EventEnvelope) -> EventEnvelope:
        self.events.append(event)
        event_id = uuid4()
        confirmation_event = EventEnvelope(
            event_id=event_id,
            event_type=ErpEventType.COST_CENTER_CREATED,
            event_version=1,
            company_id=event.company_id,
            aggregate_id=event.aggregate_id,
            aggregate_type="construction_unit",
            occurred_at=datetime.now(tz=UTC),
            producer="erp-api",
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            payload={
                "construction_project_id": event.payload["construction_project_id"],
                "construction_unit_id": str(event.aggregate_id),
                "project_synthetic_cost_center_id": event.payload["project_synthetic_cost_center_id"],
                "analytic_cost_center_id": str(uuid4()),
                "analytic_code": "CONST-OBRA-UNIT-UNIDADE-1",
            },
        )
        self.confirmation_events.append(confirmation_event)
        return confirmation_event

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

    async def deliver_event(self, *, event: EventEnvelope) -> EventEnvelope:
        if event.event_type == ConstructionEventType.PROJECT_CREATED:
            return await self.create_cost_center_hierarchy(event=event)

        if event.event_type == ConstructionEventType.UNIT_CREATED:
            return await self.create_unit_cost_center(event=event)

        if event.event_type == ConstructionEventType.MEASUREMENT_APPROVED:
            return await self.create_accounts_payable_from_measurement(event=event)

        if event.event_type == ConstructionEventType.UNIT_SOLD:
            return await self.create_contract_and_receivables_from_unit_sale(event=event)

        if event.event_type == ConstructionEventType.PROCUREMENT_REQUESTED:
            return await self.create_procurement_demand_from_request(event=event)

        raise AssertionError(f"Unsupported fake ERP event type: {event.event_type}")

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


def seed_measurement_axis(*, repository: FakeConstructionRepository, company_id, project_id):
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project_id,
        code="A-101",
        unit_type="apartment",
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    schedule_phase = ConstructionSchedulePhase(
        id=uuid4(),
        company_id=company_id,
        project_id=project_id,
        name="Fundacao",
        sequence_order=1,
        status="planned",
        progress_percent=Decimal("0"),
    )
    repository.units[(company_id, unit.id)] = unit
    repository.schedule_phases[(company_id, schedule_phase.id)] = schedule_phase
    return unit, schedule_phase


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
async def test_create_project_applies_sync_cost_center_confirmation() -> None:
    company_id = uuid4()
    user_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    erp_client = FakeErpMeasurementClient()
    dispatcher = ConstructionIntegrationDispatcher(
        event_repository=event_repository,
        event_transport=erp_client,
        integration_mode=ConstructionIntegrationMode.SYNC_HTTP,
    )
    service = ConstructionProjectService(
        repository=repository,
        event_repository=event_repository,
        erp_client=erp_client,
        integration_dispatcher=dispatcher,
    )

    project = await service.create_project(
        company_id=company_id,
        request=ConstructionProjectCreate(code="OBRA-011", name="Obra Integrada"),
        actor_user_id=user_id,
    )

    confirmation_event = erp_client.confirmation_events[0]
    assert repository.commits == 1
    assert len(event_repository.outbox_events) == 1
    assert len(erp_client.events) == 1
    assert event_repository.outbox_events[0].event_type == ConstructionEventType.PROJECT_CREATED
    assert erp_client.events[0].payload["user_id"] == str(user_id)
    assert project.synthetic_cost_center_id == UUID(str(confirmation_event.payload["synthetic_cost_center_id"]))
    assert project.analytic_cost_center_id == UUID(str(confirmation_event.payload["analytic_cost_center_id"]))


@pytest.mark.asyncio
async def test_create_unit_persists_description() -> None:
    company_id = uuid4()
    project_id = uuid4()
    repository = FakeConstructionRepository()
    repository.projects[(company_id, project_id)] = ConstructionProject(
        id=project_id,
        company_id=company_id,
        code="OBRA-UNIT",
        name="Obra com unidades",
        status=ConstructionProjectStatus.DRAFT,
        synthetic_cost_center_id=uuid4(),
    )
    service = make_service(repository=repository)

    unit = await service.create_unit(
        company_id=company_id,
        project_id=project_id,
        request=ConstructionUnitCreate(
            code="UNIDADE - 1",
            description="UNIDADE - 1",
            unit_type="Apartamento",
        ),
    )

    assert unit.description == "UNIDADE - 1"
    assert unit.code == "UNIDADE - 1"
    assert repository.commits == 1


@pytest.mark.asyncio
async def test_create_unit_applies_sync_cost_center_confirmation() -> None:
    company_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    project_synthetic_cost_center_id = uuid4()
    repository = FakeConstructionRepository()
    repository.projects[(company_id, project_id)] = ConstructionProject(
        id=project_id,
        company_id=company_id,
        code="OBRA-UNIT",
        name="Obra com unidades",
        status=ConstructionProjectStatus.DRAFT,
        synthetic_cost_center_id=project_synthetic_cost_center_id,
    )
    event_repository = FakeEventRepository()
    erp_client = FakeErpMeasurementClient()
    dispatcher = ConstructionIntegrationDispatcher(
        event_repository=event_repository,
        event_transport=erp_client,
        integration_mode=ConstructionIntegrationMode.SYNC_HTTP,
    )
    service = ConstructionProjectService(
        repository=repository,
        event_repository=event_repository,
        erp_client=erp_client,
        integration_dispatcher=dispatcher,
    )

    unit = await service.create_unit(
        company_id=company_id,
        project_id=project_id,
        request=ConstructionUnitCreate(
            code="UNIDADE - 1",
            description="Apartamento 101",
            unit_type="Apartamento",
        ),
        actor_user_id=user_id,
    )

    confirmation_event = erp_client.confirmation_events[0]
    assert repository.commits == 1
    assert len(event_repository.outbox_events) == 1
    assert len(erp_client.events) == 1
    assert event_repository.outbox_events[0].event_type == ConstructionEventType.UNIT_CREATED
    assert erp_client.events[0].payload["project_synthetic_cost_center_id"] == str(project_synthetic_cost_center_id)
    assert erp_client.events[0].payload["user_id"] == str(user_id)
    assert unit.analytic_cost_center_id == UUID(str(confirmation_event.payload["analytic_cost_center_id"]))


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
    unit, schedule_phase = seed_measurement_axis(repository=repository, company_id=company_id, project_id=project.id)
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
            unit_id=unit.id,
            schedule_phase_id=schedule_phase.id,
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
    assert erp_client.events[0].payload["construction_unit_id"] == str(unit.id)
    assert erp_client.events[0].payload["schedule_phase_id"] == str(schedule_phase.id)
    assert erp_client.events[0].payload["analytic_cost_center_id"] == str(unit.analytic_cost_center_id)
    assert any(event.event_type == ConstructionEventType.MEASUREMENT_APPROVED for event in event_repository.outbox_events)


@pytest.mark.asyncio
async def test_async_integration_mode_records_measurement_without_http_delivery() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    event_repository = FakeEventRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-033",
        name="Async measurement project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    repository.projects[(company_id, project.id)] = project
    unit, schedule_phase = seed_measurement_axis(repository=repository, company_id=company_id, project_id=project.id)
    dispatcher = ConstructionIntegrationDispatcher(
        event_repository=event_repository,
        event_transport=erp_client,
        integration_mode=ConstructionIntegrationMode.ASYNC_IN_MEMORY,
    )
    service = ConstructionProjectService(
        repository=repository,
        event_repository=event_repository,
        erp_client=erp_client,
        integration_dispatcher=dispatcher,
    )

    measurement = await service.create_measurement(
        company_id=company_id,
        project_id=project.id,
        request=ConstructionMeasurementCreate(
            code="MED-ASYNC-001",
            unit_id=unit.id,
            schedule_phase_id=schedule_phase.id,
            measured_amount=Decimal("12500.50"),
            due_date=date(2026, 5, 15),
        ),
    )
    approved_measurement = await service.approve_measurement(company_id=company_id, measurement_id=measurement.id)

    assert approved_measurement.status == ConstructionMeasurementStatus.APPROVED
    assert approved_measurement.external_accounts_payable_id is None
    assert len(erp_client.events) == 0
    assert len(event_repository.outbox_events) == 1
    assert event_repository.outbox_events[0].event_type == ConstructionEventType.MEASUREMENT_APPROVED


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
    unit, schedule_phase = seed_measurement_axis(repository=repository, company_id=company_id, project_id=project.id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)

    measurement = await service.create_measurement(
        company_id=company_id,
        project_id=project.id,
        request=ConstructionMeasurementCreate(
            code="MED-002",
            unit_id=unit.id,
            schedule_phase_id=schedule_phase.id,
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
        analytic_cost_center_id=uuid4(),
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
    assert erp_client.events[0].payload["payment_sources"] == [
        {
            "source_type": "direct_builder",
            "amount": "450000.00",
            "due_date": "2026-06-10",
            "installments": 12,
        }
    ]


@pytest.mark.asyncio
async def test_confirm_unit_sale_dispatches_composed_payment_sources() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-041",
        name="Composed unit sales project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="B-202",
        unit_type="apartment",
        sale_price=Decimal("500000.00"),
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("500000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        payment_sources=[
            {
                "source_type": "down_payment",
                "amount": Decimal("50000.00"),
                "due_date": date(2026, 6, 10),
                "installments": 1,
            },
            {
                "source_type": "direct_builder",
                "amount": Decimal("150000.00"),
                "due_date": date(2026, 7, 10),
                "installments": 12,
            },
            {
                "source_type": "fgts",
                "amount": Decimal("30000.00"),
                "due_date": date(2026, 8, 10),
                "installments": 1,
            },
            {
                "source_type": "financing",
                "amount": Decimal("270000.00"),
                "due_date": date(2026, 9, 10),
                "installments": 1,
            },
        ],
    )

    result = await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert result.status == "sold"
    assert erp_client.events[0].payload["payment_sources"] == [
        {"source_type": "down_payment", "amount": "50000.00", "due_date": "2026-06-10", "installments": 1},
        {"source_type": "direct_builder", "amount": "150000.00", "due_date": "2026-07-10", "installments": 12},
        {"source_type": "fgts", "amount": "30000.00", "due_date": "2026-08-10", "installments": 1},
        {"source_type": "financing", "amount": "270000.00", "due_date": "2026-09-10", "installments": 1},
    ]


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
