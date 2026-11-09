from sqlalchemy import func, select
from sqlalchemy.orm import undefer

from app.infrastructure.database.models.project_document import ConstructionProjectDocument


class ProjectDocumentRepository:
    def __init__(self, session):
        self.session = session

    async def lock_identity(self, company_id, identity):
        await self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"{company_id}:{identity}", 0))))

    async def find(self, company_id, identity):
        return await self.session.scalar(select(ConstructionProjectDocument).where(
            ConstructionProjectDocument.company_id == company_id,
            ConstructionProjectDocument.identity == identity,
        ))

    async def list(self, company_id, project_id, kinds):
        rows = await self.session.scalars(select(ConstructionProjectDocument).where(
            ConstructionProjectDocument.company_id == company_id,
            ConstructionProjectDocument.project_id == project_id,
            ConstructionProjectDocument.kind.in_(kinds),
        ).order_by(ConstructionProjectDocument.created_at.desc(), ConstructionProjectDocument.id.desc()))
        return rows.all()

    async def get_file(self, company_id, project_id, document_id, kinds):
        return await self.session.scalar(select(ConstructionProjectDocument).options(
            undefer(ConstructionProjectDocument.content)
        ).where(
            ConstructionProjectDocument.company_id == company_id,
            ConstructionProjectDocument.project_id == project_id,
            ConstructionProjectDocument.id == document_id,
            ConstructionProjectDocument.kind.in_(kinds),
        ))
