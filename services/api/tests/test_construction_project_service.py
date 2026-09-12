from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.constants import ConstructionMeasurementStatus, ConstructionProcurementStatus, ConstructionProjectStatus
from app.domain.exceptions import (
    ConstructionDomainError,
    ConstructionDuplicateCodeError,
    ConstructionInvalidStatusTransitionError,
    ConstructionInvalidValueError,
    ConstructionNotFoundError,
)
from app.domain.events.constants import ConstructionEventType, ConstructionIntegrationMode, ErpEventType
from app.domain.events.contracts import EventEnvelope
from app.domain.services import ConstructionIntegrationDispatcher, ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionDocumentationType,
    ConstructionMeasurement,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionMeasurementItemOccurrence,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionServiceTemplate,
    ConstructionServiceTemplateItem,
    ConstructionUnit,
    ConstructionUnitCommission,
    ConstructionUnitDocumentation,
    ConstructionUnitPaymentSource,
)
from app.schemas.construction import (
    ConstructionDocumentationTypeCreate,
    ConstructionDocumentationTypeUpdate,
    ConstructionMeasurementCreate,
    ConstructionMeasurementInspectionVerifyRequest,
    ConstructionMeasurementItemCreate,
    ConstructionMeasurementItemInspectionCreate,
    ConstructionMeasurementItemOccurrenceCreate,
    ConstructionMeasurementItemOccurrenceUpdate,
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
        self.measurement_items: dict[tuple[object, object], ConstructionMeasurementItem] = {}
        self.inspections: dict[tuple[object, object], ConstructionMeasurementItemInspection] = {}
        self.occurrences: dict[tuple[object, object], ConstructionMeasurementItemOccurrence] = {}
        self.unit_payment_sources: dict[tuple[object, object], ConstructionUnitPaymentSource] = {}
        self.service_templates: dict[tuple[object, object], ConstructionServiceTemplate] = {}
        self.service_template_items: dict[tuple[object, object], ConstructionServiceTemplateItem] = {}
        self.documentation_types: dict[tuple[object, object], ConstructionDocumentationType] = {}
        self.unit_documentations: dict[tuple[object, object], ConstructionUnitDocumentation] = {}
        self.unit_commissions: dict[tuple[object, object], ConstructionUnitCommission] = {}
        self.commits = 0
        self.replaced_children = 0

    def _template_items(self, *, company_id, service_template_id):
        return sorted(
            (
                item
                for (item_company_id, _), item in self.service_template_items.items()
                if item_company_id == company_id and item.service_template_id == service_template_id
            ),
            key=lambda item: item.sequence_number,
        )

    async def list_unit_payment_sources(self, *, company_id, unit_id):
        return sorted(
            (
                source
                for (source_company_id, _), source in self.unit_payment_sources.items()
                if source_company_id == company_id and source.unit_id == unit_id
            ),
            key=lambda source: source.source_type,
        )

    async def get_documentation_type(self, *, company_id, documentation_type_id):
        return self.documentation_types.get((company_id, documentation_type_id))

    async def get_documentation_type_by_normalized_name(self, *, company_id, normalized_name):
        return next(
            (
                documentation_type
                for (stored_company_id, _), documentation_type in self.documentation_types.items()
                if stored_company_id == company_id and documentation_type.normalized_name == normalized_name
            ),
            None,
        )

    async def list_documentation_types(self, *, company_id, only_active=True, search=None):
        documentation_types = []
        for (stored_company_id, _), documentation_type in self.documentation_types.items():
            if stored_company_id != company_id:
                continue

            if only_active and not documentation_type.is_active:
                continue

            if search and search.lower() not in documentation_type.name.lower():
                continue

            documentation_types.append(documentation_type)

        return sorted(documentation_types, key=lambda documentation_type: documentation_type.name)

    async def list_documentation_types_by_system_codes(self, *, company_id, system_codes):
        return [
            documentation_type
            for (stored_company_id, _), documentation_type in self.documentation_types.items()
            if stored_company_id == company_id and documentation_type.system_code in set(system_codes)
        ]

    async def upsert_documentation_type_system_code(
        self,
        *,
        company_id,
        name,
        normalized_name,
        system_code,
    ):
        existing = await self.get_documentation_type_by_normalized_name(
            company_id=company_id,
            normalized_name=normalized_name,
        )
        if existing is not None:
            if existing.system_code is None:
                existing.system_code = system_code

            return existing

        documentation_type = ConstructionDocumentationType(
            id=uuid4(),
            company_id=company_id,
            name=name,
            normalized_name=normalized_name,
            system_code=system_code,
            is_active=True,
        )
        self.documentation_types[(company_id, documentation_type.id)] = documentation_type
        return documentation_type

    async def insert_documentation_type_if_absent(self, *, company_id, name, normalized_name):
        existing = await self.get_documentation_type_by_normalized_name(
            company_id=company_id,
            normalized_name=normalized_name,
        )
        if existing is not None:
            return None

        documentation_type = ConstructionDocumentationType(
            id=uuid4(),
            company_id=company_id,
            name=name,
            normalized_name=normalized_name,
            is_active=True,
        )
        self.documentation_types[(company_id, documentation_type.id)] = documentation_type
        return documentation_type

    async def list_unit_documentations(self, *, company_id, unit_id):
        return sorted(
            (
                documentation
                for (stored_company_id, _), documentation in self.unit_documentations.items()
                if stored_company_id == company_id and documentation.unit_id == unit_id
            ),
            key=lambda documentation: documentation.sequence_number,
        )

    async def list_unit_commissions(self, *, company_id, unit_id):
        return sorted(
            (
                commission
                for (stored_company_id, _), commission in self.unit_commissions.items()
                if stored_company_id == company_id and commission.unit_id == unit_id
            ),
            key=lambda commission: commission.sequence_number,
        )

    async def get_unit_commission(self, *, company_id, commission_id):
        return self.unit_commissions.get((company_id, commission_id))

    async def get_next_commission_sequence(self, *, company_id, unit_id):
        commissions = await self.list_unit_commissions(company_id=company_id, unit_id=unit_id)
        if not commissions:
            return 1

        return max(commission.sequence_number for commission in commissions) + 1

    async def get_service_template(self, *, company_id, service_template_id):
        template = self.service_templates.get((company_id, service_template_id))
        if template is not None:
            template.items = self._template_items(
                company_id=company_id,
                service_template_id=service_template_id,
            )

        return template

    async def get_service_template_by_name(self, *, company_id, name):
        for (template_company_id, template_id), template in self.service_templates.items():
            if template_company_id == company_id and template.name == name:
                template.items = self._template_items(
                    company_id=company_id,
                    service_template_id=template_id,
                )
                return template

        return None

    async def list_service_templates(self, *, company_id, only_active=True, search=None):
        templates = []
        for (template_company_id, template_id), template in self.service_templates.items():
            if template_company_id != company_id:
                continue

            if only_active and not template.is_active:
                continue

            if search and search.lower() not in template.name.lower():
                continue

            template.items = self._template_items(
                company_id=company_id,
                service_template_id=template_id,
            )
            templates.append(template)

        return sorted(templates, key=lambda template: template.name)

    async def get_measurement_item(self, *, company_id, item_id):
        return self.measurement_items.get((company_id, item_id))

    async def list_measurement_items(self, *, company_id, measurement_id):
        return sorted(
            (
                item
                for (item_company_id, _), item in self.measurement_items.items()
                if item_company_id == company_id and item.measurement_id == measurement_id
            ),
            key=lambda item: item.sequence_number,
        )

    async def get_next_measurement_item_sequence(self, *, company_id, measurement_id):
        items = await self.list_measurement_items(company_id=company_id, measurement_id=measurement_id)
        if not items:
            return 1

        return max(item.sequence_number for item in items) + 1

    async def get_measurement_items_amount(self, *, company_id, measurement_id):
        items = await self.list_measurement_items(company_id=company_id, measurement_id=measurement_id)
        return sum((item.amount for item in items), Decimal("0"))

    async def get_measurement_inspection(self, *, company_id, inspection_id):
        return self.inspections.get((company_id, inspection_id))

    async def list_measurement_item_inspections(self, *, company_id, measurement_item_id):
        return sorted(
            (
                inspection
                for (inspection_company_id, _), inspection in self.inspections.items()
                if inspection_company_id == company_id and inspection.measurement_item_id == measurement_item_id
            ),
            key=lambda inspection: inspection.sequence_number,
        )

    async def get_next_inspection_sequence(self, *, company_id, measurement_item_id):
        sequences = [
            inspection.sequence_number
            for (inspection_company_id, _), inspection in self.inspections.items()
            if inspection_company_id == company_id and inspection.measurement_item_id == measurement_item_id
        ]
        if not sequences:
            return 1

        return max(sequences) + 1

    async def count_pending_measurement_inspections(self, *, company_id, measurement_id):
        items = await self.list_measurement_items(company_id=company_id, measurement_id=measurement_id)
        item_ids = {item.id for item in items}
        return sum(
            1
            for (inspection_company_id, _), inspection in self.inspections.items()
            if inspection_company_id == company_id
            and inspection.measurement_item_id in item_ids
            and "pending" in {inspection.first_status, inspection.second_status}
        )

    async def get_measurement_occurrence(self, *, company_id, occurrence_id):
        return self.occurrences.get((company_id, occurrence_id))

    async def get_next_occurrence_sequence(self, *, company_id, measurement_item_id):
        sequences = [
            occurrence.sequence_number
            for (occurrence_company_id, _), occurrence in self.occurrences.items()
            if occurrence_company_id == company_id and occurrence.measurement_item_id == measurement_item_id
        ]
        if not sequences:
            return 1

        return max(sequences) + 1

    async def count_open_measurement_occurrences(self, *, company_id, measurement_id):
        items = await self.list_measurement_items(company_id=company_id, measurement_id=measurement_id)
        item_ids = {item.id for item in items}
        return sum(
            1
            for (occurrence_company_id, _), occurrence in self.occurrences.items()
            if occurrence_company_id == company_id
            and occurrence.measurement_item_id in item_ids
            and occurrence.status == "open"
        )

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

        if isinstance(entity, ConstructionUnitPaymentSource):
            self.unit_payment_sources[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionDocumentationType):
            self.documentation_types[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionUnitDocumentation):
            entity.documentation_type = self.documentation_types.get(
                (entity.company_id, entity.documentation_type_id)
            )
            self.unit_documentations[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionUnitCommission):
            self.unit_commissions[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionServiceTemplate):
            self.service_templates[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionServiceTemplateItem):
            self.service_template_items[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionMeasurementItem):
            self.measurement_items[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionMeasurementItemInspection):
            self.inspections[(entity.company_id, entity.id)] = entity
            return

        if isinstance(entity, ConstructionMeasurementItemOccurrence):
            self.occurrences[(entity.company_id, entity.id)] = entity
            return

        self.measurements[(entity.company_id, entity.id)] = entity

    async def commit(self) -> None:
        self.commits += 1

    async def replace_unit_children(self, model, *, company_id, unit_id, entities) -> None:
        rows = self.unit_documentations if model is ConstructionUnitDocumentation else self.unit_payment_sources
        for key in [
            key
            for key, row in rows.items()
            if key[0] == company_id and row.unit_id == unit_id
        ]:
            rows.pop(key, None)

        self.replaced_children += 1
        for entity in entities:
            await self.add(entity)

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
        if isinstance(entity, ConstructionUnitPaymentSource):
            self.unit_payment_sources.pop((entity.company_id, entity.id), None)
            return

        if isinstance(entity, ConstructionUnitDocumentation):
            self.unit_documentations.pop((entity.company_id, entity.id), None)
            return

        if isinstance(entity, ConstructionUnitCommission):
            self.unit_commissions.pop((entity.company_id, entity.id), None)
            return

        if isinstance(entity, ConstructionDocumentationType):
            self.documentation_types.pop((entity.company_id, entity.id), None)
            return

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

    async def list_units(self, *, company_id, project_id):
        return [
            unit
            for (stored_company_id, _), unit in self.units.items()
            if stored_company_id == company_id and unit.project_id == project_id
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
    assert erp_client.events[0].aggregate_id == unit.id
    assert erp_client.events[0].payload["construction_unit_id"] == str(unit.id)
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
async def test_confirm_unit_sale_keeps_one_contract_and_reemits_on_edit() -> None:
    """Reconfirmar e como editar a venda: mesmo contrato, evento novo.

    O evento tem de sair de novo para o ERP reescrever contrato e cobranca. O
    atalho antigo devolvia a unidade intacta e a alteracao morria aqui.
    """
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
    assert second_result.external_receivable_id == first_result.external_receivable_id
    # Dois eventos, um contrato: o ERP reescreve o que ja existe.
    assert len(erp_client.events) == 2
    assert {event.event_type for event in erp_client.events} == {ConstructionEventType.UNIT_SOLD}
    assert any(event.event_type == ConstructionEventType.UNIT_SOLD for event in event_repository.outbox_events)
    assert erp_client.events[0].payload["payment_sources"] == [
        {
            "source_type": "balance",
            "amount": "450000.00",
            "due_date": "2026-06-10",
            "installments": 12,
            "generates_installments": True,
        }
    ]
    assert erp_client.events[0].payload["receivable_amount"] == "450000.00"


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
        {
            "source_type": "down_payment",
            "amount": "50000.00",
            "due_date": "2026-06-10",
            "installments": 1,
            "generates_installments": True,
        },
        {
            "source_type": "fgts",
            "amount": "30000.00",
            "due_date": "2026-08-10",
            "installments": 1,
            "generates_installments": False,
        },
        {
            "source_type": "financing",
            "amount": "270000.00",
            "due_date": "2026-09-10",
            "installments": 1,
            "generates_installments": False,
        },
        {
            # 500.000 - 50.000 de entrada - 30.000 de FGTS - 270.000 financiados.
            # Ninguem digitou este valor: e o que sobra do preco da venda.
            "source_type": "balance",
            "amount": "150000.00",
            "due_date": "2026-06-10",
            "installments": 12,
            "generates_installments": True,
        },
    ]
    assert erp_client.events[0].payload["receivable_amount"] == "200000.00"


async def _build_measurement_scenario(*, measured_amount: Decimal = Decimal("10000.00")):
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-060",
        name="Measurement items project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="D-401",
        unit_type="apartment",
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    measurement = ConstructionMeasurement(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        unit_id=unit.id,
        schedule_phase_id=uuid4(),
        code="MED-060",
        sequence_number=1,
        gross_amount=measured_amount,
        retentions_amount=Decimal("0"),
        net_amount=measured_amount,
        measured_amount=measured_amount,
        due_date=date(2026, 7, 10),
        status=ConstructionMeasurementStatus.DRAFT,
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    repository.measurements[(company_id, measurement.id)] = measurement
    service = ConstructionProjectService(repository=repository, erp_client=FakeErpMeasurementClient())
    return company_id, measurement, service


@pytest.mark.asyncio
async def test_measurement_amount_follows_the_sum_of_its_items() -> None:
    company_id, measurement, service = await _build_measurement_scenario()

    await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(
            description="Alvenaria de vedacao",
            amount=Decimal("4500.00"),
        ),
    )
    await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(
            description="Contrapiso",
            amount=Decimal("2500.50"),
        ),
    )

    assert measurement.gross_amount == Decimal("7000.50")
    assert measurement.net_amount == Decimal("7000.50")
    assert measurement.measured_amount == Decimal("7000.50")


