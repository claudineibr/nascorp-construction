from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_service_key
from app.domain.exceptions import ConstructionDomainError
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.session import get_session
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.infrastructure.repository.event_repository import EventRepository
from app.schemas.construction import ConstructionProjectResponse
from app.schemas.events import EventEnvelopeRequest


router = APIRouter(prefix="/internal", tags=["internal"])


async def get_project_service(session: AsyncSession = Depends(get_session)) -> ConstructionProjectService:
    return ConstructionProjectService(
        repository=ConstructionRepository(session=session),
        event_repository=EventRepository(session=session),
    )


@router.post("/events/erp-cost-center-created", response_model=ConstructionProjectResponse)
async def consume_erp_cost_center_created_event(
    request_data: EventEnvelopeRequest,
    _: None = Depends(require_service_key),
    service: ConstructionProjectService = Depends(get_project_service),
) -> ConstructionProjectResponse:
    try:
        project = await service.apply_cost_center_created_event(event=request_data.to_event_envelope())
        return ConstructionProjectResponse.model_validate(project)
    except ConstructionDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
