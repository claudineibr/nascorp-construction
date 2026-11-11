from sqlalchemy import func, select
from sqlalchemy.orm import undefer

from app.infrastructure.database.models.construction import ConstructionProject
from app.infrastructure.database.models.project_document import ConstructionProjectDocument


class ProjectDocumentRepository:
    def __init__(self, session):
        self.session = session

    async def lock_identity(self, company_id, identity):
        await self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"{company_id}:{identity}", 0))))

    async def find_reservation(self, company_id, identity):
        statement = (
            select(ConstructionProjectDocument, ConstructionProject.deleted_at)
            .join(ConstructionProject, (
                (ConstructionProject.id == ConstructionProjectDocument.project_id)
                & (ConstructionProject.company_id == ConstructionProjectDocument.company_id)
            ))
            .where(
                ConstructionProjectDocument.company_id == company_id,
                ConstructionProjectDocument.identity == identity,
            )
            .execution_options(include_deleted=True)
        )
        result = await self.session.execute(statement)
        return result.first()

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
