from sqlalchemy import select

from app.infrastructure.database.models.unit_buyer_history import ConstructionUnitBuyerHistory


class UnitBuyerHistoryRepository:
    async def unit_buyer_history(self, company_id, unit_id, open_only=False):
        query = select(ConstructionUnitBuyerHistory).where(
            ConstructionUnitBuyerHistory.company_id == company_id,
            ConstructionUnitBuyerHistory.unit_id == unit_id,
            ConstructionUnitBuyerHistory.deleted_at.is_(None),
        )
        if open_only:
            query = query.where(ConstructionUnitBuyerHistory.excluded_at.is_(None)).with_for_update()
        return list((await self.session.scalars(query.order_by(
            ConstructionUnitBuyerHistory.included_at.asc().nulls_first(), ConstructionUnitBuyerHistory.id,
        ))).all())
