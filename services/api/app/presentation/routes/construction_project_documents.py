import logging
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.context import ConstructionContext
from app.core.security import get_construction_context, require_permission
from app.domain.exceptions import ConstructionDomainError, ConstructionInvalidValueError
from app.domain.permissions import ConstructionFeature as Feature, PermissionAction as Action
from app.domain.services.project_document_parser import MAX_DOCUMENT_BYTES
from app.domain.services.project_document_service import ProjectDocumentService, document_summary, preview_document
from app.infrastructure.database.session import get_session
from app.infrastructure.repository.project_document_repository import ProjectDocumentRepository
from app.presentation.routes.construction_projects import (
    _http_error,
    get_project_service,
    require_nfse_receivable_configuration,
)
from app.schemas.construction.project import ConstructionProjectCreate, ConstructionProjectResponse, ConstructionProjectUpdate
from app.schemas.construction.project_document import ProjectDocumentHistory, ProjectDocumentPreview, ProjectDocumentResponse


router = APIRouter(prefix="/construction", tags=["construction-project-documents"])
logger = logging.getLogger(__name__)


async def get_document_service(ctx=Depends(get_construction_context), projects=Depends(get_project_service), session=Depends(get_session)):
    return ProjectDocumentService(projects, ProjectDocumentRepository(session), ctx.company_id, ctx.user_id, ctx.timezone)


def require(ctx, feature, action):
    if not ctx.can(feature, action):
        raise HTTPException(status_code=403, detail="Permissão insuficiente no módulo de Obras")


def visible_kinds(ctx):
    can_read_measurement = ctx.can(Feature.SCHEDULE, Action.READ) and ctx.can(Feature.MEASUREMENTS, Action.READ)
    return ["contract", "measurement"] if can_read_measurement else ["contract"]


def report_error(ctx, operation, error, project_id=None):
    logger.info(f"[project_documents] refused: company_id={ctx.company_id} actor_id={ctx.user_id} project_id={project_id} operation={operation} reason={error.error_code}")
    return _http_error(exc=error)