@pytest.mark.asyncio
async def test_measurement_item_sequence_is_generated_per_measurement() -> None:
    company_id, measurement, service = await _build_measurement_scenario()

    first_item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Servico A", amount=Decimal("100.00")),
    )
    second_item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Servico B", amount=Decimal("200.00")),
    )

    assert first_item.sequence_number == 1
    assert second_item.sequence_number == 2


@pytest.mark.asyncio
async def test_approved_measurement_refuses_new_items() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    measurement.status = ConstructionMeasurementStatus.APPROVED

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(description="Servico extra", amount=Decimal("100.00")),
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_LOCKED"


@pytest.mark.asyncio
async def test_item_period_rejects_end_date_before_start_date() -> None:
    company_id, measurement, service = await _build_measurement_scenario()

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(
                description="Servico com periodo invertido",
                amount=Decimal("100.00"),
                start_date=date(2026, 7, 20),
                end_date=date(2026, 7, 10),
            ),
        )

    assert error.value.error_code == "CONSTRUCTION_INVALID_PERIOD"


@pytest.mark.asyncio
async def test_second_inspection_check_requires_the_first_one() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Impermeabilizacao", amount=Decimal("800.00")),
    )
    inspection = await service.create_measurement_item_inspection(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemInspectionCreate(
            description="Teste de estanqueidade",
            verification_method="Lamina de agua por 72h",
        ),
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.verify_measurement_item_inspection(
            company_id=company_id,
            inspection_id=inspection.id,
            request=ConstructionMeasurementInspectionVerifyRequest(check_number=2, status="compliant"),
            actor_user_id=uuid4(),
        )

    assert error.value.error_code == "CONSTRUCTION_INSPECTION_FIRST_CHECK_REQUIRED"


@pytest.mark.asyncio
async def test_second_inspection_check_requires_a_different_verifier() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Impermeabilizacao", amount=Decimal("800.00")),
    )
    inspection = await service.create_measurement_item_inspection(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemInspectionCreate(description="Teste de estanqueidade"),
    )
    first_verifier_id = uuid4()

    await service.verify_measurement_item_inspection(
        company_id=company_id,
        inspection_id=inspection.id,
        request=ConstructionMeasurementInspectionVerifyRequest(check_number=1, status="compliant"),
        actor_user_id=first_verifier_id,
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.verify_measurement_item_inspection(
            company_id=company_id,
            inspection_id=inspection.id,
            request=ConstructionMeasurementInspectionVerifyRequest(check_number=2, status="compliant"),
            actor_user_id=first_verifier_id,
        )

    assert error.value.error_code == "CONSTRUCTION_INSPECTION_SAME_VERIFIER"


@pytest.mark.asyncio
async def test_item_becomes_compliant_only_after_both_checks_pass() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Pintura", amount=Decimal("1200.00")),
    )
    inspection = await service.create_measurement_item_inspection(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemInspectionCreate(description="Uniformidade da tinta"),
    )

    await service.verify_measurement_item_inspection(
        company_id=company_id,
        inspection_id=inspection.id,
        request=ConstructionMeasurementInspectionVerifyRequest(check_number=1, status="compliant"),
        actor_user_id=uuid4(),
    )

    assert item.inspection_status == "pending"

    await service.verify_measurement_item_inspection(
        company_id=company_id,
        inspection_id=inspection.id,
        request=ConstructionMeasurementInspectionVerifyRequest(check_number=2, status="compliant"),
        actor_user_id=uuid4(),
    )

    assert item.inspection_status == "compliant"
    assert inspection.is_double_checked is True


