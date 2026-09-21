import calendar
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, Protocol
from uuid import UUID, uuid4

import httpx

from app.domain.constants import (
    ConstructionInspectionRoundSource,
    BLOCK_STATUSES,
    ConstructionUnitPaymentSource,
    ConstructionDocumentationType,
    ConstructionInspectionStatus,
    ConstructionOccurrenceStatus,
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
    ConstructionDomainError,
    ConstructionDuplicateCodeError,
    ConstructionInvalidStatusTransitionError,
    ConstructionInvalidValueError,
    ConstructionNotFoundError,
    ConstructionResourceInUseError,
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
from app.domain.services.construction_service_template_parser import parse_service_template_spreadsheet
from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionDocumentationType as ConstructionDocumentationTypeModel,
    ConstructionMeasurement,
    ConstructionMeasurementItem,
    ConstructionInspectionRound,
    ConstructionServiceTemplate,
    ConstructionServiceTemplateAudit,
    ConstructionServiceTemplateItem,
    ConstructionServiceTemplateSection,
    ConstructionUnitCommission as ConstructionUnitCommissionModel,
    ConstructionUnitDocumentation as ConstructionUnitDocumentationModel,
    ConstructionUnitPaymentSource as ConstructionUnitPaymentSourceModel,
    ConstructionMeasurementItemInspection,
    ConstructionMeasurementItemOccurrence,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionUnit,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.schemas.construction import (
    ConstructionBlockCreate,
    ConstructionDocumentationTypeCreate,
    ConstructionDocumentationTypeUpdate,
    ConstructionMeasurementInspectionVerifyRequest,
    ConstructionMeasurementItemCreate,
    ConstructionMeasurementItemInspectionCreate,
    ConstructionMeasurementItemInspectionUpdate,
    ConstructionMeasurementItemOccurrenceCreate,
    ConstructionMeasurementItemOccurrenceUpdate,
    ConstructionMeasurementItemUpdate,
    ConstructionBlockUpdate,
    ConstructionProjectCreate,
    ConstructionProjectUpdate,
    ConstructionProcurementRequestCreate,
    ConstructionProcurementRequestUpdate,
    ConstructionMeasurementCreate,
    ConstructionMeasurementUpdate,
    ConstructionSchedulePhaseCreate,
    ConstructionServiceTemplateCreate,
    ConstructionServiceTemplateReplace,
    ConstructionServiceTemplateSectionInput,
    ConstructionServiceTemplateUpdate,
    ConstructionSchedulePhaseUpdate,
    ConstructionUnitAdjustmentCreate,
    ConstructionUnitCommissionCreate,
    ConstructionUnitCommissionUpdate,
    ConstructionUnitCreate,
    ConstructionUnitInstallmentCreateRequest,
    ConstructionUnitInstallmentPaymentRequest,
    ConstructionUnitReserveRequest,
    ConstructionUnitSaleConfirmRequest,
    ConstructionUnitUpdate,
)


def _describe_erp_failure(error: Exception) -> str:
    """Traduz a falha do ERP para quem esta olhando o resumo da obra.

    A mensagem vai para a tela, entao a URL interna e o status cru do httpx nao
    ajudam: o que importa e se faltou permissao ou se o ERP esta fora.
    """
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code in (401, 403):
            return "Seu usuário não tem permissão para consultar o contas a receber no ERP."
        if status_code == 404:
            return "O ERP não encontrou os recebíveis das unidades desta obra."
        return f"O ERP respondeu {status_code} ao consultar o contas a receber."

    if isinstance(error, httpx.RequestError):
        return "Não foi possível falar com o ERP agora."

    return "Não foi possível consultar o financeiro no ERP agora."


_logger = logging.getLogger(__name__)

class ErpMeasurementClient(Protocol):
    async def list_person_summaries(
        self,
        *,
        company_id: UUID,
        user_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
        person_id: UUID | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_person_qualification_status(
        self,
        *,
        company_id: UUID,
        user_id: UUID | None,
        person_id: UUID,
    ) -> str:
        raise NotImplementedError

    async def create_accounts_payable_from_measurement(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError

    async def create_contract_and_receivables_from_unit_sale(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError

    async def create_procurement_demand_from_request(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError

    async def create_unit_adjustment(
        self,
        *,
        company_id: UUID,
        user_id: UUID | None,
        construction_unit_id: UUID,
        contract_id: UUID,
        amount: Decimal,
        installments: int,
        first_due_date: date,
        reason: str | None,
        cost_center_id: UUID | None,
        unit_code: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def deliver_event(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError


class ConstructionEventDispatcher(Protocol):
    async def dispatch(self, *, event: EventEnvelope):
        raise NotImplementedError


#: Mensagem de "ainda nao verificado". Constante porque aparece em dois caminhos
#: -- a criacao do item com template e o preenchimento da data de fim -- e o
#: texto duplicado literalmente ja divergiu uma vez.
INSPECTIONS_PENDING_MESSAGE = (
    "A data de fim só pode ser preenchida depois que todos os itens de inspeção forem verificados."
)
REINSPECTION_REQUIRED_MESSAGE = (
    "Há itens reprovados na FVS. Registre a reinspeção aprovada antes de continuar."
)


class ConstructionProjectService:
    #: Empresas cujo catalogo de documentacao ja foi semeado neste processo.
    #: O seed e idempotente; isto so evita repetir a consulta a cada tecla do
    #: combobox. Nasce vazio a cada boot, entao um banco restaurado por baixo
    #: nao fica com o cache mentindo.
    _companies_with_seeded_documentation_types: ClassVar[set[UUID]] = set()

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
            raise ConstructionDuplicateCodeError(resource_name="a obra", code=request.code)

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
            receipt_template_id=request.receipt_template_id,
            commission_receipt_template_id=request.commission_receipt_template_id,
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
                message="Tipo de evento do ERP não suportado para confirmação de centro de custo.",
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
                message="Tipo de evento do ERP não suportado para confirmação de centro de custo.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        project_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="construction_project_id",
        )
        if project_id != project.id:
            raise ConstructionInvalidValueError(
                message="A confirmação de centro de custo não pertence à obra criada.",
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
        status: str | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConstructionProject], int]:
        return await self.repository.list_projects(
            company_id=company_id,
            search=search,
            status=status,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            page=page,
            page_size=page_size,
        )

    async def _resolve_supplier_qualification_status(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        supplier_person_id: UUID | None,
    ) -> str:
        """Status de qualificacao no MOMENTO da gravacao.

        Resolvido no servidor, nunca aceito do navegador: o campo e material de
        auditoria da Caixa, e quem grava o registro tem de ser quem consultou.
        Sem fornecedor, ou com o ERP indisponivel, fica `none` -- o aviso some,
        a gravacao segue (decisao D7: avisa, nao bloqueia).
        """
        if supplier_person_id is None or self.erp_client is None:
            return "none"

        return await self.erp_client.get_person_qualification_status(
            company_id=company_id,
            user_id=actor_user_id,
            person_id=supplier_person_id,
        )

    async def list_person_summaries(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        search: str | None,
        page: int,
        page_size: int,
        person_id: UUID | None = None,
    ) -> dict[str, Any]:
        """A lista de pessoas do formulario, e o caso de UMA pessoa por id.

        `person_id` existia no cliente e no ERP desde sempre; o que faltava era
        este meio do caminho. Sem ele o formulario de venda so enxerga as 50
        primeiras pessoas da empresa -- e sao 3.117 migradas. O comprador e o
        corretor de qualquer unidade praticamente nunca estao entre as 50, e o
        campo aparece VAZIO mesmo com o id gravado na unidade.

        Foi assim que a tela "Editar venda" passou a nao mostrar nem comprador
        nem corretor depois da migracao, com os dois no banco.
        """
        if self.erp_client is None:
            raise ConstructionInvalidValueError(
                message="A integração com o ERP está indisponível para consultar pessoas.",
                error_code="CONSTRUCTION_ERP_INTEGRATION_UNAVAILABLE",
            )

        return await self.erp_client.list_person_summaries(
            company_id=company_id,
            user_id=actor_user_id,
            search=search,
            page=page,
            page_size=page_size,
            person_id=person_id,
        )

    async def get_project(self, *, company_id: UUID, project_id: UUID) -> ConstructionProject:
        project = await self.repository.get_project(company_id=company_id, project_id=project_id)
        if not project:
            raise ConstructionNotFoundError(resource_name="a obra")

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
                raise ConstructionDuplicateCodeError(resource_name="a obra", code=next_code)

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
            raise ConstructionDuplicateCodeError(resource_name="o bloco", code=request.code)

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
                raise ConstructionDuplicateCodeError(resource_name="o bloco", code=next_code)

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
                message="A obra precisa de um centro de custo sintético antes de cadastrar unidades.",
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
            raise ConstructionDuplicateCodeError(resource_name="a unidade", code=request.code)

        unit = ConstructionUnit(
            id=uuid4(),
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
                raise ConstructionDuplicateCodeError(resource_name="a unidade", code=next_code)

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
                message="Só é possível reservar unidade disponível.",
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
                message="Só é possível liberar a reserva de uma unidade reservada.",
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

        # Unidade ja vendida cai no mesmo caminho de proposito: e assim que a
        # venda e editada. Antes havia um atalho que devolvia a unidade intacta
        # quando ja existia contrato, e o efeito era pior que recusar -- quem
        # trocava o comprador recebia sucesso e nada mudava.
        if unit.status not in {
            ConstructionUnitStatus.AVAILABLE,
            ConstructionUnitStatus.RESERVED,
            ConstructionUnitStatus.SOLD,
        }:
            raise ConstructionInvalidValueError(
                message="A situação da unidade não permite confirmar a venda.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )

        sale_price = request.sale_price or unit.sale_price
        if sale_price is None or sale_price <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="Informe o preço de venda da unidade para confirmar a venda.",
                error_code="CONSTRUCTION_UNIT_SALE_PRICE_REQUIRED",
            )

        if not unit.analytic_cost_center_id:
            raise ConstructionInvalidValueError(
                message="A unidade precisa de um centro de custo analítico antes de confirmar a venda.",
                error_code="CONSTRUCTION_UNIT_COST_CENTER_REQUIRED",
            )

        discount_amount = (request.discount_amount or unit.discount_amount or Decimal("0")).quantize(Decimal("0.01"))
        if discount_amount >= sale_price:
            raise ConstructionInvalidValueError(
                message="O desconto da venda precisa ser menor que o preço de venda.",
                error_code="CONSTRUCTION_UNIT_DISCOUNT_EXCEEDS_SALE_PRICE",
            )

        if request.secondary_buyer_person_id is not None and request.secondary_buyer_person_id == request.buyer_person_id:
            raise ConstructionInvalidValueError(
                message="O segundo comprador precisa ser diferente do comprador principal.",
                error_code="CONSTRUCTION_UNIT_DUPLICATE_BUYER",
            )

        net_sale_price = sale_price - discount_amount
        documentations = await self._resolve_sale_documentations(unit=unit, request=request)
        documentation_total = self._sum_documentations(documentations=documentations)
        commission_offset = self._sum_composing_commissions(
            await self.repository.list_unit_commissions(company_id=company_id, unit_id=unit_id)
        )
        payment_sources = self._build_sale_payment_sources(
            request=request,
            sale_price=sale_price,
            discount_amount=discount_amount,
            documentation_total=documentation_total,
            commission_offset=commission_offset,
        )
        # Sem entrada nao ha parcela para gerar, e isso deixou de ser erro: o
        # contrato e criado assim mesmo e o usuario lanca o que cobrar pelo
        # sinal ou por aditivo. O que continua sendo recusado e a venda em que
        # nada sobra para o comprador -- banco e desconto cobrindo o preco
        # inteiro --, porque ai nao existe venda a cobrar.
        receivable_amount = self._sum_installment_sources(payment_sources=payment_sources)
        buyer_charged_amount = self._sum_buyer_charged_sources(payment_sources=payment_sources)
        if buyer_charged_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message=(
                    "The sale has nothing left to charge the buyer: entry plus bank sources and discount "
                    "already cover the sale price plus documentation."
                ),
                error_code="CONSTRUCTION_UNIT_WITHOUT_INSTALLMENT_SOURCE",
            )

        await self._replace_unit_payment_sources(unit=unit, payment_sources=payment_sources)
        await self._replace_unit_documentations(unit=unit, documentations=documentations)

        unit.status = ConstructionUnitStatus.SOLD
        unit.buyer_person_id = request.buyer_person_id
        unit.secondary_buyer_person_id = request.secondary_buyer_person_id
        unit.broker_person_id = request.broker_person_id
        unit.sale_price = sale_price
        unit.discount_amount = discount_amount
        unit.contract_signature_date = request.contract_signature_date
        unit.sale_notes = (request.sale_notes or "").strip() or None
        unit.sold_at = datetime.now(tz=UTC)
        unit.reservation_expires_at = None

        project = await self.repository.get_project(company_id=company_id, project_id=unit.project_id)
        sale_event = self._build_unit_sold_event(
            unit=unit,
            analytic_cost_center_id=unit.analytic_cost_center_id,
            first_due_date=request.first_due_date,
            installments=request.installments,
            payment_sources=payment_sources,
            documentations=documentations,
            documentation_total=documentation_total,
            net_sale_price=net_sale_price,
            receivable_amount=receivable_amount,
            commission_offset=commission_offset,
            receipt_template_id=project.receipt_template_id if project is not None else None,
            actor_user_id=actor_user_id,
        )
        dispatch_result = await self._dispatch_integration_event(
            event=sale_event,
            fallback_message="Não foi possível registrar a venda no ERP.",
        )
        if dispatch_result is not None and dispatch_result.response_event is not None:
            erp_event = dispatch_result.response_event
            self._apply_contract_snapshot_from_payload(unit=unit, payload=erp_event.payload)

        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def apply_contract_status_updated_event(self, *, event: EventEnvelope) -> ConstructionUnit:
        if event.event_type not in {ErpEventType.CONTRACT_RECEIVABLE_CREATED, ErpEventType.CONTRACT_STATUS_UPDATED}:
            raise ConstructionInvalidValueError(
                message="Tipo de evento do ERP não suportado para sincronizar o contrato da unidade.",
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
        actor_user_id: UUID | None = None,
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
                    resource_name="a requisição de compra",
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
            supplier_qualification_status=await self._resolve_supplier_qualification_status(
                company_id=company_id,
                actor_user_id=actor_user_id,
                supplier_person_id=request.supplier_person_id,
            ),
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
            raise ConstructionNotFoundError(resource_name="a requisição de compra")

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
                message="Só é possível alterar requisição em rascunho ou rejeitada.",
                error_code="CONSTRUCTION_PROCUREMENT_LOCKED",
            )

        updates = request.model_dump(exclude_unset=True)
        next_code = updates.get("code")
        if next_code is not None:
            next_code = next_code.strip()
            if not next_code:
                raise ConstructionInvalidValueError(
                    message="Informe o código da requisição.",
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
                        resource_name="a requisição de compra",
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
                message="A requisição não pode ser enviada na situação atual.",
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
                message="Só é possível aprovar requisição que está aguardando aprovação.",
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
                message="Só é possível excluir requisição em rascunho ou rejeitada.",
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
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        await self.get_project(company_id=company_id, project_id=project_id)
        unit = await self._get_unit(company_id=company_id, unit_id=request.unit_id)
        if unit.project_id != project_id:
            raise ConstructionInvalidValueError(
                message="A unidade não pertence à obra informada.",
                error_code="CONSTRUCTION_UNIT_PROJECT_MISMATCH",
            )

        schedule_phase = await self._get_schedule_phase(company_id=company_id, phase_id=request.schedule_phase_id)
        if schedule_phase.project_id != project_id:
            raise ConstructionInvalidValueError(
                message="A fase do cronograma não pertence à obra informada.",
                error_code="CONSTRUCTION_SCHEDULE_PROJECT_MISMATCH",
            )

        existing_measurement = await self.repository.get_measurement_by_code(
            company_id=company_id,
            project_id=project_id,
            code=request.code,
        )
        if existing_measurement:
            raise ConstructionDuplicateCodeError(resource_name="a medição", code=request.code)

        sequence_number = request.sequence_number
        if sequence_number is None:
            sequence_number = await self.repository.get_next_measurement_sequence(
                company_id=company_id,
                project_id=project_id,
            )

        gross_amount = request.gross_amount or request.measured_amount
        if gross_amount is None or gross_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="Informe o valor bruto da medição.",
                error_code="CONSTRUCTION_MEASUREMENT_GROSS_REQUIRED",
            )

        retentions_amount = request.retentions_amount or Decimal("0")
        net_amount = request.net_amount or request.measured_amount or (gross_amount - retentions_amount)
        if net_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="O valor líquido da medição precisa ser maior que zero.",
                error_code="CONSTRUCTION_MEASUREMENT_NET_INVALID",
            )

        measurement = ConstructionMeasurement(
            company_id=company_id,
            project_id=project_id,
            unit_id=request.unit_id,
            schedule_phase_id=request.schedule_phase_id,
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
            supplier_qualification_status=await self._resolve_supplier_qualification_status(
                company_id=company_id,
                actor_user_id=actor_user_id,
                supplier_person_id=request.supplier_person_id,
            ),
            status=ConstructionMeasurementStatus.DRAFT,
            created_by_user_id=actor_user_id,
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
            raise ConstructionNotFoundError(resource_name="a medição")

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
                message="Medição aprovada não pode ser alterada.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        updates = request.model_dump(exclude_unset=True)
        if "unit_id" in updates:
            unit = await self._get_unit(company_id=company_id, unit_id=updates["unit_id"])
            if unit.project_id != measurement.project_id:
                raise ConstructionInvalidValueError(
                    message="A unidade não pertence à obra da medição.",
                    error_code="CONSTRUCTION_UNIT_PROJECT_MISMATCH",
                )

        if "schedule_phase_id" in updates:
            schedule_phase = await self._get_schedule_phase(company_id=company_id, phase_id=updates["schedule_phase_id"])
            if schedule_phase.project_id != measurement.project_id:
                raise ConstructionInvalidValueError(
                    message="A fase do cronograma não pertence à obra da medição.",
                    error_code="CONSTRUCTION_SCHEDULE_PROJECT_MISMATCH",
                )

        next_code = updates.get("code")
        if next_code is not None and next_code != measurement.code:
            existing_measurement = await self.repository.get_measurement_by_code(
                company_id=company_id,
                project_id=measurement.project_id,
                code=next_code,
            )
            if existing_measurement and existing_measurement.id != measurement.id:
                raise ConstructionDuplicateCodeError(resource_name="a medição", code=next_code)

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
                message="O valor líquido da medição precisa ser maior que zero.",
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

    async def submit_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Medição aprovada não pode ser enviada de novo.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        await self._assert_measurement_inspections_are_approved(
            company_id=company_id,
            measurement_id=measurement_id,
            action_label="enviar",
        )
        await self._sync_measurement_amounts_from_items(measurement=measurement)
        measurement.status = ConstructionMeasurementStatus.SUBMITTED
        measurement.rejection_reason = None
        measurement.rejected_by_user_id = None
        measurement.rejected_at = None
        measurement.submitted_by_user_id = actor_user_id
        measurement.submitted_at = datetime.now(tz=UTC)
        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def reject_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        reason: str | None = None,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Medição aprovada não pode ser rejeitada.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        measurement.status = ConstructionMeasurementStatus.REJECTED
        measurement.rejection_reason = reason.strip() if reason else None
        measurement.rejected_by_user_id = actor_user_id
        measurement.rejected_at = datetime.now(tz=UTC)
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

        # Antes das travas de unidade e fase de propósito: quem aprova precisa
        # ver o problema da FVS antes de ouvir sobre centro de custo.
        await self._assert_measurement_inspections_are_approved(
            company_id=company_id,
            measurement_id=measurement_id,
            action_label="aprovar",
        )

        if not measurement.unit_id:
            raise ConstructionInvalidValueError(
                message="Vincule a medição a uma unidade antes de aprovar.",
                error_code="CONSTRUCTION_MEASUREMENT_UNIT_REQUIRED",
            )

        if not measurement.schedule_phase_id:
            raise ConstructionInvalidValueError(
                message="Vincule a medição a uma fase do cronograma antes de aprovar.",
                error_code="CONSTRUCTION_MEASUREMENT_PHASE_REQUIRED",
            )

        unit = await self._get_unit(company_id=company_id, unit_id=measurement.unit_id)
        if not unit.analytic_cost_center_id:
            raise ConstructionInvalidValueError(
                message="A unidade precisa de um centro de custo analítico antes de aprovar medições.",
                error_code="CONSTRUCTION_UNIT_COST_CENTER_REQUIRED",
            )

        if actor_user_id is not None and measurement.submitted_by_user_id == actor_user_id:
            raise ConstructionInvalidValueError(
                message="A medição precisa ser aprovada por um usuário diferente de quem a enviou.",
                error_code="CONSTRUCTION_MEASUREMENT_SELF_APPROVAL",
            )

        await self._sync_measurement_amounts_from_items(measurement=measurement)

        measurement.status = ConstructionMeasurementStatus.APPROVED
        measurement.rejection_reason = None
        measurement.rejected_by_user_id = None
        measurement.rejected_at = None
        measurement.approved_by_user_id = actor_user_id
        if measurement.approved_at is None:
            measurement.approved_at = datetime.now(tz=UTC)

        approval_event = self._build_measurement_approved_event(
            measurement=measurement,
            analytic_cost_center_id=unit.analytic_cost_center_id,
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

    async def list_measurement_items(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
    ) -> list[ConstructionMeasurementItem]:
        await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        return await self.repository.list_measurement_items(company_id=company_id, measurement_id=measurement_id)

    async def get_measurement_item(self, *, company_id: UUID, item_id: UUID) -> ConstructionMeasurementItem:
        item = await self.repository.get_measurement_item(company_id=company_id, item_id=item_id)
        if not item:
            raise ConstructionNotFoundError(resource_name="o item da medição")

        return item

    async def create_measurement_item(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        request: ConstructionMeasurementItemCreate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurementItem:
        measurement = await self._get_editable_measurement(company_id=company_id, measurement_id=measurement_id)

        service_template = None
        if request.service_template_id is not None:
            service_template = await self.repository.get_service_template(
                company_id=company_id,
                service_template_id=request.service_template_id,
            )
            if service_template is None:
                raise ConstructionNotFoundError(resource_name="o serviço do catálogo")

        description = (request.description or "").strip()
        if not description and service_template is not None:
            description = service_template.name

        if not description:
            raise ConstructionInvalidValueError(
                message="O item da medição precisa de uma descrição ou de um serviço do catálogo.",
                error_code="CONSTRUCTION_MEASUREMENT_ITEM_DESCRIPTION_REQUIRED",
            )

        existing_items = await self.repository.list_measurement_items(
            company_id=company_id,
            measurement_id=measurement_id,
        )
        for existing_item in existing_items:
            same_template = (
                service_template is not None and existing_item.service_template_id == service_template.id
            )
            if same_template or existing_item.description.casefold() == description.casefold():
                raise ConstructionInvalidValueError(
                    message=f"O serviço {description} já faz parte desta medição.",
                    error_code="CONSTRUCTION_MEASUREMENT_ITEM_DUPLICATE_SERVICE",
                )

        sequence_number = request.sequence_number
        if sequence_number is None:
            sequence_number = await self.repository.get_next_measurement_item_sequence(
                company_id=company_id,
                measurement_id=measurement_id,
            )

        item = ConstructionMeasurementItem(
            company_id=company_id,
            measurement_id=measurement_id,
            sequence_number=sequence_number,
            service_template_id=service_template.id if service_template is not None else None,
            product_id=request.product_id or (service_template.product_id if service_template else None),
            product_description=(request.product_description or "").strip() or None,
            description=description,
            amount=request.amount.quantize(Decimal("0.01")),
            start_date=request.start_date,
            end_date=request.end_date,
            inspector_person_id=request.inspector_person_id,
            inspection_status=ConstructionInspectionStatus.PENDING,
            created_by_user_id=actor_user_id,
        )
        self._validate_item_period(start_date=item.start_date, end_date=item.end_date)
        self._validate_not_in_the_future(start_date=item.start_date, end_date=item.end_date)
        template_has_items = service_template is not None and any(
            section.items for section in service_template.sections
        )
        if item.end_date is not None and template_has_items:
            raise ConstructionInvalidValueError(
                message=INSPECTIONS_PENDING_MESSAGE,
                error_code="CONSTRUCTION_MEASUREMENT_ITEM_END_DATE_BLOCKED",
            )

        await self.repository.add(item)
        await self.repository.commit()
        await self.repository.refresh(item)

        if service_template is not None:
            inspection_sequence = 0
            for section in service_template.sections:
                for template_item in section.items:
                    inspection_sequence += 1
                    await self.repository.add(
                        ConstructionMeasurementItemInspection(
                            company_id=company_id,
                            measurement_item_id=item.id,
                            sequence_number=inspection_sequence,
                            section_name=section.name,
                            description=template_item.description,
                            verification_method=template_item.verification_method,
                            requires_comment=template_item.requires_comment,
                            requires_photo=template_item.requires_photo,
                            inspector_person_id=item.inspector_person_id,
                            status=ConstructionInspectionStatus.PENDING,
                            rounds_count=0,
                        )
                    )
            await self.repository.commit()

        await self._sync_measurement_amounts_from_items(measurement=measurement)
        await self.repository.commit()
        return await self.get_measurement_item(company_id=company_id, item_id=item.id)

    async def update_measurement_item(
        self,
        *,
        company_id: UUID,
        item_id: UUID,
        request: ConstructionMeasurementItemUpdate,
    ) -> ConstructionMeasurementItem:
        item = await self.get_measurement_item(company_id=company_id, item_id=item_id)
        measurement = await self._get_editable_measurement(
            company_id=company_id,
            measurement_id=item.measurement_id,
        )

        updates = request.model_dump(exclude_unset=True)
        if "description" in updates and updates["description"]:
            updates["description"] = updates["description"].strip()

        if "product_description" in updates:
            updates["product_description"] = (updates["product_description"] or "").strip() or None

        if "amount" in updates and updates["amount"] is not None:
            updates["amount"] = updates["amount"].quantize(Decimal("0.01"))

        self._apply_updates(entity=item, updates=updates)
        self._validate_item_period(start_date=item.start_date, end_date=item.end_date)
        self._validate_not_in_the_future(start_date=item.start_date, end_date=item.end_date)
        if "end_date" in updates and item.end_date is not None:
            await self._assert_every_inspection_is_approved(item=item)

        await self._sync_measurement_amounts_from_items(measurement=measurement)
        await self.repository.commit()
        return await self.get_measurement_item(company_id=company_id, item_id=item.id)

    async def delete_measurement_item(self, *, company_id: UUID, item_id: UUID) -> None:
        item = await self.get_measurement_item(company_id=company_id, item_id=item_id)
        measurement = await self._get_editable_measurement(
            company_id=company_id,
            measurement_id=item.measurement_id,
        )
        await self.repository.delete(item)
        await self.repository.commit()
        await self._sync_measurement_amounts_from_items(measurement=measurement)
        await self.repository.commit()

    async def create_measurement_item_inspection(
        self,
        *,
        company_id: UUID,
        item_id: UUID,
        request: ConstructionMeasurementItemInspectionCreate,
    ) -> ConstructionMeasurementItemInspection:
        item = await self.get_measurement_item(company_id=company_id, item_id=item_id)
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)

        sequence_number = request.sequence_number
        if sequence_number is None:
            sequence_number = await self.repository.get_next_inspection_sequence(
                company_id=company_id,
                measurement_item_id=item_id,
            )

        inspection = ConstructionMeasurementItemInspection(
            company_id=company_id,
            measurement_item_id=item_id,
            sequence_number=sequence_number,
            description=request.description.strip(),
            verification_method=(request.verification_method or "").strip() or None,
            start_date=request.start_date,
            end_date=request.end_date,
            inspector_person_id=request.inspector_person_id or item.inspector_person_id,
            status=ConstructionInspectionStatus.PENDING,
            rounds_count=0,
        )
        self._validate_item_period(start_date=inspection.start_date, end_date=inspection.end_date)
        await self.repository.add(inspection)
        await self.repository.commit()
        await self.repository.refresh(inspection)
        return inspection

    async def update_measurement_item_inspection(
        self,
        *,
        company_id: UUID,
        inspection_id: UUID,
        request: ConstructionMeasurementItemInspectionUpdate,
    ) -> ConstructionMeasurementItemInspection:
        inspection = await self._get_inspection(company_id=company_id, inspection_id=inspection_id)
        item = await self.get_measurement_item(company_id=company_id, item_id=inspection.measurement_item_id)
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)

        updates = request.model_dump(exclude_unset=True)
        if "description" in updates and updates["description"]:
            updates["description"] = updates["description"].strip()

        if "verification_method" in updates:
            updates["verification_method"] = (updates["verification_method"] or "").strip() or None

        self._apply_updates(entity=inspection, updates=updates)
        self._validate_item_period(start_date=inspection.start_date, end_date=inspection.end_date)
        await self.repository.commit()
        await self.repository.refresh(inspection)
        return inspection

    async def verify_measurement_item_inspection(
        self,
        *,
        company_id: UUID,
        inspection_id: UUID,
        request: ConstructionMeasurementInspectionVerifyRequest,
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
        actor_can_waive: bool = False,
    ) -> ConstructionMeasurementItemInspection:
        """Records one verification round: the first one or a reinspection.

        The round number comes from the server, never from the client: with N
        rounds the caller has no way of knowing it, and letting it choose is the
        race that the advisory lock exists to close.
        """
        inspection = await self._get_inspection(company_id=company_id, inspection_id=inspection_id)
        item = await self.get_measurement_item(company_id=company_id, item_id=inspection.measurement_item_id)
        measurement = await self.get_measurement(company_id=company_id, measurement_id=item.measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Medição aprovada não aceita novas verificações.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        if request.status == ConstructionInspectionStatus.WAIVED and not actor_can_waive:
            raise ConstructionInvalidValueError(
                message="Dispensar a reinspeção exige permissão de exclusão em Medições.",
                error_code="CONSTRUCTION_INSPECTION_WAIVE_NOT_ALLOWED",
            )

        # Em rascunho, reverificar e' correcao de clique errado e as duas rodadas
        # ficam no historico. Depois de enviada, nao: reabrir uma linha aprovada
        # numa medicao em aprovacao e' materia de ocorrencia.
        if (
            inspection.status == ConstructionInspectionStatus.COMPLIANT
            and measurement.status != ConstructionMeasurementStatus.DRAFT
        ):
            raise ConstructionInvalidValueError(
                message=(
                    "Esta linha da FVS já foi aprovada e a medição já foi enviada. "
                    "Registre uma ocorrência para reabri-la."
                ),
                error_code="CONSTRUCTION_INSPECTION_ALREADY_APPROVED",
            )

        comment = (request.comment or "").strip()
        needs_comment = request.status != ConstructionInspectionStatus.COMPLIANT or inspection.requires_comment
        if needs_comment and not comment:
            raise ConstructionInvalidValueError(
                message="Descreva o que foi encontrado: esta verificação exige comentário.",
                error_code="CONSTRUCTION_INSPECTION_COMMENT_REQUIRED",
            )

        sequence_number = await self.repository.get_next_inspection_round_sequence(
            company_id=company_id,
            inspection_id=inspection.id,
        )
        inspector_person_id = (
            request.inspector_person_id or inspection.inspector_person_id or item.inspector_person_id
        )
        inspector_name = await self._resolve_actor_name(
            company_id=company_id,
            actor_user_id=actor_user_id,
            actor_person_id=inspector_person_id,
        )
        # Quem inspecionou e quem lancou costumam ser a mesma pessoa; resolver o
        # nome duas vezes seria uma ida ao ERP a mais por rodada.
        if actor_person_id == inspector_person_id:
            recorded_by_name = inspector_name
        else:
            recorded_by_name = await self._resolve_actor_name(
                company_id=company_id,
                actor_user_id=actor_user_id,
                actor_person_id=actor_person_id,
            )

        verified_at = datetime.now(tz=UTC)
        await self.repository.add(
            ConstructionInspectionRound(
                company_id=company_id,
                inspection_id=inspection.id,
                measurement_item_id=item.id,
                sequence_number=sequence_number,
                status=request.status,
                verified_at=verified_at,
                inspected_on=request.inspected_on,
                inspector_person_id=inspector_person_id,
                inspector_name=inspector_name,
                recorded_by_user_id=actor_user_id,
                recorded_by_name=recorded_by_name,
                comment=comment or None,
                source=ConstructionInspectionRoundSource.MANUAL,
            )
        )
        inspection.status = request.status
        inspection.rounds_count = (inspection.rounds_count or 0) + 1
        inspection.last_verified_at = verified_at

        if request.open_occurrence and request.status == ConstructionInspectionStatus.NON_COMPLIANT:
            await self._open_occurrence_for_failed_round(
                company_id=company_id,
                item=item,
                inspection=inspection,
                problem=comment,
                inspector_person_id=inspector_person_id,
                actor_user_id=actor_user_id,
                opened_on=request.inspected_on,
            )

        item.inspection_status = await self._resolve_item_inspection_status(item=item)
        await self.repository.commit()
        # Rele em vez de refresh: refresh atualiza colunas, mas a colecao de
        # rodadas ja carregada nao seria sobrescrita (expire_on_commit=False).
        return await self._get_inspection(company_id=company_id, inspection_id=inspection_id)

    async def _open_occurrence_for_failed_round(
        self,
        *,
        company_id: UUID,
        item: ConstructionMeasurementItem,
        inspection: ConstructionMeasurementItemInspection,
        problem: str,
        inspector_person_id: UUID | None,
        actor_user_id: UUID | None,
        opened_on: date | None,
    ) -> None:
        """Atalho opcional: abre a ocorrencia junto com a reprovacao.

        Idempotente por inspecao: uma linha reprovada tres vezes nao vira tres
        ocorrencias abertas. Fechar continua sendo gesto humano -- uma rodada
        aprovada depois NAO resolve a ocorrencia, porque resolver exige uma
        solucao escrita que so uma pessoa tem.
        """
        already_open = any(
            occurrence.inspection_id == inspection.id
            and occurrence.status == ConstructionOccurrenceStatus.OPEN
            for occurrence in (item.occurrences or [])
        )
        if already_open:
            return

        sequence_number = await self.repository.get_next_occurrence_sequence(
            company_id=company_id,
            measurement_item_id=item.id,
        )
        await self.repository.add(
            ConstructionMeasurementItemOccurrence(
                company_id=company_id,
                measurement_item_id=item.id,
                inspection_id=inspection.id,
                sequence_number=sequence_number,
                problem=problem or f"Reprovado na verificação: {inspection.description}",
                status=ConstructionOccurrenceStatus.OPEN,
                opened_at=opened_on or datetime.now(tz=UTC).date(),
                inspector_person_id=inspector_person_id,
                registered_by_user_id=actor_user_id,
            )
        )

    async def list_inspection_rounds(
        self,
        *,
        company_id: UUID,
        inspection_id: UUID,
    ) -> list[ConstructionInspectionRound]:
        await self._get_inspection(company_id=company_id, inspection_id=inspection_id)
        return await self.repository.list_inspection_rounds(
            company_id=company_id,
            inspection_id=inspection_id,
        )

    async def delete_measurement_item_inspection(self, *, company_id: UUID, inspection_id: UUID) -> None:
        inspection = await self._get_inspection(company_id=company_id, inspection_id=inspection_id)
        item = await self.get_measurement_item(company_id=company_id, item_id=inspection.measurement_item_id)
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)
        if inspection.rounds_count:
            raise ConstructionResourceInUseError(
                message="Esta linha da FVS já foi verificada e não pode ser excluída.",
                error_code="CONSTRUCTION_INSPECTION_HAS_HISTORY",
            )

        await self.repository.delete(inspection)
        await self.repository.commit()

    async def create_measurement_item_occurrence(
        self,
        *,
        company_id: UUID,
        item_id: UUID,
        request: ConstructionMeasurementItemOccurrenceCreate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurementItemOccurrence:
        item = await self.get_measurement_item(company_id=company_id, item_id=item_id)
        await self.get_measurement(company_id=company_id, measurement_id=item.measurement_id)

        sequence_number = request.sequence_number
        if sequence_number is None:
            sequence_number = await self.repository.get_next_occurrence_sequence(
                company_id=company_id,
                measurement_item_id=item_id,
            )

        occurrence = ConstructionMeasurementItemOccurrence(
            company_id=company_id,
            measurement_item_id=item_id,
            sequence_number=sequence_number,
            problem=request.problem.strip(),
            solution=(request.solution or "").strip() or None,
            status=ConstructionOccurrenceStatus.OPEN,
            opened_at=request.opened_at or datetime.now(tz=UTC).date(),
            inspector_person_id=request.inspector_person_id or item.inspector_person_id,
            registered_by_user_id=actor_user_id,
        )
        await self.repository.add(occurrence)
        await self.repository.commit()
        await self.repository.refresh(occurrence)
        return occurrence

    async def update_measurement_item_occurrence(
        self,
        *,
        company_id: UUID,
        occurrence_id: UUID,
        request: ConstructionMeasurementItemOccurrenceUpdate,
    ) -> ConstructionMeasurementItemOccurrence:
        occurrence = await self._get_occurrence(company_id=company_id, occurrence_id=occurrence_id)

        updates = request.model_dump(exclude_unset=True)
        if "problem" in updates and updates["problem"]:
            updates["problem"] = updates["problem"].strip()

        if "solution" in updates:
            updates["solution"] = (updates["solution"] or "").strip() or None

        next_status = updates.get("status", occurrence.status)
        if next_status == ConstructionOccurrenceStatus.RESOLVED:
            solution = updates.get("solution", occurrence.solution)
            if not solution:
                raise ConstructionInvalidValueError(
                    message="Descreva a solução para resolver a ocorrência.",
                    error_code="CONSTRUCTION_OCCURRENCE_SOLUTION_REQUIRED",
                )

            if not updates.get("closed_at") and occurrence.closed_at is None:
                updates["closed_at"] = datetime.now(tz=UTC).date()

        if next_status == ConstructionOccurrenceStatus.OPEN:
            updates["closed_at"] = None

        self._apply_updates(entity=occurrence, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(occurrence)
        return occurrence

    async def delete_measurement_item_occurrence(self, *, company_id: UUID, occurrence_id: UUID) -> None:
        occurrence = await self._get_occurrence(company_id=company_id, occurrence_id=occurrence_id)
        await self.repository.delete(occurrence)
        await self.repository.commit()

    async def build_measurement_items_summary(self, *, company_id: UUID, measurement_id: UUID) -> dict[str, Any]:
        items = await self.repository.list_measurement_items(company_id=company_id, measurement_id=measurement_id)
        pending_inspections, non_compliant_inspections = (
            await self.repository.summarize_measurement_inspection_blockers(
                company_id=company_id,
                measurement_id=measurement_id,
            )
        )
        open_occurrences = await self.repository.count_open_measurement_occurrences(
            company_id=company_id,
            measurement_id=measurement_id,
        )
        return {
            "items_total_amount": sum((item.amount for item in items), Decimal("0")),
            "items_count": len(items),
            "pending_inspections_count": pending_inspections,
            "non_compliant_inspections_count": non_compliant_inspections,
            "open_occurrences_count": open_occurrences,
        }

    async def list_service_templates(
        self,
        *,
        company_id: UUID,
        only_active: bool = True,
        search: str | None = None,
        only_deleted: bool = False,
    ) -> list[ConstructionServiceTemplate]:
        return await self.repository.list_service_templates(
            company_id=company_id,
            only_active=only_active,
            search=search,
            only_deleted=only_deleted,
        )

    async def get_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        include_deleted: bool = False,
    ) -> ConstructionServiceTemplate:
        service_template = await self.repository.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
            include_deleted=include_deleted,
        )
        if service_template is None:
            raise ConstructionNotFoundError(resource_name="o serviço do catálogo")

        return service_template

    async def list_service_template_audits(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
    ) -> list[ConstructionServiceTemplateAudit]:
        """Historico do servico, do mais recente para o mais antigo.

        Le o servico com ``include_deleted`` porque o historico de um servico
        excluido e justamente o que responde quem o excluiu.
        """
        await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
            include_deleted=True,
        )
        return await self.repository.list_service_template_audits(
            company_id=company_id,
            service_template_id=service_template_id,
        )

    @staticmethod
    def _build_service_template_snapshot(
        service_template: ConstructionServiceTemplate,
    ) -> dict[str, Any]:
        """Estrutura completa do servico no momento do evento.

        Guardada inteira, e nao como diferenca: e o snapshot que permite dizer
        anos depois como a ficha estava quando a medicao foi feita, sem ter de
        reconstruir a cadeia toda de alteracoes.
        """
        return {
            "name": service_template.name,
            "product_id": str(service_template.product_id) if service_template.product_id else None,
            "source_file_name": service_template.source_file_name,
            "is_active": bool(service_template.is_active),
            "sections": [
                {
                    "sequence_number": section.sequence_number,
                    "name": section.name,
                    "items": [
                        {
                            "sequence_number": item.sequence_number,
                            "description": item.description,
                            "verification_method": item.verification_method,
                            "requires_comment": bool(item.requires_comment),
                            "requires_photo": bool(item.requires_photo),
                        }
                        for item in section.items
                    ],
                }
                for section in service_template.sections
            ],
        }

    async def _resolve_actor_name(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        actor_person_id: UUID | None,
    ) -> str | None:
        if actor_person_id is None or self.erp_client is None:
            return None

        return await self.erp_client.get_person_name(
            company_id=company_id,
            user_id=actor_user_id,
            person_id=actor_person_id,
        )

    async def _record_service_template_audit(
        self,
        *,
        company_id: UUID,
        service_template: ConstructionServiceTemplate,
        event: str,
        summary: str | None = None,
        source: str = "manual",
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> None:
        """Acrescenta uma linha ao historico do servico. Nao commita.

        Fica na mesma transacao da alteracao de proposito: se a gravacao voltar
        atras, o historico nao pode ficar afirmando que ela aconteceu.
        """
        actor_name = await self._resolve_actor_name(
            company_id=company_id,
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        sequence_number = await self.repository.get_next_service_template_audit_sequence(
            company_id=company_id,
            service_template_id=service_template.id,
        )
        await self.repository.add(
            ConstructionServiceTemplateAudit(
                company_id=company_id,
                service_template_id=service_template.id,
                service_template_name=service_template.name,
                sequence_number=sequence_number,
                event=event,
                source=source,
                actor_user_id=actor_user_id,
                actor_person_id=actor_person_id,
                actor_name=actor_name,
                summary=summary,
                snapshot=self._build_service_template_snapshot(service_template),
                created_at=datetime.now(UTC),
            )
        )

    async def update_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        request: ConstructionServiceTemplateUpdate,
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> ConstructionServiceTemplate:
        service_template = await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
        )
        updates = request.model_dump(exclude_unset=True)
        previous_name = service_template.name
        previous_is_active = bool(service_template.is_active)

        if "name" in updates and updates["name"]:
            next_name = updates["name"].strip().upper()
            if next_name != service_template.name:
                duplicated = await self.repository.get_service_template_by_name(
                    company_id=company_id,
                    name=next_name,
                )
                if duplicated is not None:
                    raise ConstructionDuplicateCodeError(
                        resource_name="o serviço do catálogo",
                        code=next_name,
                    )

            updates["name"] = next_name

        self._apply_updates(entity=service_template, updates=updates)
        service_template.updated_by_user_id = actor_user_id

        # Activating and deactivating get their own event: taking a service out
        # of circulation is how the catalog is really curated, and reading
        # "changed" in the trail would not answer who deactivated it.
        next_is_active = bool(service_template.is_active)
        if next_is_active != previous_is_active:
            event = "activated" if next_is_active else "deactivated"
            summary = "Serviço reativado." if next_is_active else "Serviço desativado."
        else:
            event = "updated"
            summary = (
                f"Nome alterado de '{previous_name}' para '{service_template.name}'."
                if service_template.name != previous_name
                else "Cabeçalho do serviço alterado."
            )

        await self._record_service_template_audit(
            company_id=company_id,
            service_template=service_template,
            event=event,
            summary=summary,
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        await self.repository.commit()
        return await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template.id,
        )

    @staticmethod
    def _normalize_section_inputs(
        sections: list[ConstructionServiceTemplateSectionInput],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen_section_names: set[str] = set()

        for section_position, section in enumerate(sections, start=1):
            section_name = " ".join(section.name.split()).strip().upper()
            if not section_name:
                raise ConstructionInvalidValueError(
                    message="Informe o nome da seção.",
                    error_code="CONSTRUCTION_TEMPLATE_SECTION_NAME_REQUIRED",
                )

            if section_name in seen_section_names:
                raise ConstructionInvalidValueError(
                    message=f"A seção '{section_name}' aparece mais de uma vez neste serviço.",
                    error_code="CONSTRUCTION_TEMPLATE_DUPLICATE_SECTION",
                )

            seen_section_names.add(section_name)
            seen_descriptions: set[str] = set()
            items: list[dict[str, Any]] = []

            for item_position, item in enumerate(section.items, start=1):
                description = " ".join(item.description.split()).strip().upper()
                verification_method = " ".join(item.verification_method.split()).strip().upper()
                if not description or not verification_method:
                    raise ConstructionInvalidValueError(
                        message="Todo item de inspeção precisa de descrição e método de verificação.",
                        error_code="CONSTRUCTION_TEMPLATE_ITEM_INCOMPLETE",
                    )

                if description in seen_descriptions:
                    raise ConstructionInvalidValueError(
                        message=f"O item '{description}' aparece mais de uma vez na seção '{section_name}'.",
                        error_code="CONSTRUCTION_TEMPLATE_DUPLICATE_ITEM",
                    )

                seen_descriptions.add(description)
                items.append(
                    {
                        "sequence_number": item.sequence_number or item_position,
                        "description": description,
                        "verification_method": verification_method,
                        "requires_comment": item.requires_comment,
                        "requires_photo": item.requires_photo,
                    }
                )

            normalized.append(
                {
                    "sequence_number": section.sequence_number or section_position,
                    "name": section_name,
                    "items": items,
                }
            )

        return normalized

    @staticmethod
    def _build_sections(
        *,
        company_id: UUID,
        service_template_id: UUID,
        normalized_sections: list[dict[str, Any]],
    ) -> list[ConstructionServiceTemplateSection]:
        sections: list[ConstructionServiceTemplateSection] = []
        for normalized in normalized_sections:
            section = ConstructionServiceTemplateSection(
                company_id=company_id,
                service_template_id=service_template_id,
                sequence_number=normalized["sequence_number"],
                name=normalized["name"],
            )
            section.items = [
                ConstructionServiceTemplateItem(
                    company_id=company_id,
                    service_template_id=service_template_id,
                    sequence_number=item["sequence_number"],
                    description=item["description"],
                    verification_method=item["verification_method"],
                    requires_comment=item["requires_comment"],
                    requires_photo=item["requires_photo"],
                )
                for item in normalized["items"]
            ]
            sections.append(section)

        return sections

    async def create_service_template(
        self,
        *,
        company_id: UUID,
        request: ConstructionServiceTemplateCreate,
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> ConstructionServiceTemplate:
        name = " ".join(request.name.split()).strip().upper()
        duplicated = await self.repository.get_service_template_by_name(company_id=company_id, name=name)
        if duplicated is not None:
            raise ConstructionDuplicateCodeError(resource_name="o serviço do catálogo", code=name)

        normalized_sections = self._normalize_section_inputs(request.sections)

        service_template = ConstructionServiceTemplate(
            company_id=company_id,
            name=name,
            product_id=request.product_id,
            is_active=request.is_active,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        await self.repository.add(service_template)
        await self.repository.commit()
        await self.repository.refresh(service_template)

        for section in self._build_sections(
            company_id=company_id,
            service_template_id=service_template.id,
            normalized_sections=normalized_sections,
        ):
            await self.repository.add(section)

        await self.repository.commit()
        created = await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template.id,
        )
        # Recorded after the sections are committed so the snapshot carries the
        # real structure instead of an empty header.
        await self._record_service_template_audit(
            company_id=company_id,
            service_template=created,
            event="created",
            summary=self._describe_service_template_structure(created),
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        await self.repository.commit()
        return created

    @staticmethod
    def _describe_service_template_structure(service_template: ConstructionServiceTemplate) -> str:
        sections_count = len(service_template.sections)
        items_count = sum(len(section.items) for section in service_template.sections)
        sections_label = "seção" if sections_count == 1 else "seções"
        items_label = "item" if items_count == 1 else "itens"
        return f"{sections_count} {sections_label}, {items_count} {items_label}."

    async def replace_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        request: ConstructionServiceTemplateReplace,
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> ConstructionServiceTemplate:
        """Replaces the header and the whole structure of the service.

        Allowed even when a measurement already uses it: measurement inspection
        items are a copy, not a reference, so revising the sheet never rewrites
        what was already checked on site.
        """
        service_template = await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
        )

        name = " ".join(request.name.split()).strip().upper()
        if name != service_template.name:
            duplicated = await self.repository.get_service_template_by_name(company_id=company_id, name=name)
            if duplicated is not None:
                raise ConstructionDuplicateCodeError(resource_name="o serviço do catálogo", code=name)

        normalized_sections = self._normalize_section_inputs(request.sections)

        self._apply_updates(
            entity=service_template,
            updates={
                "name": name,
                "product_id": request.product_id,
                "is_active": request.is_active,
            },
        )
        service_template.updated_by_user_id = actor_user_id
        await self.repository.replace_service_template_sections(
            company_id=company_id,
            service_template_id=service_template.id,
            sections=self._build_sections(
                company_id=company_id,
                service_template_id=service_template.id,
                normalized_sections=normalized_sections,
            ),
        )
        await self.repository.commit()
        replaced = await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template.id,
        )
        await self._record_service_template_audit(
            company_id=company_id,
            service_template=replaced,
            event="replaced",
            summary=self._describe_service_template_structure(replaced),
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        await self.repository.commit()
        return replaced

    async def delete_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> None:
        """Takes the service out of the catalog, unless a measurement used it.

        The delete is SOFT: the row stays with deleted_at filled in and stops
        answering every query. A physical delete would take the audit trail with
        it -- both this service's own history and, through the measurement FK
        with ondelete SET NULL, the link back to the sheet that originated the
        inspection, which is precisely what the FVS exists to prove.

        A service already used in a measurement is still refused. That is now a
        catalog rule, not a data-integrity one: what the operation depends on is
        taken out of circulation by deactivating it, which keeps it readable in
        the measurements that reference it.
        """
        service_template = await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
        )
        usage_count = await self.repository.count_measurement_items_by_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
        )
        if usage_count:
            raise ConstructionResourceInUseError(
                message=(
                    f"Este serviço já foi usado em {usage_count} item(ns) de medição. "
                    "Desative o serviço em vez de excluir."
                ),
                error_code="CONSTRUCTION_TEMPLATE_IN_USE",
            )

        # Recorded BEFORE the flag is set, so the snapshot holds the sheet as it
        # was when it left the catalog.
        await self._record_service_template_audit(
            company_id=company_id,
            service_template=service_template,
            event="deleted",
            summary="Serviço excluído do catálogo.",
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        service_template.deleted_at = datetime.now(UTC)
        service_template.deleted_by_user_id = actor_user_id
        service_template.updated_by_user_id = actor_user_id
        await self.repository.commit()

    async def list_documentation_types(
        self,
        *,
        company_id: UUID,
        only_active: bool = True,
        search: str | None = None,
    ) -> list[ConstructionDocumentationTypeModel]:
        await self._ensure_default_documentation_types(company_id=company_id)
        return await self.repository.list_documentation_types(
            company_id=company_id,
            only_active=only_active,
            search=search,
        )

    async def _ensure_default_documentation_types(self, *, company_id: UUID) -> None:
        """Semeia os quatro tipos do legado na primeira vez que a empresa olha o catalogo.

        A migration cobre quem ja tem projeto; empresa criada depois cai aqui. A
        verificacao e por ``system_code`` justamente para que renomear
        "Avaliacao" nao faca o seed recria-la.
        """
        if company_id in self._companies_with_seeded_documentation_types:
            return

        default_codes = [system_code for system_code, _ in ConstructionDocumentationType.DEFAULT_TYPES]
        existing = await self.repository.list_documentation_types_by_system_codes(
            company_id=company_id,
            system_codes=default_codes,
        )
        existing_codes = {documentation_type.system_code for documentation_type in existing}
        missing = [
            (system_code, name)
            for system_code, name in ConstructionDocumentationType.DEFAULT_TYPES
            if system_code not in existing_codes
        ]
        if missing:
            for system_code, name in missing:
                await self.repository.upsert_documentation_type_system_code(
                    company_id=company_id,
                    name=name,
                    normalized_name=ConstructionDocumentationType.normalize_name(name),
                    system_code=system_code,
                )

            await self.repository.commit()

        # O seed e idempotente, mas o combobox lista a cada tecla: sem isto
        # cada busca pagaria a consulta dos quatro codigos de novo.
        self._companies_with_seeded_documentation_types.add(company_id)

    async def create_documentation_type(
        self,
        *,
        company_id: UUID,
        request: ConstructionDocumentationTypeCreate,
    ) -> ConstructionDocumentationTypeModel:
        documentation_type = await self._get_or_create_documentation_type(
            company_id=company_id,
            name=request.name,
        )
        # Recriar um tipo inativo e o jeito de reativa-lo: foi pedido de
        # proposito, ao contrario do que acontece ao digitar o nome na venda.
        documentation_type.is_active = True
        await self.repository.commit()
        await self.repository.refresh(documentation_type)
        return documentation_type

    async def update_documentation_type(
        self,
        *,
        company_id: UUID,
        documentation_type_id: UUID,
        request: ConstructionDocumentationTypeUpdate,
    ) -> ConstructionDocumentationTypeModel:
        documentation_type = await self.repository.get_documentation_type(
            company_id=company_id,
            documentation_type_id=documentation_type_id,
        )
        if documentation_type is None:
            raise ConstructionNotFoundError(resource_name="o tipo de documentação")

        # exclude_none porque o cliente manda `name: null` quando so alterna o
        # is_active, e `name` e `is_active` sao NOT NULL: sem isso o PATCH de
        # inativar grava NULL e estoura IntegrityError.
        updates = request.model_dump(exclude_unset=True, exclude_none=True)
        if updates.get("name"):
            next_name = ConstructionDocumentationType.clean_name(updates["name"])
            normalized_name = ConstructionDocumentationType.normalize_name(next_name)
            if normalized_name != documentation_type.normalized_name:
                duplicated = await self.repository.get_documentation_type_by_normalized_name(
                    company_id=company_id,
                    normalized_name=normalized_name,
                )
                if duplicated is not None and duplicated.id != documentation_type.id:
                    raise ConstructionDuplicateCodeError(
                        resource_name="o tipo de documentação",
                        code=next_name,
                    )

            updates["name"] = next_name
            updates["normalized_name"] = normalized_name

        self._apply_updates(entity=documentation_type, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(documentation_type)
        return documentation_type

    async def _get_or_create_documentation_type(
        self,
        *,
        company_id: UUID,
        name: str,
    ) -> ConstructionDocumentationTypeModel:
        """Devolve o tipo com esse nome na empresa, criando-o se ainda nao existe.

        Nao decide nada sobre ``is_active``: quem chama e que sabe se um tipo
        inativo pode ser usado -- a venda recusa, o ``POST`` reativa.
        """
        clean_name = ConstructionDocumentationType.clean_name(name)
        if not clean_name:
            raise ConstructionInvalidValueError(
                message="Informe o nome do tipo de documentação.",
                error_code="CONSTRUCTION_DOCUMENTATION_TYPE_NAME_REQUIRED",
            )

        normalized_name = ConstructionDocumentationType.normalize_name(clean_name)
        documentation_type = await self.repository.get_documentation_type_by_normalized_name(
            company_id=company_id,
            normalized_name=normalized_name,
        )
        if documentation_type is not None:
            return documentation_type

        # O INSERT pode nao voltar nada porque outra requisicao criou o mesmo
        # nome no meio do caminho -- dois usuarios lancando "SEG CAIXA" ao
        # mesmo tempo e caso real no combobox da venda.
        created = await self.repository.insert_documentation_type_if_absent(
            company_id=company_id,
            name=clean_name,
            normalized_name=normalized_name,
        )
        if created is not None:
            return created

        return await self.repository.get_documentation_type_by_normalized_name(
            company_id=company_id,
            normalized_name=normalized_name,
        )

    async def import_service_templates(
        self,
        *,
        company_id: UUID,
        files: list[tuple[str, bytes]],
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        if not files:
            raise ConstructionInvalidValueError(
                message="Nenhuma planilha foi enviada para importação.",
                error_code="CONSTRUCTION_TEMPLATE_NO_FILE",
            )

        results: list[dict[str, Any]] = []
        for file_name, content in files:
            try:
                parsed = parse_service_template_spreadsheet(file_name=file_name, content=content)
            except ConstructionInvalidValueError as parse_error:
                results.append(
                    {
                        "file_name": file_name,
                        "status": "failed",
                        "message": parse_error.message,
                    }
                )
                continue

            existing_template = await self.repository.get_service_template_by_name(
                company_id=company_id,
                name=parsed.name,
            )
            if existing_template is not None:
                if any(section.items for section in existing_template.sections):
                    results.append(
                        {
                            "file_name": file_name,
                            "status": "skipped",
                            "service_template_id": existing_template.id,
                            "service_name": existing_template.name,
                            "items_count": sum(len(section.items) for section in existing_template.sections),
                            "sections_count": len(existing_template.sections),
                            "message": "O serviço já tem itens de inspeção.",
                        }
                    )
                    continue

                existing_template.source_file_name = file_name
                existing_template.updated_by_user_id = actor_user_id
                await self._persist_parsed_sections(
                    company_id=company_id,
                    service_template_id=existing_template.id,
                    parsed=parsed,
                )
                await self._record_import_audit(
                    company_id=company_id,
                    service_template_id=existing_template.id,
                    event="replaced",
                    file_name=file_name,
                    actor_user_id=actor_user_id,
                    actor_person_id=actor_person_id,
                )
                results.append(
                    {
                        "file_name": file_name,
                        "status": "updated",
                        "service_template_id": existing_template.id,
                        "service_name": existing_template.name,
                        "items_count": len(parsed.items),
                        "sections_count": len(parsed.sections),
                    }
                )
                continue

            service_template = ConstructionServiceTemplate(
                company_id=company_id,
                name=parsed.name,
                source_file_name=file_name,
                is_active=True,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
            await self.repository.add(service_template)
            await self.repository.commit()
            await self.repository.refresh(service_template)

            await self._persist_parsed_sections(
                company_id=company_id,
                service_template_id=service_template.id,
                parsed=parsed,
            )
            await self._record_import_audit(
                company_id=company_id,
                service_template_id=service_template.id,
                event="created",
                file_name=file_name,
                actor_user_id=actor_user_id,
                actor_person_id=actor_person_id,
            )
            results.append(
                {
                    "file_name": file_name,
                    "status": "created",
                    "service_template_id": service_template.id,
                    "service_name": service_template.name,
                    "items_count": len(parsed.items),
                    "sections_count": len(parsed.sections),
                }
            )

        return results

    async def _record_import_audit(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        event: str,
        file_name: str,
        actor_user_id: UUID | None,
        actor_person_id: UUID | None,
    ) -> None:
        """Registra no historico o servico que acabou de vir de uma planilha.

        Rele o servico antes de gravar porque o snapshot tem de sair com as
        secoes recem-inseridas -- a instancia que o import tem em maos ainda
        carrega a estrutura anterior.
        """
        imported = await self.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
        )
        await self._record_service_template_audit(
            company_id=company_id,
            service_template=imported,
            event=event,
            source="import",
            summary=f"Importado de '{file_name}'. {self._describe_service_template_structure(imported)}",
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        await self.repository.commit()

    async def _persist_parsed_sections(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        parsed: Any,
    ) -> None:
        for parsed_section in parsed.sections:
            section = ConstructionServiceTemplateSection(
                company_id=company_id,
                service_template_id=service_template_id,
                sequence_number=parsed_section.sequence_number,
                name=parsed_section.name,
            )
            section.items = [
                ConstructionServiceTemplateItem(
                    company_id=company_id,
                    service_template_id=service_template_id,
                    sequence_number=parsed_item.sequence_number,
                    description=parsed_item.description,
                    verification_method=parsed_item.verification_method,
                    requires_comment=False,
                    requires_photo=False,
                )
                for parsed_item in parsed_section.items
            ]
            await self.repository.add(section)

        await self.repository.commit()

    async def _assert_every_inspection_is_approved(self, *, item: ConstructionMeasurementItem) -> None:
        """Toda linha da FVS precisa estar aprovada (ou dispensada) para fechar.

        O erro acionavel vem primeiro: quem tem linha reprovada precisa saber que
        falta a REINSPECAO, nao que "falta verificar".
        """
        inspections = await self.repository.list_measurement_item_inspections(
            company_id=item.company_id,
            measurement_item_id=item.id,
        )
        if any(
            inspection.status == ConstructionInspectionStatus.NON_COMPLIANT for inspection in inspections
        ):
            raise ConstructionInvalidValueError(
                message=REINSPECTION_REQUIRED_MESSAGE,
                error_code="CONSTRUCTION_INSPECTION_REINSPECTION_REQUIRED",
            )

        if any(inspection.status == ConstructionInspectionStatus.PENDING for inspection in inspections):
            raise ConstructionInvalidValueError(
                message=INSPECTIONS_PENDING_MESSAGE,
                error_code="CONSTRUCTION_MEASUREMENT_ITEM_END_DATE_BLOCKED",
            )

    async def _assert_measurement_inspections_are_approved(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        action_label: str,
    ) -> None:
        pending, non_compliant = await self.repository.summarize_measurement_inspection_blockers(
            company_id=company_id,
            measurement_id=measurement_id,
        )
        if non_compliant:
            raise ConstructionInvalidValueError(
                message=(
                    f"A medição tem {non_compliant} item(ns) reprovado(s) na FVS. "
                    f"Registre a reinspeção aprovada antes de {action_label}."
                ),
                error_code="CONSTRUCTION_MEASUREMENT_REINSPECTION_REQUIRED",
            )

        if pending:
            raise ConstructionInvalidValueError(
                message=(
                    f"A medição tem {pending} item(ns) de FVS ainda não verificado(s). "
                    f"Conclua a verificação antes de {action_label}."
                ),
                error_code="CONSTRUCTION_MEASUREMENT_INSPECTIONS_PENDING",
            )

    @staticmethod
    def _sum_installment_sources(*, payment_sources: list[dict[str, Any]]) -> Decimal:
        return sum(
            (
                Decimal(str(payment_source["amount"]))
                for payment_source in payment_sources
                if payment_source.get("generates_installments")
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

    @staticmethod
    def _sum_buyer_charged_sources(*, payment_sources: list[dict[str, Any]]) -> Decimal:
        """Tudo que o comprador deve: o que virou parcela mais o saldo.

        O saldo nao gera parcela, mas continua sendo divida do comprador -- e
        por isso que ele entra aqui e nao em _sum_installment_sources.
        """
        return sum(
            (
                Decimal(str(payment_source["amount"]))
                for payment_source in payment_sources
                if str(payment_source["source_type"]) in ConstructionUnitPaymentSource.BUYER_CHARGED_SOURCES
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

    async def _replace_unit_payment_sources(
        self,
        *,
        unit: ConstructionUnit,
        payment_sources: list[dict[str, Any]],
    ) -> None:
        await self.repository.replace_unit_children(
            ConstructionUnitPaymentSourceModel,
            company_id=unit.company_id,
            unit_id=unit.id,
            entities=[
                ConstructionUnitPaymentSourceModel(
                    company_id=unit.company_id,
                    unit_id=unit.id,
                    source_type=str(payment_source["source_type"]),
                    amount=Decimal(str(payment_source["amount"])),
                    due_date=(
                        date.fromisoformat(str(payment_source["due_date"]))
                        if payment_source.get("due_date")
                        else None
                    ),
                    installments=int(payment_source.get("installments") or 1),
                    generates_installments=bool(payment_source.get("generates_installments")),
                )
                for payment_source in payment_sources
            ],
        )

    async def _resolve_sale_documentations(
        self,
        *,
        unit: ConstructionUnit,
        request: ConstructionUnitSaleConfirmRequest,
    ) -> list[dict[str, Any]]:
        """Resolve cada item de documentacao para um tipo do catalogo da empresa.

        O tipo vem por id quando o usuario escolheu um existente, ou por nome
        quando ele digitou um novo no combobox -- e so aqui o tipo novo e
        criado, nunca ao digitar.
        """
        items = request.documentations or []
        if not items:
            return []

        current_type_ids = {
            documentation.documentation_type_id
            for documentation in await self.repository.list_unit_documentations(
                company_id=unit.company_id,
                unit_id=unit.id,
            )
        }

        documentations: list[dict[str, Any]] = []
        seen_type_ids: set[UUID] = set()
        for sequence_number, item in enumerate(items, start=1):
            if item.documentation_type_id is not None:
                documentation_type = await self.repository.get_documentation_type(
                    company_id=unit.company_id,
                    documentation_type_id=item.documentation_type_id,
                )
                if documentation_type is None:
                    raise ConstructionNotFoundError(resource_name="o tipo de documentação")
            else:
                documentation_type = await self._get_or_create_documentation_type(
                    company_id=unit.company_id,
                    name=item.name or "",
                )

            # Inativar um tipo nao pode travar a edicao de uma venda que ja o
            # usava: trocar o comprador quebraria por causa do catalogo. Vale
            # igual para o tipo escolhido pelo id e para o digitado pelo nome
            # -- e a venda nunca reativa o tipo, so tolera.
            if not documentation_type.is_active and documentation_type.id not in current_type_ids:
                raise ConstructionInvalidValueError(
                    message=f"O tipo de documentação '{documentation_type.name}' está inativo.",
                    error_code="CONSTRUCTION_DOCUMENTATION_TYPE_INACTIVE",
                )

            if documentation_type.id in seen_type_ids:
                raise ConstructionInvalidValueError(
                    message=f"A documentação '{documentation_type.name}' está informada mais de uma vez.",
                    error_code="CONSTRUCTION_UNIT_DOCUMENTATION_DUPLICATE_TYPE",
                )

            seen_type_ids.add(documentation_type.id)
            documentations.append(
                {
                    "documentation_type_id": str(documentation_type.id),
                    "name": documentation_type.name,
                    "amount": self._format_event_decimal(value=item.amount.quantize(Decimal("0.01"))),
                    "sequence_number": sequence_number,
                }
            )

        return documentations

    @staticmethod
    def _sum_documentations(*, documentations: list[dict[str, Any]]) -> Decimal:
        return sum(
            (Decimal(str(documentation["amount"])) for documentation in documentations),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

    async def _replace_unit_documentations(
        self,
        *,
        unit: ConstructionUnit,
        documentations: list[dict[str, Any]],
    ) -> None:
        await self.repository.replace_unit_children(
            ConstructionUnitDocumentationModel,
            company_id=unit.company_id,
            unit_id=unit.id,
            entities=[
                ConstructionUnitDocumentationModel(
                    company_id=unit.company_id,
                    unit_id=unit.id,
                    documentation_type_id=UUID(str(documentation["documentation_type_id"])),
                    sequence_number=int(documentation.get("sequence_number") or 1),
                    amount=Decimal(str(documentation["amount"])),
                )
                for documentation in documentations
            ],
        )

    @staticmethod
    def _erp_domain_error(
        *,
        request_error: httpx.HTTPStatusError,
        fallback_message: str,
    ) -> ConstructionDomainError:
        """Traduz a recusa do ERP para a mensagem que vai a tela.

        O ERP e quem conhece a regra que recusou -- recibo ja emitido, total
        abaixo do que foi pago. Sem isso o usuario recebe um 502 generico no
        lugar da unica frase que explica o que aconteceu.
        """
        try:
            body = request_error.response.json()
        except Exception:
            body = None

        detail = body.get("message") or body.get("detail") if isinstance(body, dict) else None
        status_code = request_error.response.status_code
        return ConstructionDomainError(
            message=detail or fallback_message,
            status_code=status_code if status_code < 500 else 502,
        )

    async def build_project_summary(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Numeros da obra em uma chamada, no formato do RESUMO do legado.

        Comercial e custo saem do proprio modulo; recebido e a receber vem do
        ERP, que e quem tem as baixas.
        """
        await self.get_project(company_id=company_id, project_id=project_id)
        units = await self.repository.list_units(company_id=company_id, project_id=project_id)
        measurements = await self.repository.list_measurements(company_id=company_id, project_id=project_id)
        procurement_requests = await self.repository.list_procurement_requests(
            company_id=company_id,
            project_id=project_id,
        )

        sold_statuses = {ConstructionUnitStatus.SOLD, ConstructionUnitStatus.DELIVERED}
        sold_units = [unit for unit in units if unit.status in sold_statuses]

        units_total = sum((unit.sale_price or Decimal("0") for unit in units), Decimal("0"))
        sold_total = sum((unit.sale_price or Decimal("0") for unit in sold_units), Decimal("0"))
        discount_total = sum((unit.discount_amount or Decimal("0") for unit in sold_units), Decimal("0"))

        # Custo: o que as requisicoes preveem gastar contra o que as medicoes
        # aprovadas ja reconheceram. O legado compara com o orcamento da obra,
        # que o ONAVE ainda nao tem.
        planned_cost = sum(
            (request.estimated_amount or Decimal("0") for request in procurement_requests),
            Decimal("0"),
        )
        approved_statuses = {ConstructionMeasurementStatus.APPROVED, ConstructionMeasurementStatus.PAID}
        approved_measurements = [
            measurement for measurement in measurements if measurement.status in approved_statuses
        ]
        measured_cost = sum(
            (
                measurement.net_amount or measurement.measured_amount or Decimal("0")
                for measurement in approved_measurements
            ),
            Decimal("0"),
        )
        paid_cost = sum(
            (
                measurement.net_amount or measurement.measured_amount or Decimal("0")
                for measurement in measurements
                if measurement.status == ConstructionMeasurementStatus.PAID
            ),
            Decimal("0"),
        )

        summary: dict[str, Any] = {
            "units_count": len(units),
            "units_sold_count": len(sold_units),
            "units_reserved_count": sum(
                1 for unit in units if unit.status == ConstructionUnitStatus.RESERVED
            ),
            "units_available_count": sum(
                1 for unit in units if unit.status == ConstructionUnitStatus.AVAILABLE
            ),
            "units_total_amount": units_total,
            "units_sold_amount": sold_total,
            "discount_amount": discount_total,
            "planned_cost_amount": planned_cost,
            "measured_cost_amount": measured_cost,
            "paid_cost_amount": paid_cost,
            "cost_difference_amount": planned_cost - measured_cost,
            "measurements_count": len(measurements),
            "measurements_approved_count": len(approved_measurements),
            "procurement_requests_count": len(procurement_requests),
            "receivables_count": 0,
            "receivable_total_amount": Decimal("0"),
            "received_amount": Decimal("0"),
            "open_amount": Decimal("0"),
            "overdue_amount": Decimal("0"),
            "overdue_count": 0,
            "erp_unavailable_reason": None,
        }

        receivable_ids = [unit.external_receivable_id for unit in units if unit.external_receivable_id]
        if receivable_ids and self.erp_client is not None:
            try:
                erp_summary = await self.erp_client.get_receivables_summary(
                    company_id=company_id,
                    user_id=user_id,
                    receivable_ids=receivable_ids,
                )
                summary["receivables_count"] = erp_summary.get("receivables_count", 0)
                summary["receivable_total_amount"] = Decimal(str(erp_summary.get("total_amount", "0")))
                summary["received_amount"] = Decimal(str(erp_summary.get("paid_amount", "0")))
                summary["open_amount"] = Decimal(str(erp_summary.get("open_amount", "0")))
                summary["overdue_amount"] = Decimal(str(erp_summary.get("overdue_amount", "0")))
                summary["overdue_count"] = erp_summary.get("overdue_count", 0)
            except Exception as request_error:
                # O resumo comercial e de custo continua util mesmo sem o ERP.
                summary["erp_unavailable_reason"] = _describe_erp_failure(request_error)

        return summary

    async def build_unit_payment_plan(self, *, company_id: UUID, unit_id: UUID) -> dict[str, Any]:
        composition = await self.build_unit_sale_composition(company_id=company_id, unit_id=unit_id)
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)

        plan: dict[str, Any] = {
            "installments": [],
            "installments_total": Decimal("0"),
            "paid_total": Decimal("0"),
            "open_total": Decimal("0"),
            "overdue_count": 0,
            "contract_id": unit.external_contract_id,
            "contract_status": unit.external_contract_status,
            "contract_code": None,
            "contract_content_html": None,
            "erp_unavailable_reason": None,
        }

        # A pergunta ao ERP NAO depende mais de a unidade ter ponteiro. Ela
        # dependia, e o preco foi alto: a venda migrada do MFCON nasce sem
        # `external_receivable_id`, entao Obras nem chegava a perguntar -- 676
        # unidades com R$ 14,6 milhoes de parcela carregada e a aba vazia.
        # Agora a unidade vai como parametro, e o ERP acha pela coluna
        # `receivables.construction_unit_id`.
        if self.erp_client is not None:
            try:
                erp_plan = await self.erp_client.get_unit_payment_plan(
                    company_id=company_id,
                    receivable_id=unit.external_receivable_id,
                    contract_id=unit.external_contract_id,
                    construction_unit_id=unit.id,
                )
                plan.update(erp_plan)
            except Exception as request_error:
                plan["erp_unavailable_reason"] = str(request_error)

        composition["payment_plan"] = plan
        return composition

    async def update_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        changes: dict[str, Any],
        receivable_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Edita uma parcela da unidade, no ERP.

        A parcela vive no ERP -- aqui so validamos que a unidade realmente tem
        recebivel e repassamos. ``receivable_id`` ausente significa a serie da
        venda; preenchido, aponta a parcela de um aditivo. Vencimento e valor
        nao entram: o ERP nao os altera em caminho nenhum.
        """
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
        )

        if not changes:
            raise ConstructionDomainError(
                message="Nenhum campo para alterar na parcela.",
                status_code=422,
            )

        try:
            return await self.erp_client.update_unit_installment(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                receivable_id=target_receivable_id,
                installment_number=installment_number,
                changes=changes,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível editar a parcela no ERP.",
            ) from request_error

    async def _refuse_when_nothing_left_to_charge(self, *, company_id: UUID, unit_id: UUID) -> None:
        """Recusa cobranca nova quando o saldo devedor ja esta zerado.

        O saldo e o que ainda falta compor a venda. Zerado, tudo que o comprador
        deve ja esta lancado -- em parcela, sinal ou aditivo -- e uma cobranca a
        mais nao teria de onde sair: cobraria do comprador um valor que a venda
        nao tem.

        So vale para unidade vendida. Antes da venda nao existe composicao, e o
        saldo zero ali significa "ainda nao ha venda", nao "nao ha o que cobrar"
        -- o sinal costuma ser lancado justamente nessa fase.
        """
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        if unit.status != ConstructionUnitStatus.SOLD:
            return

        composition = await self.build_unit_sale_composition(company_id=company_id, unit_id=unit_id)
        balance = Decimal(str(composition.get("balance_total") or 0))
        if balance > Decimal("0"):
            return

        raise ConstructionInvalidValueError(
            message=(
                "O saldo devedor desta unidade está zerado: não há valor a cobrar do comprador. "
                "Para cobrar a mais, aumente o preço da venda ou lance uma documentação."
            ),
            error_code="CONSTRUCTION_UNIT_WITHOUT_BALANCE_TO_CHARGE",
        )

    async def create_unit_installments(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitInstallmentCreateRequest,
        user_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Acrescenta parcelas a uma serie da unidade.

        Vale um aviso que a tela repete: parcela nova na serie da VENDA e
        refeita na proxima edicao da venda, porque ``replace_open_installments``
        reescreve o que esta em aberto. Cobranca que precisa sobreviver a isso
        e aditivo, que tem documento proprio.
        """
        await self._refuse_when_nothing_left_to_charge(company_id=company_id, unit_id=unit_id)
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=request.receivable_id,
        )
        try:
            return await self.erp_client.create_unit_installments(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                receivable_id=target_receivable_id,
                starting_number=request.starting_number,
                count=request.count,
                first_due_date=request.first_due_date,
                amount=request.amount.quantize(Decimal("0.01")) if request.amount is not None else None,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível incluir a parcela no ERP.",
            ) from request_error

    async def pay_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        request: ConstructionUnitInstallmentPaymentRequest,
        receivable_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Baixa uma parcela da unidade -- a da venda ou a de um aditivo.

        ``receivable_id`` ausente significa a série da venda. O ERP é quem
        guarda a parcela, gera o recibo e o lançamento contábil; aqui só
        provamos que a unidade tem recebível e repassamos.
        """
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
        )
        try:
            return await self.erp_client.pay_unit_installment(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                receivable_id=target_receivable_id,
                installment_number=installment_number,
                payment=request.model_dump(exclude_unset=True, exclude_none=True, mode="json"),
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível baixar a parcela no ERP.",
            ) from request_error

    async def reverse_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        receivable_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Derruba a baixa inteira da parcela da unidade.

        Existe aqui porque a tela da unidade passou a concentrar a baixa
        multi-forma: mandar o operador ao Contas a Receber para corrigir
        supunha uma permissao que ele pode nao ter.
        """
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
        )
        try:
            return await self.erp_client.reverse_unit_installment(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                receivable_id=target_receivable_id,
                installment_number=installment_number,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível estornar a baixa da parcela no ERP.",
            ) from request_error

    async def delete_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        receivable_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> None:
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
        )
        try:
            await self.erp_client.delete_unit_installment(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                receivable_id=target_receivable_id,
                installment_number=installment_number,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível excluir a parcela no ERP.",
            ) from request_error

    async def delete_unit_adjustment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        receivable_id: UUID,
        reason: str,
        user_id: UUID | None = None,
    ) -> None:
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
        )
        try:
            await self.erp_client.delete_unit_receivable(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                receivable_id=target_receivable_id,
                reason=reason,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível excluir o aditivo no ERP.",
            ) from request_error

    async def _resolve_unit_receivable_target(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        receivable_id: UUID | None,
    ) -> tuple[ConstructionUnit, UUID]:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)

        if self.erp_client is None:
            raise ConstructionDomainError(
                message="Integração com o ERP não está configurada.",
                status_code=503,
            )

        target_receivable_id = receivable_id or unit.external_receivable_id
        if target_receivable_id is None:
            raise ConstructionDomainError(
                message="A unidade ainda não tem recebível no ERP: confirme a venda antes de mexer nas parcelas.",
                status_code=409,
            )

        return unit, target_receivable_id

    async def list_unit_commissions(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
    ) -> list[ConstructionUnitCommissionModel]:
        await self._get_unit(company_id=company_id, unit_id=unit_id)
        return await self.repository.list_unit_commissions(company_id=company_id, unit_id=unit_id)

    async def create_unit_commissions(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitCommissionCreate,
    ) -> list[ConstructionUnitCommissionModel]:
        """Lanca o sinal, replicando o "Repetir 1+" do legado.

        Um lancamento vira ``installments`` linhas com vencimento mensal, cada
        uma com sua propria numeracao. O modelo de recibo e copiado da obra
        agora, e nao lido dela na emissao: trocar o modelo da obra depois nao
        pode reescrever o que ja foi lancado.
        """
        await self._refuse_when_nothing_left_to_charge(company_id=company_id, unit_id=unit_id)
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        project = await self.repository.get_project(company_id=company_id, project_id=unit.project_id)
        receipt_template_id = project.commission_receipt_template_id if project is not None else None

        sequence_number = await self.repository.get_next_commission_sequence(
            company_id=company_id,
            unit_id=unit_id,
        )
        amount = request.amount.quantize(Decimal("0.01"))
        commissions: list[ConstructionUnitCommissionModel] = []
        for index in range(request.installments):
            commission = ConstructionUnitCommissionModel(
                id=uuid4(),
                company_id=company_id,
                unit_id=unit_id,
                beneficiary_person_id=request.beneficiary_person_id,
                sequence_number=sequence_number + index,
                amount=amount,
                due_date=self._add_months(value=request.due_date, months=index),
                composes_sale_price=True,
                receipt_template_id=receipt_template_id,
                document_number=(request.document_number or "").strip() or None,
                notes=(request.notes or "").strip() or None,
            )
            await self.repository.add(commission)
            commissions.append(commission)

        await self.repository.commit()
        for commission in commissions:
            await self.repository.refresh(commission)

        return commissions

    async def update_unit_commission(
        self,
        *,
        company_id: UUID,
        commission_id: UUID,
        request: ConstructionUnitCommissionUpdate,
    ) -> ConstructionUnitCommissionModel:
        commission = await self._get_unit_commission(company_id=company_id, commission_id=commission_id)
        updates = request.model_dump(exclude_unset=True)

        # `_apply_updates` e um setattr cru, e `exclude_unset` so diz que a chave
        # veio -- nao que veio preenchida. A tela manda as seis chaves sempre
        # (`updateConstructionUnitCommission`), entao limpar um campo obrigatorio
        # no formulario chegava aqui como `None` e ia direto para uma coluna
        # NOT NULL: IntegrityError, 500 generico, e o usuario sem saber o que
        # deu errado.
        for field_name in ("beneficiary_person_id", "amount", "due_date"):
            if field_name in updates and updates[field_name] is None:
                raise ConstructionInvalidValueError(
                    message=f"O campo '{field_name}' do sinal não pode ficar em branco.",
                    error_code="CONSTRUCTION_UNIT_COMMISSION_REQUIRED_FIELD",
                )

        if updates.get("amount") is not None:
            updates["amount"] = Decimal(str(updates["amount"])).quantize(Decimal("0.01"))

        for field_name in ("document_number", "notes"):
            if field_name in updates:
                updates[field_name] = (updates[field_name] or "").strip() or None

        self._apply_updates(entity=commission, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(commission)
        return commission

    async def settle_unit_commission(
        self,
        *,
        company_id: UUID,
        commission_id: UUID,
        payment_date: date | None,
    ) -> ConstructionUnitCommissionModel:
        """Registra (ou estorna) a baixa do sinal.

        Nao redispara o evento da venda de proposito: um sinal que compoe muda
        o saldo exibido, mas reemitir o contrato por causa de uma comissao paga
        seria pior que o problema. Quem quiser refletir no contrato reabre a
        venda e salva.
        """
        commission = await self._get_unit_commission(company_id=company_id, commission_id=commission_id)
        commission.payment_date = payment_date
        await self.repository.commit()
        await self.repository.refresh(commission)
        return commission

    async def delete_unit_commission(self, *, company_id: UUID, commission_id: UUID) -> None:
        commission = await self._get_unit_commission(company_id=company_id, commission_id=commission_id)
        # Sinal apagado nao tem de onde ser recuperado, e ja houve sumico sem
        # causa identificada: o rastro fica aqui para a proxima vez.
        _logger.info(
            "construction.commission.deleted unit_id=%s commission_id=%s sequence=%s amount=%s composes=%s",
            commission.unit_id,
            commission.id,
            commission.sequence_number,
            commission.amount,
            commission.composes_sale_price,
        )
        await self.repository.delete(commission)
        await self.repository.commit()

    async def create_unit_adjustment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitAdjustmentCreate,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Lanca o aditivo da venda, que vive no ERP como recebivel proprio.

        Nao e parcela do recebivel da venda: editar a venda chama
        ``replace_open_installments``, que refaz as parcelas em aberto e
        destruiria o aditivo.
        """
        await self._refuse_when_nothing_left_to_charge(company_id=company_id, unit_id=unit_id)
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)

        if unit.external_contract_id is None:
            raise ConstructionDomainError(
                message="A unidade ainda não tem contrato no ERP: confirme a venda antes de lançar um aditivo.",
                status_code=409,
            )

        if self.erp_client is None:
            raise ConstructionDomainError(
                message="Integração com o ERP não está configurada.",
                status_code=503,
            )

        try:
            return await self.erp_client.create_unit_adjustment(
                company_id=company_id,
                user_id=user_id,
                construction_unit_id=unit.id,
                contract_id=unit.external_contract_id,
                amount=request.amount.quantize(Decimal("0.01")),
                installments=request.installments,
                first_due_date=request.first_due_date,
                reason=(request.reason or "").strip() or None,
                cost_center_id=unit.analytic_cost_center_id,
                unit_code=unit.code,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível lançar o aditivo no ERP.",
            ) from request_error

    async def _get_unit_commission(
        self,
        *,
        company_id: UUID,
        commission_id: UUID,
    ) -> ConstructionUnitCommissionModel:
        commission = await self.repository.get_unit_commission(
            company_id=company_id,
            commission_id=commission_id,
        )
        if commission is None:
            raise ConstructionNotFoundError(resource_name="o sinal da unidade")

        return commission

    @staticmethod
    def _sum_composing_commissions(commissions: list[ConstructionUnitCommissionModel]) -> Decimal:
        """O sinal abate o saldo devedor desde o lancamento.

        Antes so o sinal pago abatia, e o efeito era o saldo cobrar de novo o
        que o sinal ja estava cobrando: lancado o sinal, o mesmo dinheiro
        aparecia nos dois lugares ate a baixa. Lancar o sinal ja e registrar a
        cobranca, entao e no lancamento que ele sai do saldo.

        Todo sinal novo compoe a venda -- nao ha mais como lancar um que nao
        componha. O filtro continua aqui apenas pelos registros gravados quando
        a tela ainda oferecia essa escolha.
        """
        return sum(
            (commission.amount for commission in commissions if commission.composes_sale_price),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

    async def build_unit_sale_composition(self, *, company_id: UUID, unit_id: UUID) -> dict[str, Any]:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        payment_sources = await self.repository.list_unit_payment_sources(
            company_id=company_id,
            unit_id=unit_id,
        )
        documentations = await self.repository.list_unit_documentations(
            company_id=company_id,
            unit_id=unit_id,
        )
        commissions = await self.repository.list_unit_commissions(
            company_id=company_id,
            unit_id=unit_id,
        )
        sale_price = unit.sale_price or Decimal("0")
        discount_amount = unit.discount_amount or Decimal("0")
        documentation_total = sum(
            (documentation.amount for documentation in documentations),
            Decimal("0"),
        )
        installment_total = sum(
            (source.amount for source in payment_sources if source.generates_installments),
            Decimal("0"),
        )
        # O saldo tambem nao gera parcela, mas nao e liberacao de banco: e
        # divida do comprador esperando virar sinal ou aditivo. Somar os dois no
        # mesmo total faria a tela dizer que o banco cobre o que o comprador
        # ainda deve.
        #
        # E recalculado, nao lido da linha gravada: a fonte guarda o saldo de
        # quando a venda foi confirmada, e um sinal lancado depois nao reescreve
        # essa linha. Lendo o valor gravado, uma venda ja quitada por sinal
        # continuava anunciando saldo a cobrar.
        commission_offset = self._sum_composing_commissions(commissions)
        informed_total = sum(
            (
                source.amount
                for source in payment_sources
                if source.source_type in ConstructionUnitPaymentSource.INFORMED_SOURCES
            ),
            Decimal("0"),
        )
        balance_total = max(
            (
                sale_price
                + documentation_total
                - discount_amount
                - informed_total
                - commission_offset
            ).quantize(Decimal("0.01")),
            Decimal("0"),
        )
        settlement_total = sum(
            (
                source.amount
                for source in payment_sources
                if source.source_type in ConstructionUnitPaymentSource.SETTLEMENT_SOURCES
            ),
            Decimal("0"),
        )
        commission_total = sum((commission.amount for commission in commissions), Decimal("0"))
        commission_paid_total = sum(
            (commission.amount for commission in commissions if commission.payment_date is not None),
            Decimal("0"),
        )
        return {
            "construction_unit_id": unit.id,
            "unit_code": unit.code,
            "sale_price": sale_price,
            "discount_amount": discount_amount,
            "documentation_total": documentation_total,
            # O liquido da unidade continua preco - desconto: a documentacao e
            # repasse cobrado do comprador, nao receita da venda. O que ele deve
            # e a soma dos dois.
            "total_charged": sale_price - discount_amount + documentation_total,
            "installment_total": installment_total,
            "balance_total": balance_total,
            "settlement_total": settlement_total,
            "commission_total": commission_total,
            "commission_paid_total": commission_paid_total,
            # O que o sinal ja abateu do saldo: compoe a venda e esta pago.
            "commission_offset": commission_offset,
            "external_receivable_id": unit.external_receivable_id,
            "external_receivable_status": unit.external_receivable_status,
            "commissions": [
                {
                    "id": commission.id,
                    "beneficiary_person_id": commission.beneficiary_person_id,
                    "sequence_number": commission.sequence_number,
                    "amount": commission.amount,
                    "due_date": commission.due_date,
                    "payment_date": commission.payment_date,
                    "composes_sale_price": commission.composes_sale_price,
                    "receipt_template_id": commission.receipt_template_id,
                    "document_number": commission.document_number,
                    "notes": commission.notes,
                }
                for commission in commissions
            ],
            "documentations": [
                {
                    "id": documentation.id,
                    "documentation_type_id": documentation.documentation_type_id,
                    "name": documentation.documentation_type.name,
                    "amount": documentation.amount,
                    "sequence_number": documentation.sequence_number,
                }
                for documentation in documentations
            ],
            "sources": [
                {
                    "source_type": source.source_type,
                    "label": ConstructionUnitPaymentSource.LABELS.get(source.source_type, source.source_type),
                    "amount": source.amount,
                    "due_date": source.due_date,
                    "installments": source.installments,
                    "generates_installments": source.generates_installments,
                }
                for source in payment_sources
            ],
        }

    @staticmethod
    def _validate_not_in_the_future(*, start_date, end_date) -> None:
        today = datetime.now(tz=UTC).date()
        if start_date is not None and start_date > today:
            raise ConstructionInvalidValueError(
                message="A data de início não pode ser futura.",
                error_code="CONSTRUCTION_INVALID_PERIOD",
            )

        if end_date is not None and end_date > today:
            raise ConstructionInvalidValueError(
                message="A data de fim não pode ser futura.",
                error_code="CONSTRUCTION_INVALID_PERIOD",
            )

    async def _get_editable_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
    ) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Medição aprovada não pode ser alterada.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        return measurement

    async def _get_inspection(
        self,
        *,
        company_id: UUID,
        inspection_id: UUID,
    ) -> ConstructionMeasurementItemInspection:
        inspection = await self.repository.get_measurement_inspection(
            company_id=company_id,
            inspection_id=inspection_id,
        )
        if not inspection:
            raise ConstructionNotFoundError(resource_name="o item de inspeção")

        return inspection

    async def _get_occurrence(
        self,
        *,
        company_id: UUID,
        occurrence_id: UUID,
    ) -> ConstructionMeasurementItemOccurrence:
        occurrence = await self.repository.get_measurement_occurrence(
            company_id=company_id,
            occurrence_id=occurrence_id,
        )
        if not occurrence:
            raise ConstructionNotFoundError(resource_name="a ocorrência da medição")

        return occurrence

    async def _sync_measurement_amounts_from_items(self, *, measurement: ConstructionMeasurement) -> None:
        items_amount = await self.repository.get_measurement_items_amount(
            company_id=measurement.company_id,
            measurement_id=measurement.id,
        )
        if items_amount <= Decimal("0"):
            return

        retentions_amount = measurement.retentions_amount or Decimal("0")
        net_amount = items_amount - retentions_amount
        if net_amount <= Decimal("0"):
            raise ConstructionInvalidValueError(
                message="As retenções da medição não podem passar da soma dos itens.",
                error_code="CONSTRUCTION_MEASUREMENT_RETENTIONS_INVALID",
            )

        measurement.gross_amount = items_amount
        measurement.net_amount = net_amount
        measurement.measured_amount = net_amount

    async def _resolve_item_inspection_status(self, *, item: ConstructionMeasurementItem) -> str:
        inspections = await self.repository.list_measurement_item_inspections(
            company_id=item.company_id,
            measurement_item_id=item.id,
        )
        if not inspections:
            return ConstructionInspectionStatus.PENDING

        statuses = [inspection.status for inspection in inspections]
        if any(status == ConstructionInspectionStatus.NON_COMPLIANT for status in statuses):
            return ConstructionInspectionStatus.NON_COMPLIANT

        if any(status == ConstructionInspectionStatus.PENDING for status in statuses):
            return ConstructionInspectionStatus.PENDING

        # Sobram `compliant` e `waived`: linha dispensada fecha o item sem
        # apagar a reprovacao, que continua no historico de rodadas.
        return ConstructionInspectionStatus.COMPLIANT

    @staticmethod
    def _validate_item_period(*, start_date, end_date) -> None:
        if start_date is not None and end_date is not None and end_date < start_date:
            raise ConstructionInvalidValueError(
                message="A data de fim não pode ser anterior à data de início.",
                error_code="CONSTRUCTION_INVALID_PERIOD",
            )

    async def delete_measurement(self, *, company_id: UUID, measurement_id: UUID) -> None:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Medição aprovada não pode ser excluída.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )

        await self.repository.delete(measurement)
        await self.repository.commit()

    async def apply_accounts_payable_updated_event(self, *, event: EventEnvelope) -> ConstructionMeasurement:
        if event.event_type not in {ErpEventType.ACCOUNTS_PAYABLE_CREATED, ErpEventType.ACCOUNTS_PAYABLE_UPDATED}:
            raise ConstructionInvalidValueError(
                message="Tipo de evento do ERP não suportado para sincronizar o contas a pagar da medição.",
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
            raise ConstructionDuplicateCodeError(resource_name="a etapa do cronograma", code=str(request.sequence_order))

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
                    resource_name="a etapa do cronograma",
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
            raise ConstructionNotFoundError(resource_name="o bloco")

        return block

    async def _get_unit(self, *, company_id: UUID, unit_id: UUID) -> ConstructionUnit:
        unit = await self.repository.get_unit(company_id=company_id, unit_id=unit_id)
        if not unit:
            raise ConstructionNotFoundError(resource_name="a unidade")

        return unit

    async def _get_schedule_phase(self, *, company_id: UUID, phase_id: UUID) -> ConstructionSchedulePhase:
        phase = await self.repository.get_schedule_phase(company_id=company_id, phase_id=phase_id)
        if not phase:
            raise ConstructionNotFoundError(resource_name="a etapa do cronograma")

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
                message="O bloco não pertence à obra informada.",
                error_code="CONSTRUCTION_BLOCK_PROJECT_MISMATCH",
            )

    @staticmethod
    def _ensure_known_value(*, value: str, allowed_values: set[str], field_name: str) -> None:
        if value not in allowed_values:
            allowed_values_text = ", ".join(sorted(allowed_values))
            raise ConstructionInvalidValueError(
                message=f"{field_name} inválido. Valores aceitos: {allowed_values_text}.",
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
            "construction_unit_id": str(measurement.unit_id),
            "schedule_phase_id": str(measurement.schedule_phase_id),
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
                message="Tipo de evento do ERP não suportado para confirmação do centro de custo da unidade.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT",
            )

        unit_id = ConstructionProjectService._read_uuid_payload(
            payload=event.payload,
            field_name="construction_unit_id",
        )
        if unit_id != unit.id:
            raise ConstructionInvalidValueError(
                message="A confirmação de centro de custo não pertence à unidade criada.",
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
    def _build_sale_payment_sources(
        *,
        request: ConstructionUnitSaleConfirmRequest,
        sale_price: Decimal,
        discount_amount: Decimal,
        documentation_total: Decimal = Decimal("0"),
        commission_offset: Decimal = Decimal("0"),
    ) -> list[dict[str, Any]]:
        """Monta a composicao da venda no modelo do legado.

        O usuario informa entrada, financiamento, FGTS e subsidio; o SALDO e o
        que sobra do preco mais a documentacao depois de abater essas fontes e o
        desconto, e e ele que vira as parcelas do contas a receber:

            SALDO = preco + documentacao - desconto - entrada - financiamento
                    - FGTS - subsidio - sinal pago que compoe

        E a mesma conta do tooltip de Dwelling/Resume.cshtml:170. Nao existe uma
        fonte "parcela construtora" para digitar: se ela pudesse ser informada,
        o usuario teria de fazer essa subtracao de cabeca. A documentacao
        tambem nao e fonte nem parcela propria -- ela dilui no saldo. O sinal
        entra pelo mesmo caminho: pago ao corretor, ele ja abateu o que o
        comprador devia.
        """
        informed_total = Decimal("0")
        payment_sources: list[dict[str, Any]] = []

        for payment_source in request.payment_sources or []:
            if payment_source.source_type in ConstructionUnitPaymentSource.COMPUTED_SOURCES:
                raise ConstructionInvalidValueError(
                    message="O saldo da venda é calculado a partir das outras origens e não pode ser informado.",
                    error_code="CONSTRUCTION_UNIT_BALANCE_IS_COMPUTED",
                )

            source_amount = payment_source.amount.quantize(Decimal("0.01"))
            informed_total += source_amount
            generates_installments = (
                payment_source.source_type in ConstructionUnitPaymentSource.INSTALLMENT_SOURCES
            )
            if not generates_installments and payment_source.installments > 1:
                raise ConstructionInvalidValueError(
                    message=(
                        f"{ConstructionUnitPaymentSource.LABELS.get(payment_source.source_type, payment_source.source_type)}"
                        " is released by the bank and cannot be split into installments."
                    ),
                    error_code="CONSTRUCTION_UNIT_SETTLEMENT_SOURCE_NOT_INSTALLMENTABLE",
                )

            payment_sources.append(
                {
                    "source_type": payment_source.source_type,
                    "amount": ConstructionProjectService._format_event_decimal(value=source_amount),
                    "due_date": ConstructionProjectService._format_event_date(value=payment_source.due_date),
                    "installments": payment_source.installments if generates_installments else 1,
                    "generates_installments": generates_installments,
                }
            )

        balance = (
            sale_price + documentation_total - discount_amount - informed_total - commission_offset
        ).quantize(Decimal("0.01"))

        if balance < Decimal("0"):
            raise ConstructionInvalidValueError(
                message="As origens de pagamento mais o desconto passam do preço de venda da unidade mais a documentação.",
                error_code="CONSTRUCTION_UNIT_PAYMENT_SOURCES_TOTAL_MISMATCH",
            )

        if balance > Decimal("0"):
            # O saldo entra na composicao para o usuario ver o que ainda falta,
            # mas nao gera parcela: quem cobra o resto e o sinal ou o aditivo.
            payment_sources.append(
                {
                    "source_type": ConstructionUnitPaymentSource.BALANCE,
                    "amount": ConstructionProjectService._format_event_decimal(value=balance),
                    "due_date": ConstructionProjectService._format_event_date(value=request.first_due_date),
                    "installments": 1,
                    "generates_installments": False,
                }
            )

        return payment_sources

    @staticmethod
    def _build_unit_sold_event(
        *,
        unit: ConstructionUnit,
        analytic_cost_center_id: UUID,
        first_due_date: date,
        installments: int,
        payment_sources: list[dict[str, Any]],
        documentations: list[dict[str, Any]],
        documentation_total: Decimal,
        net_sale_price: Decimal,
        receivable_amount: Decimal,
        commission_offset: Decimal,
        receipt_template_id: UUID | None,
        actor_user_id: UUID | None,
    ) -> EventEnvelope:
        event_id = uuid4()
        payload: dict[str, Any] = {
            "construction_unit_id": str(unit.id),
            "construction_project_id": str(unit.project_id),
            "unit_code": unit.code,
            "buyer_person_id": str(unit.buyer_person_id),
            "sale_price": ConstructionProjectService._format_event_decimal(value=unit.sale_price or Decimal("0")),
            "discount_amount": ConstructionProjectService._format_event_decimal(
                value=unit.discount_amount or Decimal("0")
            ),
            "net_sale_price": ConstructionProjectService._format_event_decimal(value=net_sale_price),
            "receivable_amount": ConstructionProjectService._format_event_decimal(value=receivable_amount),
            "first_due_date": ConstructionProjectService._format_event_date(value=first_due_date),
            "installments": installments,
            "payment_sources": payment_sources,
            "documentation_total": ConstructionProjectService._format_event_decimal(value=documentation_total),
            "documentations": documentations,
            "analytic_cost_center_id": str(analytic_cost_center_id),
        }
        # So vai ao ERP quando ha sinal pago que compoe: venda sem sinal manda
        # o mesmo payload de antes.
        if commission_offset > Decimal("0"):
            payload["commission_offset"] = ConstructionProjectService._format_event_decimal(value=commission_offset)

        if receipt_template_id is not None:
            payload["receipt_template_id"] = str(receipt_template_id)

        if unit.secondary_buyer_person_id is not None:
            payload["secondary_buyer_person_id"] = str(unit.secondary_buyer_person_id)

        if unit.broker_person_id is not None:
            payload["broker_person_id"] = str(unit.broker_person_id)

        if unit.contract_signature_date is not None:
            payload["contract_signature_date"] = ConstructionProjectService._format_event_date(
                value=unit.contract_signature_date
            )

        if unit.sale_notes:
            payload["sale_notes"] = unit.sale_notes

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

    async def _dispatch_integration_event(
        self,
        *,
        event: EventEnvelope,
        fallback_message: str = "Não foi possível registrar a operação no ERP.",
    ):
        """Envia o evento ao ERP, traduzindo a recusa dele.

        Todo evento sai por aqui, entao a traducao vale para venda, projeto,
        unidade, medicao e compra de uma vez -- antes so um 502 generico
        chegava a tela.
        """
        try:
            if self.integration_dispatcher is not None:
                return await self.integration_dispatcher.dispatch(event=event)

            if self.event_repository is not None:
                await self.event_repository.add_outbox_event(event=event)

            if self.erp_client is None:
                return None

            response_event = await self.erp_client.deliver_event(event=event)
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message=fallback_message,
            ) from request_error

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
    def _add_months(*, value: date, months: int) -> date:
        month = value.month - 1 + months
        year = value.year + month // 12
        target_month = month % 12 + 1
        day = min(value.day, calendar.monthrange(year, target_month)[1])
        return value.replace(year=year, month=target_month, day=day)

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
                message=f"O evento do ERP veio sem {field_name}.",
                error_code="CONSTRUCTION_INVALID_ERP_EVENT_PAYLOAD",
            )

        try:
            return UUID(str(value))
        except ValueError as exc:
            raise ConstructionInvalidValueError(
                message=f"O evento do ERP veio com {field_name} inválido.",
                error_code="CONSTRUCTION_INVALID_ERP_EVENT_PAYLOAD",
            ) from exc

    @staticmethod
    def _ensure_external_id_can_be_applied(*, current_id: UUID | None, next_id: UUID, field_name: str) -> None:
        if current_id is None or current_id == next_id:
            return

        raise ConstructionInvalidValueError(
            message=f"A obra já tem outro {field_name}.",
            error_code="CONSTRUCTION_EXTERNAL_ID_CONFLICT",
        )
