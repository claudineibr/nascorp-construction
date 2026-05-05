from app.core.config import settings
from app.domain.services.construction_integration_dispatcher import ConstructionIntegrationDispatcher


def create_construction_integration_dispatcher(*, event_repository, event_transport) -> ConstructionIntegrationDispatcher:
    return ConstructionIntegrationDispatcher(
        event_repository=event_repository,
        event_transport=event_transport,
        integration_mode=settings.integration_mode,
    )