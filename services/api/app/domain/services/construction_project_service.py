from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.domain.constants import (
    BLOCK_STATUSES,
    CONSTRUCTION_PROCUREMENT_APPROVAL_THRESHOLD,
    ConstructionMeasurementStatus,
    ConstructionProcurementStatus,
    PROJECT_TYPES,
    ConstructionUnitStatus,
    PROJECT_STATUS_TRANSITIONS,
    PROJECT_STATUSES,
    SCHEDULE_PHASE_STATUSES,
    UNIT_STATUSES,
)
from app.domain.exceptions import (
    ConstructionDuplicateCodeError,
    ConstructionInvalidStatusTransitionError,
    ConstructionInvalidValueError,
    ConstructionNotFoundError,
)
from app.domain.events.constants import (
    ConstructionAggregateType,
    ConstructionConsumerName,
    ConstructionEventType,
    ErpEventType,
    EventProducer,
)
from app.domain.events.contracts import EventEnvelope
from app.domain.services.construction_integration_dispatcher import ConstructionIntegrationDispatchResult
from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionMeasurement,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionUnit,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.schemas.construction import (
    ConstructionBlockCreate,
    ConstructionBlockUpdate,
    ConstructionProjectCreate,
    ConstructionProjectUpdate,
    ConstructionProcurementRequestCreate,
    ConstructionProcurementRequestUpdate,
    ConstructionMeasurementCreate,
    ConstructionMeasurementUpdate,
    ConstructionSchedulePhaseCreate,
    ConstructionSchedulePhaseUpdate,
    ConstructionUnitCreate,
    ConstructionUnitReserveRequest,
    ConstructionUnitSaleConfirmRequest,
    ConstructionUnitUpdate,
)


