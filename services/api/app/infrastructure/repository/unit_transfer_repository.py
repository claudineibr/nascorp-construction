from sqlalchemy import func, or_, select, update

from app.domain.events.constants import ConstructionEventType, EventStatus
from app.infrastructure.database.models import (
    ConstructionProject, ConstructionUnit, ConstructionUnitCommission, ConstructionUnitDocumentation,
    ConstructionUnitPaymentSource, ConstructionUnitSale, OutboxEvent,
)
from app.infrastructure.repository._project_scope_filters import scope_conditions


class UnitTransferRepository:
    async def lock_transfer_commission(self, company_id, commission_id):
        return await self.session.scalar(select(ConstructionUnitCommission).where(
            ConstructionUnitCommission.company_id == company_id, ConstructionUnitCommission.id == commission_id,
            ConstructionUnitCommission.deleted_at.is_(None),
            *scope_conditions(ConstructionUnitCommission, self.scope),
        ).with_for_update().execution_options(populate_existing=True))

    async def unit_transfer_event(self, company_id, event_id):
        return await self.session.scalar(select(OutboxEvent).where(
            OutboxEvent.company_id == company_id, OutboxEvent.event_id == event_id,
            OutboxEvent.event_type == ConstructionEventType.UNIT_TRANSFERRED,
        ).with_for_update().execution_options(populate_existing=True))

    async def unit_transfer_targets(self, company_id, unit_id, search, page, page_size):
        query = select(ConstructionUnit.id, ConstructionUnit.code, ConstructionUnit.description,
                       ConstructionUnit.project_id, ConstructionProject.name.label('project_name'),
                       ConstructionProject.code.label('project_code')).join(
            ConstructionProject, ConstructionProject.id == ConstructionUnit.project_id,
        ).where(
            ConstructionUnit.company_id == company_id, ConstructionProject.company_id == company_id,
            ConstructionProject.deleted_at.is_(None),
            ConstructionUnit.deleted_at.is_(None), ConstructionUnit.id != unit_id,
            ConstructionUnit.status == 'available', ConstructionUnit.buyer_person_id.is_(None),
            ConstructionUnit.current_sale_id.is_(None), ConstructionUnit.external_contract_id.is_(None),
            ConstructionUnit.analytic_cost_center_id.is_not(None),
            *scope_conditions(ConstructionUnit, self.scope),
        )
        if search and len(search.strip()) >= 4:
            term = f'%{search.strip()}%'
            query = query.where(or_(ConstructionUnit.code.ilike(term), ConstructionUnit.description.ilike(term),
                                     ConstructionProject.name.ilike(term), ConstructionProject.code.ilike(term)))
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = (await self.session.execute(query.order_by(ConstructionProject.name, ConstructionUnit.code)
                                          .offset((page - 1) * page_size).limit(page_size))).mappings().all()
        return {'items': [{**dict(row), 'label': f'{row["project_code"]} - {row["project_name"]} · {row["code"]} - {row["description"] or ""}'}
                          for row in rows], 'total': total, 'page': page, 'page_size': page_size,
                'total_pages': max(1, (total + page_size - 1) // page_size)}

    async def has_prior_buyer_sale(self, company_id, unit_id, sale_id, person_id):
        return await self.session.scalar(select(ConstructionUnitSale.id).where(
            ConstructionUnitSale.company_id == company_id, ConstructionUnitSale.unit_id == unit_id,
            ConstructionUnitSale.id != sale_id, ConstructionUnitSale.buyer_person_id == person_id,
        ).limit(1)) is not None

    async def pending_unit_transfer(self, company_id, unit_id):
        return await self.session.scalar(select(OutboxEvent).where(
            OutboxEvent.company_id == company_id,
            OutboxEvent.event_type == ConstructionEventType.UNIT_TRANSFERRED,
            OutboxEvent.status != EventStatus.PUBLISHED,
            or_(OutboxEvent.aggregate_id == unit_id,
                OutboxEvent.payload['target_unit_id'].astext == str(unit_id)),
        ).order_by(OutboxEvent.occurred_at).limit(1))

    async def pending_sale_integration(self, company_id, unit_id):
        return await self.session.scalar(select(OutboxEvent.id).where(
            OutboxEvent.company_id == company_id, OutboxEvent.aggregate_id == unit_id,
            OutboxEvent.event_type.in_([ConstructionEventType.UNIT_CREATED, ConstructionEventType.UNIT_SOLD,
                                        ConstructionEventType.UNIT_STATUS_CHANGED]),
            OutboxEvent.status != EventStatus.PUBLISHED,
        ).limit(1))

    async def unit_transfer_history(self, company_id, unit_id):
        query = select(OutboxEvent).where(
            OutboxEvent.company_id == company_id,
            OutboxEvent.event_type == ConstructionEventType.UNIT_TRANSFERRED,
            or_(OutboxEvent.aggregate_id == unit_id,
                OutboxEvent.payload['target_unit_id'].astext == str(unit_id)),
        )
        if self.scope is not None and not self.scope.unrestricted:
            ids = [str(value) for value in self.scope.project_ids]
            query = query.where(OutboxEvent.payload['source_project_id'].astext.in_(ids),
                                OutboxEvent.payload['target_project_id'].astext.in_(ids))
        return list((await self.session.scalars(query.order_by(OutboxEvent.occurred_at.desc()).limit(100))).all())

    async def transfer_unit_children(self, company_id, source, target, source_sale_id, target_sale_id):
        for model in [ConstructionUnitDocumentation, ConstructionUnitPaymentSource]:
            await self.replace_unit_children(model, company_id=company_id, unit_id=target.id, entities=[])
            await self.session.execute(update(model).where(
                model.company_id == company_id, model.unit_id == source.id,
            ).values(unit_id=target.id))
        last = await self.session.scalar(select(func.max(ConstructionUnitCommission.sequence_number)).where(
            ConstructionUnitCommission.company_id == company_id, ConstructionUnitCommission.unit_id == target.id,
        )) or 0
        commissions = list((await self.session.scalars(select(ConstructionUnitCommission).where(
            ConstructionUnitCommission.company_id == company_id,
            ConstructionUnitCommission.unit_id == source.id,
            ConstructionUnitCommission.deleted_at.is_(None),
            or_(ConstructionUnitCommission.sale_id == source_sale_id, ConstructionUnitCommission.sale_id.is_(None)),
        ).order_by(ConstructionUnitCommission.sequence_number).with_for_update())).all())
        moved = []
        for offset, row in enumerate(commissions, start=1):
            moved.append({'id': str(row.id), 'source_sequence': row.sequence_number, 'target_sequence': last + offset})
            row.unit_id = target.id
            row.sale_id = target_sale_id
            row.sequence_number = last + offset
        return moved
