import logging

from app.domain.business_clock import get_business_today
from app.domain.constants import ConstructionUnitCommissionStatus
from app.domain.exceptions import ConstructionDomainError, ConstructionNotFoundError
from app.domain.unit_commission_status import unit_commission_status

logger = logging.getLogger(__name__)


class UnitSignalReportService:
    def __init__(self, repository, context):
        self.repository = repository
        self.context = context

    def beneficiary_scope(self, beneficiary_id=None):
        if self.context.can_view_all_unit_signals:
            return beneficiary_id
        person_id = self.context.person_id
        if person_id is None or beneficiary_id not in (None, person_id):
            logger.info(f"[unit_signal_report] beneficiario_recusado: company_id={self.context.company_id} user_id={self.context.user_id}")
            raise ConstructionDomainError(message="Você só pode consultar seus próprios sinais.", status_code=403)
        return person_id

    async def projects(self, search):
        beneficiary_id = self.beneficiary_scope()
        rows = await self.repository.unit_signal_report_projects(self.context.company_id, search, beneficiary_id)
        return {"items": rows, "beneficiary_id": beneficiary_id}

    async def beneficiaries(self):
        if not self.context.can_view_all_unit_signals:
            raise ConstructionDomainError(message="Você só pode consultar seus próprios sinais.", status_code=403)
        return await self.repository.unit_signal_report_beneficiaries(self.context.company_id)

    async def build(self, project_id, beneficiary_id, status):
        beneficiary_id = self.beneficiary_scope(beneficiary_id)
        company_id = self.context.company_id
        today = get_business_today(self.context.timezone)
        trace = f"company_id={company_id} user_id={self.context.user_id} project_id={project_id} status={status}"
        logger.info(f"[unit_signal_report] consultar: {trace}")
        project_name = None
        if project_id is not None:
            if self.context.can_view_all_unit_signals:
                project = await self.repository.get_project(company_id=company_id, project_id=project_id)
                project_name = project.name if project else None
            else:
                project_name = await self.repository.unit_signal_report_project_name(company_id, project_id, beneficiary_id)
            if project_name is None:
                logger.info(f"[unit_signal_report] obra_recusada: {trace}")
                raise ConstructionNotFoundError(resource_name="a obra nesta empresa ou no seu acesso")
        rows = await self.repository.unit_signal_report_rows(company_id, project_id, beneficiary_id)
        statuses = {
            "all": None,
            "unpaid": {ConstructionUnitCommissionStatus.OPEN, ConstructionUnitCommissionStatus.OVERDUE},
        }
        selected = statuses.get(status, {status})
        items = []
        for row in rows:
            row_status = unit_commission_status(due_date=row.due_date, payment_date=row.payment_date, today=today)
            if selected is None or row_status in selected:
                items.append({**row, "status": row_status})
        logger.info(f"[unit_signal_report] concluido: {trace} rows={len(items)}")
        return {"items": items, "project_name": project_name, "reference_date": today}