@pytest.mark.asyncio
async def test_non_compliant_check_marks_the_whole_item_as_non_compliant() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Pintura", amount=Decimal("1200.00")),
    )
    inspection = await service.create_measurement_item_inspection(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemInspectionCreate(description="Uniformidade da tinta"),
    )

    await service.verify_measurement_item_inspection(
        company_id=company_id,
        inspection_id=inspection.id,
        request=ConstructionMeasurementInspectionVerifyRequest(check_number=1, status="non_compliant"),
        actor_user_id=uuid4(),
    )

    assert item.inspection_status == "non_compliant"


@pytest.mark.asyncio
async def test_occurrence_requires_solution_to_be_resolved() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Esquadrias", amount=Decimal("900.00")),
    )
    occurrence = await service.create_measurement_item_occurrence(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemOccurrenceCreate(problem="Janela desalinhada"),
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.update_measurement_item_occurrence(
            company_id=company_id,
            occurrence_id=occurrence.id,
            request=ConstructionMeasurementItemOccurrenceUpdate(status="resolved"),
        )

    assert error.value.error_code == "CONSTRUCTION_OCCURRENCE_SOLUTION_REQUIRED"

    resolved_occurrence = await service.update_measurement_item_occurrence(
        company_id=company_id,
        occurrence_id=occurrence.id,
        request=ConstructionMeasurementItemOccurrenceUpdate(
            status="resolved",
            solution="Esquadria reinstalada e conferida",
        ),
    )

    assert resolved_occurrence.status == "resolved"
    assert resolved_occurrence.closed_at is not None


@pytest.mark.asyncio
async def test_submit_and_approve_record_who_did_each_step() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    submitter_id = uuid4()
    approver_id = uuid4()

    await service.submit_measurement(
        company_id=company_id,
        measurement_id=measurement.id,
        actor_user_id=submitter_id,
    )

    assert measurement.status == ConstructionMeasurementStatus.SUBMITTED
    assert measurement.submitted_by_user_id == submitter_id
    assert measurement.submitted_at is not None

    await service.approve_measurement(
        company_id=company_id,
        measurement_id=measurement.id,
        actor_user_id=approver_id,
    )

    assert measurement.status == ConstructionMeasurementStatus.APPROVED
    assert measurement.approved_by_user_id == approver_id
    assert measurement.approved_at is not None


@pytest.mark.asyncio
async def test_approval_refuses_the_user_who_submitted_the_measurement() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    submitter_id = uuid4()

    await service.submit_measurement(
        company_id=company_id,
        measurement_id=measurement.id,
        actor_user_id=submitter_id,
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.approve_measurement(
            company_id=company_id,
            measurement_id=measurement.id,
            actor_user_id=submitter_id,
        )

    assert error.value.error_code == "CONSTRUCTION_MEASUREMENT_SELF_APPROVAL"
    assert measurement.status == ConstructionMeasurementStatus.SUBMITTED


@pytest.mark.asyncio
async def test_rejection_records_who_rejected_and_is_cleared_on_resubmit() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    rejecter_id = uuid4()

    await service.reject_measurement(
        company_id=company_id,
        measurement_id=measurement.id,
        reason="Faltou o relatorio de inspecao",
        actor_user_id=rejecter_id,
    )

    assert measurement.status == ConstructionMeasurementStatus.REJECTED
    assert measurement.rejected_by_user_id == rejecter_id
    assert measurement.rejected_at is not None

    await service.submit_measurement(
        company_id=company_id,
        measurement_id=measurement.id,
        actor_user_id=uuid4(),
    )

    assert measurement.rejection_reason is None
    assert measurement.rejected_by_user_id is None
    assert measurement.rejected_at is None


@pytest.mark.asyncio
async def test_measurement_items_summary_counts_pending_checks_and_open_occurrences() -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Cobertura", amount=Decimal("3200.00")),
    )
    await service.create_measurement_item_inspection(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemInspectionCreate(description="Alinhamento das telhas"),
    )
    await service.create_measurement_item_occurrence(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemOccurrenceCreate(problem="Telha trincada"),
    )

    summary = await service.build_measurement_items_summary(
        company_id=company_id,
        measurement_id=measurement.id,
    )

    assert summary["items_count"] == 1
    assert summary["items_total_amount"] == Decimal("3200.00")
    assert summary["pending_inspections_count"] == 1
    assert summary["open_occurrences_count"] == 1


def _build_sale_scenario(*, project_code: str, unit_code: str, sale_price: Decimal):
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code=project_code,
        name="Sale details project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code=unit_code,
        unit_type="apartment",
        sale_price=sale_price,
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    return company_id, unit, service, erp_client


@pytest.mark.asyncio
async def test_confirm_unit_sale_composition_matches_price_net_of_discount() -> None:
    company_id, unit, service, erp_client = _build_sale_scenario(
        project_code="OBRA-050",
        unit_code="C-301",
        sale_price=Decimal("400000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("400000.00"),
        discount_amount=Decimal("40000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        payment_sources=[
            {
                "source_type": "down_payment",
                "amount": Decimal("60000.00"),
                "due_date": date(2026, 6, 10),
                "installments": 1,
            },
        ],
    )

    result = await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert result.status == "sold"
    assert result.sale_price == Decimal("400000.00")
    assert result.discount_amount == Decimal("40000.00")
    assert result.net_sale_price == Decimal("360000.00")
    assert erp_client.events[0].payload["discount_amount"] == "40000.00"
    assert erp_client.events[0].payload["net_sale_price"] == "360000.00"
    # 60.000 de entrada + 300.000 de saldo (400.000 - 40.000 de desconto - 60.000).
    assert erp_client.events[0].payload["receivable_amount"] == "360000.00"
    assert erp_client.events[0].payload["payment_sources"][-1] == {
        "source_type": "balance",
        "amount": "300000.00",
        "due_date": "2026-06-10",
        "installments": 12,
        "generates_installments": True,
    }


@pytest.mark.asyncio
async def test_confirm_unit_sale_rejects_composition_that_ignores_discount() -> None:
    """Informar o preco cheio ignorando o desconto estoura o preco da venda."""
    company_id, unit, service, _ = _build_sale_scenario(
        project_code="OBRA-051",
        unit_code="C-302",
        sale_price=Decimal("400000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("400000.00"),
        discount_amount=Decimal("40000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
        payment_sources=[
            {
                "source_type": "financing",
                "amount": Decimal("400000.00"),
                "due_date": date(2026, 6, 10),
                "installments": 1,
            },
        ],
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_UNIT_PAYMENT_SOURCES_TOTAL_MISMATCH"
    assert unit.status == "available"


def test_unit_sale_request_does_not_accept_a_typed_balance() -> None:
    """O saldo e calculado: se pudesse ser digitado, a conta do legado sumiria."""
    for source_type in ("balance", "direct_builder"):
        with pytest.raises(PydanticValidationError):
            ConstructionUnitSaleConfirmRequest(
                buyer_person_id=uuid4(),
                sale_price=Decimal("400000.00"),
                first_due_date=date(2026, 6, 10),
                installments=1,
                payment_sources=[
                    {
                        "source_type": source_type,
                        "amount": Decimal("400000.00"),
                        "due_date": date(2026, 6, 10),
                        "installments": 1,
                    },
                ],
            )


@pytest.mark.asyncio
async def test_bank_released_sources_do_not_become_installments() -> None:
    company_id, unit, service, erp_client = _build_sale_scenario(
        project_code="OBRA-056",
        unit_code="C-307",
        sale_price=Decimal("300000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
        payment_sources=[
            {
                "source_type": "down_payment",
                "amount": Decimal("20000.00"),
                "due_date": date(2026, 6, 10),
                "installments": 2,
            },
            {
                "source_type": "government_subsidy",
                "amount": Decimal("30000.00"),
                "due_date": date(2026, 7, 10),
                "installments": 1,
            },
            {
                "source_type": "fgts",
                "amount": Decimal("50000.00"),
                "due_date": date(2026, 7, 10),
                "installments": 1,
            },
            {
                "source_type": "financing",
                "amount": Decimal("200000.00"),
                "due_date": date(2026, 8, 10),
                "installments": 1,
            },
        ],
    )

    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    payload = erp_client.events[0].payload
    installment_sources = [
        source for source in payload["payment_sources"] if source["generates_installments"]
    ]
    settlement_sources = [
        source for source in payload["payment_sources"] if not source["generates_installments"]
    ]

    assert [source["source_type"] for source in installment_sources] == ["down_payment"]
    assert sorted(source["source_type"] for source in settlement_sources) == [
        "fgts",
        "financing",
        "government_subsidy",
    ]
    assert payload["receivable_amount"] == "20000.00"

    composition = await service.build_unit_sale_composition(company_id=company_id, unit_id=unit.id)

    assert composition["installment_total"] == Decimal("20000.00")
    assert composition["settlement_total"] == Decimal("280000.00")


@pytest.mark.asyncio
async def test_bank_released_source_cannot_be_split_into_installments() -> None:
    company_id, unit, service, _ = _build_sale_scenario(
        project_code="OBRA-057",
        unit_code="C-308",
        sale_price=Decimal("300000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
        payment_sources=[
            {
                "source_type": "down_payment",
                "amount": Decimal("100000.00"),
                "due_date": date(2026, 6, 10),
                "installments": 1,
            },
            {
                "source_type": "financing",
                "amount": Decimal("200000.00"),
                "due_date": date(2026, 8, 10),
                "installments": 24,
            },
        ],
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_UNIT_SETTLEMENT_SOURCE_NOT_INSTALLMENTABLE"


@pytest.mark.asyncio
async def test_sale_only_with_bank_released_sources_is_refused() -> None:
    company_id, unit, service, _ = _build_sale_scenario(
        project_code="OBRA-058",
        unit_code="C-309",
        sale_price=Decimal("300000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
        payment_sources=[
            {
                "source_type": "financing",
                "amount": Decimal("300000.00"),
                "due_date": date(2026, 8, 10),
                "installments": 1,
            },
        ],
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_UNIT_WITHOUT_INSTALLMENT_SOURCE"


@pytest.mark.asyncio
async def test_confirm_unit_sale_without_composition_charges_price_net_of_discount() -> None:
    company_id, unit, service, erp_client = _build_sale_scenario(
        project_code="OBRA-052",
        unit_code="C-303",
        sale_price=Decimal("200000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("200000.00"),
        discount_amount=Decimal("20000.00"),
        first_due_date=date(2026, 6, 10),
        installments=10,
    )

    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert erp_client.events[0].payload["payment_sources"] == [
        {
            "source_type": "balance",
            "amount": "180000.00",
            "due_date": "2026-06-10",
            "installments": 10,
            "generates_installments": True,
        }
    ]


@pytest.mark.asyncio
async def test_confirm_unit_sale_rejects_discount_equal_to_sale_price() -> None:
    company_id, unit, service, _ = _build_sale_scenario(
        project_code="OBRA-053",
        unit_code="C-304",
        sale_price=Decimal("150000.00"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("150000.00"),
        discount_amount=Decimal("150000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_UNIT_DISCOUNT_EXCEEDS_SALE_PRICE"


@pytest.mark.asyncio
async def test_confirm_unit_sale_rejects_secondary_buyer_equal_to_buyer() -> None:
    company_id, unit, service, _ = _build_sale_scenario(
        project_code="OBRA-054",
        unit_code="C-305",
        sale_price=Decimal("150000.00"),
    )
    buyer_person_id = uuid4()

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=buyer_person_id,
        secondary_buyer_person_id=buyer_person_id,
        sale_price=Decimal("150000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_UNIT_DUPLICATE_BUYER"


@pytest.mark.asyncio
async def test_confirm_unit_sale_persists_broker_signature_and_notes() -> None:
    company_id, unit, service, erp_client = _build_sale_scenario(
        project_code="OBRA-055",
        unit_code="C-306",
        sale_price=Decimal("300000.00"),
    )
    secondary_buyer_person_id = uuid4()
    broker_person_id = uuid4()

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        secondary_buyer_person_id=secondary_buyer_person_id,
        broker_person_id=broker_person_id,
        sale_price=Decimal("300000.00"),
        contract_signature_date=date(2026, 5, 28),
        sale_notes="  Entrega das chaves apos quitacao da entrada.  ",
        first_due_date=date(2026, 6, 10),
        installments=24,
    )

    result = await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert result.secondary_buyer_person_id == secondary_buyer_person_id
    assert result.broker_person_id == broker_person_id
    assert result.contract_signature_date == date(2026, 5, 28)
    assert result.sale_notes == "Entrega das chaves apos quitacao da entrada."

    payload = erp_client.events[0].payload

    assert payload["secondary_buyer_person_id"] == str(secondary_buyer_person_id)
    assert payload["broker_person_id"] == str(broker_person_id)
    assert payload["contract_signature_date"] == "2026-05-28"
    assert payload["sale_notes"] == "Entrega das chaves apos quitacao da entrada."


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


@pytest.mark.asyncio
async def test_confirm_unit_sale_edit_changes_buyer_and_composition() -> None:
    """Editar a venda tem de mudar de verdade o que o usuario alterou."""
    company_id, unit, service, erp_client = _build_sale_scenario(
        project_code="OBRA-053",
        unit_code="C-304",
        sale_price=Decimal("300000.00"),
    )

    first_buyer = uuid4()
    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=first_buyer,
            sale_price=Decimal("300000.00"),
            first_due_date=date(2026, 6, 10),
            installments=10,
        ),
    )

    second_buyer = uuid4()
    broker = uuid4()
    result = await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=second_buyer,
            broker_person_id=broker,
            sale_price=Decimal("320000.00"),
            discount_amount=Decimal("20000.00"),
            first_due_date=date(2026, 7, 10),
            installments=6,
            payment_sources=[
                {
                    "source_type": "financing",
                    "amount": Decimal("200000.00"),
                    "due_date": date(2026, 8, 10),
                    "installments": 1,
                },
            ],
        ),
    )

    assert result.buyer_person_id == second_buyer
    assert result.broker_person_id == broker
    assert result.sale_price == Decimal("320000.00")
    assert result.discount_amount == Decimal("20000.00")

    ultimo_evento = erp_client.events[-1].payload
    assert ultimo_evento["buyer_person_id"] == str(second_buyer)
    # 320.000 - 20.000 de desconto - 200.000 financiados = 100.000 de saldo.
    assert ultimo_evento["receivable_amount"] == "100000.00"
    assert ultimo_evento["payment_sources"][-1] == {
        "source_type": "balance",
        "amount": "100000.00",
        "due_date": "2026-07-10",
        "installments": 6,
        "generates_installments": True,
    }


def _build_summary_scenario():
    """Obra com uma unidade vendida e recebivel no ERP."""
    company_id = uuid4()
    repository = FakeConstructionRepository()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-RESUMO",
        name="Resumo project",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="UN-RESUMO",
        unit_type="apartment",
        sale_price=Decimal("300000.00"),
        discount_amount=Decimal("10000.00"),
        analytic_cost_center_id=uuid4(),
        status="sold",
        external_receivable_id=uuid4(),
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    return company_id, project, unit, repository


class FakeReceivablesSummaryClient:
    """Registra como o resumo foi pedido ao ERP."""

    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.failure = failure

    async def get_receivables_summary(self, *, company_id, user_id, receivable_ids):
        self.calls.append({"company_id": company_id, "user_id": user_id, "receivable_ids": receivable_ids})
        if self.failure is not None:
            raise self.failure

        return {
            "receivables_count": 1,
            "total_amount": "290000.00",
            "paid_amount": "90000.00",
            "open_amount": "200000.00",
            "overdue_amount": "0",
            "overdue_count": 0,
        }


@pytest.mark.asyncio
async def test_project_summary_tells_the_erp_who_is_asking() -> None:
    """Sem o usuario o ERP nao avalia permissao e devolve 403."""
    company_id, project, _, repository = _build_summary_scenario()
    erp_client = FakeReceivablesSummaryClient()
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    user_id = uuid4()

    summary = await service.build_project_summary(
        company_id=company_id,
        project_id=project.id,
        user_id=user_id,
    )

    assert erp_client.calls[0]["user_id"] == user_id
    assert summary["received_amount"] == Decimal("90000.00")
    assert summary["open_amount"] == Decimal("200000.00")
    assert summary["erp_unavailable_reason"] is None


@pytest.mark.asyncio
async def test_project_summary_survives_an_erp_refusal_without_leaking_the_url() -> None:
    """Recusa do ERP nao derruba o resumo comercial nem vaza endereco interno."""
    company_id, project, _, repository = _build_summary_scenario()
    refusal = httpx.HTTPStatusError(
        "Client error '403 Forbidden' for url 'http://onave-api:8000/v1/internal/construction/receivables-summary'",
        request=httpx.Request("POST", "http://onave-api:8000/v1/internal/construction/receivables-summary"),
        response=httpx.Response(403),
    )
    service = ConstructionProjectService(
        repository=repository,
        erp_client=FakeReceivablesSummaryClient(failure=refusal),
    )

    summary = await service.build_project_summary(
        company_id=company_id,
        project_id=project.id,
        user_id=uuid4(),
    )

    assert summary["units_sold_count"] == 1
    assert summary["units_sold_amount"] == Decimal("300000.00")
    assert summary["discount_amount"] == Decimal("10000.00")
    assert summary["received_amount"] == Decimal("0")
    assert "permiss" in summary["erp_unavailable_reason"]
    assert "http" not in summary["erp_unavailable_reason"]


def build_sale_scenario(*, sale_price="300000.00"):
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code="OBRA-DOC",
        name="Unit sale with documentation",
        status=ConstructionProjectStatus.ACTIVE,
        analytic_cost_center_id=uuid4(),
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="D-101",
        unit_type="house",
        sale_price=Decimal(sale_price),
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    return company_id, repository, erp_client, unit, service


async def test_documentation_is_diluted_into_the_balance_the_buyer_still_owes() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        payment_sources=[
            {
                "source_type": "financing",
                "amount": Decimal("200000.00"),
                "due_date": date(2026, 9, 10),
                "installments": 1,
            }
        ],
        documentations=[
            {"name": "Cartório", "amount": Decimal("5000.00")},
        ],
    )

    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    payload = erp_client.events[0].payload
    balance = next(
        source for source in payload["payment_sources"] if source["source_type"] == "balance"
    )
    assert balance["amount"] == "105000.00"
    assert payload["receivable_amount"] == "105000.00"
    assert payload["documentation_total"] == "5000.00"
    assert payload["documentations"] == [
        {
            "documentation_type_id": payload["documentations"][0]["documentation_type_id"],
            "name": "Cartório",
            "amount": "5000.00",
            "sequence_number": 1,
        }
    ]


async def test_documentation_type_is_reused_regardless_of_the_typed_case() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    existing = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[{"name": "  sanesul ", "amount": Decimal("298.20")}],
    )

    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    payload = erp_client.events[0].payload
    assert payload["documentations"][0]["documentation_type_id"] == str(existing.id)
    assert payload["documentations"][0]["name"] == "SANESUL"
    assert len(repository.documentation_types) == 1


async def test_the_same_documentation_type_twice_in_one_sale_is_refused() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[
            {"name": "Cartório", "amount": Decimal("1000.00")},
            {"name": "  cartório ", "amount": Decimal("500.00")},
        ],
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_UNIT_DOCUMENTATION_DUPLICATE_TYPE"


async def test_an_inactive_documentation_type_is_refused_on_a_new_sale() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    documentation_type = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=documentation_type.id,
        request=ConstructionDocumentationTypeUpdate(is_active=False),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[
            {"documentation_type_id": documentation_type.id, "amount": Decimal("298.20")},
        ],
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_DOCUMENTATION_TYPE_INACTIVE"


async def test_an_inactive_type_already_used_by_the_sale_still_allows_editing_it() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    documentation_type = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    first_request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[
            {"documentation_type_id": documentation_type.id, "amount": Decimal("298.20")},
        ],
    )
    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=first_request)
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=documentation_type.id,
        request=ConstructionDocumentationTypeUpdate(is_active=False),
    )

    edit_request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[
            {"documentation_type_id": documentation_type.id, "amount": Decimal("298.20")},
        ],
    )
    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=edit_request)

    documentations = await repository.list_unit_documentations(company_id=company_id, unit_id=unit.id)
    assert len(documentations) == 1
    assert repository.replaced_children > 0


async def test_editing_the_sale_without_documentation_clears_what_was_there() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    first_request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[{"name": "Cartório", "amount": Decimal("2521.40")}],
    )
    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=first_request)

    edit_request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[],
    )
    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=edit_request)

    assert await repository.list_unit_documentations(company_id=company_id, unit_id=unit.id) == []
    assert erp_client.events[-1].payload["documentation_total"] == "0.00"
    assert erp_client.events[-1].payload["receivable_amount"] == "300000.00"


