import logging
from datetime import UTC, datetime

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session, with_loader_criteria

from app.domain.constants import ConstructionMeasurementStatus
from app.infrastructure.database.history import PreservedHistory


logger = logging.getLogger(__name__)


@event.listens_for(Session, "do_orm_execute")
def filter_preserved_history(execution):
    if execution.is_select and not execution.execution_options.get("include_deleted", False):
        execution.statement = execution.statement.options(
            with_loader_criteria(PreservedHistory, lambda model: model.deleted_at.is_(None), include_aliases=True)
        )
        from app.infrastructure.database.base import Base
        from app.infrastructure.database.models import (
            ConstructionProject, ConstructionUnit, ConstructionMeasurement, ConstructionMeasurementItem,
            ConstructionMeasurementItemInspection,
        )

        for mapper in Base.registry.mappers:
            model = mapper.class_
            if issubclass(model, PreservedHistory):
                continue

            for key, parent in (('project_id', ConstructionProject), ('unit_id', ConstructionUnit),
                                ('measurement_id', ConstructionMeasurement),
                                ('measurement_item_id', ConstructionMeasurementItem),
                                ('inspection_id', ConstructionMeasurementItemInspection)):
                if key in mapper.columns:
                    table = parent.__table__
                    active = select(table.c.id).where(table.c.deleted_at.is_(None))
                    execution.statement = execution.statement.options(
                        with_loader_criteria(model, mapper.columns[key].in_(active), include_aliases=True)
                    )


def descendant_conditions(entity):
    from app.infrastructure.database.models import (
        ConstructionProject, ConstructionUnit, ConstructionMeasurement, ConstructionMeasurementItem,
        ConstructionMeasurementItemInspection, ConstructionMeasurementItemOccurrence,
    )

    conditions = {type(entity): type(entity).id == entity.id}
    if isinstance(entity, ConstructionProject):
        conditions[ConstructionUnit] = ConstructionUnit.project_id == entity.id
        conditions[ConstructionMeasurement] = ConstructionMeasurement.project_id == entity.id
    elif isinstance(entity, ConstructionUnit):
        conditions[ConstructionMeasurement] = ConstructionMeasurement.unit_id == entity.id

    if ConstructionMeasurement in conditions:
        measurements = select(ConstructionMeasurement.id).where(
            ConstructionMeasurement.company_id == entity.company_id, conditions[ConstructionMeasurement]
        )
        conditions[ConstructionMeasurementItem] = ConstructionMeasurementItem.measurement_id.in_(measurements)

    if ConstructionMeasurementItem in conditions:
        items = select(ConstructionMeasurementItem.id).where(
            ConstructionMeasurementItem.company_id == entity.company_id, conditions[ConstructionMeasurementItem]
        )
        conditions[ConstructionMeasurementItemInspection] = ConstructionMeasurementItemInspection.measurement_item_id.in_(items)
        conditions[ConstructionMeasurementItemOccurrence] = ConstructionMeasurementItemOccurrence.measurement_item_id.in_(items)

    return conditions


async def preserve_deletion(session, entity):
    actor = session.info.get("actor_user_id")
    now = datetime.now(UTC)
    for model, condition in reversed(list(descendant_conditions(entity).items())):
        await session.execute(
            update(model).where(model.company_id == entity.company_id, model.deleted_at.is_(None), condition)
            .values(deleted_at=now, deleted_by_user_id=actor)
            .execution_options(synchronize_session=False, include_deleted=True)
        )

    logger.info(f"[construction_history] deleted: company_id={entity.company_id} entity={entity.__tablename__} id={entity.id} actor={actor}")


async def protected_history(session, entity):
    from app.infrastructure.database.models import ConstructionMeasurement, ConstructionUnit, ConstructionProject

    await session.execute(select(type(entity).id).where(
        type(entity).id == entity.id, type(entity).company_id == entity.company_id
    ).with_for_update())
    conditions = descendant_conditions(entity)
    if ConstructionMeasurement in conditions:
        rows = await session.scalars(select(ConstructionMeasurement).where(
            ConstructionMeasurement.company_id == entity.company_id, conditions[ConstructionMeasurement]
        ).with_for_update().execution_options(populate_existing=True))
        if any(row.status in (ConstructionMeasurementStatus.APPROVED, ConstructionMeasurementStatus.PAID,
                              ConstructionMeasurementStatus.SUBMITTED, ConstructionMeasurementStatus.IN_APPROVAL) or
               row.external_accounts_payable_id is not None or row.reversal_pending for row in rows):
            return True

    if ConstructionUnit in conditions:
        units = (await session.scalars(select(ConstructionUnit).where(
            ConstructionUnit.company_id == entity.company_id, conditions[ConstructionUnit]
        ).with_for_update().execution_options(populate_existing=True))).all()
        if isinstance(entity, ConstructionProject) and units:
            return True

        if any(row.external_contract_id is not None or row.external_receivable_id is not None for row in units):
            return True

    return False
