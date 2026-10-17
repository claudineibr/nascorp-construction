from datetime import datetime
from math import ceil
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.security import get_construction_context, require_permission
from app.domain.exceptions import ConstructionDomainError
from app.domain.permissions import ConstructionFeature, PermissionAction
from app.domain.services.assistance_service import AssistanceRequestService, serialize, serialize_summary
from app.infrastructure.database.session import get_session
from app.infrastructure.repository.assistance_repository import AssistanceRepository
from app.schemas.construction.assistance import (
    AssistanceInput,
    AssistanceResponse,
    AssistanceListResponse,
    ReopenInput,
    AssistanceReferenceList,
    AssistancePrintResponse,
)


router = APIRouter(prefix="/construction/assistance-requests", tags=["assistance-requests"])


async def get_assistance_service(session=Depends(get_session), ctx=Depends(get_construction_context)):
    return AssistanceRequestService(AssistanceRepository(session, ctx.project_scope))


async def response(service, row):
    return serialize(row, await service.repository.labels([row]))


@router.get("", response_model=AssistanceListResponse)
async def list_requests(
    project_id: UUID | None = None,
    unit_id: UUID | None = None,
    customer_person_id: UUID | None = None,
    responsible_person_id: UUID | None = None,
    status: Literal["open", "completed"] | None = None,
    opened_from: datetime | None = None,
    opened_to: datetime | None = None,
    overdue: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service=Depends(get_assistance_service),
):
    filters = dict(
        project_id=project_id,
        unit_id=unit_id,
        customer_person_id=customer_person_id,
        responsible_person_id=responsible_person_id,
        status=status,
        opened_from=opened_from,
        opened_to=opened_to,
        overdue=overdue,
    )
    rows, total = await service.repository.list(
        ctx.company_id, filters, datetime.now(ZoneInfo("America/Sao_Paulo")).date(), page, page_size
    )
    labels = await service.repository.labels(rows)
    return dict(
        items=[serialize_summary(row, labels) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size),
    )


@router.get("/references", response_model=AssistanceReferenceList)
async def references(
    kind: Literal["project", "unit", "person", "employee"],
    search: str | None = Query(default=None, max_length=150),
    project_id: UUID | None = None,
    reference_id: UUID | None = None,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service=Depends(get_assistance_service),
):
    return {"items": await service.repository.references(ctx.company_id, kind, search, project_id, reference_id)}


@router.get("/{request_id}/print-context", response_model=AssistancePrintResponse)
async def print_request(
    request_id: UUID,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service=Depends(get_assistance_service),
):
    try:
        return await service.print_context(ctx.company_id, request_id)
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{request_id}", response_model=AssistanceResponse)
async def get_request(
    request_id: UUID,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.READ)),
    service=Depends(get_assistance_service),
):
    try:
        return await response(service, await service.get(ctx.company_id, request_id))
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("", response_model=AssistanceResponse, status_code=201)
async def create_request(
    data: AssistanceInput,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.CREATE)),
    service=Depends(get_assistance_service),
):
    try:
        return await response(service, await service.save(ctx.company_id, data, ctx.user_id))
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/{request_id}", response_model=AssistanceResponse)
async def update_request(
    request_id: UUID,
    data: AssistanceInput,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service=Depends(get_assistance_service),
):
    try:
        return await response(service, await service.save(ctx.company_id, data, ctx.user_id, request_id))
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{request_id}/complete", response_model=AssistanceResponse)
async def complete_request(
    request_id: UUID,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service=Depends(get_assistance_service),
):
    try:
        return await response(service, await service.transition(ctx.company_id, request_id, ctx.user_id, "completed"))
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{request_id}/reopen", response_model=AssistanceResponse)
async def reopen_request(
    request_id: UUID,
    data: ReopenInput,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.UPDATE)),
    service=Depends(get_assistance_service),
):
    try:
        return await response(
            service, await service.transition(ctx.company_id, request_id, ctx.user_id, "reopened", data.justification)
        )
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{request_id}", status_code=204)
async def delete_request(
    request_id: UUID,
    ctx=Depends(require_permission(ConstructionFeature.UNITS, PermissionAction.DELETE)),
    service=Depends(get_assistance_service),
):
    try:
        await service.transition(ctx.company_id, request_id, ctx.user_id, "deleted")
        return Response(status_code=204)
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
