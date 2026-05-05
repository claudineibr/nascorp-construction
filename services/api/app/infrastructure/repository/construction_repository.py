from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionMeasurement,
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
