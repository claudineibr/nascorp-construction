from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import ConstructionContext
from app.core.security import require_permission
from app.domain.exceptions import ConstructionDomainError
from app.domain.permissions import ConstructionFeature, PermissionAction
from app.domain.services import ConstructionProjectService
from app.infrastructure.clients import ErpConstructionClient
from app.infrastructure.database.session import get_session
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.schemas.construction import (
    ConstructionBlockCreate,
    ConstructionBlockListResponse,
    ConstructionBlockResponse,
    ConstructionBlockUpdate,
    ConstructionProjectCreate,
    ConstructionProjectListResponse,
    ConstructionProjectResponse,
    ConstructionProjectUpdate,
    ConstructionMeasurementCreate,
    ConstructionMeasurementListResponse,
    ConstructionMeasurementReject,
    ConstructionMeasurementResponse,
    ConstructionMeasurementUpdate,
    ConstructionSchedulePhaseCreate,
    ConstructionSchedulePhaseListResponse,
    ConstructionSchedulePhaseResponse,
    ConstructionSchedulePhaseUpdate,
    ConstructionUnitCreate,
    ConstructionUnitListResponse,
    ConstructionUnitReserveRequest,
    ConstructionUnitResponse,
    ConstructionUnitSaleConfirmRequest,
    ConstructionUnitUpdate,
)


router = APIRouter(prefix="/construction", tags=["construction"])


async def get_erp_construction_client() -> ErpConstructionClient:
    return ErpConstructionClient()


async def get_project_service(
    session: AsyncSession = Depends(get_session),
    erp_client: ErpConstructionClient = Depends(get_erp_construction_client),
) -> ConstructionProjectService:
    return ConstructionProjectService(
        repository=ConstructionRepository(session=session),
        event_repository=EventRepository(session=session),
        erp_client=erp_client,
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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.PROJECTS, PermissionAction.READ)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProjectListResponse:
    items, total = await service.list_projects(
        company_id=ctx.company_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ConstructionProjectListResponse(
        items=[ConstructionProjectResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


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
        project = await service.update_project(company_id=ctx.company_id, project_id=project_id, request=request_data)
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
        unit = await service.create_unit(company_id=ctx.company_id, project_id=project_id, request=request_data)
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
        unit = await service.update_unit(company_id=ctx.company_id, unit_id=unit_id, request=request_data)
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
        )
        return ConstructionMeasurementResponse.model_validate(measurement)
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
        return ConstructionMeasurementResponse.model_validate(measurement)
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
        )
        return ConstructionMeasurementResponse.model_validate(measurement)
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
        )
        return ConstructionMeasurementResponse.model_validate(measurement)
    except ConstructionDomainError as exc:
        raise _http_error(exc=exc) from exc


@router.post("/measurements/{measurement_id}/reject", response_model=ConstructionMeasurementResponse)
async def reject_measurement(
    measurement_id: UUID,
    request_data: ConstructionMeasurementReject,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionMeasurementResponse:
    del request_data
    try:
        measurement = await service.reject_measurement(company_id=ctx.company_id, measurement_id=measurement_id)
        return ConstructionMeasurementResponse.model_validate(measurement)
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