def project_request(schema, data, ctx):
    try:
        request_data = schema.model_validate_json(data)
    except ValidationError as exc:
        errors = [
            {"loc": ["body", *error["loc"]], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors(include_input=False, include_context=False)
        ]
        raise HTTPException(status_code=422, detail=errors) from exc
    require_nfse_receivable_configuration(ctx, request_data)
    return request_data


async def document_source(service, authorization, project_id, file, source_file_id, fallback_name):
    if source_file_id is None and file is not None:
        return file.filename or fallback_name, await file.read(MAX_DOCUMENT_BYTES + 1)
    if file is not None or source_file_id is None or project_id is None:
        raise ConstructionInvalidValueError(message="Envie o documento ou selecione um arquivo da obra.")
    return await service.projects.erp_client.read_project_file(
        company_id=service.company_id, project_id=project_id, file_id=source_file_id,
        authorization=authorization, max_bytes=MAX_DOCUMENT_BYTES,
    )


@router.post("/project-documents/preview", response_model=ProjectDocumentPreview)
async def preview(
    kind: Literal["contract", "measurement"] = Form(...),
    file: UploadFile | None = File(None),
    project_id: UUID | None = Form(None),
    source_file_id: UUID | None = Form(None),
    authorization: str = Header(...),
    ctx: ConstructionContext = Depends(require_permission(Feature.PROJECTS, Action.READ)),
    service: ProjectDocumentService = Depends(get_document_service),
):
    if kind == "measurement":
        require(ctx, Feature.SCHEDULE, Action.READ)
        require(ctx, Feature.MEASUREMENTS, Action.READ | Action.CREATE)
        if project_id is None:
            raise HTTPException(status_code=400, detail="Informe a obra de Empreitada para conferir o boletim.")
    elif project_id is None:
        require(ctx, Feature.PROJECTS, Action.CREATE)
    else:
        require(ctx, Feature.PROJECTS, Action.UPDATE)
    try:
        if kind == "measurement":
            await service.require_contract_project(project_id)
        elif project_id is not None:
            await service.projects.get_project(company_id=ctx.company_id, project_id=project_id)
        filename, data = await document_source(
            service, authorization, project_id, file, source_file_id,
            "Boletim.xlsx" if kind == "measurement" else "Contrato.pdf",
        )
        return await run_in_threadpool(preview_document, kind, filename, data)
    except ConstructionDomainError as exc:
        raise report_error(ctx, "preview", exc, project_id) from exc


@router.post("/projects/from-contract", response_model=ConstructionProjectResponse, status_code=201)
async def create_from_contract(
    file: UploadFile = File(...),
    project_data: str | None = Form(None),
    code: str | None = Form(None, max_length=50),
    name: str | None = Form(None, max_length=255),
    ctx: ConstructionContext = Depends(require_permission(Feature.PROJECTS, Action.READ | Action.CREATE)),
    service: ProjectDocumentService = Depends(get_document_service),
):
    try:
        request_data = project_request(ConstructionProjectCreate, project_data, ctx) if project_data is not None else None
        return await service.create_from_contract(
            file.filename or "Contrato.pdf", await file.read(MAX_DOCUMENT_BYTES + 1),
            code=code, name=name, request=request_data,
        )
    except ConstructionDomainError as exc:
        raise report_error(ctx, "create_from_contract", exc) from exc


@router.patch("/projects/{project_id}/from-contract", response_model=ConstructionProjectResponse)
async def update_from_contract(
    project_id: UUID,
    project_data: str = Form(...),
    file: UploadFile | None = File(None),
    source_file_id: UUID | None = Form(None),
    authorization: str = Header(...),
    ctx: ConstructionContext = Depends(require_permission(Feature.PROJECTS, Action.READ | Action.UPDATE)),
    service: ProjectDocumentService = Depends(get_document_service),
):
    request_data = project_request(ConstructionProjectUpdate, project_data, ctx)
    try:
        await service.projects.get_project(company_id=ctx.company_id, project_id=project_id)
        filename, data = await document_source(service, authorization, project_id, file, source_file_id, "Contrato.pdf")
        return await service.update_with_contract(project_id, filename, data, request_data, source_file_id)
    except ConstructionDomainError as exc:
        raise report_error(ctx, "update_from_contract", exc, project_id) from exc


@router.get("/projects/{project_id}/documents", response_model=ProjectDocumentHistory)
async def list_documents(
    project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(Feature.PROJECTS, Action.READ)),
    service: ProjectDocumentService = Depends(get_document_service),
):
    try:
        return await service.history(project_id, visible_kinds(ctx))
    except ConstructionDomainError as exc:
        raise report_error(ctx, "history", exc, project_id) from exc


@router.post("/projects/{project_id}/documents", response_model=ProjectDocumentResponse)
async def attach_document(
    project_id: UUID,
    kind: Literal["contract", "measurement"] = Form(...),
    create_phases: bool = Form(False),
    file: UploadFile | None = File(None),
    source_file_id: UUID | None = Form(None),
    authorization: str = Header(...),
    ctx: ConstructionContext = Depends(require_permission(Feature.SCHEDULE, Action.READ)),
    service: ProjectDocumentService = Depends(get_document_service),
):
    require(ctx, Feature.PROJECTS, Action.READ)
    if kind == "contract":
        require(ctx, Feature.PROJECTS, Action.UPDATE)
    else:
        require(ctx, Feature.MEASUREMENTS, Action.READ | Action.CREATE)
        if create_phases:
            require(ctx, Feature.SCHEDULE, Action.CREATE)
    try:
        if source_file_id is not None:
            await service.require_contract_project(project_id)
        filename, data = await document_source(
            service, authorization, project_id, file, source_file_id,
            "Boletim.xlsx" if kind == "measurement" else "Contrato.pdf",
        )
        result = await service.attach(
            project_id, kind, filename, data, create_phases=create_phases, source_file_id=source_file_id,
        )
        return document_summary(result)
    except ConstructionDomainError as exc:
        raise report_error(ctx, "attach", exc, project_id) from exc


@router.get("/projects/{project_id}/documents/{document_id}/download")
async def download_document(
    project_id: UUID,
    document_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(Feature.PROJECTS, Action.READ)),
    service: ProjectDocumentService = Depends(get_document_service),
):
    try:
        document = await service.download(project_id, document_id, visible_kinds(ctx))
    except ConstructionDomainError as exc:
        raise report_error(ctx, "download", exc, project_id) from exc
    return Response(
        content=document.content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.file_name, safe='')}"},
    )
