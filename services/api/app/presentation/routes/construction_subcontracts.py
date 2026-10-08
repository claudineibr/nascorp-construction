from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.context import ConstructionContext
from app.core.security import require_permission
from app.domain.exceptions import ConstructionDomainError
from app.domain.permissions import ConstructionFeature, PermissionAction
from app.domain.services.subcontract_service import SubcontractService
from app.presentation.routes.construction_projects import get_project_service
from app.schemas.construction.subcontract import SubcontractRequest, SubcontractDirectBillRequest, SubcontractDeductionRequest, SubcontractReasonRequest


router = APIRouter(prefix="/construction", tags=["construction-subcontracts"])


async def get_subcontracts(projects=Depends(get_project_service)):
    return SubcontractService(projects)


def error(exc):
    return HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code})


@router.get("/projects/{project_id}/subcontracts")
async def list_contracts(project_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        await service.projects.get_project(company_id=ctx.company_id, project_id=project_id)
        rows = await service.repository.list(ctx.company_id, project_id)
        return {"items": [service.header(row) for row in rows]}
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.get("/subcontracts/{contract_id}")
async def contract_detail(contract_id: UUID, version_id: UUID | None = None,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.detail(ctx.company_id, contract_id, version_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.post("/projects/{project_id}/subcontracts")
async def create_contract(project_id: UUID, request: SubcontractRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.CREATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.save(ctx.company_id, project_id, request, ctx.user_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.put("/subcontracts/{contract_id}")
async def update_contract(contract_id: UUID, request: SubcontractRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        row = await service.get(ctx.company_id, contract_id)
        return await service.save(ctx.company_id, row.project_id, request, ctx.user_id, contract_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.post("/subcontracts/{contract_id}/release")
async def release_contract(contract_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.release(ctx.company_id, contract_id, ctx.user_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.get("/subcontracts/{contract_id}/direct-bills")
async def direct_bills(contract_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        await service.get(ctx.company_id, contract_id)
        rows = await service.repository.direct_bills(ctx.company_id, contract_id)
        return {"items": [{"id": row.id, "amount": str(row.amount), "deducted_amount": str(row.deducted_amount),
            "remaining_amount": str(row.amount - row.deducted_amount), "snapshot": row.document_snapshot} for row in rows]}
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.get("/projects/{project_id}/direct-billing-documents")
async def material_documents(project_id: UUID, search: str | None = None,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        await service.projects.get_project(company_id=ctx.company_id, project_id=project_id)
        await service.session.commit()
        return await service.projects.erp_client.list_direct_billing_documents(company_id=ctx.company_id,
            project_id=project_id, user_id=ctx.user_id, search=search)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.post("/subcontracts/{contract_id}/direct-bills")
async def register_direct_bill(contract_id: UUID, request: SubcontractDirectBillRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.register_direct_bill(ctx.company_id, contract_id, request, ctx.user_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.get("/measurements/{measurement_id}/direct-billing-deductions")
async def measurement_deductions(measurement_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.READ)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        await service.projects.get_measurement(company_id=ctx.company_id, measurement_id=measurement_id)
        rows = await service.repository.deductions(ctx.company_id, measurement_id)
        return {"items": [{"id": row.id, "direct_bill_id": row.direct_bill_id, "amount": str(row.amount),
            "status": row.status} for row in rows]}
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.put("/measurements/{measurement_id}/direct-billing-deductions")
async def update_deduction(measurement_id: UUID, request: SubcontractDeductionRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.set_deduction(ctx.company_id, measurement_id, request)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.post("/measurements/{measurement_id}/reverse-contract-consumption")
async def reverse_contract_measurement(measurement_id: UUID, request: SubcontractReasonRequest,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.request_reversal(ctx.company_id, measurement_id, request.reason, ctx.user_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.post("/subcontracts/{contract_id}/close")
async def close_contract(contract_id: UUID, request: SubcontractReasonRequest, cancel: bool = False,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.close(ctx.company_id, contract_id, request.reason, ctx.user_id, cancel)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.post("/subcontracts/{contract_id}/reopen")
async def reopen_contract(contract_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        return await service.reopen(ctx.company_id, contract_id)
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.delete("/subcontracts/{contract_id}/direct-bills/{bill_id}")
async def remove_direct_bill(contract_id: UUID, bill_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        await service.remove_direct_bill(ctx.company_id, contract_id, bill_id)
        return {"removed": True}
    except ConstructionDomainError as exc:
        raise error(exc) from exc


@router.delete("/measurements/{measurement_id}/direct-billing-deductions/{deduction_id}")
async def remove_direct_deduction(measurement_id: UUID, deduction_id: UUID,
    ctx: ConstructionContext = Depends(require_permission(ConstructionFeature.MEASUREMENTS, PermissionAction.UPDATE)),
    service: SubcontractService = Depends(get_subcontracts)):
    try:
        await service.remove_deduction(ctx.company_id, measurement_id, deduction_id)
        return {"removed": True}
    except ConstructionDomainError as exc:
        raise error(exc) from exc
