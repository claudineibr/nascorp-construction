from datetime import date
from decimal import Decimal
from math import ceil
from uuid import UUID

from fastapi import Header, APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import ConstructionContext
from app.core.security import get_construction_context, require_permission, require_service_key
from app.domain.exceptions import ConstructionDomainError
from app.domain.permissions import ConstructionFeature, PermissionAction
from app.domain.services import ConstructionProjectService
from app.domain.services.construction_contract_context_service import ConstructionContractContextService
from app.schemas.construction.unit_contract import ConstructionUnitContractContextResponse
from app.domain.services.construction_service_template_parser import build_service_template_example
from app.infrastructure.clients import ErpConstructionClient
from app.infrastructure.database.session import get_session
from app.infrastructure.events import create_construction_integration_dispatcher
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.schemas.construction.project import (
    ConstructionMeasurementPayableLink,
    ConstructionProjectBuyerUnit,
    ConstructionProjectServiceLinkRequest,
    ConstructionProjectServiceReplaceRequest,
    ConstructionSharedPayableMeasurementsRequest,
    ConstructionSharedPayableResult,
    ConstructionZeroValueMeasurementListResponse,
    ConstructionZeroValueSupplier,
)
from app.schemas.construction import (
    ConstructionBlockCreate,
    ConstructionBlockListResponse,
    ConstructionBlockResponse,
    ConstructionBlockUpdate,
    ConstructionDocumentationTypeCreate,
    ConstructionDocumentationTypeListResponse,
    ConstructionDocumentationTypeResponse,
    ConstructionDocumentationTypeUpdate,
    ConstructionPersonSummaryListResponse,
    ConstructionUnitInstallmentCreateRequest,
    ConstructionUnitInstallmentPaymentRequest,
    ConstructionUnitInstallmentReversalRequest,
    ConstructionUnitInstallmentUpdateRequest,
    ConstructionProjectCreate,
    ConstructionProjectListResponse,
    ConstructionProjectResponse,
    ConstructionProjectUpdate,
    ConstructionProcurementRequestCreate,
    ConstructionProcurementRequestListResponse,
    ConstructionProcurementRequestResponse,
    ConstructionProcurementRequestUpdate,
    ConstructionMeasurementCreate,
    ConstructionInspectionRoundListResponse,
    ConstructionInspectionRoundResponse,
    ConstructionMeasurementInspectionVerifyRequest,
    ConstructionMeasurementItemCreate,
    ConstructionMeasurementItemInspectionCreate,
    ConstructionMeasurementItemInspectionResponse,
    ConstructionMeasurementItemInspectionUpdate,
    ConstructionMeasurementItemListResponse,
    ConstructionMeasurementItemOccurrenceCreate,
    ConstructionMeasurementItemOccurrenceResponse,
    ConstructionMeasurementItemOccurrenceUpdate,
    ConstructionMeasurementItemResponse,
    ConstructionMeasurementItemUpdate,
    ConstructionMeasurementListResponse,
    ConstructionMeasurementReject,
    ConstructionMeasurementResponse,
    ConstructionMeasurementUpdate,
    ConstructionSchedulePhaseCreate,
    ConstructionSchedulePhaseListResponse,
    ConstructionServiceTemplateCreate,
    ConstructionServiceTemplateImportResponse,
    ConstructionServiceTemplateImportResult,
    ConstructionServiceTemplateAuditListResponse,
    ConstructionServiceTemplateAuditResponse,
    ConstructionServiceTemplateListResponse,
    ConstructionServiceTemplateReplace,
    ConstructionServiceTemplateResponse,
    ConstructionServiceTemplateUpdate,
    ConstructionSchedulePhaseResponse,
    ConstructionSchedulePhaseUpdate,
    ConstructionUnitAdjustmentCreate,
    ConstructionUnitCommissionCreate,
    ConstructionUnitCommissionListResponse,
    ConstructionUnitCommissionResponse,
    ConstructionUnitCommissionSettleRequest,
    ConstructionUnitCommissionUpdate,
    ConstructionUnitCreate,
    ConstructionUnitListResponse,
    ConstructionUnitReserveRequest,
    ConstructionUnitResponse,
    ConstructionUnitSaleConfirmRequest,
    ConstructionUnitUpdate,
)


router = APIRouter(prefix="/construction", tags=["construction"])

@router.get("/internal/units/{unit_id}/contract-context", response_model=ConstructionUnitContractContextResponse, dependencies=[Depends(require_service_key)])
async def unit_contract_context(unit_id: UUID, company_id: UUID = Header(alias="X-Company-ID"), session=Depends(get_session)):
    return await ConstructionContractContextService(session).get_context(company_id, unit_id)


MAX_SERVICE_TEMPLATE_FILES = 30
MAX_SERVICE_TEMPLATE_FILE_BYTES = 5 * 1024 * 1024


async def get_erp_construction_client() -> ErpConstructionClient:
    return ErpConstructionClient()