async def test_sale_composition_exposes_the_documentation_and_the_total_charged() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        discount_amount=Decimal("10000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[
            {"name": "Cartório", "amount": Decimal("2521.40")},
            {"name": "SANESUL", "amount": Decimal("298.20")},
        ],
    )
    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    composition = await service.build_unit_sale_composition(company_id=company_id, unit_id=unit.id)

    assert composition["documentation_total"] == Decimal("2819.60")
    assert composition["total_charged"] == Decimal("292819.60")
    assert [item["name"] for item in composition["documentations"]] == ["Cartório", "SANESUL"]
    assert [item["sequence_number"] for item in composition["documentations"]] == [1, 2]


async def test_documentation_larger_than_the_sale_still_has_a_balance_to_charge() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=1,
        payment_sources=[
            {
                "source_type": "financing",
                "amount": Decimal("300000.00"),
                "due_date": date(2026, 9, 10),
                "installments": 1,
            }
        ],
        documentations=[{"name": "Cartório", "amount": Decimal("2521.40")}],
    )

    await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert erp_client.events[0].payload["receivable_amount"] == "2521.40"


async def test_the_erp_refusal_reaches_the_user_instead_of_a_generic_gateway_error() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()

    async def refuse_event(*, event):
        raise httpx.HTTPStatusError(
            "conflict",
            request=httpx.Request("POST", "http://erp/v1/internal/construction/unit-sold-event"),
            response=httpx.Response(
                409,
                json={"message": "O total da venda ficou abaixo do que já foi pago."},
            ),
        )

    erp_client.deliver_event = refuse_event

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[{"name": "Cartório", "amount": Decimal("2521.40")}],
    )

    with pytest.raises(ConstructionDomainError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.status_code == 409
    assert "já foi pago" in error.value.message
    assert repository.commits == 0


async def test_typing_the_name_of_an_inactive_type_does_not_resurrect_it_on_a_new_sale() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    documentation_type = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=documentation_type.id,
        request=ConstructionDocumentationTypeUpdate(is_active=False),
    )

    request = ConstructionUnitSaleConfirmRequest(
        buyer_person_id=uuid4(),
        sale_price=Decimal("300000.00"),
        first_due_date=date(2026, 6, 10),
        installments=12,
        documentations=[{"name": "sanesul", "amount": Decimal("298.20")}],
    )

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.confirm_unit_sale(company_id=company_id, unit_id=unit.id, request=request)

    assert error.value.error_code == "CONSTRUCTION_DOCUMENTATION_TYPE_INACTIVE"
    assert repository.documentation_types[(company_id, documentation_type.id)].is_active is False


async def test_typing_the_name_of_an_inactive_type_the_sale_already_used_still_works() -> None:
    company_id, repository, erp_client, unit, service = build_sale_scenario()
    documentation_type = await service.create_documentation_type(
        company_id=company_id,
        request=ConstructionDocumentationTypeCreate(name="SANESUL"),
    )
    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("300000.00"),
            first_due_date=date(2026, 6, 10),
            installments=12,
            documentations=[{"documentation_type_id": documentation_type.id, "amount": Decimal("298.20")}],
        ),
    )
    await service.update_documentation_type(
        company_id=company_id,
        documentation_type_id=documentation_type.id,
        request=ConstructionDocumentationTypeUpdate(is_active=False),
    )

    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("300000.00"),
            first_due_date=date(2026, 6, 10),
            installments=12,
            documentations=[{"name": "SANESUL", "amount": Decimal("350.00")}],
        ),
    )

    documentations = await repository.list_unit_documentations(company_id=company_id, unit_id=unit.id)
    assert [documentation.amount for documentation in documentations] == [Decimal("350.00")]
