from __future__ import annotations

from uuid import UUID

from decimal import Decimal

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.constants import ConstructionInspectionStatus, ConstructionOccurrenceStatus

from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionDocumentationType,
    ConstructionMeasurement,
    ConstructionServiceTemplate,
    ConstructionUnitCommission,
    ConstructionUnitDocumentation,
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

    async def replace_unit_children(
        self,
        model: type,
        *,
        company_id: UUID,
        unit_id: UUID,
        entities: list[object],
    ) -> None:
        """Troca todas as linhas filhas de uma unidade pelas novas.

        O DELETE sai como statement, antes dos INSERT, por construcao: o unit
        of work do SQLAlchemy emite os INSERT antes dos DELETE que ele mesmo
        agenda, e as tabelas de fonte e de documentacao tem unique por
        (unidade, tipo) -- editar a venda mantendo a mesma fonte estouraria.
        """
        await self.session.execute(
            delete(model).where(model.company_id == company_id, model.unit_id == unit_id)
        )
        for entity in entities:
            self.session.add(entity)

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

    async def _next_scoped_sequence(self, *, column, filters, lock_scope: str) -> int:
        """Reserva o proximo numero da serie, segurando quem chega junto.

        Ler o MAX e inserir depois e uma corrida contra o indice unico que essas
        series tem: dois pedidos simultaneos leem o mesmo numero, o segundo
        INSERT estoura `IntegrityError` e, como ninguem trata, o usuario ve um
        500 -- num "Lancar sinal" que ele so tentou duas vezes ao mesmo tempo.

        O advisory lock e por TRANSACAO: solta sozinho no commit e no rollback,
        entao nao ha lock vazado, e a chave e a propria serie -- duas unidades
        diferentes continuam alocando em paralelo.
        """
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": lock_scope},
        )
        result = await self.session.execute(select(func.max(column)).where(*filters))
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1

        return int(current_sequence) + 1

    async def get_next_measurement_sequence(self, *, company_id: UUID, project_id: UUID) -> int:
        return await self._next_scoped_sequence(
            column=ConstructionMeasurement.sequence_number,
            filters=(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.project_id == project_id,
            ),
            lock_scope=f"construction_measurements:{project_id}",
        )

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

    async def get_documentation_type(
        self,
        *,
        company_id: UUID,
        documentation_type_id: UUID,
    ) -> ConstructionDocumentationType | None:
        result = await self.session.execute(
            select(ConstructionDocumentationType).where(
                ConstructionDocumentationType.company_id == company_id,
                ConstructionDocumentationType.id == documentation_type_id,
            )
        )
        return result.scalars().first()

    async def get_documentation_type_by_normalized_name(
        self,
        *,
        company_id: UUID,
        normalized_name: str,
    ) -> ConstructionDocumentationType | None:
        result = await self.session.execute(
            select(ConstructionDocumentationType).where(
                ConstructionDocumentationType.company_id == company_id,
                ConstructionDocumentationType.normalized_name == normalized_name,
            )
        )
        return result.scalars().first()

    async def list_documentation_types(
        self,
        *,
        company_id: UUID,
        only_active: bool = True,
        search: str | None = None,
    ) -> list[ConstructionDocumentationType]:
        statement = select(ConstructionDocumentationType).where(
            ConstructionDocumentationType.company_id == company_id
        )
        if only_active:
            statement = statement.where(ConstructionDocumentationType.is_active.is_(True))

        if search:
            statement = statement.where(ConstructionDocumentationType.name.ilike(f"%{search}%"))

        result = await self.session.execute(statement.order_by(ConstructionDocumentationType.name))
        return list(result.scalars().all())

    async def list_documentation_types_by_system_codes(
        self,
        *,
        company_id: UUID,
        system_codes: list[str],
    ) -> list[ConstructionDocumentationType]:
        if not system_codes:
            return []

        result = await self.session.execute(
            select(ConstructionDocumentationType).where(
                ConstructionDocumentationType.company_id == company_id,
                ConstructionDocumentationType.system_code.in_(system_codes),
            )
        )
        return list(result.scalars().all())

    async def insert_documentation_type_if_absent(
        self,
        *,
        company_id: UUID,
        name: str,
        normalized_name: str,
    ) -> ConstructionDocumentationType | None:
        """Cria o tipo sem estourar quando outra requisicao criou o mesmo nome.

        O combobox da venda cria tipo digitando, entao dois usuarios lancando
        "SEG CAIXA" ao mesmo tempo e um caso real -- e um 500 por violacao de
        unique seria a unica pista. Devolve ``None`` quando a linha ja existia.
        """
        statement = (
            pg_insert(ConstructionDocumentationType)
            .values(company_id=company_id, name=name, normalized_name=normalized_name)
            .on_conflict_do_nothing(constraint="uq_construction_documentation_types_normalized_name")
            .returning(ConstructionDocumentationType)
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def upsert_documentation_type_system_code(
        self,
        *,
        company_id: UUID,
        name: str,
        normalized_name: str,
        system_code: str,
    ) -> ConstructionDocumentationType | None:
        """Semeia o tipo, ou carimba o ``system_code`` no que a empresa ja tinha.

        A empresa pode ter criado "Cartorio" a mao antes do seed. Um
        ``DO NOTHING`` descartaria o INSERT e o tipo nunca ganharia o codigo
        que o ETL usa para achar o de-para -- por isso o UPDATE, restrito a
        quem ainda nao tem codigo nenhum.

        Devolve ``None`` quando havia linha com esse nome e ela ja carregava
        outro ``system_code``: o de-para dela e escolha de quem a criou, e o
        seed nao sobrescreve.
        """
        statement = (
            pg_insert(ConstructionDocumentationType)
            .values(
                company_id=company_id,
                name=name,
                normalized_name=normalized_name,
                system_code=system_code,
            )
            .on_conflict_do_update(
                constraint="uq_construction_documentation_types_normalized_name",
                set_={"system_code": system_code},
                where=ConstructionDocumentationType.system_code.is_(None),
            )
            .returning(ConstructionDocumentationType)
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def list_unit_documentations(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
    ) -> list[ConstructionUnitDocumentation]:
        result = await self.session.execute(
            select(ConstructionUnitDocumentation)
            .options(selectinload(ConstructionUnitDocumentation.documentation_type))
            .where(
                ConstructionUnitDocumentation.company_id == company_id,
                ConstructionUnitDocumentation.unit_id == unit_id,
            )
            .order_by(ConstructionUnitDocumentation.sequence_number)
        )
        return list(result.scalars().all())

    async def list_unit_commissions(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
    ) -> list[ConstructionUnitCommission]:
        result = await self.session.execute(
            select(ConstructionUnitCommission)
            .where(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.unit_id == unit_id,
            )
            .order_by(ConstructionUnitCommission.sequence_number)
        )
        return list(result.scalars().all())

    async def get_unit_commission(
        self,
        *,
        company_id: UUID,
        commission_id: UUID,
    ) -> ConstructionUnitCommission | None:
        result = await self.session.execute(
            select(ConstructionUnitCommission).where(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.id == commission_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_next_commission_sequence(self, *, company_id: UUID, unit_id: UUID) -> int:
        return await self._next_scoped_sequence(
            column=ConstructionUnitCommission.sequence_number,
            filters=(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.unit_id == unit_id,
            ),
            lock_scope=f"construction_unit_commissions:{unit_id}",
        )

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
        return await self._next_scoped_sequence(
            column=ConstructionMeasurementItem.sequence_number,
            filters=(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
            ),
            lock_scope=f"construction_measurement_items:{measurement_id}",
        )

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
        return await self._next_scoped_sequence(
            column=ConstructionMeasurementItemInspection.sequence_number,
            filters=(
                ConstructionMeasurementItemInspection.company_id == company_id,
                ConstructionMeasurementItemInspection.measurement_item_id == measurement_item_id,
            ),
            lock_scope=f"construction_measurement_item_inspections:{measurement_item_id}",
        )

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
        return await self._next_scoped_sequence(
            column=ConstructionMeasurementItemOccurrence.sequence_number,
            filters=(
                ConstructionMeasurementItemOccurrence.company_id == company_id,
                ConstructionMeasurementItemOccurrence.measurement_item_id == measurement_item_id,
            ),
            lock_scope=f"construction_measurement_item_occurrences:{measurement_item_id}",
        )

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
