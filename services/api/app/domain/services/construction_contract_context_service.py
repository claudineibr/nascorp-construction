import logging

from app.domain.constants import ConstructionUnitStatus
from app.domain.exceptions import ConstructionNotFoundError, ConstructionResourceInUseError


logger = logging.getLogger(__name__)


class ConstructionContractContextService:
    def __init__(self, repository):
        self.repository = repository

    async def get_context(self, company_id, unit_id):
        context = await self.repository.contract_context(company_id, unit_id)
        if context is None:
            raise ConstructionNotFoundError(resource_name="a unidade nesta empresa")
        return context

    async def get_summary_context(self, company_id, unit_id, sale_id):
        unit = await self.repository.lock_unit(company_id=company_id, unit_id=unit_id)
        if unit is None:
            raise ConstructionNotFoundError(resource_name="a unidade nesta empresa")
        return await self.build_summary_context(company_id, unit, sale_id)

    async def build_summary_context(self, company_id, unit, sale_id):
        unit_id = unit.id
        trace = f"company_id={company_id} unit_id={unit_id} sale_id={sale_id}"
        logger.info(f"[unit_summary_context] consultar: {trace}")
        if unit.current_sale_id != sale_id or unit.status not in (ConstructionUnitStatus.SOLD, ConstructionUnitStatus.DELIVERED):
            raise ConstructionResourceInUseError(message="A venda vigente mudou. Reabra os detalhes da unidade.")
        sale = await self.repository.get_unit_sale(company_id=company_id, sale_id=sale_id)
        project = await self.repository.get_project(company_id=company_id, project_id=unit.project_id)
        if project is None or sale is None or sale.unit_id != unit_id or sale.status != "ACTIVE":
            raise ConstructionNotFoundError(resource_name="a venda vigente desta unidade")
        if unit.buyer_person_id is None or sale.buyer_person_id != unit.buyer_person_id:
            raise ConstructionResourceInUseError(message="Confira o comprador principal da venda.")

        sources = await self.repository.list_unit_payment_sources(company_id=company_id, unit_id=unit_id)
        documentation = await self.repository.list_unit_documentations(company_id=company_id, unit_id=unit_id)
        signals = await self.repository.list_unit_commissions(company_id=company_id, unit_id=unit_id, sale_id=sale_id)
        logger.info(f"[unit_summary_context] lido: {trace} documentacoes={len(documentation)} sinais={len(signals)}")
        return {
            "project_id": project.id,
            "project_name": project.name,
            "cost_center_id": unit.analytic_cost_center_id,
            "unit_code": unit.code,
            "unit_description": unit.description,
            "buyer_id": unit.buyer_person_id,
            "contract_id": unit.external_contract_id or sale.external_contract_id,
            "receivable_id": unit.external_receivable_id or sale.external_receivable_id,
            "sold_at": unit.sold_at,
            "sale_price": unit.sale_price,
            "discount": unit.discount_amount,
            "sources": {row.source_type: row.amount for row in sources},
            "documentation": [
                {"label": row.documentation_type.name, "amount": row.amount}
                for row in documentation if row.documentation_type.company_id == company_id
            ],
            "signals": [
                {"amount": row.amount, "due_date": row.due_date, "payment_date": row.payment_date,
                 "composes_sale_price": row.composes_sale_price}
                for row in signals if row.deleted_at is None
            ],
        }
