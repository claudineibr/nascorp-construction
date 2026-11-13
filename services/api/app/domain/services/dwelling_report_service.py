import logging

from app.domain.exceptions import ConstructionNotFoundError

logger = logging.getLogger(__name__)


class DwellingReportService:
    def __init__(self, repository):
        self.repository = repository

    async def build(self, company_id, **filters):
        logger.info(f"[dwelling_report] consultar: company_id={company_id} project_id={filters.get('project_id')}")
        project_id = filters.get("project_id")
        project = None
        if project_id:
            project = await self.repository.get_project(company_id=company_id, project_id=project_id)
            if project is None or project.development_type != "INCORPORATION":
                logger.info(f"[dwelling_report] obra_recusada: company_id={company_id} project_id={project_id}")
                raise ConstructionNotFoundError(resource_name="a obra de incorporação nesta empresa ou no seu acesso")
        rows = await self.repository.dwelling_report(company_id, **filters)
        logger.info(f"[dwelling_report] concluido: company_id={company_id} rows={len(rows)}")
        return {"items": rows, "total": len(rows), "project_name": project.name if project else None}

    async def correspondents(self, company_id, search=None):
        rows = await self.repository.dwelling_correspondent_options(company_id, search)
        return {"items": rows, "total": len(rows)}

    async def projects(self, company_id, search=None):
        rows = await self.repository.dwelling_project_options(company_id, search)
        return {"items": [{"id": str(row["id"]), "name": row["name"]} for row in rows], "total": len(rows)}