class ErpMeasurementClient(Protocol):
    async def list_person_summaries(
        self,
        *,
        company_id: UUID,
        user_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def create_accounts_payable_from_measurement(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError

    async def create_contract_and_receivables_from_unit_sale(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError

    async def create_procurement_demand_from_request(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError

    async def deliver_event(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError


class ConstructionEventDispatcher(Protocol):
    async def dispatch(self, *, event: EventEnvelope):
        raise NotImplementedError


class ConstructionProjectService:
    def __init__(
        self,
        repository: ConstructionRepository,
        event_repository: EventRepository | None = None,
        erp_client: ErpMeasurementClient | None = None,
        integration_dispatcher: ConstructionEventDispatcher | None = None,
    ) -> None:
        self.repository = repository
        self.event_repository = event_repository
        self.erp_client = erp_client
        self.integration_dispatcher = integration_dispatcher

    async def create_project(
        self,
        *,
        company_id: UUID,
        request: ConstructionProjectCreate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionProject:
        self._ensure_known_value(value=request.status, allowed_values=PROJECT_STATUSES, field_name="status")
        self._ensure_known_value(value=request.project_type, allowed_values=PROJECT_TYPES, field_name="project_type")
        existing_project = await self.repository.get_project_by_code(company_id=company_id, code=request.code)
        if existing_project:
            raise ConstructionDuplicateCodeError(resource_name="Construction project", code=request.code)

        project = ConstructionProject(
            id=uuid4(),
            company_id=company_id,
            code=request.code.strip(),
            name=request.name.strip(),
            description=request.description,
            status=request.status,
            project_type=request.project_type,
            customer_person_id=request.customer_person_id,
            cnpj_spe=request.cnpj_spe.strip() if request.cnpj_spe else None,
            address_json=request.address_json,
            start_date=request.start_date,
            expected_end_date=request.expected_end_date,
            actual_end_date=request.actual_end_date,
        )
        await self.repository.add(project)
        project_created_event = self._build_project_created_event(project=project, actor_user_id=actor_user_id)
        dispatch_result = await self._dispatch_integration_event(event=project_created_event)
        if dispatch_result is not None and dispatch_result.response_event is not None:
            self._apply_cost_center_snapshot_from_event(project=project, event=dispatch_result.response_event)

        await self.repository.commit()
        await self.repository.refresh(project)
        return project

    async def apply_cost_center_created_event(self, *, event: EventEnvelope) -> ConstructionProject:
        if event.event_type != ErpEventType.COST_CENTER_CREATED:
            raise ConstructionInvalidValueError(
                message="Unsupported ERP event type for cost center confirmation.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        project_id = self._read_uuid_payload(payload=event.payload, field_name="construction_project_id")
        project = await self.get_project(company_id=event.company_id, project_id=project_id)

        if self.event_repository is not None:
            should_process_event = await self.event_repository.mark_processed(
                consumer_name=ConstructionConsumerName.COST_CENTER_CREATED,
                event=event,
            )
            if not should_process_event:
                return project

        synthetic_cost_center_id = self._read_uuid_payload(payload=event.payload, field_name="synthetic_cost_center_id")
        analytic_cost_center_id = self._read_uuid_payload(payload=event.payload, field_name="analytic_cost_center_id")
        self._ensure_external_id_can_be_applied(
            current_id=project.synthetic_cost_center_id,
            next_id=synthetic_cost_center_id,
            field_name="synthetic_cost_center_id",
        )
        self._ensure_external_id_can_be_applied(
            current_id=project.analytic_cost_center_id,
            next_id=analytic_cost_center_id,
            field_name="analytic_cost_center_id",
        )

        project.synthetic_cost_center_id = synthetic_cost_center_id
        project.analytic_cost_center_id = analytic_cost_center_id
        await self.repository.commit()
        await self.repository.refresh(project)
        return project

    @staticmethod
    def _apply_cost_center_snapshot_from_event(*, project: ConstructionProject, event: EventEnvelope) -> None:
        if event.event_type != ErpEventType.COST_CENTER_CREATED:
            raise ConstructionInvalidValueError(
                message="Unsupported ERP event type for cost center confirmation.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        project_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="construction_project_id",
        )
        if project_id != project.id:
            raise ConstructionInvalidValueError(
                message="Cost center confirmation does not belong to the created construction project.",
                error_code="CONSTRUCTION_COST_CENTER_PROJECT_MISMATCH",
            )

        synthetic_cost_center_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="synthetic_cost_center_id",
        )
        analytic_cost_center_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="analytic_cost_center_id",
        )
        ConstructionProjectService._ensure_external_id_can_be_applied(
            current_id=project.synthetic_cost_center_id,
            next_id=synthetic_cost_center_id,
            field_name="synthetic_cost_center_id",
        )
        ConstructionProjectService._ensure_external_id_can_be_applied(
            current_id=project.analytic_cost_center_id,
            next_id=analytic_cost_center_id,
            field_name="analytic_cost_center_id",
        )

        project.synthetic_cost_center_id = synthetic_cost_center_id
        project.analytic_cost_center_id = analytic_cost_center_id

    async def list_projects(
        self,
        *,
        company_id: UUID,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConstructionProject], int]:
        return await self.repository.list_projects(
            company_id=company_id,
            search=search,
            page=page,
            page_size=page_size,
        )

    async def list_person_summaries(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if self.erp_client is None:
            raise ConstructionInvalidValueError(
                message="ERP integration client is unavailable for person lookup.",
                error_code="CONSTRUCTION_ERP_INTEGRATION_UNAVAILABLE",
            )

        return await self.erp_client.list_person_summaries(
            company_id=company_id,
            user_id=actor_user_id,
            search=search,
            page=page,
            page_size=page_size,
        )

    async def get_project(self, *, company_id: UUID, project_id: UUID) -> ConstructionProject:
        project = await self.repository.get_project(company_id=company_id, project_id=project_id)
        if not project:
            raise ConstructionNotFoundError(resource_name="Construction project")

        return project

    async def update_project(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionProjectUpdate,
    ) -> ConstructionProject:
        project = await self.get_project(company_id=company_id, project_id=project_id)
        updates = request.model_dump(exclude_unset=True)
        next_status = updates.get("status")
        if next_status is not None:
            self._ensure_project_status_transition(current_status=project.status, next_status=next_status)

        next_project_type = updates.get("project_type")
        if next_project_type is not None:
            self._ensure_known_value(
                value=next_project_type,
                allowed_values=PROJECT_TYPES,
                field_name="project_type",
            )

        next_code = updates.get("code")
        if next_code is not None and next_code != project.code:
            existing_project = await self.repository.get_project_by_code(company_id=company_id, code=next_code)
            if existing_project and existing_project.id != project.id:
                raise ConstructionDuplicateCodeError(resource_name="Construction project", code=next_code)

        self._apply_updates(entity=project, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(project)
        return project

    async def delete_project(self, *, company_id: UUID, project_id: UUID) -> None:
        project = await self.get_project(company_id=company_id, project_id=project_id)
        await self.repository.delete(project)
        await self.repository.commit()

    async def create_block(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionBlockCreate,
    ) -> ConstructionBlock:
        await self.get_project(company_id=company_id, project_id=project_id)
        self._ensure_known_value(value=request.status, allowed_values=BLOCK_STATUSES, field_name="status")
        existing_block = await self.repository.get_block_by_code(
            company_id=company_id,
            project_id=project_id,
            code=request.code,
        )
        if existing_block:
            raise ConstructionDuplicateCodeError(resource_name="Construction block", code=request.code)

        block = ConstructionBlock(
            company_id=company_id,
            project_id=project_id,
            code=request.code.strip(),
            name=request.name.strip(),
            status=request.status,
            floors_count=request.floors_count,
        )
        await self.repository.add(block)
        await self.repository.commit()
        await self.repository.refresh(block)
        return block

    async def list_blocks(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionBlock]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_blocks(company_id=company_id, project_id=project_id)

    async def get_block(self, *, company_id: UUID, block_id: UUID) -> ConstructionBlock:
        return await self._get_block(company_id=company_id, block_id=block_id)

    async def update_block(
        self,
        *,
        company_id: UUID,
        block_id: UUID,
        request: ConstructionBlockUpdate,
    ) -> ConstructionBlock:
        block = await self._get_block(company_id=company_id, block_id=block_id)
        updates = request.model_dump(exclude_unset=True)
        next_status = updates.get("status")
        if next_status is not None:
            self._ensure_known_value(value=next_status, allowed_values=BLOCK_STATUSES, field_name="status")

        next_code = updates.get("code")
        if next_code is not None and next_code != block.code:
            existing_block = await self.repository.get_block_by_code(
                company_id=company_id,
                project_id=block.project_id,
                code=next_code,
            )
            if existing_block and existing_block.id != block.id:
                raise ConstructionDuplicateCodeError(resource_name="Construction block", code=next_code)

        self._apply_updates(entity=block, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(block)
        return block

    async def delete_block(self, *, company_id: UUID, block_id: UUID) -> None:
        block = await self._get_block(company_id=company_id, block_id=block_id)
        await self.repository.delete(block)
        await self.repository.commit()

    async def create_unit(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionUnitCreate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionUnit:
        project = await self.get_project(company_id=company_id, project_id=project_id)
        if not project.synthetic_cost_center_id:
            raise ConstructionInvalidValueError(
                message="Project must have a synthetic cost center before creating construction units.",
                error_code="CONSTRUCTION_PROJECT_COST_CENTER_REQUIRED",
            )

        self._ensure_known_value(value=request.status, allowed_values=UNIT_STATUSES, field_name="status")
        await self._ensure_block_belongs_to_project(
            company_id=company_id,
            project_id=project_id,
            block_id=request.block_id,
        )
        existing_unit = await self.repository.get_unit_by_code(
            company_id=company_id,
            project_id=project_id,
            code=request.code,
        )
        if existing_unit:
            raise ConstructionDuplicateCodeError(resource_name="Construction unit", code=request.code)

        unit = ConstructionUnit(
            company_id=company_id,
            project_id=project_id,
            block_id=request.block_id,
            code=request.code.strip(),
            description=request.description.strip() if request.description else None,
            unit_type=request.unit_type.strip(),
            typology=request.typology.strip() if request.typology else None,
            floor=request.floor,
            private_area=request.private_area,
            total_area=request.total_area,
            sale_price=request.sale_price,
            status=request.status,
        )
        await self.repository.add(unit)
        unit_created_event = self._build_unit_created_event(
            unit=unit,
            project=project,
            actor_user_id=actor_user_id,
        )
        dispatch_result = await self._dispatch_integration_event(event=unit_created_event)
        if dispatch_result is not None and dispatch_result.response_event is not None:
            self._apply_unit_cost_center_snapshot_from_event(unit=unit, event=dispatch_result.response_event)

        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def list_units(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionUnit]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_units(company_id=company_id, project_id=project_id)

    async def get_unit(self, *, company_id: UUID, unit_id: UUID) -> ConstructionUnit:
        return await self._get_unit(company_id=company_id, unit_id=unit_id)

    async def update_unit(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitUpdate,
    ) -> ConstructionUnit:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        updates = request.model_dump(exclude_unset=True)
        next_status = updates.get("status")
        if next_status is not None:
            self._ensure_known_value(value=next_status, allowed_values=UNIT_STATUSES, field_name="status")

        next_block_id = updates.get("block_id")
        if "block_id" in updates:
            await self._ensure_block_belongs_to_project(
                company_id=company_id,
                project_id=unit.project_id,
                block_id=next_block_id,
            )

        next_code = updates.get("code")
        if next_code is not None and next_code != unit.code:
            existing_unit = await self.repository.get_unit_by_code(
                company_id=company_id,
                project_id=unit.project_id,
                code=next_code,
            )
            if existing_unit and existing_unit.id != unit.id:
                raise ConstructionDuplicateCodeError(resource_name="Construction unit", code=next_code)

        self._apply_updates(entity=unit, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def delete_unit(self, *, company_id: UUID, unit_id: UUID) -> None:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        await self.repository.delete(unit)
        await self.repository.commit()

    async def reserve_unit(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitReserveRequest,
    ) -> ConstructionUnit:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        if unit.status != ConstructionUnitStatus.AVAILABLE:
            raise ConstructionInvalidValueError(
                message="Only available units can be reserved.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )

        unit.status = ConstructionUnitStatus.RESERVED
        unit.buyer_person_id = request.buyer_person_id
        unit.reserved_at = datetime.now(tz=UTC)
        unit.reservation_expires_at = request.reservation_expires_at or (date.today() + timedelta(days=7))
        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def release_unit_reservation(self, *, company_id: UUID, unit_id: UUID) -> ConstructionUnit:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        if unit.status != ConstructionUnitStatus.RESERVED:
            raise ConstructionInvalidValueError(
                message="Only reserved units can have reservation released.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )

        unit.status = ConstructionUnitStatus.AVAILABLE
        unit.buyer_person_id = None
        unit.reserved_at = None
        unit.reservation_expires_at = None
        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def confirm_unit_sale(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitSaleConfirmRequest,
        actor_user_id: UUID | None = None,
    ) -> ConstructionUnit:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        if unit.status == ConstructionUnitStatus.SOLD and unit.external_contract_id is not None:
            return unit

        if unit.status not in {
            ConstructionUnitStatus.AVAILABLE,
            ConstructionUnitStatus.RESERVED,
            ConstructionUnitStatus.SOLD,
        }:
            raise ConstructionInvalidValueError(
                message="Unit status does not allow sale confirmation.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )

        sale_price = request.sale_price or unit.sale_price
        if sale_price is None or sale_price <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="Unit sale price is required to confirm sale.",
                error_code="CONSTRUCTION_UNIT_SALE_PRICE_REQUIRED",
            )

        if not unit.analytic_cost_center_id:
            raise ConstructionInvalidValueError(
                message="Unit must have an analytic cost center before confirming sale.",
                error_code="CONSTRUCTION_UNIT_COST_CENTER_REQUIRED",
            )

        unit.status = ConstructionUnitStatus.SOLD
        unit.buyer_person_id = request.buyer_person_id
        unit.sale_price = sale_price
        unit.sold_at = datetime.now(tz=UTC)
        unit.reservation_expires_at = None

        sale_event = self._build_unit_sold_event(
            unit=unit,
            analytic_cost_center_id=unit.analytic_cost_center_id,
            first_due_date=request.first_due_date,
            installments=request.installments,
            actor_user_id=actor_user_id,
        )
        dispatch_result = await self._dispatch_integration_event(event=sale_event)
        if dispatch_result is not None and dispatch_result.response_event is not None:
            erp_event = dispatch_result.response_event
            self._apply_contract_snapshot_from_payload(unit=unit, payload=erp_event.payload)

        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def apply_contract_status_updated_event(self, *, event: EventEnvelope) -> ConstructionUnit:
        if event.event_type not in {ErpEventType.CONTRACT_RECEIVABLE_CREATED, ErpEventType.CONTRACT_STATUS_UPDATED}:
            raise ConstructionInvalidValueError(
                message="Unsupported ERP event type for unit contract sync.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        unit_id = self._read_uuid_payload(payload=event.payload, field_name="construction_unit_id")
        unit = await self._get_unit(company_id=event.company_id, unit_id=unit_id)

        if self.event_repository is not None:
            should_process_event = await self.event_repository.mark_processed(
                consumer_name=ConstructionConsumerName.CONTRACT_STATUS_UPDATED,
                event=event,
            )
            if not should_process_event:
                return unit

        self._apply_contract_snapshot_from_payload(unit=unit, payload=event.payload)
        contract_status = str(event.payload.get("contract_status") or "")
        if contract_status.upper() == "CANCELED":
            unit.status = ConstructionUnitStatus.AVAILABLE
            unit.sold_at = None
            unit.external_contract_status = contract_status

        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def create_procurement_request(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionProcurementRequestCreate,
    ) -> ConstructionProcurementRequest:
        await self.get_project(company_id=company_id, project_id=project_id)
        procurement_code = (request.code or "").strip()
        if procurement_code:
            existing_request = await self.repository.get_procurement_request_by_code(
                company_id=company_id,
                project_id=project_id,
                code=procurement_code,
            )
            if existing_request:
                raise ConstructionDuplicateCodeError(
                    resource_name="Construction procurement request",
                    code=procurement_code,
                )
        else:
            procurement_code = self._generate_procurement_code()

        procurement_request = ConstructionProcurementRequest(
            company_id=company_id,
            project_id=project_id,
            code=procurement_code,
            title=request.title.strip(),
            description=request.description,
            estimated_amount=request.estimated_amount,
            needed_by_date=request.needed_by_date,
            supplier_person_id=request.supplier_person_id,
            status=ConstructionProcurementStatus.DRAFT,
            rejection_reason=None,
        )
        await self.repository.add(procurement_request)
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return procurement_request

    async def list_procurement_requests(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
    ) -> list[ConstructionProcurementRequest]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_procurement_requests(company_id=company_id, project_id=project_id)

    async def get_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
    ) -> ConstructionProcurementRequest:
        procurement_request = await self.repository.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request_id,
        )
        if not procurement_request:
            raise ConstructionNotFoundError(resource_name="Construction procurement request")

        return procurement_request

    async def update_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
        request: ConstructionProcurementRequestUpdate,
    ) -> ConstructionProcurementRequest:
        procurement_request = await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request_id,
        )
        if procurement_request.status not in {
            ConstructionProcurementStatus.DRAFT,
            ConstructionProcurementStatus.REJECTED,
        }:
            raise ConstructionInvalidValueError(
                message="Only draft or rejected procurement requests can be edited.",
                error_code="CONSTRUCTION_PROCUREMENT_LOCKED",
            )

        updates = request.model_dump(exclude_unset=True)
        next_code = updates.get("code")
        if next_code is not None:
            next_code = next_code.strip()
            if not next_code:
                raise ConstructionInvalidValueError(
                    message="Procurement request code cannot be empty.",
                    error_code="CONSTRUCTION_PROCUREMENT_INVALID_CODE",
                )

            if next_code != procurement_request.code:
                existing_request = await self.repository.get_procurement_request_by_code(
                    company_id=company_id,
                    project_id=procurement_request.project_id,
                    code=next_code,
                )
                if existing_request and existing_request.id != procurement_request.id:
                    raise ConstructionDuplicateCodeError(
                        resource_name="Construction procurement request",
                        code=next_code,
                    )

            updates["code"] = next_code

        self._apply_updates(entity=procurement_request, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return procurement_request

    async def submit_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
        actor_user_id: UUID | None,
    ) -> ConstructionProcurementRequest:
        procurement_request = await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request_id,
        )
        if procurement_request.status not in {
            ConstructionProcurementStatus.DRAFT,
            ConstructionProcurementStatus.REJECTED,
        }:
            raise ConstructionInvalidValueError(
                message="Procurement request cannot be submitted from current status.",
                error_code="CONSTRUCTION_PROCUREMENT_INVALID_STATUS",
            )

        if procurement_request.estimated_amount >= Decimal(str(CONSTRUCTION_PROCUREMENT_APPROVAL_THRESHOLD)):
            procurement_request.status = ConstructionProcurementStatus.PENDING_APPROVAL
            await self.repository.commit()
            await self.repository.refresh(procurement_request)
            return procurement_request

        procurement_request.status = ConstructionProcurementStatus.APPROVED
        procurement_request.approved_by_user_id = actor_user_id
        procurement_request.approved_at = datetime.now(tz=UTC)
        procurement_request.rejection_reason = None
        await self._dispatch_procurement_request_to_erp(
            procurement_request=procurement_request,
            actor_user_id=actor_user_id,
        )
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return procurement_request

    async def approve_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
        actor_user_id: UUID | None,
    ) -> ConstructionProcurementRequest:
        procurement_request = await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request_id,
        )
        if procurement_request.status != ConstructionProcurementStatus.PENDING_APPROVAL:
            raise ConstructionInvalidValueError(
                message="Only pending approval procurement requests can be approved.",
                error_code="CONSTRUCTION_PROCUREMENT_INVALID_STATUS",
            )

        procurement_request.status = ConstructionProcurementStatus.APPROVED
        procurement_request.approved_by_user_id = actor_user_id
        procurement_request.approved_at = datetime.now(tz=UTC)
        procurement_request.rejection_reason = None
        await self._dispatch_procurement_request_to_erp(
            procurement_request=procurement_request,
            actor_user_id=actor_user_id,
        )
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return procurement_request

    async def reject_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
        reason: str | None = None,
    ) -> ConstructionProcurementRequest:
        procurement_request = await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request_id,
        )
        procurement_request.status = ConstructionProcurementStatus.REJECTED
        procurement_request.rejection_reason = reason.strip() if reason else None
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return procurement_request

    async def delete_procurement_request(self, *, company_id: UUID, procurement_request_id: UUID) -> None:
        procurement_request = await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request_id,
        )
        if procurement_request.status not in {
            ConstructionProcurementStatus.DRAFT,
            ConstructionProcurementStatus.REJECTED,
        }:
            raise ConstructionInvalidValueError(
                message="Only draft or rejected procurement requests can be deleted.",
                error_code="CONSTRUCTION_PROCUREMENT_LOCKED",
            )

        await self.repository.delete(procurement_request)
        await self.repository.commit()

    async def create_measurement(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionMeasurementCreate,
    ) -> ConstructionMeasurement:
        await self.get_project(company_id=company_id, project_id=project_id)
        existing_measurement = await self.repository.get_measurement_by_code(
            company_id=company_id,
            project_id=project_id,
            code=request.code,
        )
        if existing_measurement:
            raise ConstructionDuplicateCodeError(resource_name="Construction measurement", code=request.code)

        sequence_number = request.sequence_number
        if sequence_number is None:
            sequence_number = await self.repository.get_next_measurement_sequence(
                company_id=company_id,
                project_id=project_id,
            )

        gross_amount = request.gross_amount or request.measured_amount
        if gross_amount is None or gross_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="Measurement gross amount is required.",
                error_code="CONSTRUCTION_MEASUREMENT_GROSS_REQUIRED",
            )

        retentions_amount = request.retentions_amount or Decimal("0")
        net_amount = request.net_amount or request.measured_amount or (gross_amount - retentions_amount)
        if net_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="Measurement net amount must be greater than zero.",
                error_code="CONSTRUCTION_MEASUREMENT_NET_INVALID",
            )

        measurement = ConstructionMeasurement(
            company_id=company_id,
            project_id=project_id,
            code=request.code.strip(),
            sequence_number=sequence_number,
            measurement_type=request.measurement_type.strip() if request.measurement_type else None,
            competence_date=request.competence_date,
            description=request.description,
            gross_amount=gross_amount,
            retentions_amount=retentions_amount,
            net_amount=net_amount,
            document_type=request.document_type.strip() if request.document_type else None,
            document_number=request.document_number.strip() if request.document_number else None,
            measured_amount=net_amount,
            due_date=request.due_date,
            supplier_person_id=request.supplier_person_id,
            status=ConstructionMeasurementStatus.DRAFT,
        )
        await self.repository.add(measurement)
        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def list_measurements(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionMeasurement]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_measurements(company_id=company_id, project_id=project_id)

    async def get_measurement(self, *, company_id: UUID, measurement_id: UUID) -> ConstructionMeasurement:
        measurement = await self.repository.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if not measurement:
            raise ConstructionNotFoundError(resource_name="Construction measurement")

        return measurement

    async def update_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        request: ConstructionMeasurementUpdate,
    ) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Approved measurements cannot be edited.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        updates = request.model_dump(exclude_unset=True)
        next_code = updates.get("code")
        if next_code is not None and next_code != measurement.code:
            existing_measurement = await self.repository.get_measurement_by_code(
                company_id=company_id,
                project_id=measurement.project_id,
                code=next_code,
            )
            if existing_measurement and existing_measurement.id != measurement.id:
                raise ConstructionDuplicateCodeError(resource_name="Construction measurement", code=next_code)

        gross_amount = updates.get("gross_amount", measurement.gross_amount)
        retentions_amount = updates.get("retentions_amount", measurement.retentions_amount)
        net_amount = updates.get("net_amount", measurement.net_amount)
        measured_amount = updates.get("measured_amount", measurement.measured_amount)

        if gross_amount is None:
            gross_amount = measured_amount

        if retentions_amount is None:
            retentions_amount = Decimal("0")

        if net_amount is None:
            if "gross_amount" in updates or "retentions_amount" in updates:
                net_amount = gross_amount - retentions_amount
            else:
                net_amount = measured_amount

        if net_amount is None or net_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="Measurement net amount must be greater than zero.",
                error_code="CONSTRUCTION_MEASUREMENT_NET_INVALID",
            )

        updates["gross_amount"] = gross_amount
        updates["retentions_amount"] = retentions_amount
        updates["net_amount"] = net_amount
        updates["measured_amount"] = net_amount

        self._apply_updates(entity=measurement, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def reject_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        reason: str | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Approved measurements cannot be rejected.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        measurement.status = ConstructionMeasurementStatus.REJECTED
        measurement.rejection_reason = reason.strip() if reason else None
        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def approve_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if (
            measurement.status == ConstructionMeasurementStatus.APPROVED
            and measurement.external_accounts_payable_id is not None
        ):
            return measurement

        project = await self.get_project(company_id=company_id, project_id=measurement.project_id)
        if not project.analytic_cost_center_id:
            raise ConstructionInvalidValueError(
                message="Project must have an analytic cost center before approving measurements.",
                error_code="CONSTRUCTION_PROJECT_COST_CENTER_REQUIRED",
            )

        measurement.status = ConstructionMeasurementStatus.APPROVED
        measurement.rejection_reason = None
        if measurement.approved_at is None:
            measurement.approved_at = datetime.now(tz=UTC)

        approval_event = self._build_measurement_approved_event(
            measurement=measurement,
            analytic_cost_center_id=project.analytic_cost_center_id,
            actor_user_id=actor_user_id,
        )
        dispatch_result = await self._dispatch_integration_event(event=approval_event)
        if dispatch_result is not None and dispatch_result.response_event is not None:
            erp_event = dispatch_result.response_event
            self._apply_accounts_payable_snapshot_from_payload(
                measurement=measurement,
                payload=erp_event.payload,
            )

        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def delete_measurement(self, *, company_id: UUID, measurement_id: UUID) -> None:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Approved measurements cannot be deleted.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        await self.repository.delete(measurement)
        await self.repository.commit()

    async def apply_accounts_payable_updated_event(self, *, event: EventEnvelope) -> ConstructionMeasurement:
        if event.event_type not in {ErpEventType.ACCOUNTS_PAYABLE_CREATED, ErpEventType.ACCOUNTS_PAYABLE_UPDATED}:
            raise ConstructionInvalidValueError(
                message="Unsupported ERP event type for measurement accounts payable sync.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        measurement_id = self._read_uuid_payload(payload=event.payload, field_name="construction_measurement_id")
        measurement = await self.get_measurement(company_id=event.company_id, measurement_id=measurement_id)

        if self.event_repository is not None:
            should_process_event = await self.event_repository.mark_processed(
                consumer_name=ConstructionConsumerName.ACCOUNTS_PAYABLE_UPDATED,
                event=event,
            )
            if not should_process_event:
                return measurement

        self._apply_accounts_payable_snapshot_from_payload(
            measurement=measurement,
            payload=event.payload,
        )
        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def create_schedule_phase(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionSchedulePhaseCreate,
    ) -> ConstructionSchedulePhase:
        await self.get_project(company_id=company_id, project_id=project_id)
        self._ensure_known_value(value=request.status, allowed_values=SCHEDULE_PHASE_STATUSES, field_name="status")
        existing_phase = await self.repository.get_schedule_phase_by_sequence(
            company_id=company_id,
            project_id=project_id,
            sequence_order=request.sequence_order,
        )
        if existing_phase:
            raise ConstructionDuplicateCodeError(resource_name="Construction schedule phase", code=str(request.sequence_order))

        phase = ConstructionSchedulePhase(
            company_id=company_id,
            project_id=project_id,
            name=request.name.strip(),
            sequence_order=request.sequence_order,
            status=request.status,
            planned_start_date=request.planned_start_date,
            planned_end_date=request.planned_end_date,
            actual_start_date=request.actual_start_date,
            actual_end_date=request.actual_end_date,
            progress_percent=request.progress_percent,
        )
        await self.repository.add(phase)
        await self.repository.commit()
        await self.repository.refresh(phase)
        return phase

    async def list_schedule_phases(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionSchedulePhase]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_schedule_phases(company_id=company_id, project_id=project_id)

    async def get_schedule_phase(self, *, company_id: UUID, phase_id: UUID) -> ConstructionSchedulePhase:
        return await self._get_schedule_phase(company_id=company_id, phase_id=phase_id)

    async def update_schedule_phase(
        self,
        *,
        company_id: UUID,
        phase_id: UUID,
        request: ConstructionSchedulePhaseUpdate,
    ) -> ConstructionSchedulePhase:
        phase = await self._get_schedule_phase(company_id=company_id, phase_id=phase_id)
        updates = request.model_dump(exclude_unset=True)
        next_status = updates.get("status")
        if next_status is not None:
            self._ensure_known_value(value=next_status, allowed_values=SCHEDULE_PHASE_STATUSES, field_name="status")

        next_sequence_order = updates.get("sequence_order")
        if next_sequence_order is not None and next_sequence_order != phase.sequence_order:
            existing_phase = await self.repository.get_schedule_phase_by_sequence(
                company_id=company_id,
                project_id=phase.project_id,
                sequence_order=next_sequence_order,
            )
            if existing_phase and existing_phase.id != phase.id:
                raise ConstructionDuplicateCodeError(
                    resource_name="Construction schedule phase",
                    code=str(next_sequence_order),
                )

        self._apply_updates(entity=phase, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(phase)
        return phase

    async def delete_schedule_phase(self, *, company_id: UUID, phase_id: UUID) -> None:
        phase = await self._get_schedule_phase(company_id=company_id, phase_id=phase_id)
        await self.repository.delete(phase)
        await self.repository.commit()

    async def _get_block(self, *, company_id: UUID, block_id: UUID) -> ConstructionBlock:
        block = await self.repository.get_block(company_id=company_id, block_id=block_id)
        if not block:
            raise ConstructionNotFoundError(resource_name="Construction block")

        return block

    async def _get_unit(self, *, company_id: UUID, unit_id: UUID) -> ConstructionUnit:
        unit = await self.repository.get_unit(company_id=company_id, unit_id=unit_id)
        if not unit:
            raise ConstructionNotFoundError(resource_name="Construction unit")

        return unit

    async def _get_schedule_phase(self, *, company_id: UUID, phase_id: UUID) -> ConstructionSchedulePhase:
        phase = await self.repository.get_schedule_phase(company_id=company_id, phase_id=phase_id)
        if not phase:
            raise ConstructionNotFoundError(resource_name="Construction schedule phase")

        return phase

    async def _ensure_block_belongs_to_project(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        block_id: UUID | None,
    ) -> None:
        if block_id is None:
            return

        block = await self._get_block(company_id=company_id, block_id=block_id)
        if block.project_id != project_id:
            raise ConstructionInvalidValueError(
                message="Block does not belong to the informed construction project.",
                error_code="CONSTRUCTION_BLOCK_PROJECT_MISMATCH",
            )

    @staticmethod
    def _ensure_known_value(*, value: str, allowed_values: set[str], field_name: str) -> None:
        if value not in allowed_values:
            allowed_values_text = ", ".join(sorted(allowed_values))
            raise ConstructionInvalidValueError(
                message=f"Invalid {field_name}. Allowed values: {allowed_values_text}.",
                error_code="CONSTRUCTION_INVALID_ENUM_VALUE",
            )

    @staticmethod
    def _ensure_project_status_transition(*, current_status: str, next_status: str) -> None:
        if next_status == current_status:
            return

        if next_status not in PROJECT_STATUS_TRANSITIONS.get(current_status, set()):
            raise ConstructionInvalidStatusTransitionError(current_status=current_status, next_status=next_status)

    @staticmethod
    def _apply_updates(*, entity: object, updates: dict[str, object]) -> None:
        for field_name, field_value in updates.items():
            if isinstance(field_value, str):
                field_value = field_value.strip()

            setattr(entity, field_name, field_value)

    @staticmethod
    def _build_project_created_event(*, project: ConstructionProject, actor_user_id: UUID | None) -> EventEnvelope:
        event_id = uuid4()
        payload: dict[str, Any] = {
            "construction_project_id": str(project.id),
            "project_code": project.code,
            "project_name": project.name,
            "project_type": project.project_type,
            "customer_person_id": str(project.customer_person_id) if project.customer_person_id else None,
            "cnpj_spe": project.cnpj_spe,
            "address": project.address_json,
            "start_date": ConstructionProjectService._format_event_date(value=project.start_date),
            "expected_end_date": ConstructionProjectService._format_event_date(value=project.expected_end_date),
        }
        if actor_user_id is not None:
            payload["user_id"] = str(actor_user_id)

        return EventEnvelope(
            event_id=event_id,
            event_type=ConstructionEventType.PROJECT_CREATED,
            event_version=1,
            company_id=project.company_id,
            aggregate_id=project.id,
            aggregate_type=ConstructionAggregateType.PROJECT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.CONSTRUCTION_API,
            correlation_id=event_id,
            causation_id=None,
            payload=payload,
        )

    @staticmethod
    def _build_measurement_approved_event(
        *,
        measurement: ConstructionMeasurement,
        analytic_cost_center_id: UUID,
        actor_user_id: UUID | None,
    ) -> EventEnvelope:
        event_id = uuid4()
        payload: dict[str, Any] = {
            "construction_measurement_id": str(measurement.id),
            "construction_project_id": str(measurement.project_id),
            "measurement_code": measurement.code,
            "description": measurement.description,
            "measured_amount": ConstructionProjectService._format_event_decimal(value=measurement.measured_amount),
            "due_date": ConstructionProjectService._format_event_date(value=measurement.due_date),
            "supplier_person_id": str(measurement.supplier_person_id) if measurement.supplier_person_id else None,
            "analytic_cost_center_id": str(analytic_cost_center_id),
        }
        if actor_user_id is not None:
            payload["user_id"] = str(actor_user_id)

        return EventEnvelope(
            event_id=event_id,
            event_type=ConstructionEventType.MEASUREMENT_APPROVED,
            event_version=1,
            company_id=measurement.company_id,
            aggregate_id=measurement.id,
            aggregate_type=ConstructionAggregateType.MEASUREMENT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.CONSTRUCTION_API,
            correlation_id=event_id,
            causation_id=None,
            payload=payload,
        )

    @staticmethod
    def _build_unit_created_event(
        *,
        unit: ConstructionUnit,
        project: ConstructionProject,
        actor_user_id: UUID | None,
    ) -> EventEnvelope:
        event_id = uuid4()
        payload: dict[str, Any] = {
            "construction_unit_id": str(unit.id),
            "construction_project_id": str(unit.project_id),
            "project_code": project.code,
            "project_name": project.name,
            "project_synthetic_cost_center_id": str(project.synthetic_cost_center_id),
            "unit_code": unit.code,
            "unit_description": unit.description,
            "unit_type": unit.unit_type,
            "block_id": str(unit.block_id) if unit.block_id else None,
        }
        if actor_user_id is not None:
            payload["user_id"] = str(actor_user_id)

        return EventEnvelope(
            event_id=event_id,
            event_type=ConstructionEventType.UNIT_CREATED,
            event_version=1,
            company_id=unit.company_id,
            aggregate_id=unit.id,
            aggregate_type=ConstructionAggregateType.UNIT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.CONSTRUCTION_API,
            correlation_id=event_id,
            causation_id=None,
            payload=payload,
        )

    @staticmethod
    def _apply_unit_cost_center_snapshot_from_event(*, unit: ConstructionUnit, event: EventEnvelope) -> None:
        if event.event_type != ErpEventType.COST_CENTER_CREATED:
            raise ConstructionInvalidValueError(
                message="Unsupported ERP event type for unit cost center confirmation.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        unit_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="construction_unit_id",
        )
        if unit_id != unit.id:
            raise ConstructionInvalidValueError(
                message="Cost center confirmation does not belong to the created construction unit.",
                error_code="CONSTRUCTION_COST_CENTER_UNIT_MISMATCH",
            )

        analytic_cost_center_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="analytic_cost_center_id",
        )
        ConstructionProjectService._ensure_external_id_can_be_applied(
            current_id=unit.analytic_cost_center_id,
            next_id=analytic_cost_center_id,
            field_name="analytic_cost_center_id",
        )
        unit.analytic_cost_center_id = analytic_cost_center_id

    @staticmethod
    def _apply_accounts_payable_snapshot_from_payload(
        *,
        measurement: ConstructionMeasurement,
        payload: dict[str, Any],
    ) -> None:
        accounts_payable_id = payload.get("accounts_payable_document_id")
        if accounts_payable_id is not None:
            measurement.external_accounts_payable_id = ConstructionProjectService._read_uuid_payload(
                payload=payload,
                field_name="accounts_payable_document_id",
            )

        accounts_payable_status = payload.get("accounts_payable_status")
        if accounts_payable_status is not None:
            measurement.external_accounts_payable_status = str(accounts_payable_status)

    @staticmethod
    def _build_unit_sold_event(
        *,
        unit: ConstructionUnit,
        analytic_cost_center_id: UUID,
        first_due_date: date,
        installments: int,
        actor_user_id: UUID | None,
    ) -> EventEnvelope:
        event_id = uuid4()
        payload: dict[str, Any] = {
            "construction_unit_id": str(unit.id),
            "construction_project_id": str(unit.project_id),
            "unit_code": unit.code,
            "buyer_person_id": str(unit.buyer_person_id),
            "sale_price": ConstructionProjectService._format_event_decimal(value=unit.sale_price or Decimal("0")),
            "first_due_date": ConstructionProjectService._format_event_date(value=first_due_date),
            "installments": installments,
            "analytic_cost_center_id": str(analytic_cost_center_id),
        }
        if actor_user_id is not None:
            payload["user_id"] = str(actor_user_id)

        return EventEnvelope(
            event_id=event_id,
            event_type=ConstructionEventType.UNIT_SOLD,
            event_version=1,
            company_id=unit.company_id,
            aggregate_id=unit.id,
            aggregate_type=ConstructionAggregateType.UNIT,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.CONSTRUCTION_API,
            correlation_id=event_id,
            causation_id=None,
            payload=payload,
        )

    @staticmethod
    def _apply_contract_snapshot_from_payload(*, unit: ConstructionUnit, payload: dict[str, Any]) -> None:
        contract_id = payload.get("external_contract_id") or payload.get("contract_id")
        if contract_id is not None:
            unit.external_contract_id = ConstructionProjectService._read_uuid_payload(
                payload={"external_contract_id": contract_id},
                field_name="external_contract_id",
            )

        contract_status = payload.get("contract_status")
        if contract_status is not None:
            unit.external_contract_status = str(contract_status)

        receivable_id = payload.get("external_receivable_id") or payload.get("receivable_id")
        if receivable_id is not None:
            unit.external_receivable_id = ConstructionProjectService._read_uuid_payload(
                payload={"external_receivable_id": receivable_id},
                field_name="external_receivable_id",
            )

        receivable_status = payload.get("receivable_status")
        if receivable_status is not None:
            unit.external_receivable_status = str(receivable_status)

    async def _dispatch_procurement_request_to_erp(
        self,
        *,
        procurement_request: ConstructionProcurementRequest,
        actor_user_id: UUID | None,
    ) -> None:
        request_event = self._build_procurement_requested_event(
            procurement_request=procurement_request,
            actor_user_id=actor_user_id,
        )
        procurement_request.status = ConstructionProcurementStatus.SENT_TO_ERP
        dispatch_result = await self._dispatch_integration_event(event=request_event)
        if dispatch_result is not None and dispatch_result.response_event is not None:
            self._apply_procurement_snapshot_from_payload(
                procurement_request=procurement_request,
                payload=dispatch_result.response_event.payload,
            )

    async def _dispatch_integration_event(self, *, event: EventEnvelope):
        if self.integration_dispatcher is not None:
            return await self.integration_dispatcher.dispatch(event=event)

        if self.event_repository is not None:
            await self.event_repository.add_outbox_event(event=event)

        if self.erp_client is None:
            return None

        response_event = await self.erp_client.deliver_event(event=event)
        return ConstructionIntegrationDispatchResult(
            event=event,
            response_event=response_event,
            integration_mode="sync_http",
        )

    @staticmethod
    def _build_procurement_requested_event(
        *,
        procurement_request: ConstructionProcurementRequest,
        actor_user_id: UUID | None,
    ) -> EventEnvelope:
        event_id = uuid4()
        payload: dict[str, Any] = {
            "construction_procurement_request_id": str(procurement_request.id),
            "construction_project_id": str(procurement_request.project_id),
            "code": procurement_request.code,
            "title": procurement_request.title,
            "description": procurement_request.description,
            "estimated_amount": ConstructionProjectService._format_event_decimal(
                value=procurement_request.estimated_amount
            ),
            "needed_by_date": ConstructionProjectService._format_event_date(value=procurement_request.needed_by_date),
            "supplier_person_id": (
                str(procurement_request.supplier_person_id) if procurement_request.supplier_person_id else None
            ),
            "approval_threshold": CONSTRUCTION_PROCUREMENT_APPROVAL_THRESHOLD,
        }
        if actor_user_id is not None:
            payload["user_id"] = str(actor_user_id)

        return EventEnvelope(
            event_id=event_id,
            event_type=ConstructionEventType.PROCUREMENT_REQUESTED,
            event_version=1,
            company_id=procurement_request.company_id,
            aggregate_id=procurement_request.id,
            aggregate_type=ConstructionAggregateType.PROCUREMENT_REQUEST,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.CONSTRUCTION_API,
            correlation_id=event_id,
            causation_id=None,
            payload=payload,
        )

    @staticmethod
    def _apply_procurement_snapshot_from_payload(
        *,
        procurement_request: ConstructionProcurementRequest,
        payload: dict[str, Any],
    ) -> None:
        external_procurement_id = payload.get("external_procurement_id")
        if external_procurement_id is not None:
            procurement_request.external_procurement_id = ConstructionProjectService._read_uuid_payload(
                payload={"external_procurement_id": external_procurement_id},
                field_name="external_procurement_id",
            )

        external_procurement_status = payload.get("external_procurement_status")
        if external_procurement_status is not None:
            procurement_request.external_procurement_status = str(external_procurement_status)

    @staticmethod
    def _format_event_date(*, value: date | None) -> str | None:
        if value is None:
            return None

        return value.isoformat()

    @staticmethod
    def _format_event_decimal(*, value: Decimal) -> str:
        return format(value, "f")

    @staticmethod
    def _generate_procurement_code() -> str:
        return f"REQ-{uuid4().hex[:8].upper()}"

    @staticmethod
    def _read_uuid_payload(*, payload: dict[str, Any], field_name: str) -> UUID:
        value = payload.get(field_name)
        if value is None:
            raise ConstructionInvalidValueError(
                message=f"ERP event payload is missing {field_name}.",
                error_code="CONSTRUCTION_INVALID_ERP_EVENT_PAYLOAD",
            )

        try:
            return UUID(str(value))
        except ValueError as exc:
            raise ConstructionInvalidValueError(
                message=f"ERP event payload has an invalid {field_name}.",
                error_code="CONSTRUCTION_INVALID_ERP_EVENT_PAYLOAD",
            ) from exc

    @staticmethod
    def _ensure_external_id_can_be_applied(*, current_id: UUID | None, next_id: UUID, field_name: str) -> None:
        if current_id is None or current_id == next_id:
            return

        raise ConstructionInvalidValueError(
            message=f"Project already has a different {field_name}.",
            error_code="CONSTRUCTION_EXTERNAL_ID_CONFLICT",
        )
