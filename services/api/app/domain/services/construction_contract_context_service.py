from app.domain.exceptions import ConstructionNotFoundError
from app.infrastructure.repository.construction_repository import ConstructionRepository


class ConstructionContractContextService:
    def __init__(self, session):
        self.repository = ConstructionRepository(session=session)

    async def get_context(self, company_id, unit_id):
        context = await self.repository.contract_context(company_id, unit_id)
        if context is None:
            raise ConstructionNotFoundError(resource_name="a unidade nesta empresa")
        return context
