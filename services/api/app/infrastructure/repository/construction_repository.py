from __future__ import annotations

from uuid import UUID

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.constants import ConstructionInspectionStatus, ConstructionOccurrenceStatus

from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionMeasurement,
    ConstructionServiceTemplate,
    ConstructionUnitPaymentSource,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionMeasurementItemOccurrence,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionSchedulePhase,
    ConstructionUnit,
)


class ConstructionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entity: object) -> None:
        self.session.add(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)

    async def delete(self, entity: object) -> None:
        await self.session.delete(entity)

    async def get_project(self, *, company_id: UUID, project_id: UUID) -> ConstructionProject | None:
        result = await self.session.execute(
            select(ConstructionProject).where(
                ConstructionProject.company_id == company_id,
                ConstructionProject.id == project_id,
            )
        )
        return result.scalars().first()

    async def get_project_by_code(self, *, company_id: UUID, code: str) -> ConstructionProject | None:
        result = await self.session.execute(
            select(ConstructionProject).where(
                ConstructionProject.company_id == company_id,
                ConstructionProject.code == code,
            )
        )
        return result.scalars().first()

    async def list_projects(
        self,
        *,
        company_id: UUID,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConstructionProject], int]:
        conditions = [ConstructionProject.company_id == company_id]
        if search:
            search_pattern = f"%{search}%"
            conditions.append(ConstructionProject.name.ilike(search_pattern) | ConstructionProject.code.ilike(search_pattern))

        total_result = await self.session.execute(select(func.count()).select_from(ConstructionProject).where(*conditions))
        total = int(total_result.scalar_one())
        result = await self.session.execute(
            select(ConstructionProject)
            .where(*conditions)
            .order_by(ConstructionProject.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_block(self, *, company_id: UUID, block_id: UUID) -> ConstructionBlock | None:
        result = await self.session.execute(
            select(ConstructionBlock).where(
                ConstructionBlock.company_id == company_id,
                ConstructionBlock.id == block_id,
            )
        )
        return result.scalars().first()

    async def get_block_by_code(self, *, company_id: UUID, project_id: UUID, code: str) -> ConstructionBlock | None:
        result = await self.session.execute(
            select(ConstructionBlock).where(
                ConstructionBlock.company_id == company_id,
                ConstructionBlock.project_id == project_id,
                ConstructionBlock.code == code,
            )
        )
        return result.scalars().first()

    async def list_blocks(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionBlock]:
        result = await self.session.execute(
            select(ConstructionBlock)
            .where(
                ConstructionBlock.company_id == company_id,
                ConstructionBlock.project_id == project_id,
            )
            .order_by(ConstructionBlock.code)
        )
        return list(result.scalars().all())

    async def get_unit(self, *, company_id: UUID, unit_id: UUID) -> ConstructionUnit | None:
        result = await self.session.execute(
            select(ConstructionUnit).where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.id == unit_id,
            )
        )
        return result.scalars().first()

    async def get_unit_by_code(self, *, company_id: UUID, project_id: UUID, code: str) -> ConstructionUnit | None:
        result = await self.session.execute(
            select(ConstructionUnit).where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.project_id == project_id,
                ConstructionUnit.code == code,
            )
        )
        return result.scalars().first()

    async def get_unit_by_external_contract_id(
        self,
        *,
        company_id: UUID,
        external_contract_id: UUID,
    ) -> ConstructionUnit | None:
        result = await self.session.execute(
            select(ConstructionUnit).where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.external_contract_id == external_contract_id,
            )
        )
        return result.scalars().first()

    async def list_units(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionUnit]:
        result = await self.session.execute(
            select(ConstructionUnit)
            .where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.project_id == project_id,
            )
            .order_by(ConstructionUnit.code)
        )
        return list(result.scalars().all())

    async def get_schedule_phase(self, *, company_id: UUID, phase_id: UUID) -> ConstructionSchedulePhase | None:
        result = await self.session.execute(
            select(ConstructionSchedulePhase).where(
                ConstructionSchedulePhase.company_id == company_id,
                ConstructionSchedulePhase.id == phase_id,
            )
        )
        return result.scalars().first()

    async def get_schedule_phase_by_sequence(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        sequence_order: int,
    ) -> ConstructionSchedulePhase | None:
        result = await self.session.execute(
            select(ConstructionSchedulePhase).where(
                ConstructionSchedulePhase.company_id == company_id,
                ConstructionSchedulePhase.project_id == project_id,
                ConstructionSchedulePhase.sequence_order == sequence_order,
            )
        )
        return result.scalars().first()

    async def list_schedule_phases(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionSchedulePhase]:
        result = await self.session.execute(
            select(ConstructionSchedulePhase)
            .where(
                ConstructionSchedulePhase.company_id == company_id,
                ConstructionSchedulePhase.project_id == project_id,
            )
            .order_by(ConstructionSchedulePhase.sequence_order)
        )
        return list(result.scalars().all())

    async def get_measurement(self, *, company_id: UUID, measurement_id: UUID) -> ConstructionMeasurement | None:
        result = await self.session.execute(
            select(ConstructionMeasurement).where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.id == measurement_id,
            )
        )
        return result.scalars().first()

    async def get_measurement_by_code(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        code: str,
    ) -> ConstructionMeasurement | None:
        result = await self.session.execute(
            select(ConstructionMeasurement).where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.project_id == project_id,
                ConstructionMeasurement.code == code,
            )
        )
        return result.scalars().first()

    async def get_next_measurement_sequence(self, *, company_id: UUID, project_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(ConstructionMeasurement.sequence_number)).where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.project_id == project_id,
            )
        )
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1

        return int(current_sequence) + 1

    async def get_measurement_by_external_accounts_payable_id(
        self,
        *,
        company_id: UUID,
        accounts_payable_id: UUID,
    ) -> ConstructionMeasurement | None:
        result = await self.session.execute(
            select(ConstructionMeasurement).where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.external_accounts_payable_id == accounts_payable_id,
            )
        )
        return result.scalars().first()

    async def list_measurements(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionMeasurement]:
        result = await self.session.execute(
            select(ConstructionMeasurement)
            .where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.project_id == project_id,
            )
            .order_by(ConstructionMeasurement.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_unit_payment_sources(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
    ) -> list[ConstructionUnitPaymentSource]:
        result = await self.session.execute(
            select(ConstructionUnitPaymentSource)
            .where(
                ConstructionUnitPaymentSource.company_id == company_id,
                ConstructionUnitPaymentSource.unit_id == unit_id,
            )
            .order_by(ConstructionUnitPaymentSource.source_type)
        )
        return list(result.scalars().all())

    async def get_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
    ) -> ConstructionServiceTemplate | None:
        result = await self.session.execute(
            select(ConstructionServiceTemplate)
            .options(selectinload(ConstructionServiceTemplate.items))
            .where(
                ConstructionServiceTemplate.company_id == company_id,
                ConstructionServiceTemplate.id == service_template_id,
            )
        )
        return result.scalars().first()

    async def get_service_template_by_name(
        self,
        *,
        company_id: UUID,
        name: str,
    ) -> ConstructionServiceTemplate | None:
        result = await self.session.execute(
            select(ConstructionServiceTemplate)
            .options(selectinload(ConstructionServiceTemplate.items))
            .where(
                ConstructionServiceTemplate.company_id == company_id,
                ConstructionServiceTemplate.name == name,
            )
        )
        return result.scalars().first()

    async def list_service_templates(
        self,
        *,
        company_id: UUID,
        only_active: bool = True,
        search: str | None = None,
    ) -> list[ConstructionServiceTemplate]:
        statement = (
            select(ConstructionServiceTemplate)
            .options(selectinload(ConstructionServiceTemplate.items))
            .where(ConstructionServiceTemplate.company_id == company_id)
        )
        if only_active:
            statement = statement.where(ConstructionServiceTemplate.is_active.is_(True))

        if search:
            statement = statement.where(ConstructionServiceTemplate.name.ilike(f"%{search}%"))

        result = await self.session.execute(statement.order_by(ConstructionServiceTemplate.name))
        return list(result.scalars().all())

    async def get_measurement_item(
        self,
        *,
        company_id: UUID,
        item_id: UUID,
    ) -> ConstructionMeasurementItem | None:
        result = await self.session.execute(
            select(ConstructionMeasurementItem)
            .options(
                selectinload(ConstructionMeasurementItem.inspections),
                selectinload(ConstructionMeasurementItem.occurrences),
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.id == item_id,
            )
        )
        return result.scalars().first()

    async def list_measurement_items(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
    ) -> list[ConstructionMeasurementItem]:
        result = await self.session.execute(
            select(ConstructionMeasurementItem)
            .options(
                selectinload(ConstructionMeasurementItem.inspections),
                selectinload(ConstructionMeasurementItem.occurrences),
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
            )
            .order_by(ConstructionMeasurementItem.sequence_number)
        )
        return list(result.scalars().all())

    async def get_next_measurement_item_sequence(self, *, company_id: UUID, measurement_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(ConstructionMeasurementItem.sequence_number)).where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
            )
        )
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1

        return int(current_sequence) + 1

    async def get_measurement_items_amount(self, *, company_id: UUID, measurement_id: UUID) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(ConstructionMeasurementItem.amount), 0)).where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
            )
        )
        return Decimal(str(result.scalar_one()))

    async def get_measurement_inspection(
        self,
        *,
        company_id: UUID,
        inspection_id: UUID,
    ) -> ConstructionMeasurementItemInspection | None:
        result = await self.session.execute(
            select(ConstructionMeasurementItemInspection).where(
                ConstructionMeasurementItemInspection.company_id == company_id,
                ConstructionMeasurementItemInspection.id == inspection_id,
            )
        )
        return result.scalars().first()

    async def list_measurement_item_inspections(
        self,
        *,
        company_id: UUID,
        measurement_item_id: UUID,
    ) -> list[ConstructionMeasurementItemInspection]:
        result = await self.session.execute(
            select(ConstructionMeasurementItemInspection)
            .where(
                ConstructionMeasurementItemInspection.company_id == company_id,
                ConstructionMeasurementItemInspection.measurement_item_id == measurement_item_id,
            )
            .order_by(ConstructionMeasurementItemInspection.sequence_number)
        )
        return list(result.scalars().all())

    async def get_next_inspection_sequence(self, *, company_id: UUID, measurement_item_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(ConstructionMeasurementItemInspection.sequence_number)).where(
                ConstructionMeasurementItemInspection.company_id == company_id,
                ConstructionMeasurementItemInspection.measurement_item_id == measurement_item_id,
            )
        )
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1

        return int(current_sequence) + 1

    async def count_pending_measurement_inspections(self, *, company_id: UUID, measurement_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ConstructionMeasurementItemInspection)
            .join(
                ConstructionMeasurementItem,
                ConstructionMeasurementItem.id == ConstructionMeasurementItemInspection.measurement_item_id,
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
                or_(
                    ConstructionMeasurementItemInspection.first_status == ConstructionInspectionStatus.PENDING,
                    ConstructionMeasurementItemInspection.second_status == ConstructionInspectionStatus.PENDING,
                ),
            )
        )
        return int(result.scalar_one())

    async def get_measurement_occurrence(
        self,
        *,
        company_id: UUID,
        occurrence_id: UUID,
    ) -> ConstructionMeasurementItemOccurrence | None:
        result = await self.session.execute(
            select(ConstructionMeasurementItemOccurrence).where(
                ConstructionMeasurementItemOccurrence.company_id == company_id,
                ConstructionMeasurementItemOccurrence.id == occurrence_id,
            )
        )
        return result.scalars().first()

    async def get_next_occurrence_sequence(self, *, company_id: UUID, measurement_item_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(ConstructionMeasurementItemOccurrence.sequence_number)).where(
                ConstructionMeasurementItemOccurrence.company_id == company_id,
                ConstructionMeasurementItemOccurrence.measurement_item_id == measurement_item_id,
            )
        )
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1

        return int(current_sequence) + 1

    async def count_open_measurement_occurrences(self, *, company_id: UUID, measurement_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ConstructionMeasurementItemOccurrence)
            .join(
                ConstructionMeasurementItem,
                ConstructionMeasurementItem.id == ConstructionMeasurementItemOccurrence.measurement_item_id,
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
                ConstructionMeasurementItemOccurrence.status == ConstructionOccurrenceStatus.OPEN,
            )
        )
        return int(result.scalar_one())

    async def get_procurement_request(
        self,
        *,
        company_id: UUID,
        procurement_request_id: UUID,
    ) -> ConstructionProcurementRequest | None:
        result = await self.session.execute(
            select(ConstructionProcurementRequest).where(
                ConstructionProcurementRequest.company_id == company_id,
                ConstructionProcurementRequest.id == procurement_request_id,
            )
        )
        return result.scalars().first()

    async def get_procurement_request_by_code(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        code: str,
    ) -> ConstructionProcurementRequest | None:
        result = await self.session.execute(
            select(ConstructionProcurementRequest).where(
                ConstructionProcurementRequest.company_id == company_id,
                ConstructionProcurementRequest.project_id == project_id,
                ConstructionProcurementRequest.code == code,
            )
        )
        return result.scalars().first()

    async def list_procurement_requests(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
    ) -> list[ConstructionProcurementRequest]:
        result = await self.session.execute(
            select(ConstructionProcurementRequest)
            .where(
                ConstructionProcurementRequest.company_id == company_id,
                ConstructionProcurementRequest.project_id == project_id,
            )
            .order_by(ConstructionProcurementRequest.created_at.desc())
        )
        return list(result.scalars().all())
