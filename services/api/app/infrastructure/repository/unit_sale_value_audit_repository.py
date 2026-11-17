from sqlalchemy import func, select

from app.infrastructure.database.models.unit_sale_value_audit import ConstructionUnitSaleValueAudit
from app.infrastructure.repository._project_scope_filters import scope_conditions


class UnitSaleValueAuditRepository:
    async def list_unit_sale_value_audits(self, *, company_id, unit_id, page, page_size, direction):
        model = ConstructionUnitSaleValueAudit
        conditions = [model.company_id == company_id, model.unit_id == unit_id,
                      *scope_conditions(model, self.scope)]
        total = await self.session.scalar(select(func.count()).select_from(model).where(*conditions))
        ordering = (model.changed_at.asc(), model.id.asc()) if direction == "asc" else (
            model.changed_at.desc(), model.id.desc(),
        )
        rows = await self.session.scalars(select(model).where(*conditions).order_by(*ordering)
                                         .offset((page - 1) * page_size).limit(page_size))
        return {"items": list(rows), "total": total, "page": page, "page_size": page_size,
                "total_pages": max(1, (total + page_size - 1) // page_size)}
