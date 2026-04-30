from typing import Protocol

from app.domain.events.contracts import EventEnvelope
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject


class CostCenterHierarchyClient(Protocol):
    async def create_cost_center_hierarchy(self, *, event: EventEnvelope) -> EventEnvelope:
        raise NotImplementedError


class ConstructionCostCenterIntegrationService:
    def __init__(self, *, project_service: ConstructionProjectService, erp_client: CostCenterHierarchyClient) -> None:
        self.project_service = project_service
        self.erp_client = erp_client

    async def sync_project_created_event(self, *, event: EventEnvelope) -> ConstructionProject:
        confirmation_event = await self.erp_client.create_cost_center_hierarchy(event=event)
        return await self.project_service.apply_cost_center_created_event(event=confirmation_event)