async def get_project_service(
    session: AsyncSession = Depends(get_session),
    erp_client: ErpConstructionClient = Depends(get_erp_construction_client),
    ctx: ConstructionContext = Depends(get_construction_context),
) -> ConstructionProjectService:
    """A costura do escopo por registro: uma linha, e vale para as 78 rotas.

    `get_construction_context` ja e dependencia de toda rota por dentro de
    `require_permission`, e o FastAPI resolve dependencia uma vez por
    requisicao -- pedi-la aqui NAO gera uma segunda consulta ao ERP.
    """
    event_repository = EventRepository(session=session)
    session.info['actor_user_id'] = ctx.user_id
    return ConstructionProjectService(
        repository=ConstructionRepository(session=session, scope=ctx.project_scope),
        event_repository=event_repository,
        erp_client=erp_client,
        integration_dispatcher=create_construction_integration_dispatcher(
            event_repository=event_repository,
            event_transport=erp_client,
        ),
    )


@router.post(
    "/projects",
    response_model=ConstructionProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    request_data: ConstructionProjectCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProjectResponse:
    try:
        project = await service.create_project(
            company_id=ctx.company_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionProjectResponse.model_validate(project)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects", response_model=ConstructionProjectListResponse)
async def list_projects(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_date_from: date | None = Query(default=None),
    start_date_to: date | None = Query(default=None),
    buyer_person_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    # O teto de 100 e o do banco, nao o da tela: a lista de obras pagina no
    # servidor e o seletor de itens por pagina para em 100 pelo mesmo motivo.
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProjectListResponse:
    items, total, buyer_units = await service.list_projects(
        company_id=ctx.company_id,
        search=search,
        status=status,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        buyer_person_id=buyer_person_id,
        page=page,
        page_size=page_size,
    )
    return ConstructionProjectListResponse(
        items=[
            ConstructionProjectResponse.model_validate(item).model_copy(
                update={
                    "buyer_units": [
                        ConstructionProjectBuyerUnit.model_validate(unit) for unit in buyer_units.get(item.id, [])
                    ]
                }
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/person-summaries", response_model=ConstructionPersonSummaryListResponse)
async def list_person_summaries(
    search: str | None = Query(default=None),
    # Uma pessoa pelo id. E como o formulario mostra o comprador e o corretor
    # que a unidade ja tem: eles quase nunca cabem nas 50 primeiras de um
    # cadastro de 3.117 pessoas.
    person_id: UUID | None = Query(default=None),
    # O papel COMERCIAL da pessoa (`broker`, `supplier`...). O campo Corretor
    # listava as 3.116 pessoas do cadastro; com o recorte, lista as 10 que sao
    # corretoras de fato.
    business_role: str | None = Query(default=None),
    construction_unit_buyer: bool = Query(default=False),
    construction_project_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionPersonSummaryListResponse:
    try:
        payload = await service.list_person_summaries(
            company_id=ctx.company_id,
            actor_user_id=ctx.user_id,
            search=search,
            page=page,
            page_size=page_size,
            person_id=person_id,
            business_role=business_role,
            construction_unit_buyer=construction_unit_buyer,
            construction_project_id=construction_project_id,
        )
        return ConstructionPersonSummaryListResponse.model_validate(payload)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}", response_model=ConstructionProjectResponse)
async def get_project(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProjectResponse:
    try:
        project = await service.get_project(company_id=ctx.company_id, project_id=project_id)
        return ConstructionProjectResponse.model_validate(project)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/projects/{project_id}", response_model=ConstructionProjectResponse)
async def update_project(
    project_id: UUID,
    request_data: ConstructionProjectUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProjectResponse:
    try:
        project = await service.update_project(
            company_id=ctx.company_id, project_id=project_id, request=request_data, actor_user_id=ctx.user_id
        )
        return ConstructionProjectResponse.model_validate(project)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_project(company_id=ctx.company_id, project_id=project_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/blocks",
    response_model=ConstructionBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_block(
    project_id: UUID,
    request_data: ConstructionBlockCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionBlockResponse:
    try:
        block = await service.create_block(company_id=ctx.company_id, project_id=project_id, request=request_data)
        return ConstructionBlockResponse.model_validate(block)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/blocks", response_model=ConstructionBlockListResponse)
async def list_blocks(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionBlockListResponse:
    try:
        items = await service.list_blocks(company_id=ctx.company_id, project_id=project_id)
        return ConstructionBlockListResponse(
            items=[ConstructionBlockResponse.model_validate(item) for item in items],
            total=len(items),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/blocks/{block_id}", response_model=ConstructionBlockResponse)
async def get_block(
    block_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionBlockResponse:
    try:
        block = await service.get_block(company_id=ctx.company_id, block_id=block_id)
        return ConstructionBlockResponse.model_validate(block)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/blocks/{block_id}", response_model=ConstructionBlockResponse)
async def update_block(
    block_id: UUID,
    request_data: ConstructionBlockUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionBlockResponse:
    try:
        block = await service.update_block(company_id=ctx.company_id, block_id=block_id, request=request_data)
        return ConstructionBlockResponse.model_validate(block)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    block_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_block(company_id=ctx.company_id, block_id=block_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/units",
    response_model=ConstructionUnitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_unit(
    project_id: UUID,
    request_data: ConstructionUnitCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitResponse:
    try:
        unit = await service.create_unit(
            company_id=ctx.company_id,
            project_id=project_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionUnitResponse.model_validate(unit)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/units", response_model=ConstructionUnitListResponse)
async def list_units(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitListResponse:
    try:
        items = await service.list_units(company_id=ctx.company_id, project_id=project_id)
        return ConstructionUnitListResponse(
            items=[ConstructionUnitResponse.model_validate(item) for item in items],
            total=len(items),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/units/{unit_id}", response_model=ConstructionUnitResponse)
async def get_unit(
    unit_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitResponse:
    try:
        unit = await service.get_unit(company_id=ctx.company_id, unit_id=unit_id)
        return ConstructionUnitResponse.model_validate(unit)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/units/{unit_id}", response_model=ConstructionUnitResponse)
async def update_unit(
    unit_id: UUID,
    request_data: ConstructionUnitUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitResponse:
    try:
        unit = await service.update_unit(
            company_id=ctx.company_id,
            unit_id=unit_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionUnitResponse.model_validate(unit)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/reserve", response_model=ConstructionUnitResponse)
async def reserve_unit(
    unit_id: UUID,
    request_data: ConstructionUnitReserveRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitResponse:
    try:
        unit = await service.reserve_unit(
            company_id=ctx.company_id,
            unit_id=unit_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionUnitResponse.model_validate(unit)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/release", response_model=ConstructionUnitResponse)
async def release_unit_reservation(
    unit_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitResponse:
    try:
        unit = await service.release_unit_reservation(company_id=ctx.company_id, unit_id=unit_id)
        return ConstructionUnitResponse.model_validate(unit)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/confirm-sale", response_model=ConstructionUnitResponse)
async def confirm_unit_sale(
    unit_id: UUID,
    request_data: ConstructionUnitSaleConfirmRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitResponse:
    try:
        unit = await service.confirm_unit_sale(
            company_id=ctx.company_id,
            unit_id=unit_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionUnitResponse.model_validate(unit)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(
    unit_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_unit(company_id=ctx.company_id, unit_id=unit_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


async def _build_measurement_response(
    *,
    service: ConstructionProjectService,
    ctx: ConstructionContext,
    measurement,
) -> ConstructionMeasurementResponse:
    response = ConstructionMeasurementResponse.model_validate(measurement)
    summary = await service.build_measurement_items_summary(
        company_id=ctx.company_id,
        measurement_id=measurement.id,
    )
    return response.model_copy(update=summary)


@router.post(
    "/projects/{project_id}/measurements",
    response_model=ConstructionMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement(
    project_id: UUID,
    request_data: ConstructionMeasurementCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.create_measurement(
            company_id=ctx.company_id,
            project_id=project_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/measurements", response_model=ConstructionMeasurementListResponse)
async def list_measurements(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementListResponse:
    try:
        items = await service.list_measurements(company_id=ctx.company_id, project_id=project_id)
        return ConstructionMeasurementListResponse(
            items=[ConstructionMeasurementResponse.model_validate(item) for item in items],
            total=len(items),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/measurements/{measurement_id}", response_model=ConstructionMeasurementResponse)
async def get_measurement(
    measurement_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.get_measurement(company_id=ctx.company_id, measurement_id=measurement_id)
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/measurements/{measurement_id}", response_model=ConstructionMeasurementResponse)
async def update_measurement(
    measurement_id: UUID,
    request_data: ConstructionMeasurementUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.update_measurement(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/measurements/{measurement_id}/approve", response_model=ConstructionMeasurementResponse)
async def approve_measurement(
    measurement_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.approve_measurement(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            actor_user_id=ctx.user_id,
            actor_can_self_approve=ctx.can(
                feature=ConstructionFeature.MEASUREMENT_SELF_APPROVAL,
                action=PermissionAction.UPDATE,
            ),
        )
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/measurements/{measurement_id}/payable-candidates")
async def list_measurement_payable_candidates(
    measurement_id: UUID,
    search: str | None = Query(default=None, max_length=150),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        items = await service.list_measurement_payable_candidates(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            user_id=ctx.user_id,
            search=search,
        )
        return {"items": items, "total": len(items)}
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/measurements/{measurement_id}/link-payable", response_model=ConstructionMeasurementResponse)
async def link_measurement_payable(
    measurement_id: UUID,
    request_data: ConstructionMeasurementPayableLink,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.link_measurement_payable(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            payable_document_id=request_data.payable_document_id,
            user_id=ctx.user_id,
        )
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


def _zero_value_filters(
    supplier_person_id: UUID | None = Query(default=None),
    payable_document_id: UUID | None = Query(default=None),
    block_id: UUID | None = Query(default=None),
    unit_search: str | None = Query(default=None, max_length=60),
    due_from: date | None = Query(default=None),
    due_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=60),
) -> dict:
    return {
        "supplier_person_id": supplier_person_id,
        "payable_document_id": payable_document_id,
        "block_id": block_id,
        "unit_search": unit_search,
        "due_from": due_from,
        "due_to": due_to,
        "search": search,
    }


@router.get("/projects/{project_id}/zero-value-suppliers", response_model=list[ConstructionZeroValueSupplier])
async def list_zero_value_suppliers(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> list[ConstructionZeroValueSupplier]:
    try:
        rows = await service.list_zero_value_suppliers(company_id=ctx.company_id, project_id=project_id)
        return [ConstructionZeroValueSupplier(**row) for row in rows]
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get(
    "/projects/{project_id}/zero-value-measurements",
    response_model=ConstructionZeroValueMeasurementListResponse,
)
async def list_zero_value_measurements(
    project_id: UUID,
    filters: dict = Depends(_zero_value_filters),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionZeroValueMeasurementListResponse:
    try:
        rows, total = await service.list_zero_value_measurements(
            company_id=ctx.company_id, project_id=project_id, page=page, page_size=page_size, **filters
        )
        return ConstructionZeroValueMeasurementListResponse(
            items=rows,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/zero-value-measurements/ids", response_model=list[UUID])
async def list_zero_value_measurement_ids(
    project_id: UUID,
    filters: dict = Depends(_zero_value_filters),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> list[UUID]:
    try:
        return await service.zero_value_measurement_ids(company_id=ctx.company_id, project_id=project_id, **filters)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/shared-payables")
async def list_shared_payables(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        items = await service.list_shared_payables(company_id=ctx.company_id, project_id=project_id, user_id=ctx.user_id)
        return {"items": items, "total": len(items)}
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/shared-payable-candidates")
async def list_shared_payable_candidates(
    project_id: UUID,
    supplier_person_id: UUID = Query(...),
    search: str | None = Query(default=None, max_length=150),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        items = await service.list_shared_payable_candidates(
            company_id=ctx.company_id,
            project_id=project_id,
            supplier_person_id=supplier_person_id,
            user_id=ctx.user_id,
            search=search,
        )
        return {"items": items, "total": len(items)}
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/shared-payables/{payable_document_id}/measurements",
    response_model=ConstructionSharedPayableResult,
)
async def link_shared_payable(
    project_id: UUID,
    payable_document_id: UUID,
    request_data: ConstructionSharedPayableMeasurementsRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionSharedPayableResult:
    try:
        affected = await service.link_shared_payable(
            company_id=ctx.company_id,
            project_id=project_id,
            payable_document_id=payable_document_id,
            measurement_ids=request_data.measurement_ids,
            user_id=ctx.user_id,
        )
        return ConstructionSharedPayableResult(payable_document_id=payable_document_id, affected=affected)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/shared-payables/{payable_document_id}/measurements/remove",
    response_model=ConstructionSharedPayableResult,
)
async def unlink_shared_payable(
    project_id: UUID,
    payable_document_id: UUID,
    request_data: ConstructionSharedPayableMeasurementsRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionSharedPayableResult:
    try:
        affected = await service.unlink_shared_payable(
            company_id=ctx.company_id,
            project_id=project_id,
            payable_document_id=payable_document_id,
            measurement_ids=request_data.measurement_ids,
        )
        return ConstructionSharedPayableResult(payable_document_id=payable_document_id, affected=affected)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/measurements/{measurement_id}/reject", response_model=ConstructionMeasurementResponse)
async def reject_measurement(
    measurement_id: UUID,
    request_data: ConstructionMeasurementReject,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.reject_measurement(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            reason=request_data.reason,
            actor_user_id=ctx.user_id,
        )
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/measurements/{measurement_id}/submit", response_model=ConstructionMeasurementResponse)
async def submit_measurement(
    measurement_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    try:
        measurement = await service.submit_measurement(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            actor_user_id=ctx.user_id,
        )
        return await _build_measurement_response(service=service, ctx=ctx, measurement=measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/summary")
async def get_project_summary(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        return await service.build_project_summary(
            company_id=ctx.company_id,
            project_id=project_id,
            user_id=ctx.user_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/units/{unit_id}/payment-plan")
async def get_unit_payment_plan(
    unit_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        return await service.build_unit_payment_plan(company_id=ctx.company_id, unit_id=unit_id, user_id=ctx.user_id)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/units/{unit_id}/installments/{installment_number}")
async def update_unit_installment(
    unit_id: UUID,
    installment_number: int,
    payload: ConstructionUnitInstallmentUpdateRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        changes = payload.model_dump(exclude_unset=True, exclude_none=True, mode="json")
        changes.pop("receivable_id", None)
        return await service.update_unit_installment(
            company_id=ctx.company_id,
            unit_id=unit_id,
            installment_number=installment_number,
            changes=changes,
            receivable_id=payload.receivable_id,
            user_id=ctx.user_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/installments")
async def create_unit_installments(
    unit_id: UUID,
    payload: ConstructionUnitInstallmentCreateRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> list[dict]:
    try:
        return await service.create_unit_installments(
            company_id=ctx.company_id,
            unit_id=unit_id,
            request=payload,
            user_id=ctx.user_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/installments/{installment_number}/pay")
async def pay_unit_installment(
    unit_id: UUID,
    installment_number: int,
    payload: ConstructionUnitInstallmentPaymentRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        return await service.pay_unit_installment(
            company_id=ctx.company_id,
            unit_id=unit_id,
            installment_number=installment_number,
            request=payload,
            receivable_id=payload.receivable_id,
            user_id=ctx.user_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/installments/{installment_number}/reverse")
async def reverse_unit_installment(
    unit_id: UUID,
    installment_number: int,
    payload: ConstructionUnitInstallmentReversalRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        return await service.reverse_unit_installment(
            company_id=ctx.company_id,
            unit_id=unit_id,
            installment_number=installment_number,
            receivable_id=payload.receivable_id,
            user_id=ctx.user_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/units/{unit_id}/installments/{installment_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit_installment(
    unit_id: UUID,
    installment_number: int,
    receivable_id: UUID | None = Query(default=None),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_unit_installment(
            company_id=ctx.company_id,
            unit_id=unit_id,
            installment_number=installment_number,
            receivable_id=receivable_id,
            user_id=ctx.user_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/units/{unit_id}/adjustments/{receivable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit_adjustment(
    unit_id: UUID,
    receivable_id: UUID,
    reason: str = Query(..., min_length=1, max_length=255),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_unit_adjustment(
            company_id=ctx.company_id,
            unit_id=unit_id,
            receivable_id=receivable_id,
            reason=reason,
            user_id=ctx.user_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/units/{unit_id}/commissions", response_model=ConstructionUnitCommissionListResponse)
async def list_unit_commissions(
    unit_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitCommissionListResponse:
    try:
        commissions = await service.list_unit_commissions(company_id=ctx.company_id, unit_id=unit_id)
        return ConstructionUnitCommissionListResponse(
            items=[service.to_commission_response(commission) for commission in commissions],
            total=len(commissions),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/commissions", response_model=ConstructionUnitCommissionListResponse)
async def create_unit_commissions(
    unit_id: UUID,
    request_data: ConstructionUnitCommissionCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitCommissionListResponse:
    try:
        commissions = await service.create_unit_commissions(
            company_id=ctx.company_id,
            unit_id=unit_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionUnitCommissionListResponse(
            items=[service.to_commission_response(commission) for commission in commissions],
            total=len(commissions),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/commissions/{commission_id}", response_model=ConstructionUnitCommissionResponse)
async def update_unit_commission(
    commission_id: UUID,
    request_data: ConstructionUnitCommissionUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitCommissionResponse:
    try:
        commission = await service.update_unit_commission(
            company_id=ctx.company_id,
            commission_id=commission_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return service.to_commission_response(commission)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/commissions/{commission_id}/settle", response_model=ConstructionUnitCommissionResponse)
async def settle_unit_commission(
    commission_id: UUID,
    request_data: ConstructionUnitCommissionSettleRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionUnitCommissionResponse:
    try:
        commission = await service.settle_unit_commission(
            company_id=ctx.company_id,
            commission_id=commission_id,
            payment_date=request_data.payment_date,
        )
        return service.to_commission_response(commission)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/commissions/{commission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit_commission(
    commission_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_unit_commission(company_id=ctx.company_id, commission_id=commission_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/units/{unit_id}/adjustments")
async def create_unit_adjustment(
    unit_id: UUID,
    request_data: ConstructionUnitAdjustmentCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> dict:
    try:
        return await service.create_unit_adjustment(
            company_id=ctx.company_id,
            unit_id=unit_id,
            request=request_data,
            user_id=ctx.user_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/documentation-types", response_model=ConstructionDocumentationTypeListResponse)
async def list_documentation_types(
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
    search: str | None = Query(default=None),
    only_active: bool = Query(default=True),
) -> ConstructionDocumentationTypeListResponse:
    try:
        documentation_types = await service.list_documentation_types(
            company_id=ctx.company_id,
            only_active=only_active,
            search=search,
        )
        return ConstructionDocumentationTypeListResponse(
            items=[
                ConstructionDocumentationTypeResponse.model_validate(documentation_type)
                for documentation_type in documentation_types
            ],
            total=len(documentation_types),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/documentation-types", response_model=ConstructionDocumentationTypeResponse)
async def create_documentation_type(
    request_data: ConstructionDocumentationTypeCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionDocumentationTypeResponse:
    try:
        documentation_type = await service.create_documentation_type(
            company_id=ctx.company_id,
            request=request_data,
        )
        return ConstructionDocumentationTypeResponse.model_validate(documentation_type)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/documentation-types/{documentation_type_id}", response_model=ConstructionDocumentationTypeResponse)
async def update_documentation_type(
    documentation_type_id: UUID,
    request_data: ConstructionDocumentationTypeUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionDocumentationTypeResponse:
    try:
        documentation_type = await service.update_documentation_type(
            company_id=ctx.company_id,
            documentation_type_id=documentation_type_id,
            request=request_data,
        )
        return ConstructionDocumentationTypeResponse.model_validate(documentation_type)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/service-templates", response_model=ConstructionServiceTemplateListResponse)
async def list_service_templates(
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
    search: str | None = Query(default=None),
    only_active: bool = Query(default=True),
    only_deleted: bool = Query(
        default=False,
        description="Lista os servicos excluidos, para consultar o historico de quem os removeu.",
    ),
    project_id: UUID | None = Query(
        default=None,
        description="Servicos que a medicao da obra pode usar: a lista da obra ou, sem lista, o catalogo inteiro.",
    ),
) -> ConstructionServiceTemplateListResponse:
    try:
        if project_id is not None:
            templates, restricted = await service.list_service_templates_for_project(
                company_id=ctx.company_id,
                project_id=project_id,
                search=search,
            )
            return ConstructionServiceTemplateListResponse(
                items=[ConstructionServiceTemplateResponse.from_model(template) for template in templates],
                total=len(templates),
                restricted_to_project=restricted,
            )
        templates = await service.list_service_templates(
            company_id=ctx.company_id,
            only_active=only_active,
            search=search,
            only_deleted=only_deleted,
        )
        return ConstructionServiceTemplateListResponse(
            items=[ConstructionServiceTemplateResponse.from_model(template) for template in templates],
            total=len(templates),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/service-templates",
    response_model=ConstructionServiceTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_template(
    request_data: ConstructionServiceTemplateCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateResponse:
    try:
        template = await service.create_service_template(
            company_id=ctx.company_id,
            request=request_data,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
        )
        return ConstructionServiceTemplateResponse.from_model(template)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/service-templates/example")
async def download_service_template_example(
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
) -> Response:
    """Serves the blank FVS spreadsheet used as a starting point for imports.

    Declared before GET /service-templates/{id} on purpose: FastAPI matches in
    declaration order, and the other way around "example" would be parsed as a
    UUID and rejected with 422.
    """
    return Response(
        content=build_service_template_example(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="modelo-fvs.xlsx"'},
    )


@router.get("/service-templates/{service_template_id}", response_model=ConstructionServiceTemplateResponse)
async def get_service_template(
    service_template_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateResponse:
    try:
        template = await service.get_service_template(
            company_id=ctx.company_id,
            service_template_id=service_template_id,
        )
        return ConstructionServiceTemplateResponse.from_model(template)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.put("/service-templates/{service_template_id}", response_model=ConstructionServiceTemplateResponse)
async def replace_service_template(
    service_template_id: UUID,
    request_data: ConstructionServiceTemplateReplace,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateResponse:
    try:
        template = await service.replace_service_template(
            company_id=ctx.company_id,
            service_template_id=service_template_id,
            request=request_data,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
        )
        return ConstructionServiceTemplateResponse.from_model(template)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/service-templates/{service_template_id}", response_model=ConstructionServiceTemplateResponse)
async def update_service_template(
    service_template_id: UUID,
    request_data: ConstructionServiceTemplateUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateResponse:
    try:
        template = await service.update_service_template(
            company_id=ctx.company_id,
            service_template_id=service_template_id,
            request=request_data,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
        )
        return ConstructionServiceTemplateResponse.from_model(template)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/service-templates/{service_template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_template(
    service_template_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> None:
    try:
        await service.delete_service_template(
            company_id=ctx.company_id,
            service_template_id=service_template_id,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get(
    "/service-templates/{service_template_id}/audits",
    response_model=ConstructionServiceTemplateAuditListResponse,
)
async def list_service_template_audits(
    service_template_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateAuditListResponse:
    """Historico de quem gravou, alterou, desativou ou excluiu o servico."""
    try:
        audits = await service.list_service_template_audits(
            company_id=ctx.company_id,
            service_template_id=service_template_id,
        )
        return ConstructionServiceTemplateAuditListResponse(
            items=[ConstructionServiceTemplateAuditResponse.model_validate(audit) for audit in audits],
            total=len(audits),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/service-templates/import", response_model=ConstructionServiceTemplateImportResponse)
async def import_service_templates(
    files: list[UploadFile] = File(...),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateImportResponse:
    uploaded_files = await _read_service_template_files(files)
    try:
        results = await service.import_service_templates(
            company_id=ctx.company_id,
            files=uploaded_files,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc

    return _service_template_import_response(results)


async def _read_service_template_files(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    if len(files) > MAX_SERVICE_TEMPLATE_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Envie no máximo {MAX_SERVICE_TEMPLATE_FILES} planilhas por importação.",
        )

    uploaded_files: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        if len(content) > MAX_SERVICE_TEMPLATE_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"A planilha {upload.filename} passa do limite de 5 MB.",
            )

        uploaded_files.append((upload.filename or "planilha.xlsx", content))
    return uploaded_files


def _service_template_import_response(results: list[dict]) -> ConstructionServiceTemplateImportResponse:
    parsed_results = [ConstructionServiceTemplateImportResult(**result) for result in results]
    return ConstructionServiceTemplateImportResponse(
        results=parsed_results,
        created=sum(1 for result in parsed_results if result.status == "created"),
        updated=sum(1 for result in parsed_results if result.status == "updated"),
        skipped=sum(1 for result in parsed_results if result.status == "skipped"),
        failed=sum(1 for result in parsed_results if result.status == "failed"),
    )


@router.get(
    "/measurements/{measurement_id}/items",
    response_model=ConstructionMeasurementItemListResponse,
)
async def list_measurement_items(
    measurement_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemListResponse:
    try:
        items = await service.list_measurement_items(company_id=ctx.company_id, measurement_id=measurement_id)
        return ConstructionMeasurementItemListResponse(
            items=[ConstructionMeasurementItemResponse.model_validate(item) for item in items],
            total=len(items),
            total_amount=sum((item.amount for item in items), Decimal("0")),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/measurements/{measurement_id}/items",
    response_model=ConstructionMeasurementItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement_item(
    measurement_id: UUID,
    request_data: ConstructionMeasurementItemCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemResponse:
    try:
        item = await service.create_measurement_item(
            company_id=ctx.company_id,
            measurement_id=measurement_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionMeasurementItemResponse.model_validate(item)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/measurement-items/{item_id}", response_model=ConstructionMeasurementItemResponse)
async def get_measurement_item(
    item_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemResponse:
    try:
        item = await service.get_measurement_item(company_id=ctx.company_id, item_id=item_id)
        return ConstructionMeasurementItemResponse.model_validate(item)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/measurement-items/{item_id}", response_model=ConstructionMeasurementItemResponse)
async def update_measurement_item(
    item_id: UUID,
    request_data: ConstructionMeasurementItemUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemResponse:
    try:
        item = await service.update_measurement_item(
            company_id=ctx.company_id,
            item_id=item_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionMeasurementItemResponse.model_validate(item)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/measurement-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement_item(
    item_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_measurement_item(company_id=ctx.company_id, item_id=item_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/measurement-items/{item_id}/inspections",
    response_model=ConstructionMeasurementItemInspectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement_item_inspection(
    item_id: UUID,
    request_data: ConstructionMeasurementItemInspectionCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemInspectionResponse:
    try:
        inspection = await service.create_measurement_item_inspection(
            company_id=ctx.company_id,
            item_id=item_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionMeasurementItemInspectionResponse.model_validate(inspection)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch(
    "/measurement-inspections/{inspection_id}",
    response_model=ConstructionMeasurementItemInspectionResponse,
)
async def update_measurement_item_inspection(
    inspection_id: UUID,
    request_data: ConstructionMeasurementItemInspectionUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemInspectionResponse:
    try:
        inspection = await service.update_measurement_item_inspection(
            company_id=ctx.company_id,
            inspection_id=inspection_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionMeasurementItemInspectionResponse.model_validate(inspection)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/measurement-inspections/{inspection_id}/verify",
    response_model=ConstructionMeasurementItemInspectionResponse,
)
async def verify_measurement_item_inspection(
    inspection_id: UUID,
    request_data: ConstructionMeasurementInspectionVerifyRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.INSPECTION_VERDICT, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemInspectionResponse:
    try:
        inspection = await service.verify_measurement_item_inspection(
            company_id=ctx.company_id,
            inspection_id=inspection_id,
            request=request_data,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
            actor_can_waive=ctx.can(
                feature=ConstructionFeature.INSPECTION_VERDICT,
                action=PermissionAction.DELETE,
            ),
        )
        return ConstructionMeasurementItemInspectionResponse.model_validate(inspection)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get(
    "/measurement-inspections/{inspection_id}/rounds",
    response_model=ConstructionInspectionRoundListResponse,
)
async def list_inspection_rounds(
    inspection_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionInspectionRoundListResponse:
    """Historico de verificacoes e reinspecoes de uma linha da FVS."""
    try:
        rounds = await service.list_inspection_rounds(
            company_id=ctx.company_id,
            inspection_id=inspection_id,
        )
        return ConstructionInspectionRoundListResponse(
            items=[ConstructionInspectionRoundResponse.model_validate(item) for item in rounds],
            total=len(rounds),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/measurement-inspections/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement_item_inspection(
    inspection_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_measurement_item_inspection(company_id=ctx.company_id, inspection_id=inspection_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/measurement-items/{item_id}/occurrences",
    response_model=ConstructionMeasurementItemOccurrenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement_item_occurrence(
    item_id: UUID,
    request_data: ConstructionMeasurementItemOccurrenceCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemOccurrenceResponse:
    try:
        occurrence = await service.create_measurement_item_occurrence(
            company_id=ctx.company_id,
            item_id=item_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionMeasurementItemOccurrenceResponse.model_validate(occurrence)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch(
    "/measurement-occurrences/{occurrence_id}",
    response_model=ConstructionMeasurementItemOccurrenceResponse,
)
async def update_measurement_item_occurrence(
    occurrence_id: UUID,
    request_data: ConstructionMeasurementItemOccurrenceUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementItemOccurrenceResponse:
    try:
        occurrence = await service.update_measurement_item_occurrence(
            company_id=ctx.company_id,
            occurrence_id=occurrence_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionMeasurementItemOccurrenceResponse.model_validate(occurrence)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/measurement-occurrences/{occurrence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement_item_occurrence(
    occurrence_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_measurement_item_occurrence(company_id=ctx.company_id, occurrence_id=occurrence_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/measurements/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement(
    measurement_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_measurement(company_id=ctx.company_id, measurement_id=measurement_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/procurement-requests",
    response_model=ConstructionProcurementRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_procurement_request(
    project_id: UUID,
    request_data: ConstructionProcurementRequestCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROCUREMENT, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProcurementRequestResponse:
    try:
        procurement_request = await service.create_procurement_request(
            company_id=ctx.company_id,
            project_id=project_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionProcurementRequestResponse.model_validate(procurement_request)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get(
    "/projects/{project_id}/procurement-requests",
    response_model=ConstructionProcurementRequestListResponse,
)
async def list_procurement_requests(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROCUREMENT, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProcurementRequestListResponse:
    try:
        items = await service.list_procurement_requests(company_id=ctx.company_id, project_id=project_id)
        return ConstructionProcurementRequestListResponse(
            items=[ConstructionProcurementRequestResponse.model_validate(item) for item in items],
            total=len(items),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/procurement-requests/{procurement_request_id}", response_model=ConstructionProcurementRequestResponse)
async def get_procurement_request(
    procurement_request_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROCUREMENT, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProcurementRequestResponse:
    try:
        procurement_request = await service.get_procurement_request(
            company_id=ctx.company_id,
            procurement_request_id=procurement_request_id,
        )
        await service.sync_procurement_statuses(
            company_id=ctx.company_id, actor_user_id=ctx.user_id, items=[procurement_request],
        )
        return ConstructionProcurementRequestResponse.model_validate(procurement_request)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/procurement-requests/{procurement_request_id}", response_model=ConstructionProcurementRequestResponse)
async def update_procurement_request(
    procurement_request_id: UUID,
    request_data: ConstructionProcurementRequestUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROCUREMENT, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProcurementRequestResponse:
    try:
        procurement_request = await service.update_procurement_request(
            company_id=ctx.company_id,
            procurement_request_id=procurement_request_id,
            request=request_data,
            actor_user_id=ctx.user_id,
        )
        return ConstructionProcurementRequestResponse.model_validate(procurement_request)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/procurement-requests/{procurement_request_id}/submit",
    response_model=ConstructionProcurementRequestResponse,
)
async def submit_procurement_request(
    procurement_request_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROCUREMENT, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProcurementRequestResponse:
    try:
        procurement_request = await service.submit_procurement_request(
            company_id=ctx.company_id,
            procurement_request_id=procurement_request_id,
            actor_user_id=ctx.user_id,
        )
        return ConstructionProcurementRequestResponse.model_validate(procurement_request)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/procurement-requests/{procurement_request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_procurement_request(
    procurement_request_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROCUREMENT, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_procurement_request(
            company_id=ctx.company_id,
            procurement_request_id=procurement_request_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/schedule-phases",
    response_model=ConstructionSchedulePhaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_phase(
    project_id: UUID,
    request_data: ConstructionSchedulePhaseCreate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.SCHEDULE, PermissionAction.CREATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionSchedulePhaseResponse:
    try:
        phase = await service.create_schedule_phase(company_id=ctx.company_id, project_id=project_id, request=request_data)
        return ConstructionSchedulePhaseResponse.model_validate(phase)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/service-templates", response_model=ConstructionServiceTemplateListResponse)
async def list_project_services(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateListResponse:
    try:
        templates = await service.list_project_services(company_id=ctx.company_id, project_id=project_id)
        return ConstructionServiceTemplateListResponse(
            items=[ConstructionServiceTemplateResponse.from_model(template) for template in templates],
            total=len(templates),
            restricted_to_project=bool(templates),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/projects/{project_id}/service-templates", response_model=ConstructionServiceTemplateListResponse)
async def link_project_services(
    project_id: UUID,
    request_data: ConstructionProjectServiceLinkRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateListResponse:
    try:
        templates = await service.link_project_services(
            company_id=ctx.company_id,
            project_id=project_id,
            service_template_ids=request_data.service_template_ids,
            actor_user_id=ctx.user_id,
        )
        return ConstructionServiceTemplateListResponse(
            items=[ConstructionServiceTemplateResponse.from_model(template) for template in templates],
            total=len(templates),
            restricted_to_project=bool(templates),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.put("/projects/{project_id}/service-templates", response_model=ConstructionServiceTemplateListResponse)
async def replace_project_services(
    project_id: UUID,
    request_data: ConstructionProjectServiceReplaceRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateListResponse:
    try:
        templates = await service.replace_project_services(
            company_id=ctx.company_id,
            project_id=project_id,
            service_template_ids=request_data.service_template_ids,
            actor_user_id=ctx.user_id,
        )
        return ConstructionServiceTemplateListResponse(
            items=[ConstructionServiceTemplateResponse.from_model(template) for template in templates],
            total=len(templates),
            restricted_to_project=bool(templates),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post(
    "/projects/{project_id}/service-templates/import",
    response_model=ConstructionServiceTemplateImportResponse,
)
async def import_project_services(
    project_id: UUID,
    files: list[UploadFile] = File(...),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.UPDATE)),
    _catalog: ConstructionContext = Depends(
        require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)
    ),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionServiceTemplateImportResponse:
    uploaded_files = await _read_service_template_files(files)
    try:
        results = await service.import_project_services(
            company_id=ctx.company_id,
            project_id=project_id,
            files=uploaded_files,
            actor_user_id=ctx.user_id,
            actor_person_id=ctx.person_id,
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc

    return _service_template_import_response(results)


@router.delete(
    "/projects/{project_id}/service-templates/{service_template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_project_service(
    project_id: UUID,
    service_template_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.unlink_project_service(
            company_id=ctx.company_id,
            project_id=project_id,
            service_template_id=service_template_id,
            actor_user_id=ctx.user_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/projects/{project_id}/schedule-phases", response_model=ConstructionSchedulePhaseListResponse)
async def list_schedule_phases(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.SCHEDULE, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionSchedulePhaseListResponse:
    try:
        items = await service.list_schedule_phases(company_id=ctx.company_id, project_id=project_id)
        return ConstructionSchedulePhaseListResponse(
            items=[ConstructionSchedulePhaseResponse.model_validate(item) for item in items],
            total=len(items),
        )
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.get("/schedule-phases/{phase_id}", response_model=ConstructionSchedulePhaseResponse)
async def get_schedule_phase(
    phase_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.SCHEDULE, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionSchedulePhaseResponse:
    try:
        phase = await service.get_schedule_phase(company_id=ctx.company_id, phase_id=phase_id)
        return ConstructionSchedulePhaseResponse.model_validate(phase)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.patch("/schedule-phases/{phase_id}", response_model=ConstructionSchedulePhaseResponse)
async def update_schedule_phase(
    phase_id: UUID,
    request_data: ConstructionSchedulePhaseUpdate,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.SCHEDULE, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionSchedulePhaseResponse:
    try:
        phase = await service.update_schedule_phase(company_id=ctx.company_id, phase_id=phase_id, request=request_data)
        return ConstructionSchedulePhaseResponse.model_validate(phase)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.delete("/schedule-phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_phase(
    phase_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.SCHEDULE, PermissionAction.DELETE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> Response:
    try:
        await service.delete_schedule_phase(company_id=ctx.company_id, phase_id=phase_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


def _http_error(*, exc: ConstructionDomainError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"message": exc.message, "error_code": exc.error_code},
    )
