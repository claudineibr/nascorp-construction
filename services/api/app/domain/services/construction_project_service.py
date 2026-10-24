import calendar
import hashlib
import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, ClassVar, Protocol
from uuid import UUID, uuid4

import httpx

from app.domain.business_clock import BRAZIL_TIMEZONES, current_business_timezone, get_business_today
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
    ConstructionIntegrationUnconfirmedError,
    ConstructionInvalidStatusTransitionError,
    ConstructionInvalidValueError,
    ConstructionNotFoundError,
    ConstructionPersonOutsideCompanyError,
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
from app.domain.services.subcontract_service import SubcontractService
from app.domain.measurement_workflow import assert_measurement_editable, measurement_item_label, measurement_purpose, resolve_measurement_purpose
from app.domain.unit_commission_status import unit_commission_status
from app.domain.unit_termination_terms import normalize_termination_terms
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
    ConstructionProcurementItem,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionUnit,
    ConstructionUnitSale,
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
    ConstructionProcurementItemInput,
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
    ConstructionUnitTerminationReactivateRequest,
    ConstructionUnitTerminationRequest,
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

SHARED_PAYABLE_BATCH_LIMIT = 1000


def _brl(value: Decimal) -> str:
    formatted = f"{value.quantize(Decimal('0.01')):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"

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

    async def validate_procurement_products(
        self,
        *,
        company_id: UUID,
        user_id: UUID | None,
        product_ids: list[UUID],
    ) -> list[dict[str, Any]]:
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
    @staticmethod
    def to_commission_response(commission):
        from app.schemas.construction.project import ConstructionUnitCommissionResponse

        response = ConstructionUnitCommissionResponse.model_validate(commission)
        response.status = unit_commission_status(
            due_date=response.due_date,
            payment_date=response.payment_date,
            today=get_business_today(current_business_timezone()),
        )
        return response

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
        await self._validate_contract_template(company_id, request.contract_template_id)
        await self._validate_receipt_template(company_id, request.receipt_template_id)
        await self._validate_receipt_template(company_id, request.commission_receipt_template_id)
        await self._require_company_people(
            company_id=company_id,
            actor_user_id=actor_user_id,
            people={"O cliente da obra": request.customer_person_id},
        )
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
            development_type=request.development_type,
            customer_person_id=request.customer_person_id,
            cnpj_spe=request.cnpj_spe.strip() if request.cnpj_spe else None,
            address_json=request.address_json,
            start_date=request.start_date,
            expected_end_date=request.expected_end_date,
            actual_end_date=request.actual_end_date,
            receipt_template_id=request.receipt_template_id,
            commission_receipt_template_id=request.commission_receipt_template_id,
            contract_template_id=request.contract_template_id,
            lot=request.lot,
            registration=request.registration,
            land_area=request.land_area,
            has_segregated_assets=request.has_segregated_assets,
            termination_defaults=(
                normalize_termination_terms(
                    request.termination_defaults.model_dump(mode="json"),
                    has_segregated_assets=request.has_segregated_assets,
                )
                if request.termination_defaults is not None
                else None
            ),
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
        buyer_person_id: UUID | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConstructionProject], int, dict[UUID, list]]:
        items, total = await self.repository.list_projects(
            company_id=company_id,
            search=search,
            status=status,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            buyer_person_id=buyer_person_id,
            page=page,
            page_size=page_size,
        )
        if buyer_person_id is None:
            return items, total, {}

        _logger.info(
            "construction.projects.list_by_buyer buyer_person_id=%s total=%s",
            buyer_person_id,
            total,
        )
        buyer_units = await self.repository.list_buyer_units(
            company_id=company_id,
            project_ids=[item.id for item in items],
            buyer_person_id=buyer_person_id,
        )
        units_by_project: dict[UUID, list] = {}
        for unit in buyer_units:
            units_by_project.setdefault(unit.project_id, []).append(unit)
        return items, total, units_by_project

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

    async def _require_company_people(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        people: dict[str, UUID | None],
    ) -> None:
        pending = {label: person_id for label, person_id in people.items() if person_id is not None}
        if not pending:
            return
        if self.erp_client is None or not hasattr(self.erp_client, "list_person_summaries"):
            _logger.info(f"[construction] require_company_people: erp_unconfigured company_id={company_id}")
            raise ConstructionDomainError(
                message="Não foi possível validar as pessoas no ERP agora. Tente novamente.",
                status_code=503,
                error_code="CONSTRUCTION_ERP_INTEGRATION_UNAVAILABLE",
            )
        for label, person_id in pending.items():
            try:
                result = await self.erp_client.list_person_summaries(
                    company_id=company_id,
                    user_id=actor_user_id,
                    search=None,
                    page=1,
                    page_size=1,
                    person_id=person_id,
                )
            except Exception as exc:
                _logger.info(
                    f"[construction] require_company_people: erp_unavailable company_id={company_id} "
                    f"person_id={person_id} error={type(exc).__name__}"
                )
                raise ConstructionDomainError(
                    message="Não foi possível validar as pessoas no ERP agora. Tente novamente.",
                    status_code=503,
                    error_code="CONSTRUCTION_ERP_INTEGRATION_UNAVAILABLE",
                ) from exc
            if not any(str(person.get("id")) == str(person_id) for person in result.get("items") or []):
                _logger.info(
                    f"[construction] require_company_people: refused company_id={company_id} "
                    f"person_id={person_id} label={label}"
                )
                raise ConstructionPersonOutsideCompanyError(label=label)

    async def _require_company_products(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        product_ids: list[UUID | None],
    ) -> None:
        pending = list(dict.fromkeys(product_id for product_id in product_ids if product_id is not None))
        if not pending:
            return
        if self.erp_client is None or not hasattr(self.erp_client, "validate_procurement_products"):
            _logger.info(f"[construction] require_company_products: erp_unconfigured company_id={company_id}")
            raise ConstructionInvalidValueError(
                message="Não foi possível validar os produtos no ERP agora.",
                error_code="CONSTRUCTION_PROCUREMENT_PRODUCT_VALIDATION_UNAVAILABLE",
            )
        try:
            products = await self.erp_client.validate_procurement_products(
                company_id=company_id,
                user_id=actor_user_id,
                product_ids=pending,
            )
        except Exception as exc:
            raise ConstructionInvalidValueError(
                message="Não foi possível validar os produtos no ERP agora. Tente novamente.",
                error_code="CONSTRUCTION_PROCUREMENT_PRODUCT_VALIDATION_UNAVAILABLE",
            ) from exc
        if {str(product.get("id")) for product in products} != {str(product_id) for product_id in pending}:
            _logger.info(f"[construction] require_company_products: refused company_id={company_id} product_ids={pending}")
            raise ConstructionInvalidValueError(
                message="Um ou mais produtos não existem, estão inativos ou pertencem a outra empresa.",
                error_code="CONSTRUCTION_PROCUREMENT_PRODUCT_UNAVAILABLE",
            )

    async def _validate_receipt_template(self, company_id: UUID, template_id: UUID | None) -> None:
        if template_id and not await self.repository.valid_receipt_template(company_id, template_id):
            _logger.info(f"[construction] validate_receipt_template: refused company_id={company_id} template_id={template_id}")
            raise ConstructionInvalidValueError(
                message="O modelo de recibo deve estar ativo e cadastrado nesta empresa.",
                error_code="CONSTRUCTION_RECEIPT_TEMPLATE_INVALID",
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
        business_role: str | None = None,
        construction_unit_buyer: bool = False,
        construction_project_id: UUID | None = None,
    ) -> dict[str, Any]:
        """A lista de pessoas do formulario, e o caso de UMA pessoa por id.

        `person_id` existia no cliente e no ERP desde sempre; o que faltava era
        este meio do caminho. Sem ele o formulario de venda so enxerga as 50
        primeiras pessoas da empresa -- e sao 3.117 migradas. O comprador e o
        corretor de qualquer unidade praticamente nunca estao entre as 50, e o
        campo aparece VAZIO mesmo com o id gravado na unidade.

        Foi assim que a tela "Editar venda" passou a nao mostrar nem comprador
        nem corretor depois da migracao, com os dois no banco.

        `business_role` recorta pelo papel comercial -- e o que faz o campo
        Corretor parar de listar as 3.116 pessoas da empresa e mostrar so as 10
        que tem o papel. Quem ja esta gravado na unidade continua sendo buscado
        por `person_id`, que ignora o recorte de proposito.
        """
        if self.erp_client is None:
            raise ConstructionInvalidValueError(
                message="A integração com o ERP está indisponível para consultar pessoas.",
                error_code="CONSTRUCTION_ERP_INTEGRATION_UNAVAILABLE",
            )
        if construction_project_id is not None:
            await self.get_project(company_id=company_id, project_id=construction_project_id)

        return await self.erp_client.list_person_summaries(
            company_id=company_id,
            user_id=actor_user_id,
            search=search,
            page=page,
            page_size=page_size,
            person_id=person_id,
            business_role=business_role,
            construction_unit_buyer=construction_unit_buyer,
            construction_project_id=construction_project_id,
        )

    async def get_project(self, *, company_id: UUID, project_id: UUID) -> ConstructionProject:
        project = await self.repository.get_project(company_id=company_id, project_id=project_id)
        if not project:
            raise ConstructionNotFoundError(resource_name="a obra")

        return project

    async def _validate_contract_template(self, company_id, template_id):
        if template_id and not await self.repository.valid_contract_template(company_id, template_id):
            raise ConstructionInvalidValueError(message="O template de contrato deve estar publicado nesta empresa e conter um arquivo Word.")

    async def update_project(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        request: ConstructionProjectUpdate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionProject:
        project = await self.get_project(company_id=company_id, project_id=project_id)
        updates = request.model_dump(exclude_unset=True)
        await self._validate_contract_template(company_id, updates.get("contract_template_id"))
        for field_name in ("receipt_template_id", "commission_receipt_template_id"):
            if updates.get(field_name) != getattr(project, field_name):
                await self._validate_receipt_template(company_id, updates.get(field_name))
        if updates.get("customer_person_id") != project.customer_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O cliente da obra": updates.get("customer_person_id")},
            )
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

        if updates.get("has_segregated_assets", True) is None:
            updates.pop("has_segregated_assets")
        if "termination_defaults" in updates or "has_segregated_assets" in updates:
            segregated = updates.get("has_segregated_assets", project.has_segregated_assets)
            defaults = updates.get("termination_defaults", project.termination_defaults)
            if defaults is not None:
                updates["termination_defaults"] = normalize_termination_terms(
                    defaults, has_segregated_assets=bool(segregated)
                )

        self._apply_updates(entity=project, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(project)
        return project

    async def delete_project(self, *, company_id: UUID, project_id: UUID) -> None:
        project = await self.get_project(company_id=company_id, project_id=project_id)
        await self._assert_history_can_be_deleted(project)
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
            ideal_fraction=request.ideal_fraction,
            delivered_at=datetime.now(UTC) if request.status == ConstructionUnitStatus.DELIVERED else None,
            terminated_at=datetime.now(UTC) if request.status == ConstructionUnitStatus.TERMINATED else None,
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
        actor_user_id: UUID | None = None,
    ) -> ConstructionUnit:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        updates = request.model_dump(exclude_unset=True)
        if "status" in updates:
            unit = await self.repository.lock_unit(company_id=company_id, unit_id=unit_id)
            if unit is None:
                raise ConstructionNotFoundError(resource_name="a unidade")

        next_status = updates.get("status")
        if next_status is not None:
            self._ensure_known_value(value=next_status, allowed_values=UNIT_STATUSES, field_name="status")
            self._ensure_status_change_without_termination(current_status=unit.status, next_status=next_status)

        next_block_id = updates.get("block_id")
        if "block_id" in updates:
            await self._ensure_block_belongs_to_project(
                company_id=company_id,
                project_id=unit.project_id,
                block_id=next_block_id,
            )

        next_code = updates.get("code")
        if next_code is not None and next_code != unit.code:
            # O CODIGO E IMUTAVEL depois que a unidade ganha centro de custo.
            #
            # O centro de custo analitico nasce com o codigo derivado daqui --
            # `CONST-{obra}-{unidade}` -- e batizado uma unica vez, na criacao
            # da unidade. Trocar o codigo aqui fazia os dois divergirem em
            # silencio: o vinculo e por UUID, entao nada quebrava, e o relatorio
            # de custos passava a mostrar um codigo que nao existe mais em
            # Obras.
            #
            # E renomear o centro de custo junto nao e alternativa: o codigo
            # dele e identificador contabil. 676 recebiveis ja apontam para
            # estes centros, um deles com lancamento gerado, e documento ja
            # emitido carrega o codigo da epoca. Quem precisa de outro codigo
            # precisa de outra unidade.
            if unit.analytic_cost_center_id is not None:
                raise ConstructionInvalidValueError(
                    message=(
                        "O código da unidade não pode mudar depois que ela tem centro de custo: "
                        "ele é o identificador contábil usado nos lançamentos. A descrição pode ser "
                        "alterada à vontade."
                    ),
                    error_code="CONSTRUCTION_UNIT_CODE_IS_IMMUTABLE",
                )

            existing_unit = await self.repository.get_unit_by_code(
                company_id=company_id,
                project_id=unit.project_id,
                code=next_code,
            )
            if existing_unit and existing_unit.id != unit.id:
                raise ConstructionDuplicateCodeError(resource_name="a unidade", code=next_code)

        # A descricao carrega o DONO, e muda a cada revenda. O centro de custo
        # era batizado na criacao e nunca mais: o relatorio de custos seguia
        # mostrando o comprador anterior. Renomeia ANTES de gravar -- se o ERP
        # recusar, a unidade nao muda, e os dois nunca divergem.
        nova_descricao = updates.get("description")
        renomear = (
            nova_descricao is not None
            and (nova_descricao or "").strip() != (unit.description or "").strip()
            and unit.analytic_cost_center_id is not None
            and self.erp_client is not None
        )
        if renomear:
            try:
                await self.erp_client.rename_unit_cost_center(
                    company_id=company_id,
                    user_id=actor_user_id,
                    cost_center_id=unit.analytic_cost_center_id,
                    description=nova_descricao,
                )
            except httpx.HTTPStatusError as request_error:
                raise self._erp_domain_error(
                    request_error=request_error,
                    fallback_message="Não foi possível renomear o centro de custo da unidade no ERP.",
                ) from request_error

        previous_status = unit.status
        if next_status and next_status != previous_status and next_status == ConstructionUnitStatus.DELIVERED:
            unit.delivered_at = datetime.now(UTC)
        reclassify = next_status is not None and next_status != previous_status and "delivered" in {
            previous_status, next_status,
        }
        if reclassify:
            if self.event_repository is None or actor_user_id is None:
                raise ConstructionInvalidValueError(
                    message="A entrega exige usuário identificado e integração contábil disponível.")

            event_id = uuid4()
            await self.event_repository.add_outbox_event(event=EventEnvelope(
                event_id=event_id,
                event_type=ConstructionEventType.UNIT_STATUS_CHANGED,
                event_version=1,
                company_id=company_id,
                aggregate_id=unit.id,
                aggregate_type=ConstructionAggregateType.UNIT,
                occurred_at=datetime.now(UTC),
                producer=EventProducer.CONSTRUCTION_API,
                correlation_id=event_id,
                causation_id=None,
                payload={"status": next_status, "previous_status": previous_status,
                         "user_id": str(actor_user_id)},
            ))
            _logger.info(f"[accounting] unit_status_queued: unit_id={unit.id} previous={previous_status} status={next_status}")

        self._apply_updates(entity=unit, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    @staticmethod
    def _ensure_status_change_without_termination(*, current_status: str, next_status: str) -> None:
        if next_status == current_status:
            return
        sale_statuses = {ConstructionUnitStatus.SOLD, ConstructionUnitStatus.DELIVERED}
        leaves_sale = current_status in sale_statuses and next_status not in sale_statuses
        if (
            next_status == ConstructionUnitStatus.TERMINATED
            or leaves_sale
            or current_status == ConstructionUnitStatus.TERMINATED
        ):
            _logger.info(
                f"[unit_termination] status_refused: current={current_status} next={next_status}"
            )
            raise ConstructionInvalidValueError(
                message=(
                    "Para desfazer a venda use a ação Distratar da unidade: ela calcula a devolução, "
                    "baixa as parcelas em aberto e devolve a unidade para Disponível."
                ),
                error_code="CONSTRUCTION_UNIT_STATUS_REQUIRES_TERMINATION",
            )

    async def _refuse_when_unit_has_installments(self, *, company_id: UUID, unit: ConstructionUnit, acao: str) -> None:
        """Recusa tirar o dono da unidade enquanto houver parcela no ERP.

        Quem responde pelas parcelas e o COMPRADOR: `receivables.person_id` sai
        de `construction_units.buyer_person_id` -- e na venda viva e na carga do
        MFCON. Zerar o comprador aqui nao apaga nada no ERP: o recebivel
        continua inteiro, no nome de quem era dono, e a unidade deixa de
        alcanca-lo pela tela. A divida fica orfa por relacao, nao por dado --
        que e a pior forma, porque nao aparece em nenhum relatorio.

        A contagem vem do plano de pagamento, e NAO de
        `external_receivable_id`: o aditivo e recebivel proprio, sem ponteiro na
        unidade, e a venda migrada do MFCON so ganhou o ponteiro em 2026-09-21.
        `construction_unit_id` alcanca os dois.

        Quando o ERP nao responde a operacao e RECUSADA, nao liberada. Deixar
        passar sem saber e exatamente o defeito que este guard fecha.
        """
        if self.erp_client is None:
            return

        try:
            plan = await self.erp_client.get_unit_payment_plan(
                company_id=company_id,
                receivable_id=unit.external_receivable_id,
                contract_id=unit.external_contract_id,
                construction_unit_id=unit.id,
            )
        except httpx.HTTPError as request_error:
            raise ConstructionResourceInUseError(
                message=(
                    f"Não foi possível conferir as parcelas da unidade no ERP para {acao}. "
                    "Tente novamente em instantes."
                ),
                error_code="CONSTRUCTION_UNIT_INSTALLMENTS_UNKNOWN",
            ) from request_error

        parcelas = plan.get("installments") or []
        if not parcelas:
            return

        raise ConstructionResourceInUseError(
            message=(
                f"A unidade {unit.code} tem {len(parcelas)} parcela(s) no contas a receber. "
                f"Remova as parcelas antes de {acao}, senão a cobrança fica sem dono."
            ),
            error_code="CONSTRUCTION_UNIT_HAS_INSTALLMENTS",
        )

    async def delete_unit(self, *, company_id: UUID, unit_id: UUID) -> None:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        await self._assert_history_can_be_deleted(unit)
        # Apagar a unidade tira o dono junto -- pela porta maior. Ver
        # `_refuse_when_unit_has_installments`.
        await self._refuse_when_unit_has_installments(
            company_id=company_id, unit=unit, acao="excluir a unidade"
        )
        await self.repository.delete(unit)
        await self.repository.commit()

    async def reserve_unit(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitReserveRequest,
        actor_user_id: UUID | None = None,
    ) -> ConstructionUnit:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        if unit.status != ConstructionUnitStatus.AVAILABLE:
            raise ConstructionInvalidValueError(
                message="Só é possível reservar unidade disponível.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )
        await self._require_company_people(
            company_id=company_id,
            actor_user_id=actor_user_id,
            people={"O comprador": request.buyer_person_id},
        )

        unit.status = ConstructionUnitStatus.RESERVED
        unit.buyer_person_id = request.buyer_person_id
        unit.reserved_at = datetime.now(tz=UTC)
        unit.reservation_expires_at = request.reservation_expires_at or (get_business_today(current_business_timezone()) + timedelta(days=7))
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

        await self._refuse_when_unit_has_installments(
            company_id=company_id, unit=unit, acao="liberar a reserva"
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

        changed_people = {
            label: person_id
            for label, person_id, stored_id in (
                ("O comprador", request.buyer_person_id, unit.buyer_person_id),
                ("O segundo comprador", request.secondary_buyer_person_id, unit.secondary_buyer_person_id),
                ("O corretor", request.broker_person_id, unit.broker_person_id),
            )
            if person_id != stored_id
        }
        await self._require_company_people(
            company_id=company_id,
            actor_user_id=actor_user_id,
            people=changed_people,
        )

        net_sale_price = sale_price - discount_amount
        documentations = await self._resolve_sale_documentations(unit=unit, request=request)
        documentation_total = self._sum_documentations(documentations=documentations)
        commission_offset = self._sum_composing_commissions(
            await self.repository.list_unit_commissions(
                company_id=company_id, unit_id=unit_id, sale_id=unit.current_sale_id
            )
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

        if request.financing_date is not None:
            if request.financing_date > get_business_today(current_business_timezone()):
                raise ConstructionInvalidValueError(
                    message="A data do financiamento não pode ser futura.",
                    error_code="CONSTRUCTION_FINANCING_FUTURE_DATE",
                )

            if not any(source["source_type"] == "financing" and source["amount"] > 0 for source in payment_sources):
                raise ConstructionInvalidValueError(
                    message="A data do financiamento exige financiamento maior que zero.",
                    error_code="CONSTRUCTION_FINANCING_REQUIRED",
                )

        await self._replace_unit_payment_sources(unit=unit, payment_sources=payment_sources)
        await self._replace_unit_documentations(unit=unit, documentations=documentations)

        unit.status = ConstructionUnitStatus.SOLD
        unit.buyer_person_id = request.buyer_person_id
        unit.secondary_buyer_person_id = request.secondary_buyer_person_id
        unit.broker_person_id = request.broker_person_id
        unit.sale_price = sale_price
        unit.discount_amount = discount_amount
        unit.financing_completed = request.financing_completed
        unit.financing_date = request.financing_date
        unit.contract_signature_date = request.contract_signature_date
        unit.sale_notes = (request.sale_notes or "").strip() or None
        unit.sold_at = unit.sold_at or datetime.now(tz=UTC)
        unit.reservation_expires_at = None

        project = await self.repository.get_project(company_id=company_id, project_id=unit.project_id)
        sale = await self._upsert_current_sale(
            unit=unit,
            project=project,
            request=request,
            payment_sources=payment_sources,
            documentations=documentations,
            actor_user_id=actor_user_id,
        )
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
            sale=sale,
        )
        dispatch_result = await self._dispatch_integration_event(
            event=sale_event,
            fallback_message="Não foi possível registrar a venda no ERP.",
        )
        if dispatch_result is not None and dispatch_result.response_event is not None:
            erp_event = dispatch_result.response_event
            self._apply_contract_snapshot_from_payload(unit=unit, payload=erp_event.payload)
        sale.external_contract_id = unit.external_contract_id
        sale.external_receivable_id = unit.external_receivable_id

        await self.repository.commit()
        await self.repository.refresh(unit)
        return unit

    async def _upsert_current_sale(
        self,
        *,
        unit: ConstructionUnit,
        project: ConstructionProject | None,
        request: ConstructionUnitSaleConfirmRequest,
        payment_sources: list[dict[str, Any]],
        documentations: list[dict[str, Any]],
        actor_user_id: UUID | None,
    ) -> ConstructionUnitSale:
        sale = await self._ensure_current_sale(unit=unit, project=project, actor_user_id=actor_user_id)
        if request.termination_terms is not None:
            segregated = self._sale_has_segregated_assets(sale=sale, project=project)
            sale.termination_terms = {
                **normalize_termination_terms(
                    request.termination_terms.model_dump(mode="json"), has_segregated_assets=segregated
                ),
                "has_segregated_assets": segregated,
            }
        sale.buyer_person_id = unit.buyer_person_id
        sale.secondary_buyer_person_id = unit.secondary_buyer_person_id
        sale.broker_person_id = unit.broker_person_id
        sale.sale_price = unit.sale_price
        sale.discount_amount = unit.discount_amount
        sale.sale_notes = unit.sale_notes
        sale.sold_at = unit.sold_at
        sale.financing_completed = unit.financing_completed
        sale.financing_date = unit.financing_date
        sale.contract_signature_date = unit.contract_signature_date
        sale.payment_sources = self._json_safe(payment_sources)
        sale.documentations = self._json_safe(documentations)
        return sale

    @classmethod
    def _json_safe(cls, value):
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value

    async def _record_unit_termination(self, unit, sale):
        deleted_commissions = await self.repository.delete_unpaid_unit_commissions(
            company_id=unit.company_id, unit_id=unit.id, sale_id=unit.current_sale_id
        )
        terminated_at = datetime.now(UTC)
        cost_history_appended = bool(unit.sold_at)
        if cost_history_appended:
            unit.cost_sale_history = [*(unit.cost_sale_history or []),
                {"sold_at": unit.sold_at.isoformat(), "terminated_at": terminated_at.isoformat()}]
        sale.delivered_at = unit.delivered_at
        sale.external_contract_status = unit.external_contract_status
        sale.external_receivable_status = unit.external_receivable_status
        sale.termination_snapshot = self._json_safe({
            "cost_sale_history_appended": cost_history_appended,
            "unit_status": unit.status,
            "deleted_commissions": [
                {
                    "id": commission.id,
                    "beneficiary_person_id": commission.beneficiary_person_id,
                    "sequence_number": commission.sequence_number,
                    "amount": commission.amount,
                    "due_date": commission.due_date,
                    "composes_sale_price": commission.composes_sale_price,
                    "receipt_template_id": commission.receipt_template_id,
                    "document_number": commission.document_number,
                    "notes": commission.notes,
                }
                for commission in deleted_commissions
            ],
        })
        unit.terminated_at = terminated_at
        unit.delivered_at = None
        return terminated_at

    async def _release_terminated_unit(self, unit):
        await self._replace_unit_payment_sources(unit=unit, payment_sources=[])
        await self._replace_unit_documentations(unit=unit, documentations=[])
        unit.status = ConstructionUnitStatus.AVAILABLE
        unit.buyer_person_id = None
        unit.secondary_buyer_person_id = None
        unit.broker_person_id = None
        unit.discount_amount = None
        unit.financing_completed = False
        unit.financing_date = None
        unit.contract_signature_date = None
        unit.sale_notes = None
        unit.sold_at = None
        unit.reserved_at = None
        unit.reservation_expires_at = None
        unit.external_contract_id = None
        unit.external_contract_status = None
        unit.external_receivable_id = None
        unit.external_receivable_status = None
        unit.current_sale_id = None

    TERMINABLE_UNIT_STATUSES: ClassVar[set[str]] = {
        ConstructionUnitStatus.SOLD,
        ConstructionUnitStatus.DELIVERED,
        ConstructionUnitStatus.TERMINATED,
    }

    @staticmethod
    def _sale_has_segregated_assets(*, sale: ConstructionUnitSale | None, project: ConstructionProject | None) -> bool:
        stored = (getattr(sale, "termination_terms", None) or {}).get("has_segregated_assets")
        if stored is not None:
            return bool(stored)
        return bool(getattr(project, "has_segregated_assets", False))

    def _build_current_sale(
        self, *, unit: ConstructionUnit, project: ConstructionProject | None, actor_user_id: UUID | None, sequence: int
    ) -> ConstructionUnitSale:
        segregated = bool(getattr(project, "has_segregated_assets", False))
        return ConstructionUnitSale(
            id=uuid4(),
            company_id=unit.company_id,
            unit_id=unit.id,
            sequence=sequence,
            status="ACTIVE",
            source="NATIVE",
            buyer_person_id=unit.buyer_person_id,
            secondary_buyer_person_id=unit.secondary_buyer_person_id,
            broker_person_id=unit.broker_person_id,
            sale_price=unit.sale_price,
            discount_amount=unit.discount_amount,
            sale_notes=unit.sale_notes,
            sold_at=unit.sold_at,
            financing_completed=unit.financing_completed,
            financing_date=unit.financing_date,
            contract_signature_date=unit.contract_signature_date,
            external_contract_id=unit.external_contract_id,
            external_receivable_id=unit.external_receivable_id,
            created_by_user_id=actor_user_id,
            termination_terms={
                **normalize_termination_terms(
                    getattr(project, "termination_defaults", None), has_segregated_assets=segregated
                ),
                "has_segregated_assets": segregated,
            },
        )

    async def _create_current_sale(
        self, *, unit: ConstructionUnit, project: ConstructionProject | None, actor_user_id: UUID | None
    ) -> ConstructionUnitSale:
        sequence = await self.repository.next_unit_sale_sequence(company_id=unit.company_id, unit_id=unit.id)
        sale = self._build_current_sale(unit=unit, project=project, actor_user_id=actor_user_id, sequence=sequence)
        await self.repository.add(sale)
        unit.current_sale_id = sale.id
        await self.repository.attach_unit_commissions_to_sale(
            company_id=unit.company_id, unit_id=unit.id, sale_id=sale.id
        )
        _logger.info(f"[unit_sale] criada: unit_id={unit.id} sale_id={sale.id} sequence={sale.sequence}")
        return sale

    async def _get_active_current_sale(self, *, unit: ConstructionUnit) -> ConstructionUnitSale | None:
        if unit.current_sale_id is None:
            return None
        sale = await self.repository.get_unit_sale(company_id=unit.company_id, sale_id=unit.current_sale_id, lock=True)
        return sale if sale is not None and sale.status == "ACTIVE" else None

    async def _ensure_current_sale(
        self, *, unit: ConstructionUnit, project: ConstructionProject | None, actor_user_id: UUID | None
    ) -> ConstructionUnitSale:
        sale = await self._get_active_current_sale(unit=unit)
        if sale is not None:
            return sale
        return await self._create_current_sale(unit=unit, project=project, actor_user_id=actor_user_id)

    def _require_terminable_unit(self, unit: ConstructionUnit | None) -> ConstructionUnit:
        if unit is None:
            raise ConstructionNotFoundError(resource_name="a unidade")
        if unit.status not in self.TERMINABLE_UNIT_STATUSES:
            _logger.info(f"[unit_termination] recusado_status: unit_id={unit.id} status={unit.status}")
            raise ConstructionInvalidValueError(
                message="Só é possível distratar unidade vendida ou entregue.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )
        return unit

    async def _termination_payload(
        self,
        *,
        unit: ConstructionUnit,
        sale: ConstructionUnitSale,
        project: ConstructionProject | None,
        request: ConstructionUnitTerminationRequest,
    ) -> dict[str, Any]:
        commissions = await self.repository.list_unit_commissions(
            company_id=unit.company_id, unit_id=unit.id, sale_id=sale.id
        )
        broker_signal = sum(
            (
                Decimal(str(commission.amount))
                for commission in commissions
                if commission.composes_sale_price and commission.payment_date is not None
            ),
            Decimal("0"),
        )
        price = sale.sale_price if sale.sale_price is not None else unit.sale_price
        discount = sale.discount_amount if sale.discount_amount is not None else unit.discount_amount
        net = (Decimal(str(price)) - Decimal(str(discount or 0))) if price is not None else None
        payload: dict[str, Any] = {
            "construction_unit_id": str(unit.id),
            "construction_sale_id": str(sale.id),
            "contract_id": str(unit.external_contract_id) if unit.external_contract_id else None,
            "termination_date": request.termination_date.isoformat(),
            "reason": request.reason.strip(),
            "notes": (request.notes or "").strip() or None,
            "terms": {
                key: value for key, value in (sale.termination_terms or {}).items() if key != "has_segregated_assets"
            },
            "has_segregated_assets": self._sale_has_segregated_assets(sale=sale, project=project),
            "contract_amount": self._format_event_decimal(value=net) if net is not None and net > 0 else None,
            "broker_signal_amount": self._format_event_decimal(value=broker_signal),
            "additional_refund": self._format_event_decimal(value=request.additional_refund),
            "preview_version": request.preview_version,
        }
        if request.refund is not None:
            payload["refund"] = {
                "first_due_date": request.refund.first_due_date.isoformat(),
                "installments": request.refund.installments,
            }
        return payload

    async def preview_unit_termination(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitTerminationRequest,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        try:
            unit = self._require_terminable_unit(
                await self.repository.lock_unit(company_id=company_id, unit_id=unit_id)
            )
            project = await self.repository.get_project(company_id=company_id, project_id=unit.project_id)
            sale = await self._get_active_current_sale(unit=unit) or self._build_current_sale(
                unit=unit, project=project, actor_user_id=actor_user_id, sequence=0
            )
            payload = await self._termination_payload(unit=unit, sale=sale, project=project, request=request)
            try:
                return await self.erp_client.preview_unit_termination(
                    company_id=company_id, user_id=actor_user_id, payload=payload
                )
            except httpx.HTTPStatusError as request_error:
                raise self._erp_domain_error(
                    request_error=request_error,
                    fallback_message="Não foi possível calcular o distrato no ERP.",
                ) from request_error
        finally:
            await self.repository.rollback()

    async def terminate_unit(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitTerminationRequest,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        _logger.info(f"[unit_termination] distratar: company_id={company_id} unit_id={unit_id} user={actor_user_id}")
        unit = self._require_terminable_unit(await self.repository.lock_unit(company_id=company_id, unit_id=unit_id))
        project = await self.repository.get_project(company_id=company_id, project_id=unit.project_id)
        sale = await self._ensure_current_sale(unit=unit, project=project, actor_user_id=actor_user_id)
        sale_id = sale.id
        payload = await self._termination_payload(unit=unit, sale=sale, project=project, request=request)
        await self.repository.commit()
        try:
            result = await self.erp_client.apply_unit_termination(
                company_id=company_id, user_id=actor_user_id, payload=payload
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível registrar o distrato no ERP.",
            ) from request_error

        unit = await self.repository.lock_unit(company_id=company_id, unit_id=unit_id)
        sale = await self.repository.get_unit_sale(company_id=company_id, sale_id=sale_id, lock=True)
        if sale.status != "ACTIVE" or unit.current_sale_id != sale_id:
            _logger.info(f"[unit_termination] ja_registrado: unit_id={unit_id} sale_id={sale_id} status={sale.status}")
            return {**result, "unit_status": unit.status}
        erp_date = self._read_optional_date(result.get("termination_date"))
        if erp_date is not None and erp_date != request.termination_date:
            _logger.info(
                f"[unit_termination] data_do_erp: unit_id={unit_id} sale_id={sale_id} "
                f"pedido={request.termination_date} erp={erp_date}"
            )
        sale.status = "TERMINATED"
        sale.terminated_at = await self._record_unit_termination(unit, sale)
        sale.termination_date = erp_date or request.termination_date
        sale.termination_reason = str(result.get("reason") or "").strip() or request.reason.strip()
        sale.termination_notes = (request.notes or "").strip() or None
        sale.external_termination_id = self._read_optional_uuid(result.get("termination_id"))
        sale.refund_amount = Decimal(str(result.get("refund_amount") or 0))
        sale.paid_amount = Decimal(str(result.get("paid_amount") or 0))
        sale.terminated_by_user_id = actor_user_id
        sale.external_contract_id = sale.external_contract_id or unit.external_contract_id
        sale.external_receivable_id = sale.external_receivable_id or unit.external_receivable_id
        await self._release_terminated_unit(unit)
        await self.repository.commit()
        await self.repository.refresh(unit)
        _logger.info(
            f"[unit_termination] distratada: unit_id={unit_id} sale_id={sale_id} "
            f"termination_id={sale.external_termination_id} refund={sale.refund_amount}"
        )
        return {**result, "unit_status": unit.status}

    async def reactivate_unit_termination(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitTerminationReactivateRequest,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        _logger.info(f"[unit_termination] reativar: company_id={company_id} unit_id={unit_id} user={actor_user_id}")
        unit = await self.repository.lock_unit(company_id=company_id, unit_id=unit_id)
        if unit is None:
            raise ConstructionNotFoundError(resource_name="a unidade")
        if unit.status != ConstructionUnitStatus.AVAILABLE or unit.current_sale_id is not None:
            _logger.info(f"[unit_termination] reativar_recusado_status: unit_id={unit_id} status={unit.status}")
            raise ConstructionInvalidValueError(
                message="Só é possível reativar o distrato enquanto a unidade estiver disponível, sem nova venda.",
                error_code="CONSTRUCTION_UNIT_INVALID_STATUS",
            )
        sale = await self.repository.get_latest_native_terminated_sale(company_id=company_id, unit_id=unit_id)
        if sale is None:
            _logger.info(f"[unit_termination] reativar_sem_distrato: unit_id={unit_id}")
            raise ConstructionInvalidValueError(
                message="A unidade não tem distrato que possa ser reativado.",
                error_code="CONSTRUCTION_UNIT_TERMINATION_NOT_FOUND",
            )
        sale_id = sale.id
        try:
            result = await self.erp_client.reactivate_unit_termination(
                company_id=company_id,
                user_id=actor_user_id,
                payload={
                    "construction_unit_id": str(unit.id),
                    "construction_sale_id": str(sale_id),
                    "reason": request.reason.strip(),
                },
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível reativar o distrato no ERP.",
            ) from request_error

        snapshot = dict(sale.termination_snapshot or {})
        unit.delivered_at = sale.delivered_at or unit.delivered_at
        previous_status = snapshot.get("unit_status")
        if previous_status in {ConstructionUnitStatus.SOLD, ConstructionUnitStatus.DELIVERED}:
            unit.status = previous_status
        else:
            unit.status = ConstructionUnitStatus.DELIVERED if unit.delivered_at else ConstructionUnitStatus.SOLD
        unit.buyer_person_id = sale.buyer_person_id
        unit.secondary_buyer_person_id = sale.secondary_buyer_person_id
        unit.broker_person_id = sale.broker_person_id
        unit.sale_price = sale.sale_price if sale.sale_price is not None else unit.sale_price
        unit.discount_amount = sale.discount_amount
        unit.financing_completed = sale.financing_completed
        unit.financing_date = sale.financing_date
        unit.contract_signature_date = sale.contract_signature_date
        unit.sale_notes = sale.sale_notes
        unit.sold_at = sale.sold_at
        unit.external_contract_id = sale.external_contract_id
        unit.external_contract_status = sale.external_contract_status
        unit.external_receivable_id = sale.external_receivable_id
        unit.external_receivable_status = sale.external_receivable_status
        unit.current_sale_id = sale.id
        history = list(unit.cost_sale_history or [])
        if snapshot.get("cost_sale_history_appended", sale.sold_at is not None) and history and history[-1].get("terminated_at"):
            history.pop()
        unit.cost_sale_history = history
        unit.terminated_at = None
        await self._restore_terminated_commissions(unit=unit, sale=sale, snapshot=snapshot)
        await self._replace_unit_payment_sources(unit=unit, payment_sources=list(sale.payment_sources or []))
        await self._replace_unit_documentations(
            unit=unit,
            documentations=[
                {**row, "sequence_number": row.get("sequence_number") or index}
                for index, row in enumerate(sale.documentations or [], start=1)
                if row.get("documentation_type_id")
            ],
        )
        sale.status = "ACTIVE"
        sale.terminated_at = None
        sale.termination_date = None
        sale.termination_reason = None
        sale.termination_notes = None
        sale.external_termination_id = None
        sale.refund_amount = None
        sale.paid_amount = None
        sale.terminated_by_user_id = None
        sale.termination_snapshot = None
        await self.repository.commit()
        await self.repository.refresh(unit)
        _logger.info(f"[unit_termination] reativada: unit_id={unit_id} sale_id={sale_id}")
        return {**result, "unit_status": unit.status}

    async def _restore_terminated_commissions(self, *, unit, sale, snapshot):
        deleted = [row for row in snapshot.get("deleted_commissions") or [] if row.get("id")]
        if not deleted:
            return
        restored = await self.repository.restore_unit_commissions(
            company_id=unit.company_id,
            unit_id=unit.id,
            sale_id=sale.id,
            commission_ids=[UUID(str(row["id"])) for row in deleted],
        )
        missing = [row for row in deleted if UUID(str(row["id"])) not in restored]
        if not missing:
            return
        sequence = await self.repository.get_next_commission_sequence(company_id=unit.company_id, unit_id=unit.id)
        for offset, row in enumerate(missing):
            await self.repository.add(
                ConstructionUnitCommissionModel(
                    id=uuid4(),
                    company_id=unit.company_id,
                    unit_id=unit.id,
                    sale_id=sale.id,
                    beneficiary_person_id=UUID(str(row["beneficiary_person_id"])),
                    sequence_number=sequence + offset,
                    amount=Decimal(str(row["amount"])),
                    due_date=date.fromisoformat(str(row["due_date"])),
                    composes_sale_price=bool(row.get("composes_sale_price", True)),
                    receipt_template_id=self._read_optional_uuid(row.get("receipt_template_id")),
                    document_number=row.get("document_number"),
                    notes=row.get("notes"),
                )
            )
        _logger.info(f"[unit_termination] sinais_recriados: unit_id={unit.id} sale_id={sale.id} count={len(missing)}")

    async def list_unit_sales(self, *, company_id: UUID, unit_id: UUID) -> list[ConstructionUnitSale]:
        await self._get_unit(company_id=company_id, unit_id=unit_id)
        return await self.repository.list_unit_sales(company_id=company_id, unit_id=unit_id)

    async def list_unit_buyer_credits(
        self, *, company_id: UUID, unit_id: UUID, actor_user_id: UUID | None = None
    ) -> dict[str, Any]:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        if unit.buyer_person_id is None:
            return {"items": [], "total": 0, "page": 1, "page_size": 50, "total_pages": 1, "open_total": "0"}
        try:
            return await self.erp_client.list_person_customer_credits(
                company_id=company_id, user_id=actor_user_id, person_id=unit.buyer_person_id
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível consultar o saldo credor no ERP.",
            ) from request_error

    async def offset_unit_installment_with_credit(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        amount: Decimal,
        paid_at: date,
        receivable_id: UUID | None = None,
        observation: str | None = None,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        unit, target_receivable_id = await self._resolve_unit_receivable_target(
            company_id=company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
        )
        try:
            return await self.erp_client.offset_unit_installment_with_credit(
                company_id=company_id,
                user_id=actor_user_id,
                payload={
                    "receivable_id": str(target_receivable_id),
                    "installment_number": installment_number,
                    "amount": self._format_event_decimal(value=amount),
                    "paid_at": paid_at.isoformat(),
                    "observation": observation,
                },
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível abater o saldo credor no ERP.",
            ) from request_error

    @staticmethod
    def _read_optional_uuid(value: Any) -> UUID | None:
        try:
            return UUID(str(value)) if value else None
        except ValueError:
            return None

    @staticmethod
    def _read_optional_date(value: Any) -> date | None:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10]) if value else None
        except ValueError:
            return None

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
        if contract_status.upper() == "CANCELED" and unit.status in self.TERMINABLE_UNIT_STATUSES:
            project = await self.repository.get_project(company_id=unit.company_id, project_id=unit.project_id)
            sale = await self._ensure_current_sale(unit=unit, project=project, actor_user_id=None)
            reason = str(event.payload.get("reason") or "").strip() or "Contrato cancelado no ERP"
            _logger.info(
                f"[unit_termination] contrato_cancelado_no_erp: unit_id={unit.id} sale_id={sale.id} event_id={event.event_id}"
            )
            sale.status = "TERMINATED"
            sale.terminated_at = await self._record_unit_termination(unit, sale)
            company_timezone = await self.repository.get_company_timezone(company_id=unit.company_id)
            if company_timezone not in BRAZIL_TIMEZONES:
                company_timezone = current_business_timezone()
            sale.termination_date = get_business_today(company_timezone)
            sale.termination_reason = reason[:500]
            sale.external_contract_id = sale.external_contract_id or unit.external_contract_id
            sale.external_receivable_id = sale.external_receivable_id or unit.external_receivable_id
            await self._release_terminated_unit(unit)

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
        items, _, total = await self._prepare_procurement_items(
            company_id=company_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            item_inputs=request.items,
            discount_amount=request.discount_amount,
        )
        await self._require_company_people(
            company_id=company_id,
            actor_user_id=actor_user_id,
            people={"O fornecedor": request.supplier_person_id},
        )
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
            created_by_user_id=actor_user_id,
            code=procurement_code,
            title=request.title.strip(),
            description=request.description,
            estimated_amount=total,
            discount_amount=request.discount_amount,
            needed_by_date=request.needed_by_date,
            supplier_person_id=request.supplier_person_id,
            supplier_qualification_status=await self._resolve_supplier_qualification_status(
                company_id=company_id,
                actor_user_id=actor_user_id,
                supplier_person_id=request.supplier_person_id,
            ),
            status=ConstructionProcurementStatus.DRAFT,
            submission_revision=0,
            rejection_reason=None,
        )
        procurement_request.items = [
            ConstructionProcurementItem(
                company_id=company_id,
                sequence_number=index,
                product_id=item["product_id"],
                product_code=item["product_code"],
                product_description=item["product_description"],
                quantity=item["quantity"],
                unit_of_measure=item["unit_of_measure"],
                unit_price=item["unit_price"],
                line_total=item["line_total"],
                schedule_phase_id=item["schedule_phase_id"],
                construction_unit_id=item["construction_unit_id"],
            )
            for index, item in enumerate(items, start=1)
        ]
        await self.repository.add(procurement_request)
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request.id,
        )

    async def list_procurement_requests(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
    ) -> list[ConstructionProcurementRequest]:
        await self.get_project(company_id=company_id, project_id=project_id)
        items = await self.repository.list_procurement_requests(company_id=company_id, project_id=project_id)
        return items

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
        actor_user_id: UUID | None = None,
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

        updates = request.model_dump(exclude_unset=True, exclude={"items", "discount_amount"})
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

        if "items" in request.model_fields_set or "discount_amount" in request.model_fields_set:
            next_discount = request.discount_amount
            if next_discount is None:
                next_discount = procurement_request.discount_amount
            next_items = request.items
            if next_items is None:
                next_items = [
                    ConstructionProcurementItemInput(
                        product_id=item.product_id,
                        quantity=item.quantity,
                        unit_of_measure=item.unit_of_measure,
                        unit_price=item.unit_price,
                        schedule_phase_id=item.schedule_phase_id,
                        construction_unit_id=item.construction_unit_id,
                    )
                    for item in procurement_request.items
                ]
            prepared_items, _, total = await self._prepare_procurement_items(
                company_id=company_id,
                project_id=procurement_request.project_id,
                actor_user_id=actor_user_id,
                item_inputs=next_items,
                discount_amount=next_discount,
                stored_items=procurement_request.items,
            )
            existing_items = {item.sequence_number: item for item in procurement_request.items}
            next_entities = []
            for index, item in enumerate(prepared_items, start=1):
                entity = existing_items.get(index)
                if entity is None:
                    entity = ConstructionProcurementItem(company_id=company_id, sequence_number=index)
                for field, value in item.items():
                    setattr(entity, field, value)
                next_entities.append(entity)
            procurement_request.items = next_entities
            procurement_request.discount_amount = next_discount
            procurement_request.estimated_amount = total
        if "supplier_person_id" in updates and updates["supplier_person_id"] != procurement_request.supplier_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O fornecedor": updates["supplier_person_id"]},
            )
            procurement_request.supplier_qualification_status = await self._resolve_supplier_qualification_status(
                company_id=company_id,
                actor_user_id=actor_user_id,
                supplier_person_id=updates["supplier_person_id"],
            )
        self._apply_updates(entity=procurement_request, updates=updates)
        await self.repository.commit()
        await self.repository.refresh(procurement_request)
        return await self.get_procurement_request(
            company_id=company_id,
            procurement_request_id=procurement_request.id,
        )

    async def submit_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
        actor_user_id: UUID | None,
    ) -> ConstructionProcurementRequest:
        procurement_request = await self.repository.get_procurement_request(
            company_id=company_id, procurement_request_id=procurement_request_id, lock=True)
        if procurement_request is None:
            raise ConstructionNotFoundError(resource_name="a requisição de compra")
        unconfirmed = (
            procurement_request.status == ConstructionProcurementStatus.PENDING_APPROVAL
            and procurement_request.external_procurement_id is None
        )
        if unconfirmed:
            event = await self.event_repository.latest_procurement_event(
                company_id=company_id, aggregate_id=procurement_request.id)
            if event is None:
                procurement_request.submission_revision = max(procurement_request.submission_revision or 0, 1)
                await self._dispatch_procurement_request_to_erp(procurement_request=procurement_request, actor_user_id=actor_user_id)
                await self.repository.commit()
                return procurement_request
            if event.status == "dead_letter":
                event.status, event.retry_count, event.last_error = "pending", 0, None
                procurement_request.delivery_status = "sending"
                await self.repository.commit()
            return procurement_request
        if not unconfirmed and procurement_request.status not in {
            ConstructionProcurementStatus.DRAFT,
            ConstructionProcurementStatus.REJECTED,
        }:
            raise ConstructionInvalidValueError(
                message="A requisição não pode ser enviada na situação atual.",
                error_code="CONSTRUCTION_PROCUREMENT_INVALID_STATUS",
            )

        procurement_request.rejection_reason = None
        procurement_request.submission_revision += 1
        try:
            await self._dispatch_procurement_request_to_erp(
                procurement_request=procurement_request,
                actor_user_id=actor_user_id,
            )
        except ConstructionDomainError:
            await self.repository.rollback()
            raise
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

        subcontract = None
        if request.subcontract_id:
            contracts = SubcontractService(self)
            subcontract = await contracts.get(company_id, request.subcontract_id)
            if subcontract.project_id != project_id or subcontract.status != "RELEASED":
                raise ConstructionInvalidValueError(message="Selecione contrato liberado desta obra.")
            contracts.assert_itemized(subcontract)
            if request.supplier_person_id and request.supplier_person_id != subcontract.supplier_person_id:
                raise ConstructionInvalidValueError(message="O fornecedor da medição precisa corresponder ao contrato.")
            await self._assert_contract_competence(contracts, subcontract, None, request.competence_date)
        else:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O fornecedor": request.supplier_person_id},
            )

        code_number = await self.repository.get_next_measurement_code_number(
            company_id=company_id,
            project_id=project_id,
        )
        code = f"MED-{code_number:06d}"
        sequence_number = await self.repository.get_next_measurement_sequence(
            company_id=company_id,
            unit_id=unit.id,
        )
        _logger.info(
            "construction.measurement.code_generated project_id=%s unit_id=%s code=%s sequence_number=%s",
            project_id,
            unit.id,
            code,
            sequence_number,
        )
        gross_amount = request.gross_amount or request.measured_amount or Decimal("0")
        retentions_amount = request.retentions_amount or Decimal("0")
        net_amount = request.net_amount or request.measured_amount or (gross_amount - retentions_amount)
        if net_amount < Decimal("0") and subcontract is None:
            raise ConstructionInvalidValueError(
                message="As retenções da medição não podem passar do valor bruto.",
                error_code="CONSTRUCTION_MEASUREMENT_NET_INVALID",
            )

        purpose = resolve_measurement_purpose(request.purpose, request.subcontract_id, gross_amount)
        if purpose == "CONTROL" and (retentions_amount or net_amount):
            raise ConstructionInvalidValueError(message="OS de controle não tem valor próprio nem retenções.")
        measurement = ConstructionMeasurement(
            purpose=purpose,
            company_id=company_id,
            project_id=project_id,
            subcontract_id=subcontract.id if subcontract else None,
            retention_details=[item.model_dump(mode="json") for item in request.retention_details],
            unit_id=request.unit_id,
            schedule_phase_id=request.schedule_phase_id,
            code=code,
            sequence_number=sequence_number,
            competence_date=request.competence_date,
            description=request.description,
            gross_amount=gross_amount,
            retentions_amount=retentions_amount,
            net_amount=net_amount,
            document_type=request.document_type.strip() if request.document_type else None,
            document_number=request.document_number.strip() if request.document_number else None,
            measured_amount=net_amount,
            due_date=request.due_date,
            supplier_person_id=subcontract.supplier_person_id if subcontract else request.supplier_person_id,
            supplier_qualification_status=await self._resolve_supplier_qualification_status(
                company_id=company_id,
                actor_user_id=actor_user_id,
                supplier_person_id=subcontract.supplier_person_id if subcontract else request.supplier_person_id,
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

    async def _measurement_open_for_payable_link(self, *, company_id: UUID, measurement_id: UUID) -> ConstructionMeasurement:
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.status != ConstructionMeasurementStatus.APPROVED:
            raise ConstructionInvalidValueError(
                message="Só medição aprovada pode ser vinculada a um título do ERP.",
                error_code="CONSTRUCTION_MEASUREMENT_LINK_REQUIRES_APPROVAL",
            )
        if measurement.external_accounts_payable_id is not None:
            raise ConstructionInvalidValueError(
                message="A medição já está vinculada a um título do ERP.",
                error_code="CONSTRUCTION_MEASUREMENT_ALREADY_LINKED",
            )
        if getattr(measurement, "reversal_pending", False):
            raise ConstructionInvalidValueError(
                message="A medição está com estorno pendente e não pode receber título.",
                error_code="CONSTRUCTION_MEASUREMENT_REVERSAL_PENDING",
            )
        if measurement.supplier_person_id is None:
            raise ConstructionInvalidValueError(
                message="Informe o fornecedor da medição antes de vincular um título.",
                error_code="CONSTRUCTION_MEASUREMENT_SUPPLIER_REQUIRED",
            )
        if measurement.subcontract_id is not None:
            _logger.info(
                "construction.measurement.payable_link_refused reason=contract measurement_id=%s", measurement.id
            )
            raise ConstructionInvalidValueError(
                message="Medição de contrato é paga pela DNF do contrato: vincule no próprio contrato, na aba Empreitada da obra, em DNF das medições do contrato.",
                error_code="CONSTRUCTION_MEASUREMENT_CONTRACT_PAID_BY_SUBCONTRACT",
            )
        amount = measurement.net_amount if measurement.net_amount is not None else measurement.measured_amount
        if amount is None or amount <= Decimal("0"):
            _logger.info(
                "construction.measurement.payable_link_refused reason=zero_value measurement_id=%s", measurement.id
            )
            raise ConstructionInvalidValueError(
                message="Medição sem valor não recebe título próprio: o pagamento da empreitada fica na DNF que paga o conjunto.",
                error_code="CONSTRUCTION_MEASUREMENT_ZERO_VALUE_NO_TITLE",
            )
        if self.erp_client is None:
            raise ConstructionDomainError(message="A integração com o ERP não está disponível.", status_code=502)
        return measurement

    async def list_measurement_payable_candidates(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        user_id: UUID | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        measurement = await self._measurement_open_for_payable_link(company_id=company_id, measurement_id=measurement_id)
        try:
            result = await self.erp_client.list_measurement_payable_candidates(
                company_id=company_id,
                measurement_id=measurement.id,
                user_id=user_id,
                search=search,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível buscar os títulos no ERP.",
            ) from request_error
        except httpx.RequestError as request_error:
            raise ConstructionDomainError(message="Não foi possível falar com o ERP agora.", status_code=502) from request_error
        return list(result.get("items", []))

    async def link_measurement_payable(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        payable_document_id: UUID,
        user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self._measurement_open_for_payable_link(company_id=company_id, measurement_id=measurement_id)
        _logger.info(
            "construction.measurement.payable_link measurement_id=%s payable_document_id=%s",
            measurement.id,
            payable_document_id,
        )
        try:
            payload = await self.erp_client.link_measurement_payable(
                company_id=company_id,
                measurement_id=measurement.id,
                user_id=user_id,
                payable_document_id=payable_document_id,
            )
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(
                request_error=request_error,
                fallback_message="Não foi possível vincular o título no ERP.",
            ) from request_error
        except httpx.RequestError as request_error:
            raise ConstructionDomainError(message="Não foi possível falar com o ERP agora.", status_code=502) from request_error
        self._apply_accounts_payable_snapshot_from_payload(measurement=measurement, payload=payload)
        await self.repository.commit()
        await self.repository.refresh(measurement)
        _logger.info(
            "construction.measurement.payable_linked measurement_id=%s payable_document_id=%s",
            measurement.id,
            measurement.external_accounts_payable_id,
        )
        return measurement

    async def _erp_request(self, call, *, fallback_message: str) -> Any:
        if self.erp_client is None:
            raise ConstructionDomainError(message="A integração com o ERP não está disponível.", status_code=502)
        try:
            return await call()
        except httpx.HTTPStatusError as request_error:
            raise self._erp_domain_error(request_error=request_error, fallback_message=fallback_message) from request_error
        except httpx.RequestError as request_error:
            raise ConstructionDomainError(message="Não foi possível falar com o ERP agora.", status_code=502) from request_error

    async def list_zero_value_suppliers(self, *, company_id: UUID, project_id: UUID) -> list[dict[str, Any]]:
        await self.get_project(company_id=company_id, project_id=project_id)
        rows = await self.repository.zero_value_suppliers(company_id=company_id, project_id=project_id)
        return [{"supplier_person_id": supplier_id, "open_count": count} for supplier_id, count in rows]

    async def list_zero_value_measurements(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        page: int,
        page_size: int,
        **filters,
    ) -> tuple[list[dict[str, Any]], int]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_zero_value_measurements(
            company_id=company_id, project_id=project_id, page=page, page_size=page_size, **filters
        )

    async def zero_value_measurement_ids(self, *, company_id: UUID, project_id: UUID, **filters) -> list[UUID]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.zero_value_measurement_ids(
            company_id=company_id, project_id=project_id, limit=SHARED_PAYABLE_BATCH_LIMIT, **filters
        )

    async def list_shared_payables(self, *, company_id: UUID, project_id: UUID, user_id: UUID | None) -> list[dict]:
        await self.get_project(company_id=company_id, project_id=project_id)
        result = await self._erp_request(
            lambda: self.erp_client.list_shared_payables(company_id=company_id, project_id=project_id, user_id=user_id),
            fallback_message="Não foi possível buscar as DNFs da empreitada no ERP.",
        )
        return list(result.get("items", []))

    async def list_shared_payable_candidates(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        supplier_person_id: UUID,
        user_id: UUID | None,
        search: str | None = None,
    ) -> list[dict]:
        await self.get_project(company_id=company_id, project_id=project_id)
        result = await self._erp_request(
            lambda: self.erp_client.list_shared_payable_candidates(
                company_id=company_id,
                project_id=project_id,
                user_id=user_id,
                supplier_person_id=supplier_person_id,
                search=search,
            ),
            fallback_message="Não foi possível buscar os títulos no ERP.",
        )
        return list(result.get("items", []))

    async def _shared_payable_measurements(
        self, *, company_id: UUID, project_id: UUID, measurement_ids: list[UUID], lock: bool = False
    ) -> list[ConstructionMeasurement]:
        await self.get_project(company_id=company_id, project_id=project_id)
        unique_ids = list(dict.fromkeys(measurement_ids))
        measurements = await self.repository.list_measurements_by_ids(
            company_id=company_id, project_id=project_id, measurement_ids=unique_ids, lock=lock
        )
        if len(measurements) != len(unique_ids):
            raise ConstructionNotFoundError(resource_name="uma ou mais medições desta obra")
        return measurements

    @staticmethod
    def _measurement_contract_id(measurement) -> UUID | None:
        return measurement.subcontract_id or getattr(measurement, "global_contract_id", None)

    async def link_shared_payable(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        payable_document_id: UUID,
        measurement_ids: list[UUID],
        user_id: UUID | None = None,
        subcontract_id: UUID | None = None,
    ) -> int:
        _logger.info(
            "construction.measurement.shared_payable_link project_id=%s payable_document_id=%s requested=%s subcontract_id=%s",
            project_id,
            payable_document_id,
            len(measurement_ids),
            subcontract_id,
        )
        await self.repository.lock_shared_payable(company_id=company_id, payable_document_id=payable_document_id)
        contracts = None
        contract = None
        if subcontract_id is not None:
            contracts = SubcontractService(self)
            contract = await contracts.get(company_id, subcontract_id, True)
            if contract.project_id != project_id:
                raise ConstructionNotFoundError(resource_name="o contrato de empreitada desta obra")
        measurements = await self._shared_payable_measurements(
            company_id=company_id, project_id=project_id, measurement_ids=measurement_ids, lock=True
        )
        global_contract = contract is not None and contract.pricing_mode == "GLOBAL"
        for measurement in measurements:
            amount = measurement.net_amount if measurement.net_amount is not None else measurement.measured_amount
            if contract is not None:
                belongs = (
                    getattr(measurement, "global_contract_id", None) == contract.id
                    if global_contract
                    else measurement.subcontract_id == contract.id
                )
                if (
                    measurement.status != ConstructionMeasurementStatus.APPROVED
                    or not belongs
                    or getattr(measurement, "reversal_pending", False)
                    or (global_contract and amount is not None and amount > Decimal("0"))
                ):
                    raise ConstructionInvalidValueError(
                        message=f"A OS {measurement.code} não é uma medição aprovada do contrato {contract.code}.",
                        error_code="CONSTRUCTION_MEASUREMENT_SHARED_NOT_IN_CONTRACT",
                    )
            elif (
                measurement.status != ConstructionMeasurementStatus.APPROVED
                or self._measurement_contract_id(measurement) is not None
                or (amount is not None and amount > Decimal("0"))
            ):
                raise ConstructionInvalidValueError(
                    message=(
                        f"A OS {measurement.code} não é uma OS aprovada sem valor e sem contrato: "
                        "a OS de contrato é paga pela DNF vinculada no próprio contrato, na aba Empreitada."
                    ),
                    error_code="CONSTRUCTION_MEASUREMENT_SHARED_NOT_ZERO",
                )
            if measurement.external_accounts_payable_id is not None and not (
                measurement.external_accounts_payable_id == payable_document_id
                and measurement.external_accounts_payable_shared
            ):
                raise ConstructionInvalidValueError(
                    message=f"A OS {measurement.code} já está vinculada a outro título do ERP.",
                    error_code="CONSTRUCTION_MEASUREMENT_SHARED_ALREADY_LINKED",
                )
            if measurement.supplier_person_id is None:
                raise ConstructionInvalidValueError(
                    message=f"A OS {measurement.code} não tem fornecedor. Informe o fornecedor antes de vincular a DNF.",
                    error_code="CONSTRUCTION_MEASUREMENT_SUPPLIER_REQUIRED",
                )
        suppliers = {measurement.supplier_person_id for measurement in measurements}
        if len(suppliers) > 1:
            raise ConstructionInvalidValueError(
                message="As OS marcadas são de fornecedores diferentes. Vincule as de um fornecedor por vez.",
                error_code="CONSTRUCTION_MEASUREMENT_SHARED_OTHER_SUPPLIER",
            )
        await self._assert_shared_payable_single_contract(
            company_id=company_id,
            payable_document_id=payable_document_id,
            measurements=measurements,
            contract_id=contract.id if contract is not None else None,
        )
        supplier_person_id = suppliers.pop()
        payload = await self._erp_request(
            lambda: self.erp_client.check_shared_payable(
                company_id=company_id,
                project_id=project_id,
                user_id=user_id,
                payable_document_id=payable_document_id,
                supplier_person_id=supplier_person_id,
            ),
            fallback_message="Não foi possível conferir a DNF no ERP.",
        )
        if str(payload.get("person_id")) != str(supplier_person_id):
            raise ConstructionInvalidValueError(
                message="A DNF é de outro fornecedor. Escolha uma DNF do fornecedor das OS.",
                error_code="CONSTRUCTION_MEASUREMENT_SHARED_OTHER_SUPPLIER",
            )
        if global_contract:
            await contracts.register_global_payable(company_id, contract.id, payable_document_id, payload, user_id)
        elif contract is not None:
            await self._assert_contract_payable_total(
                company_id=company_id, payable_document_id=payable_document_id, payload=payload, measurements=measurements
            )
        linked = 0
        for measurement in measurements:
            if measurement.external_accounts_payable_id is None:
                linked += 1
            self._apply_accounts_payable_snapshot_from_payload(measurement=measurement, payload=payload)
            measurement.external_accounts_payable_shared = True
        await self.repository.commit()
        _logger.info(
            "construction.measurement.shared_payable_linked project_id=%s payable_document_id=%s count=%s",
            project_id,
            payable_document_id,
            linked,
        )
        return linked

    async def _assert_shared_payable_single_contract(
        self, *, company_id, payable_document_id, measurements, contract_id
    ) -> None:
        covered_contracts = await self.repository.shared_payable_contract_ids(
            company_id=company_id,
            payable_document_id=payable_document_id,
            exclude_measurement_ids=[measurement.id for measurement in measurements],
        )
        if covered_contracts and covered_contracts != {contract_id}:
            _logger.info(
                f"[construction] shared_payable: mixed_contracts payable_document_id={payable_document_id} "
                f"contract_id={contract_id}"
            )
            raise ConstructionInvalidValueError(
                message=(
                    "Esta DNF já paga OS de outro contrato ou OS sem contrato. "
                    "Uma DNF paga OS de um contrato só, ou só OS sem contrato."
                ),
                error_code="CONSTRUCTION_MEASUREMENT_SHARED_MIXED_CONTRACTS",
            )

    async def _assert_contract_payable_total(self, *, company_id, payable_document_id, payload, measurements) -> None:
        new_ids = {measurement.id for measurement in measurements}
        already_linked = await self.repository.shared_payable_net_total(
            company_id=company_id, payable_document_id=payable_document_id, exclude_measurement_ids=list(new_ids)
        )
        covered = already_linked + sum(
            (
                measurement.net_amount if measurement.net_amount is not None else (measurement.measured_amount or Decimal("0"))
                for measurement in measurements
            ),
            Decimal("0"),
        )
        document_net = Decimal(str(payload.get("net_amount") or payload.get("total_amount") or "0"))
        if abs(covered - document_net) > Decimal("0.01"):
            _logger.info(
                f"[construction] shared_payable: contract_total_mismatch payable_document_id={payable_document_id} "
                f"covered={covered} document_net={document_net}"
            )
            raise ConstructionInvalidValueError(
                message=(
                    f"A soma dos líquidos das OS ({_brl(covered)}) precisa ser igual ao líquido da DNF "
                    f"({_brl(document_net)}, valor menos os tributos retidos)."
                ),
                error_code="CONSTRUCTION_MEASUREMENT_SHARED_TOTAL_MISMATCH",
            )

    async def unlink_shared_payable(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        payable_document_id: UUID,
        measurement_ids: list[UUID],
        user_id: UUID | None = None,
    ) -> int:
        await self.repository.lock_shared_payable(company_id=company_id, payable_document_id=payable_document_id)
        measurements = await self._shared_payable_measurements(
            company_id=company_id, project_id=project_id, measurement_ids=measurement_ids, lock=True
        )
        for measurement in measurements:
            if measurement.external_accounts_payable_id != payable_document_id or not measurement.external_accounts_payable_shared:
                raise ConstructionInvalidValueError(
                    message=f"A OS {measurement.code} não está vinculada a esta DNF da empreitada.",
                    error_code="CONSTRUCTION_MEASUREMENT_SHARED_NOT_IN_PAYABLE",
                )
        contract_measurements = [m for m in measurements if self._measurement_contract_id(m) is not None]
        if contract_measurements:
            try:
                payload = await self._erp_request(
                    lambda: self.erp_client.check_shared_payable(
                        company_id=company_id,
                        project_id=project_id,
                        user_id=user_id,
                        payable_document_id=payable_document_id,
                        supplier_person_id=contract_measurements[0].supplier_person_id,
                    ),
                    fallback_message="Não foi possível conferir a DNF no ERP.",
                )
            except ConstructionDomainError as check_error:
                if check_error.status_code >= 500:
                    raise
                _logger.info(
                    f"[construction] shared_payable: unlink_without_active_payable payable_document_id={payable_document_id} "
                    f"reason={check_error.message}"
                )
                payload = {}
            if payload.get("accounts_payable_status") in {"PAID", "PARTIALLY_PAID"}:
                _logger.info(
                    f"[construction] shared_payable: unlink_refused_paid payable_document_id={payable_document_id}"
                )
                raise ConstructionInvalidValueError(
                    message="A DNF já tem pagamento: estorne os pagamentos no Contas a Pagar antes de tirar OS de contrato dela.",
                    error_code="CONSTRUCTION_MEASUREMENT_SHARED_PAYABLE_PAID",
                )
        for measurement in measurements:
            measurement.external_accounts_payable_id = None
            measurement.external_accounts_payable_status = None
            measurement.external_accounts_payable_shared = False
        global_contract_ids = {getattr(m, "global_contract_id", None) for m in measurements} - {None}
        if global_contract_ids:
            await self.repository.flush()
            contracts = SubcontractService(self)
            for global_contract_id in global_contract_ids:
                await contracts.release_global_payable_if_empty(company_id, global_contract_id, payable_document_id)
        await self.repository.commit()
        _logger.info(
            "construction.measurement.shared_payable_unlinked project_id=%s payable_document_id=%s count=%s",
            project_id,
            payable_document_id,
            len(measurements),
        )
        return len(measurements)

    async def update_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        request: ConstructionMeasurementUpdate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self._get_editable_measurement(company_id=company_id, measurement_id=measurement_id)
        assert_measurement_editable(measurement)

        updates = request.model_dump(exclude_unset=True)
        financial_fields_changed = any(
            field in updates and updates[field] != getattr(measurement, field)
            for field in ("gross_amount", "retentions_amount", "net_amount", "measured_amount")
        )
        if "subcontract_id" in updates or getattr(measurement, "subcontract_id", None):
            contracts = SubcontractService(self)
            contract = await contracts.bind_parent(measurement, updates)
            if contract is not None:
                await self._assert_contract_competence(
                    contracts,
                    contract,
                    measurement.subcontract_version_id,
                    updates.get("competence_date", measurement.competence_date),
                )
        if (
            updates.get("subcontract_id", getattr(measurement, "subcontract_id", None)) is None
            and "supplier_person_id" in updates
            and updates["supplier_person_id"] != measurement.supplier_person_id
        ):
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O fornecedor": updates["supplier_person_id"]},
            )
        if "retention_details" in updates:
            updates["retention_details"] = [item.model_dump(mode="json") for item in (request.retention_details or [])]
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

        if net_amount is None or net_amount < Decimal("0"):
            raise ConstructionInvalidValueError(
                message="As retenções da medição não podem passar do valor bruto.",
                error_code="CONSTRUCTION_MEASUREMENT_NET_INVALID",
            )

        updates["gross_amount"] = gross_amount
        updates["retentions_amount"] = retentions_amount
        updates["net_amount"] = net_amount
        updates["measured_amount"] = net_amount

        contract_id = updates.get("subcontract_id", measurement.subcontract_id)
        purpose = resolve_measurement_purpose(updates.get("purpose") or ("CONTRACT" if contract_id else "SERVICE" if measurement.subcontract_id else measurement_purpose(measurement)), contract_id, gross_amount)
        if purpose == "CONTROL" and any((gross_amount, retentions_amount, net_amount)):
            raise ConstructionInvalidValueError(message="OS de controle não tem valor próprio nem retenções.")
        if getattr(measurement, "global_contract_id", None) and purpose != "CONTROL":
            raise ConstructionInvalidValueError(
                message="A OS está num contrato por valor global e continua sem valor próprio. Tire-a do contrato antes de mudar a finalidade.",
                error_code="CONSTRUCTION_MEASUREMENT_IN_GLOBAL_CONTRACT",
            )
        if purpose != measurement_purpose(measurement):
            items = await self.repository.list_measurement_items(company_id=company_id, measurement_id=measurement_id)
            if items:
                raise ConstructionInvalidValueError(message="Remova os itens antes de trocar a finalidade da medição.")
        updates["purpose"] = purpose
        self._apply_updates(entity=measurement, updates=updates)
        if purpose == "SERVICE" and financial_fields_changed:
            await self._sync_measurement_amounts_from_items(measurement=measurement)
            if measurement.retentions_amount > measurement.gross_amount:
                raise ConstructionInvalidValueError(
                    message="As retenções da medição não podem passar da soma dos itens.",
                    error_code="CONSTRUCTION_MEASUREMENT_RETENTIONS_INVALID",
                )
            _logger.info(f"[measurement] amounts_recalculated: company_id={company_id} measurement_id={measurement_id} "
                         f"gross={measurement.gross_amount} retained={measurement.retentions_amount} net={measurement.net_amount}")

        await self.repository.commit()
        await self.repository.refresh(measurement)
        return measurement

    async def _assert_measurement_references(self, measurement):
        if not measurement.unit_id:
            raise ConstructionInvalidValueError(
                message="Vincule a medição a uma unidade antes de enviar ou aprovar.",
                error_code="CONSTRUCTION_MEASUREMENT_UNIT_REQUIRED",
            )

        if not measurement.schedule_phase_id:
            raise ConstructionInvalidValueError(
                message="Vincule a medição a uma fase do cronograma antes de enviar ou aprovar.",
                error_code="CONSTRUCTION_MEASUREMENT_PHASE_REQUIRED",
            )

        unit = await self._get_unit(company_id=measurement.company_id, unit_id=measurement.unit_id)
        if not unit.analytic_cost_center_id:
            raise ConstructionInvalidValueError(
                message="A unidade precisa de um centro de custo analítico antes de enviar ou aprovar medições.",
                error_code="CONSTRUCTION_UNIT_COST_CENTER_REQUIRED",
            )

        if not measurement.supplier_person_id:
            raise ConstructionInvalidValueError(
                message="Informe o fornecedor da medição antes de enviar ou aprovar.",
                error_code="CONSTRUCTION_MEASUREMENT_SUPPLIER_REQUIRED",
            )


        if measurement.subcontract_id:
            contracts = SubcontractService(self)
            contract = await contracts.get(measurement.company_id, measurement.subcontract_id)
            if contract.status != "RELEASED":
                raise ConstructionInvalidValueError(message="Libere a planilha do contrato antes de enviar a medição.")
            await self._assert_contract_competence(
                contracts, contract, measurement.subcontract_version_id, measurement.competence_date)

    async def _assert_contract_competence(self, contracts, contract, version_id, competence_date):
        version = await contracts.measurement_version(contract.company_id, contract, version_id)
        if version is None:
            raise ConstructionInvalidValueError(message="Libere a planilha do contrato antes de medir.")
        contracts.assert_competence(version, competence_date)

    async def submit_measurement(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurement:
        measurement = await self._get_editable_measurement(company_id=company_id, measurement_id=measurement_id)
        assert_measurement_editable(measurement)
        await self._assert_measurement_references(measurement)

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
        normalized_reason = (reason or "").strip()
        if not normalized_reason:
            _logger.info(f"[construction] reject_measurement: missing_reason measurement_id={measurement_id}")
            raise ConstructionInvalidValueError(
                message="Informe o motivo da rejeição.",
                error_code="CONSTRUCTION_MEASUREMENT_REJECTION_REASON_REQUIRED",
            )
        measurement = await self.repository.lock_measurement(company_id, measurement_id)
        if measurement is None:
            raise ConstructionNotFoundError(resource_name="a medição")
        if measurement.status in {ConstructionMeasurementStatus.APPROVED, ConstructionMeasurementStatus.PAID}:
            raise ConstructionInvalidValueError(
                message="Medição aprovada não pode ser rejeitada.",
                error_code="CONSTRUCTION_MEASUREMENT_LOCKED",
            )
        if measurement.status not in {ConstructionMeasurementStatus.SUBMITTED, ConstructionMeasurementStatus.IN_APPROVAL}:
            _logger.info(
                f"[construction] reject_measurement: not_submitted measurement_id={measurement_id} status={measurement.status}"
            )
            raise ConstructionInvalidValueError(
                message="Só medição enviada ou em aprovação pode ser rejeitada.",
                error_code="CONSTRUCTION_MEASUREMENT_REJECT_REQUIRES_SUBMISSION",
            )

        measurement.status = ConstructionMeasurementStatus.REJECTED
        measurement.rejection_reason = normalized_reason
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
        actor_can_self_approve: bool = False,
    ) -> ConstructionMeasurement:
        measurement = await self.repository.lock_measurement(company_id, measurement_id)
        if measurement is None:
            raise ConstructionNotFoundError(resource_name="a medição")
        if getattr(measurement, "subcontract_id", None):
            measurement = await SubcontractService(self).repository.measurement(company_id, measurement_id, True)
            if measurement.reversal_pending:
                raise ConstructionInvalidValueError(message="Aguarde a confirmação do estorno financeiro da medição.")
        if measurement.status == ConstructionMeasurementStatus.APPROVED:
            return measurement
        if measurement.status == ConstructionMeasurementStatus.PAID:
            raise ConstructionInvalidValueError(
                message="A medição já está paga e não pode ser aprovada novamente.",
                error_code="CONSTRUCTION_MEASUREMENT_ALREADY_PAID",
            )

        # Antes das travas de unidade e fase de propósito: quem aprova precisa
        # ver o problema da FVS antes de ouvir sobre centro de custo.
        if measurement.status not in {
            ConstructionMeasurementStatus.SUBMITTED,
            ConstructionMeasurementStatus.IN_APPROVAL,
        }:
            raise ConstructionInvalidValueError(
                message="Envie a medição para aprovação antes de aprovar.",
                error_code="CONSTRUCTION_MEASUREMENT_MUST_BE_SUBMITTED",
            )

        await self._assert_measurement_inspections_are_approved(
            company_id=company_id,
            measurement_id=measurement_id,
            action_label="aprovar",
        )

        await self._assert_measurement_references(measurement)

        is_own_measurement = actor_user_id is not None and actor_user_id in {
            measurement.submitted_by_user_id,
            measurement.created_by_user_id,
        }
        if is_own_measurement:
            if not actor_can_self_approve:
                raise ConstructionInvalidValueError(
                    message="Quem criou ou enviou a medição não pode aprová-la. Peça a outro usuário com permissão para aprovar.",
                    error_code="CONSTRUCTION_MEASUREMENT_SELF_APPROVAL",
                )
            _logger.info(
                "construction.measurement.self_approved measurement_id=%s user_id=%s",
                measurement.id,
                actor_user_id,
            )

        await self._sync_measurement_amounts_from_items(measurement=measurement)
        if getattr(measurement, "subcontract_id", None):
            await SubcontractService(self).consume(measurement)

        measurement.status = ConstructionMeasurementStatus.APPROVED
        measurement.rejection_reason = None
        measurement.rejected_by_user_id = None
        measurement.rejected_at = None
        measurement.approved_by_user_id = actor_user_id
        if measurement.approved_at is None:
            measurement.approved_at = datetime.now(tz=UTC)
        _logger.info(
            "construction.measurement.approved measurement_id=%s user_id=%s payable=manual",
            measurement.id,
            actor_user_id,
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
        commit=True,
    ) -> ConstructionMeasurementItem:
        measurement = await self._get_editable_measurement(company_id=company_id, measurement_id=measurement_id)

        contract_item = None
        if measurement.subcontract_id:
            contract_version, contract_item = await SubcontractService(self).contract_item(measurement, request.subcontract_item_id, request.quantity)
            request = request.model_copy(update={
                "service_template_id": UUID(contract_item["service_template_id"]) if contract_item.get("service_template_id") else None,
                "description": contract_item["description"],
            })
        elif request.subcontract_item_id or request.quantity is not None:
            raise ConstructionInvalidValueError(message="Vincule a medição ao contrato antes de selecionar o item contratado.")
        elif measurement_purpose(measurement) == "CONTROL":
            if request.amount not in {None, Decimal("0")}:
                raise ConstructionInvalidValueError(message="Os serviços da OS de controle não têm valor próprio.")
        elif request.amount is None or request.amount <= 0:
            raise ConstructionInvalidValueError(message="Informe valor positivo para o serviço avulso.")

        service_template = None
        if request.service_template_id is not None:
            service_template = await self.repository.get_service_template(
                company_id=company_id,
                service_template_id=request.service_template_id,
            )
            if service_template is None:
                raise ConstructionNotFoundError(resource_name="o serviço do catálogo")
            if not service_template.is_active and contract_item is None:
                raise ConstructionInvalidValueError(
                    message=f"O serviço {service_template.name} está desativado no catálogo.",
                    error_code="CONSTRUCTION_SERVICE_TEMPLATE_INACTIVE",
                )

        project_service_ids = await self.repository.project_service_template_ids(
            company_id=company_id,
            project_id=measurement.project_id,
        )
        if project_service_ids and contract_item is None:
            if service_template is None:
                _logger.info(
                    "construction.project_services.rejected measurement_id=%s reason=free_text",
                    measurement_id,
                )
                raise ConstructionInvalidValueError(
                    message="Esta obra tem lista de serviços: escolha um serviço da lista.",
                    error_code="CONSTRUCTION_MEASUREMENT_ITEM_PROJECT_SERVICE_REQUIRED",
                )
            if service_template.id not in project_service_ids:
                _logger.info(
                    "construction.project_services.rejected measurement_id=%s service_template_id=%s reason=not_linked",
                    measurement_id,
                    service_template.id,
                )
                raise ConstructionInvalidValueError(
                    message=f"O serviço {service_template.name} não está na lista de serviços da obra.",
                    error_code="CONSTRUCTION_MEASUREMENT_ITEM_SERVICE_NOT_IN_PROJECT",
                )

        description = (request.description or "").strip()
        if not description and service_template is not None:
            description = service_template.name

        if not description:
            raise ConstructionInvalidValueError(
                message="O item da medição precisa de uma descrição ou de um serviço do catálogo.",
                error_code="CONSTRUCTION_MEASUREMENT_ITEM_DESCRIPTION_REQUIRED",
            )

        await self._assert_measurement_item_unique(
            company_id=company_id,
            measurement=measurement,
            service_template=service_template,
            description=description,
            subcontract_item_id=request.subcontract_item_id if contract_item else None,
        )
        if contract_item is None and not request.confirm_unit_duplicate:
            await self._warn_unit_service_duplicate(
                company_id=company_id,
                measurement=measurement,
                service_template=service_template,
                description=description,
            )

        await self._require_company_people(
            company_id=company_id,
            actor_user_id=actor_user_id,
            people={"O inspetor": request.inspector_person_id},
        )
        await self._require_company_products(
            company_id=company_id,
            actor_user_id=actor_user_id,
            product_ids=[request.product_id],
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
            amount=(request.amount or Decimal("0")).quantize(Decimal("0.01")),
            start_date=request.start_date,
            end_date=request.end_date,
            inspector_person_id=request.inspector_person_id,
            inspection_status=ConstructionInspectionStatus.PENDING,
            created_by_user_id=actor_user_id,
        )
        if getattr(measurement, "subcontract_id", None):
            await SubcontractService(self).bind_item(measurement, item, request.subcontract_item_id, request.quantity,
                terms=(contract_version, contract_item))
        elif request.subcontract_item_id or request.quantity is not None:
            raise ConstructionInvalidValueError(message="Vincule a medição ao contrato antes de selecionar o item contratado.")
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
        await self.repository.flush()

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
            await self.repository.flush()

        await self._sync_measurement_amounts_from_items(measurement=measurement)
        if commit:
            await self.repository.commit()
        return await self.get_measurement_item(company_id=company_id, item_id=item.id)

    async def _assert_measurement_item_unique(
        self, *, company_id, measurement, service_template, description, subcontract_item_id, exclude_item_id=None
    ) -> None:
        existing_items = await self.repository.list_measurement_items(
            company_id=company_id,
            measurement_id=measurement.id,
        )
        for existing_item in existing_items:
            if existing_item.id == exclude_item_id:
                continue
            if subcontract_item_id is not None:
                duplicate = existing_item.subcontract_item_id == subcontract_item_id
            elif service_template is not None:
                duplicate = existing_item.service_template_id == service_template.id
            else:
                duplicate = (
                    existing_item.service_template_id is None
                    and existing_item.description.casefold() == description.casefold()
                )
            if duplicate:
                service_name = service_template.name if service_template is not None else description
                _logger.info(
                    f"[construction] measurement_item: duplicate_in_measurement measurement_id={measurement.id} "
                    f"service={service_name}"
                )
                raise ConstructionInvalidValueError(
                    message=f"O serviço {service_name} já faz parte desta medição.",
                    error_code="CONSTRUCTION_MEASUREMENT_ITEM_DUPLICATE_SERVICE",
                )

    async def _warn_unit_service_duplicate(self, *, company_id, measurement, service_template, description) -> None:
        if not measurement.unit_id:
            return
        order = await self.repository.find_unit_order_with_service(
            company_id=company_id,
            unit_id=measurement.unit_id,
            exclude_measurement_id=measurement.id,
            service_template_id=service_template.id if service_template is not None else None,
            description=description,
        )
        if order is None:
            return
        service_name = service_template.name if service_template is not None else description
        _logger.info(
            f"[construction] measurement_item: duplicate_in_unit measurement_id={measurement.id} "
            f"unit_id={measurement.unit_id} other_measurement_id={order.id}"
        )
        raise ConstructionInvalidValueError(
            message=(
                f"O serviço {service_name} já está lançado nesta unidade na OS nº "
                f"{order.sequence_number or '-'} ({order.code}). Confirme para incluir mesmo assim."
            ),
            error_code="CONSTRUCTION_MEASUREMENT_ITEM_DUPLICATE_IN_UNIT",
        )

    async def create_measurement_items(self, company_id, measurement_id, requests, actor_user_id):
        if not requests or len(requests) > 100:
            raise ConstructionInvalidValueError(message="Envie entre 1 e 100 itens por vez.")
        measurement = await self.repository.lock_measurement(company_id, measurement_id)
        if measurement is None:
            raise ConstructionNotFoundError(resource_name="a medição")
        assert_measurement_editable(measurement)
        _logger.info(f"[measurement] add_items: company_id={company_id} measurement_id={measurement_id} count={len(requests)}")
        created = []
        try:
            for request in requests:
                created.append(await self.create_measurement_item(company_id=company_id,
                    measurement_id=measurement_id, request=request, actor_user_id=actor_user_id, commit=False))
            await self.repository.commit()
        except Exception:
            await self.repository.rollback()
            raise
        return created

    async def update_measurement_item(
        self,
        *,
        company_id: UUID,
        item_id: UUID,
        request: ConstructionMeasurementItemUpdate,
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurementItem:
        item = await self.get_measurement_item(company_id=company_id, item_id=item_id)
        measurement = await self._get_editable_measurement(
            company_id=company_id,
            measurement_id=item.measurement_id,
        )

        updates = request.model_dump(exclude_unset=True)
        confirm_unit_duplicate = updates.pop("confirm_unit_duplicate", False)
        if updates.get("inspector_person_id") != item.inspector_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O inspetor": updates.get("inspector_person_id")},
            )
        if updates.get("product_id") != item.product_id:
            await self._require_company_products(
                company_id=company_id,
                actor_user_id=actor_user_id,
                product_ids=[updates.get("product_id")],
            )
        if "description" in updates:
            description = (updates["description"] or "").strip()
            service_template = None
            if item.service_template_id is not None:
                service_template = await self.repository.get_service_template(
                    company_id=company_id,
                    service_template_id=item.service_template_id,
                )
            if not description and service_template is not None:
                description = service_template.name
            if not description:
                raise ConstructionInvalidValueError(
                    message="O item da medição precisa de uma descrição ou de um serviço do catálogo.",
                    error_code="CONSTRUCTION_MEASUREMENT_ITEM_DESCRIPTION_REQUIRED",
                )
            if service_template is None and not item.subcontract_item_id and description.casefold() != item.description.casefold():
                await self._assert_measurement_item_unique(
                    company_id=company_id,
                    measurement=measurement,
                    service_template=None,
                    description=description,
                    subcontract_item_id=None,
                    exclude_item_id=item.id,
                )
                if not confirm_unit_duplicate:
                    await self._warn_unit_service_duplicate(
                        company_id=company_id,
                        measurement=measurement,
                        service_template=None,
                        description=description,
                    )
            updates["description"] = description

        if "product_description" in updates:
            updates["product_description"] = (updates["product_description"] or "").strip() or None

        if "subcontract_item_id" in updates and updates["subcontract_item_id"] != item.subcontract_item_id:
            raise ConstructionInvalidValueError(message="Remova o item e inclua a linha contratada correta para preservar a FVS.")
        if "amount" in updates and measurement_purpose(measurement) == "CONTROL" and updates["amount"] not in {None, Decimal("0")}:
            raise ConstructionInvalidValueError(message="Os serviços da OS de controle não têm valor próprio.")
        if "amount" in updates and measurement_purpose(measurement) == "SERVICE" and (updates["amount"] is None or updates["amount"] <= 0):
            raise ConstructionInvalidValueError(message="Informe valor positivo para o serviço avulso.")
        if "amount" in updates and updates["amount"] is not None:
            updates["amount"] = updates["amount"].quantize(Decimal("0.01"))

        self._apply_updates(entity=item, updates=updates)
        if getattr(measurement, "subcontract_id", None):
            await SubcontractService(self).bind_item(measurement, item, item.subcontract_item_id, item.quantity)
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
        if getattr(measurement, "subcontract_id", None) and await SubcontractService(self).repository.item_has_history(company_id, item_id):
            raise ConstructionInvalidValueError(message="O item possui histórico de consumo contratual e precisa ser preservado.")
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
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurementItemInspection:
        item = await self.get_measurement_item(company_id=company_id, item_id=item_id)
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)
        if request.inspector_person_id != item.inspector_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O inspetor": request.inspector_person_id},
            )

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
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurementItemInspection:
        inspection = await self._get_inspection(company_id=company_id, inspection_id=inspection_id)
        item = await self.get_measurement_item(company_id=company_id, item_id=inspection.measurement_item_id)
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)

        updates = request.model_dump(exclude_unset=True)
        if updates.get("inspector_person_id") != inspection.inspector_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O inspetor": updates.get("inspector_person_id")},
            )
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
        measurement = await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)

        if request.status == ConstructionInspectionStatus.WAIVED and not actor_can_waive:
            raise ConstructionInvalidValueError(
                message="Dispensar a reinspeção exige permissão de exclusão em Verificação da FVS.",
                error_code="CONSTRUCTION_INSPECTION_WAIVE_NOT_ALLOWED",
            )

        # Em rascunho, reverificar e' correcao de clique errado e as duas rodadas
        # ficam no historico. Depois de enviada, nao: reabrir uma linha aprovada
        # numa medicao em aprovacao e' materia de ocorrencia.
        if (
            inspection.status == ConstructionInspectionStatus.COMPLIANT
            and measurement.status not in {ConstructionMeasurementStatus.DRAFT, ConstructionMeasurementStatus.REJECTED}
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
        if request.status != ConstructionInspectionStatus.WAIVED:
            inspector_person_id = request.inspector_person_id or actor_person_id
            if actor_person_id is None or inspector_person_id != actor_person_id:
                _logger.info(
                    f"[construction] verify_inspection: inspector_mismatch inspection_id={inspection_id} "
                    f"inspector_person_id={inspector_person_id} actor_person_id={actor_person_id}"
                )
                raise ConstructionInvalidValueError(
                    message=(
                        "Somente o inspetor desta rodada registra o parecer. "
                        "Escolha você como inspetor da rodada ou entre com o usuário do inspetor."
                        if actor_person_id
                        else "Seu usuário não está vinculado a uma pessoa do cadastro; "
                        "peça ao administrador para vinculá-lo antes de registrar o parecer da FVS."
                    ),
                    error_code="CONSTRUCTION_INSPECTION_INSPECTOR_MISMATCH",
                )
        if request.inspector_person_id not in {inspection.inspector_person_id, item.inspector_person_id}:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O inspetor": request.inspector_person_id},
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
                opened_at=opened_on or get_business_today(current_business_timezone()),
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
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)
        if request.inspector_person_id != item.inspector_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O inspetor": request.inspector_person_id},
            )

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
            opened_at=request.opened_at or get_business_today(current_business_timezone()),
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
        actor_user_id: UUID | None = None,
    ) -> ConstructionMeasurementItemOccurrence:
        occurrence = await self._get_occurrence(company_id=company_id, occurrence_id=occurrence_id)

        item = await self.get_measurement_item(company_id=company_id, item_id=occurrence.measurement_item_id)
        await self._get_editable_measurement(company_id=company_id, measurement_id=item.measurement_id)

        updates = request.model_dump(exclude_unset=True)
        if updates.get("inspector_person_id") != occurrence.inspector_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O inspetor": updates.get("inspector_person_id")},
            )
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
                updates["closed_at"] = get_business_today(current_business_timezone())

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

    async def list_service_templates_for_project(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        search: str | None = None,
    ) -> tuple[list[ConstructionServiceTemplate], bool]:
        await self.get_project(company_id=company_id, project_id=project_id)
        linked_ids = await self.repository.project_service_template_ids(company_id=company_id, project_id=project_id)
        templates = await self.repository.list_service_templates(
            company_id=company_id,
            only_active=True,
            search=search,
            restrict_to_project_id=project_id if linked_ids else None,
        )
        return templates, bool(linked_ids)

    async def list_project_services(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionServiceTemplate]:
        await self.get_project(company_id=company_id, project_id=project_id)
        return await self.repository.list_project_service_templates(company_id=company_id, project_id=project_id)

    async def _active_service_template(self, *, company_id: UUID, service_template_id: UUID) -> ConstructionServiceTemplate:
        template = await self.repository.get_service_template(
            company_id=company_id,
            service_template_id=service_template_id,
        )
        if template is None:
            raise ConstructionNotFoundError(resource_name="o serviço do catálogo")
        if not template.is_active:
            raise ConstructionInvalidValueError(
                message=f"O serviço {template.name} está desativado no catálogo. Ative-o antes de usá-lo.",
                error_code="CONSTRUCTION_SERVICE_TEMPLATE_INACTIVE",
            )
        return template

    async def link_project_services(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        service_template_ids: list[UUID],
        actor_user_id: UUID | None = None,
    ) -> list[ConstructionServiceTemplate]:
        await self.get_project(company_id=company_id, project_id=project_id)
        requested = list(dict.fromkeys(service_template_ids))
        if not requested:
            raise ConstructionInvalidValueError(
                message="Escolha ao menos um serviço do catálogo para vincular à obra.",
                error_code="CONSTRUCTION_PROJECT_SERVICE_REQUIRED",
            )
        for service_template_id in requested:
            await self._active_service_template(company_id=company_id, service_template_id=service_template_id)
        linked = await self.repository.link_project_service_templates(
            company_id=company_id,
            project_id=project_id,
            service_template_ids=requested,
            actor_user_id=actor_user_id,
        )
        await self.repository.commit()
        _logger.info(
            "construction.project_services.linked project_id=%s requested=%s linked=%s",
            project_id,
            len(requested),
            linked,
        )
        return await self.repository.list_project_service_templates(company_id=company_id, project_id=project_id)

    async def unlink_project_service(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        service_template_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> None:
        await self.get_project(company_id=company_id, project_id=project_id)
        removed = await self.repository.unlink_project_service_templates(
            company_id=company_id,
            project_id=project_id,
            service_template_ids=[service_template_id],
            actor_user_id=actor_user_id,
        )
        if not removed:
            raise ConstructionNotFoundError(resource_name="o serviço na lista da obra")
        await self.repository.commit()
        _logger.info(
            "construction.project_services.unlinked project_id=%s service_template_id=%s",
            project_id,
            service_template_id,
        )

    async def replace_project_services(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        service_template_ids: list[UUID],
        actor_user_id: UUID | None = None,
    ) -> list[ConstructionServiceTemplate]:
        await self.get_project(company_id=company_id, project_id=project_id)
        requested = list(dict.fromkeys(service_template_ids))
        current = await self.repository.project_service_template_ids(company_id=company_id, project_id=project_id)
        to_add = [service_template_id for service_template_id in requested if service_template_id not in current]
        to_remove = list(current - set(requested))
        for service_template_id in to_add:
            await self._active_service_template(company_id=company_id, service_template_id=service_template_id)
        await self.repository.link_project_service_templates(
            company_id=company_id,
            project_id=project_id,
            service_template_ids=to_add,
            actor_user_id=actor_user_id,
        )
        await self.repository.unlink_project_service_templates(
            company_id=company_id,
            project_id=project_id,
            service_template_ids=to_remove,
            actor_user_id=actor_user_id,
        )
        await self.repository.commit()
        _logger.info(
            "construction.project_services.replaced project_id=%s added=%s removed=%s",
            project_id,
            len(to_add),
            len(to_remove),
        )
        return await self.repository.list_project_service_templates(company_id=company_id, project_id=project_id)

    async def import_project_services(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        files: list[tuple[str, bytes]],
        actor_user_id: UUID | None = None,
        actor_person_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        await self.get_project(company_id=company_id, project_id=project_id)
        results = await self.import_service_templates(
            company_id=company_id,
            files=files,
            actor_user_id=actor_user_id,
            actor_person_id=actor_person_id,
        )
        to_link: list[UUID] = []
        for result in results:
            template_id = result.get("service_template_id")
            result["linked"] = False
            if template_id is None:
                continue
            template = await self.repository.get_service_template(
                company_id=company_id,
                service_template_id=template_id,
            )
            if template is None or not template.is_active:
                result["message"] = "O serviço está desativado no catálogo e não foi vinculado à obra."
                continue
            result["linked"] = True
            to_link.append(template_id)
        linked = await self.repository.link_project_service_templates(
            company_id=company_id,
            project_id=project_id,
            service_template_ids=to_link,
            actor_user_id=actor_user_id,
        )
        await self.repository.commit()
        _logger.info(
            "construction.project_services.imported project_id=%s files=%s linked=%s",
            project_id,
            len(files),
            linked,
        )
        return results

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
        await self.repository.lock_service_template(company_id, service_template_id)
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

        if updates.get("product_id") != service_template.product_id:
            await self._require_company_products(
                company_id=company_id,
                actor_user_id=actor_user_id,
                product_ids=[updates.get("product_id")],
            )

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
        await self._require_company_products(
            company_id=company_id,
            actor_user_id=actor_user_id,
            product_ids=[request.product_id],
        )

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
        await self.repository.lock_service_template(company_id, service_template_id)
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
        if request.product_id != service_template.product_id:
            await self._require_company_products(
                company_id=company_id,
                actor_user_id=actor_user_id,
                product_ids=[request.product_id],
            )

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
        await self.repository.flush()
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
        await self.repository.lock_service_template(company_id, service_template_id)
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
        mode="create",
        expected_revisions=None,
    ) -> list[dict[str, Any]]:
        if not files:
            raise ConstructionInvalidValueError(
                message="Nenhuma planilha foi enviada para importação.",
                error_code="CONSTRUCTION_TEMPLATE_NO_FILE",
            )

        if len({name for name, _ in files}) != len(files):
            raise ConstructionInvalidValueError(message="Use nomes de arquivo distintos na mesma importação.")
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
            previous = [(section.name, item.description, item.verification_method) for section in existing_template.sections for item in section.items] if existing_template else []
            incoming = [(section.name, item.description, item.verification_method) for section in parsed.sections for item in section.items]
            if mode != "preview" and existing_template is not None:
                await self.repository.lock_service_template(company_id, existing_template.id)
                existing_template = await self.get_service_template(company_id=company_id, service_template_id=existing_template.id)
            revision = {
                "id": str(existing_template.id) if existing_template else None,
                "name": existing_template.name if existing_template else parsed.name,
                "active": existing_template.is_active if existing_template else None,
                "product_id": str(existing_template.product_id) if existing_template and existing_template.product_id else None,
                "sections": [(section.name, [(item.description, item.verification_method, item.requires_comment, item.requires_photo)
                    for item in section.items]) for section in existing_template.sections] if existing_template else [],
                "file_digest": hashlib.sha256(content).hexdigest(),
            }
            token = hashlib.sha256(json.dumps(revision, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            changes = [f"Remover: {section} / {description} ({method})" for section, description, method in previous if (section, description, method) not in incoming]
            changes += [f"Incluir: {section} / {description} ({method})" for section, description, method in incoming if (section, description, method) not in previous]
            if previous != incoming and not changes:
                changes.append("Alterar a ordem das linhas da ficha.")
            if mode == "preview":
                results.append({"file_name": file_name, "status": "preview",
                    "service_template_id": existing_template.id if existing_template else None,
                    "service_name": parsed.name, "items_count": len(parsed.items), "sections_count": len(parsed.sections),
                    "existing_items_count": len(previous), "revision_token": token, "changes": changes,
                    "message": "Ficha existente: aplicação requer escolha explícita." if existing_template else "Novo serviço."})
                continue
            if mode == "replace":
                expected = (expected_revisions or {}).get(file_name)
                if expected != token:
                    raise ConstructionInvalidValueError(message=f"A ficha {parsed.name} mudou desde a prévia. Gere outra prévia antes de aplicar.")
                if existing_template is not None:
                    flags = {(section.name, item.description): (item.requires_comment, item.requires_photo) for section in existing_template.sections for item in section.items}
                    sections = [ConstructionServiceTemplateSection(company_id=company_id, service_template_id=existing_template.id,
                        sequence_number=section.sequence_number, name=section.name,
                        items=[ConstructionServiceTemplateItem(company_id=company_id, service_template_id=existing_template.id,
                            sequence_number=item.sequence_number, description=item.description, verification_method=item.verification_method,
                            requires_comment=flags.get((section.name, item.description), (False, False))[0],
                            requires_photo=flags.get((section.name, item.description), (False, False))[1]) for item in section.items]) for section in parsed.sections]
                    existing_template.source_file_name = file_name
                    existing_template.updated_by_user_id = actor_user_id
                    await self.repository.replace_service_template_sections(company_id=company_id, service_template_id=existing_template.id, sections=sections)
                    await self.repository.flush()
                    await self._record_import_audit(company_id=company_id, service_template_id=existing_template.id,
                        event="replaced", file_name=file_name, actor_user_id=actor_user_id, actor_person_id=actor_person_id, commit=False)
                    results.append({"file_name": file_name, "status": "updated", "service_template_id": existing_template.id,
                        "service_name": parsed.name, "items_count": len(parsed.items), "sections_count": len(parsed.sections),
                        "message": "Revisão aplicada ao catálogo. Inspeções já copiadas foram preservadas."})
                    continue
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
                    commit=False,
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
            await self.repository.flush()

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
                commit=False,
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

        if mode != "preview":
            await self.repository.commit()
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
        commit=True,
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
        if commit:
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

        await self.repository.flush()

    async def _assert_every_inspection_is_approved(self, *, item: ConstructionMeasurementItem) -> None:
        """Toda linha da FVS precisa estar aprovada (ou dispensada) para fechar.

        O erro acionavel vem primeiro: quem tem linha reprovada precisa saber que
        falta a REINSPECAO, nao que "falta verificar".
        """
        inspections = await self.repository.list_measurement_item_inspections(
            company_id=item.company_id,
            measurement_item_id=item.id,
        )
        if not inspections:
            raise ConstructionInvalidValueError(message="Cadastre as linhas de inspeção do serviço antes de concluir.")
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
        items = await self.repository.list_measurement_items(
            company_id=company_id,
            measurement_id=measurement_id,
        )
        measurement = await self.get_measurement(company_id=company_id, measurement_id=measurement_id)
        if measurement.subcontract_id and sum((item.amount for item in items), Decimal("0")) <= 0:
            raise ConstructionInvalidValueError(message="A medição contratual precisa de itens e valor positivo.")
        missing = [
            measurement_item_label(item.description, getattr(item, "service_template_name", None))
            for item in items
            if not item.inspections
        ]
        if missing:
            raise ConstructionInvalidValueError(
                message=f"Cadastre a FVS dos serviços sem inspeção: {', '.join(missing[:5])}.",
                error_code="CONSTRUCTION_MEASUREMENT_SERVICE_INSPECTIONS_REQUIRED",
            )
        if not items:
            raise ConstructionInvalidValueError(
                message=f"Inclua itens de inspeção na medição antes de {action_label}.",
                error_code="CONSTRUCTION_MEASUREMENT_INSPECTIONS_REQUIRED",
            )

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

        approved_procurements = [
            request for request in procurement_requests
            if request.external_procurement_status in {"APPROVED", "PARTIALLY_ORDERED", "ORDERED"}
        ]
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
            "planned_cost_amount": None,
            "approved_requisition_amount": None,
            "committed_order_amount": None,
            "realized_amount": None,
            "legacy_unknown_amount": None,
            "purchase_phases": [],
            "purchase_totals_unavailable_reason": None,
            "measured_cost_amount": measured_cost,
            "paid_cost_amount": paid_cost,
            "measurements_count": len(measurements),
            "measurements_approved_count": len(approved_measurements),
            "procurement_requests_count": len(procurement_requests),
            "procurement_approved_count": len(approved_procurements),
            "receivables_count": 0,
            "receivable_total_amount": Decimal("0"),
            "received_amount": Decimal("0"),
            "open_amount": Decimal("0"),
            "overdue_amount": Decimal("0"),
            "overdue_count": 0,
            "erp_unavailable_reason": None,
        }

        receivable_ids = [unit.external_receivable_id for unit in units if unit.external_receivable_id]
        try:
            if self.erp_client is None:
                raise RuntimeError("Integração com o ERP indisponível")
            purchases = await self.erp_client.get_purchase_totals(company_id=company_id, project_id=project_id, user_id=user_id)
            for field in ["approved_requisition_amount", "committed_order_amount", "realized_amount", "legacy_unknown_amount"]:
                summary[field] = Decimal(str(purchases[field]))
            summary["committed_order_amount"] = Decimal(str(purchases.get("committed_total_amount", purchases["committed_order_amount"])))
            summary["planned_cost_amount"] = summary["approved_requisition_amount"]
            summary["measured_cost_amount"] = Decimal(str(purchases["measured_amount"]))
            summary["purchase_phases"] = purchases.get("phases", [])
        except Exception:
            summary["purchase_totals_unavailable_reason"] = "Não foi possível consultar os compromissos no ERP agora."
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

    async def build_unit_payment_plan(self, *, company_id: UUID, unit_id: UUID, user_id: UUID | None = None) -> dict[str, Any]:
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
                    user_id=user_id,
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
            # A mensagem antiga dizia "confirme a venda antes de mexer nas
            # parcelas", e em 2026-09-21 ela estava MENTINDO: a venda estava
            # confirmada, as parcelas estavam na tela, e o que faltava era o
            # ponteiro -- que a venda migrada nunca teve, porque o recebivel
            # nasce no ETL e nao no fluxo de venda. Eram 676 unidades.
            #
            # O ponteiro foi preenchido e a 05B passou a grava-lo, entao o caso
            # que sobra aqui e outro: unidade cujas parcelas sao TODAS de
            # aditivo, sem serie de venda (6 no legado). Mandar essa pessoa
            # "confirmar a venda" nao resolveria nada.
            raise ConstructionDomainError(
                message=(
                    "Esta unidade não tem série de parcelas da venda no ERP. "
                    "Se as parcelas dela são de aditivo, a operação precisa ser feita "
                    "pela linha do aditivo."
                ),
                status_code=409,
            )

        return unit, target_receivable_id

    async def list_unit_commissions(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
    ) -> list[ConstructionUnitCommissionModel]:
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        return await self.repository.list_unit_commissions(
            company_id=company_id, unit_id=unit_id, sale_id=unit.current_sale_id
        )

    async def create_unit_commissions(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        request: ConstructionUnitCommissionCreate,
        actor_user_id: UUID | None = None,
    ) -> list[ConstructionUnitCommissionModel]:
        """Lanca o sinal, replicando o "Repetir 1+" do legado.

        Um lancamento vira ``installments`` linhas com vencimento mensal, cada
        uma com sua propria numeracao. O modelo de recibo e copiado da obra
        agora, e nao lido dela na emissao: trocar o modelo da obra depois nao
        pode reescrever o que ja foi lancado.
        """
        await self._refuse_when_nothing_left_to_charge(company_id=company_id, unit_id=unit_id)
        unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
        await self._require_company_people(
            company_id=company_id,
            actor_user_id=actor_user_id,
            people={"O beneficiário do sinal": request.beneficiary_person_id},
        )
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
                sale_id=unit.current_sale_id,
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
        actor_user_id: UUID | None = None,
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

        if "beneficiary_person_id" in updates and updates["beneficiary_person_id"] != commission.beneficiary_person_id:
            await self._require_company_people(
                company_id=company_id,
                actor_user_id=actor_user_id,
                people={"O beneficiário do sinal": updates["beneficiary_person_id"]},
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
            sale_id=unit.current_sale_id,
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
        today = get_business_today(current_business_timezone())
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
                    "status": unit_commission_status(
                        due_date=commission.due_date,
                        payment_date=commission.payment_date,
                        today=today,
                    ),
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
        today = get_business_today(current_business_timezone())
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
        measurement = await self.repository.lock_measurement(company_id, measurement_id)
        if measurement is None:
            raise ConstructionNotFoundError(resource_name="a medição")
        assert_measurement_editable(measurement)

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
        if measurement_purpose(measurement) == "CONTROL":
            measurement.gross_amount = measurement.net_amount = measurement.measured_amount = Decimal("0")
            measurement.retentions_amount = Decimal("0")
            return
        items_amount = await self.repository.get_measurement_items_amount(
            company_id=measurement.company_id,
            measurement_id=measurement.id,
        )
        if items_amount <= Decimal("0"):
            if getattr(measurement, "subcontract_id", None):
                measurement.gross_amount = measurement.net_amount = measurement.measured_amount = Decimal("0")
                return
            measurement.gross_amount = measurement.net_amount = measurement.measured_amount = Decimal("0")
            return

        retentions_amount = measurement.retentions_amount or Decimal("0")
        net_amount = items_amount - retentions_amount
        if getattr(measurement, "subcontract_id", None):
            net_amount = await SubcontractService(self).financial_amounts(measurement, items_amount)
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
        measurement = await self._get_editable_measurement(company_id=company_id, measurement_id=measurement_id)
        assert_measurement_editable(measurement)

        await self._assert_history_can_be_deleted(measurement)
        await self.repository.delete(measurement)
        await self.repository.commit()

    async def assert_integration_delivery(self, request_event):
        aggregate = await self.repository.lock_integration_aggregate(request_event)
        if aggregate is None:
            raise ConstructionNotFoundError(resource_name="o registro ativo para integração")

    async def apply_integration_response(self, *, request_event, response_event):
        if (response_event.company_id != request_event.company_id or
                response_event.aggregate_id != request_event.aggregate_id or
                response_event.causation_id != request_event.event_id):
            raise ConstructionInvalidValueError(message="A confirmação do ERP não pertence ao evento enviado.")

        if request_event.event_type == ConstructionEventType.PROJECT_CREATED:
            project = await self.get_project(company_id=request_event.company_id, project_id=request_event.aggregate_id)
            self._apply_cost_center_snapshot_from_event(project=project, event=response_event)
        elif request_event.event_type == ConstructionEventType.UNIT_CREATED:
            unit = await self._get_unit(company_id=request_event.company_id, unit_id=request_event.aggregate_id)
            self._apply_unit_cost_center_snapshot_from_event(unit=unit, event=response_event)
        elif request_event.event_type == ConstructionEventType.UNIT_SOLD:
            if response_event.event_type != ErpEventType.CONTRACT_RECEIVABLE_CREATED:
                raise ConstructionInvalidValueError(message="O ERP não confirmou o contrato da unidade.")
            unit = await self._get_unit(company_id=request_event.company_id, unit_id=request_event.aggregate_id)
            self._apply_contract_snapshot_from_payload(unit=unit, payload=response_event.payload)
        elif request_event.event_type == ConstructionEventType.UNIT_STATUS_CHANGED:
            if response_event.event_type != ErpEventType.UNIT_RECLASSIFIED:
                raise ConstructionInvalidValueError(message="O ERP não confirmou a reclassificação da unidade.")
        else:
            raise ConstructionInvalidValueError(message="Evento sem consumidor ativo de integração.")

    async def _assert_history_can_be_deleted(self, entity):
        if await self.repository.has_protected_history(entity):
            raise ConstructionResourceInUseError(
                message="O registro possui unidades, SAT, medição em aprovação, aprovada ou vínculo financeiro e não pode ser excluído. Trate as unidades pelo fluxo próprio antes de excluir a obra.",
                error_code="CONSTRUCTION_HISTORY_LOCKED",
            )

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
        if getattr(measurement, "subcontract_id", None):
            payload.update({"subcontract_id": str(measurement.subcontract_id),
                "approval_cycle": measurement.approval_cycle,
                "subcontract_version_id": str(measurement.subcontract_version_id),
                "gross_amount": str(measurement.gross_amount), "retentions_amount": str(measurement.retentions_amount),
                "escrow_amount": str(measurement.escrow_amount),
                "escrow_due_date": measurement.escrow_due_date.isoformat() if measurement.escrow_due_date else None,
                "direct_billing_amount": str(measurement.direct_billing_amount),
                "document_type": measurement.document_type, "document_number": measurement.document_number})
            payload["retention_details"] = measurement.retention_details
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
        sale: ConstructionUnitSale | None = None,
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

        if sale is not None:
            payload["construction_sale_id"] = str(sale.id)
            payload["sale_sequence"] = sale.sequence

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
        project = await self.get_project(company_id=procurement_request.company_id, project_id=procurement_request.project_id)
        request_event.payload["source_reference"] = f"{project.code} - {project.name}"[:150]
        procurement_request.status = ConstructionProcurementStatus.PENDING_APPROVAL
        # O vínculo anterior não confirma esta versão reenviada.
        procurement_request.delivery_status = "sending"
        procurement_request.external_snapshot_at = None
        procurement_request.external_procurement_id = None
        procurement_request.external_procurement_status = None
        dispatch_result = await self._dispatch_integration_event(event=request_event)
        if dispatch_result is not None and dispatch_result.response_event is not None:
            self._apply_procurement_snapshot_from_payload(
                procurement_request=procurement_request,
                payload=dispatch_result.response_event.payload,
            )

    async def apply_cash_received_event(self, *, event):
        if event.event_type != "construction.unit.installment.cash_received.v1" or event.event_version != 1:
            raise ConstructionInvalidValueError(message="Evento de caixa ou versão inválidos.")
        unit_id = self._read_uuid_payload(payload=event.payload, field_name="unit_id")
        if unit_id != event.aggregate_id:
            raise ConstructionInvalidValueError(message="Unidade do evento de caixa divergente.")
        unit = await self.repository.get_unit(company_id=event.company_id, unit_id=unit_id)
        if unit is None:
            raise ConstructionNotFoundError(resource_name="a unidade do recebimento")
        accepted = await self.event_repository.mark_processed(consumer_name="construction_cash_received_v1", event=event)
        await self.repository.commit()
        return {"accepted": True, "duplicate": not accepted, "unit_id": str(unit.id)}

    async def apply_procurement_updated_event(self, *, event: EventEnvelope):
        if event.event_type != ErpEventType.PROCUREMENT_REQUEST_UPDATED:
            raise ConstructionInvalidValueError(message="Tipo de evento de compras inválido.",
                error_code="CONSTRUCTION_UNSUPPORTED_ERP_EVENT")
        source_id = self._read_uuid_payload(payload=event.payload, field_name="source_id")
        if source_id != event.aggregate_id:
            raise ConstructionInvalidValueError(message="A origem do evento não corresponde à requisição.",
                error_code="CONSTRUCTION_PROCUREMENT_EVENT_INVALID")
        request = await self.repository.get_procurement_request(company_id=event.company_id,
            procurement_request_id=source_id, lock=True)
        if request is None:
            raise ConstructionNotFoundError(resource_name="a requisição de compra")
        if not await self.event_repository.mark_processed(consumer_name=ConstructionConsumerName.PROCUREMENT_UPDATED, event=event):
            return request
        revision = event.payload.get("source_revision")
        current_time = request.external_snapshot_at
        if revision == request.submission_revision and (current_time is None or event.occurred_at >= current_time):
            self._apply_procurement_snapshot_from_payload(procurement_request=request, payload=event.payload)
            request.external_snapshot_at = event.occurred_at
            request.delivery_status = "sent"
            request.external_items = list(event.payload.get("items") or [])
            request.external_orders = list(event.payload.get("orders") or [])
            request.rejection_reason = event.payload.get("rejection_reason")
        await self.repository.commit()
        return request

    async def sync_procurement_statuses(self, *, company_id, actor_user_id, items):
        if not items or not hasattr(self.erp_client, "get_procurement_statuses"):
            return
        sent = [item for item in items if item.external_procurement_id or item.status == ConstructionProcurementStatus.PENDING_APPROVAL]
        changed = False
        for start in range(0, len(sent), 200):
            batch = sent[start:start + 200]
            try:
                snapshots = await self.erp_client.get_procurement_statuses(company_id=company_id, user_id=actor_user_id, source_ids=[item.id for item in batch])
            except Exception:
                _logger.warning("Não foi possível atualizar as situações de compras no ERP.")
                continue
            by_id = {str(item.id): item for item in batch}
            for snapshot in snapshots:
                item = by_id.get(snapshot.get("source_id"))
                if item is None:
                    continue
                if snapshot.get("source_revision") != item.submission_revision:
                    continue
                before = (item.status, item.external_procurement_id, item.external_procurement_status, item.external_order_number, tuple(item.external_order_numbers or []), item.rejection_reason)
                self._apply_procurement_snapshot_from_payload(procurement_request=item, payload=snapshot)
                next_items, next_orders = list(snapshot.get("items") or []), list(snapshot.get("orders") or [])
                changed = changed or item.external_items != next_items or item.external_orders != next_orders or item.delivery_status != "sent"
                item.external_items, item.external_orders = next_items, next_orders
                item.delivery_status = "sent"
                if snapshot.get("external_procurement_status") == "REJECTED":
                    item.rejection_reason = snapshot.get("rejection_reason")
                changed = changed or before != (item.status, item.external_procurement_id, item.external_procurement_status, item.external_order_number, tuple(item.external_order_numbers or []), item.rejection_reason)
        if changed:
            await self.repository.commit()

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

            if event.event_type == ConstructionEventType.PROCUREMENT_REQUESTED:
                if self.event_repository is None:
                    raise ConstructionInvalidValueError(
                        message="Outbox indisponivel para registrar o envio de compras.",
                        error_code="CONSTRUCTION_PROCUREMENT_OUTBOX_UNAVAILABLE",
                    )
                return ConstructionIntegrationDispatchResult(event=event, response_event=None, integration_mode="outbox")

            if self.erp_client is None:
                return None

            response_event = await self.erp_client.deliver_event(event=event)
            if self.event_repository is not None:
                await self.event_repository.mark_delivered(event.event_id)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ConstructionDomainError(
                message="Não foi possível conectar ao ERP. Tente novamente.",
                status_code=503,
                error_code="CONSTRUCTION_ERP_UNAVAILABLE",
            ) from exc
        except httpx.TransportError as exc:
            raise ConstructionIntegrationUnconfirmedError() from exc
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
            "discount_amount": ConstructionProjectService._format_event_decimal(
                value=procurement_request.discount_amount
            ),
            "items": [
                {
                    "sequence_number": item.sequence_number,
                    "product_id": str(item.product_id),
                    "product_code": item.product_code,
                    "product_description": item.product_description,
                    "quantity": ConstructionProjectService._format_event_decimal(value=item.quantity),
                    "unit_of_measure": item.unit_of_measure,
                    "unit_price": ConstructionProjectService._format_event_decimal(value=item.unit_price) if item.unit_price is not None else None,
                    "line_total": ConstructionProjectService._format_event_decimal(value=item.line_total) if item.line_total is not None else None,
                    "schedule_phase_id": str(item.schedule_phase_id) if item.schedule_phase_id else None,
                    "construction_unit_id": str(item.construction_unit_id) if item.construction_unit_id else None,
                }
                for item in procurement_request.items
            ],
            "needed_by_date": ConstructionProjectService._format_event_date(value=procurement_request.needed_by_date),
            "supplier_person_id": (
                str(procurement_request.supplier_person_id) if procurement_request.supplier_person_id else None
            ),
            "approval_threshold": CONSTRUCTION_PROCUREMENT_APPROVAL_THRESHOLD,
            "source_revision": procurement_request.submission_revision,
        }
        if actor_user_id is not None:
            payload["user_id"] = str(actor_user_id)

        creator_id = procurement_request.created_by_user_id
        payload["created_by_user_id"] = str(creator_id) if creator_id else None

        return EventEnvelope(
            event_id=event_id,
            event_type=ConstructionEventType.PROCUREMENT_REQUESTED,
            event_version=2,
            company_id=procurement_request.company_id,
            aggregate_id=procurement_request.id,
            aggregate_type=ConstructionAggregateType.PROCUREMENT_REQUEST,
            occurred_at=datetime.now(tz=UTC),
            producer=EventProducer.CONSTRUCTION_API,
            correlation_id=event_id,
            causation_id=None,
            payload=payload,
        )

    async def _prepare_procurement_items(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        actor_user_id: UUID | None,
        item_inputs,
        discount_amount: Decimal,
        stored_items=(),
    ) -> tuple[list[dict[str, Any]], Decimal, Decimal]:
        if not item_inputs:
            raise ConstructionInvalidValueError(
                message="Inclua pelo menos um produto na requisição.",
                error_code="CONSTRUCTION_PROCUREMENT_ITEMS_REQUIRED",
            )
        stored_phase_ids = {item.schedule_phase_id for item in stored_items}
        stored_unit_ids = {item.construction_unit_id for item in stored_items}
        for phase_id in dict.fromkeys(item.schedule_phase_id for item in item_inputs):
            if phase_id is None or phase_id in stored_phase_ids:
                continue
            phase = await self._get_schedule_phase(company_id=company_id, phase_id=phase_id)
            if phase.project_id != project_id:
                _logger.info(f"[construction] procurement_items: phase_refused project_id={project_id} phase_id={phase_id}")
                raise ConstructionInvalidValueError(
                    message="A etapa do cronograma do item não pertence à obra da requisição.",
                    error_code="CONSTRUCTION_SCHEDULE_PROJECT_MISMATCH",
                )
        for unit_id in dict.fromkeys(item.construction_unit_id for item in item_inputs):
            if unit_id is None or unit_id in stored_unit_ids:
                continue
            unit = await self._get_unit(company_id=company_id, unit_id=unit_id)
            if unit.project_id != project_id:
                _logger.info(f"[construction] procurement_items: unit_refused project_id={project_id} unit_id={unit_id}")
                raise ConstructionInvalidValueError(
                    message="A unidade do item não pertence à obra da requisição.",
                    error_code="CONSTRUCTION_UNIT_PROJECT_MISMATCH",
                )
        if discount_amount < Decimal("0"):
            raise ConstructionInvalidValueError(
                message="O desconto não pode ser negativo.",
                error_code="CONSTRUCTION_PROCUREMENT_DISCOUNT_INVALID",
            )
        if self.erp_client is None or not hasattr(self.erp_client, "validate_procurement_products"):
            raise ConstructionInvalidValueError(
                message="Não foi possível validar os produtos no ERP agora.",
                error_code="CONSTRUCTION_PROCUREMENT_PRODUCT_VALIDATION_UNAVAILABLE",
            )
        product_ids = list(dict.fromkeys(item.product_id for item in item_inputs))
        try:
            products = await self.erp_client.validate_procurement_products(
                company_id=company_id,
                user_id=actor_user_id,
                product_ids=product_ids,
            )
        except Exception as exc:
            raise ConstructionInvalidValueError(
                message="Não foi possível validar os produtos no ERP agora. Tente novamente.",
                error_code="CONSTRUCTION_PROCUREMENT_PRODUCT_VALIDATION_UNAVAILABLE",
            ) from exc
        products_by_id = {str(product["id"]): product for product in products}
        prepared: list[dict[str, Any]] = []
        subtotal = Decimal("0.00")
        for item in item_inputs:
            product = products_by_id.get(str(item.product_id))
            if product is None:
                raise ConstructionInvalidValueError(
                    message="Um ou mais produtos não existem, estão inativos ou pertencem a outra empresa.",
                    error_code="CONSTRUCTION_PROCUREMENT_PRODUCT_UNAVAILABLE",
                )
            if item.quantity <= 0 or (item.unit_price is not None and item.unit_price < 0):
                raise ConstructionInvalidValueError(
                    message="Informe quantidade maior que zero e, quando informado, preço unitário igual ou maior que zero.",
                    error_code="CONSTRUCTION_PROCUREMENT_ITEM_VALUE_INVALID",
                )
            if not item.unit_of_measure.strip():
                raise ConstructionInvalidValueError(
                    message="Informe a unidade de medida de cada produto.",
                    error_code="CONSTRUCTION_PROCUREMENT_UNIT_REQUIRED",
                )
            line_total = (item.quantity * item.unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if item.unit_price is not None else None
            if line_total is not None:
                subtotal += line_total
            prepared.append(
                {
                    "product_id": item.product_id,
                    "product_code": str(product["code"]),
                    "product_description": str(product["description"]),
                    "quantity": item.quantity,
                    "unit_of_measure": item.unit_of_measure.strip(),
                    "unit_price": item.unit_price,
                    "line_total": line_total,
                    "schedule_phase_id": item.schedule_phase_id,
                    "construction_unit_id": item.construction_unit_id,
                }
            )
        total = (subtotal - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if discount_amount > subtotal:
            raise ConstructionInvalidValueError(
                message="O desconto não pode ser maior que o subtotal dos produtos.",
                error_code="CONSTRUCTION_PROCUREMENT_DISCOUNT_INVALID",
            )
        if total < 0:
            raise ConstructionInvalidValueError(
                message="O desconto não pode gerar um total estimado negativo.",
                error_code="CONSTRUCTION_PROCUREMENT_TOTAL_INVALID",
            )
        return prepared, subtotal, total

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
            statuses = {
                "PENDING_APPROVAL": ConstructionProcurementStatus.PENDING_APPROVAL,
                "APPROVED": ConstructionProcurementStatus.APPROVED,
                "REJECTED": ConstructionProcurementStatus.REJECTED,
                "PARTIALLY_ORDERED": ConstructionProcurementStatus.SENT_TO_ERP,
                "ORDERED": ConstructionProcurementStatus.SENT_TO_ERP,
                "CLOSED": ConstructionProcurementStatus.CLOSED,
            }
            if external_procurement_status in statuses:
                procurement_request.status = statuses[external_procurement_status]
            if payload.get("order_numbers") is not None:
                procurement_request.external_order_numbers = list(payload["order_numbers"])
                procurement_request.external_order_number = procurement_request.external_order_numbers[0] if procurement_request.external_order_numbers else None
            elif payload.get("order_number"):
                procurement_request.external_order_numbers = [payload["order_number"]]
                procurement_request.external_order_number = payload["order_number"]

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
