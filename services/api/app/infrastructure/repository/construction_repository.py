from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from decimal import Decimal

from sqlalchemy import Integer, and_, cast, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.constants import (
    ConstructionInspectionStatus,
    ConstructionMeasurementStatus,
    ConstructionOccurrenceStatus,
    ConstructionUnitStatus,
)
from app.infrastructure.repository._project_scope_filters import scope_conditions
from app.infrastructure.database.history import PreservedHistory
from app.infrastructure.repository._history import preserve_deletion, protected_history
from app.domain.events.constants import ConstructionEventType

from app.infrastructure.database.models import (
    ConstructionBlock,
    ConstructionDocumentationType,
    ConstructionInspectionRound,
    ConstructionMeasurement,
    ConstructionServiceTemplate,
    ConstructionServiceTemplateAudit,
    ConstructionServiceTemplateSection,
    ConstructionUnitCommission,
    ConstructionUnitDocumentation,
    ConstructionUnitPaymentSource,
    ConstructionUnitSale,
    ConstructionMeasurementItem,
    ConstructionMeasurementItemInspection,
    ConstructionMeasurementItemOccurrence,
    ConstructionProcurementRequest,
    ConstructionProject,
    ConstructionProjectServiceTemplate,
    ConstructionSchedulePhase,
    ConstructionUnit,
)

BUYER_HOLDING_UNIT_STATUSES = (
    ConstructionUnitStatus.RESERVED,
    ConstructionUnitStatus.SOLD,
    ConstructionUnitStatus.DELIVERED,
)


def _buyer_unit_conditions(buyer_person_id: UUID) -> list:
    return [
        or_(
            ConstructionUnit.buyer_person_id == buyer_person_id,
            ConstructionUnit.secondary_buyer_person_id == buyer_person_id,
        ),
        ConstructionUnit.status.in_(BUYER_HOLDING_UNIT_STATUSES),
    ]


logger = logging.getLogger(__name__)


class ConstructionRepository:
    """As consultas de Obras, ja limitadas as obras que o ator enxerga.

    O escopo entra AQUI, e nao nas 79 rotas: `ConstructionProjectService` tem
    118 metodos async e 103 deles recebem `company_id` -- filtrar la seria 103
    chances de esquecer uma. O repositorio e o unico caminho ate o banco.

    `scope=None` e irrestrito de proposito: e o que o handler de evento interno
    usa, porque evento vindo do ERP nao tem pessoa a quem restringir.

    Tres familias de consulta ficam DE FORA do filtro, e nenhuma por esquecimento:

    1. **Os `*_by_code`.** Sao guarda de unicidade, nao leitura. Esconder a obra
       de codigo ja usado faria o servico seguir e o INSERT estourar no indice
       unico -- um 500 no lugar do "codigo ja existe". O que vaza e a existencia
       do codigo, e so para quem ja tentou criar aquele codigo.
    2. **Os geradores de sequencia** (`_next_scoped_sequence`). Filtrar o MAX
       devolveria um numero ja usado por uma linha fora do escopo -- duplicata
       no indice unico, que e justamente a corrida que o advisory lock evita.
    3. **As contagens de bloqueio** (inspecao pendente, ocorrencia aberta, item
       usando o servico). Sao guarda de fechamento e de exclusao: contagem
       filtrada CONTA MENOS, e contar menos aqui libera o que devia travar.
    """

    def __init__(self, session: AsyncSession, scope=None) -> None:
        self.session = session
        self.scope = scope

    async def add(self, entity: object) -> None:
        self.session.add(entity)

    async def flush(self):
        await self.session.flush()

    async def lock_service_template(self, company_id, template_id):
        return await self.session.scalar(select(ConstructionServiceTemplate).where(
            ConstructionServiceTemplate.company_id == company_id,
            ConstructionServiceTemplate.id == template_id,
            *scope_conditions(ConstructionServiceTemplate, self.scope),
        ).with_for_update())

    async def lock_measurement(self, company_id, measurement_id):
        return await self.session.scalar(select(ConstructionMeasurement).where(
            ConstructionMeasurement.company_id == company_id,
            ConstructionMeasurement.id == measurement_id,
            *scope_conditions(ConstructionMeasurement, self.scope),
        ).with_for_update().execution_options(populate_existing=True))

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)

    async def delete(self, entity: object) -> None:
        if isinstance(entity, PreservedHistory):
            await preserve_deletion(self.session, entity)
        else:
            await self.session.delete(entity)

    async def has_protected_history(self, entity):
        return await protected_history(self.session, entity)

    async def lock_integration_aggregate(self, event):
        model = {
            ConstructionEventType.PROJECT_CREATED: ConstructionProject,
            ConstructionEventType.UNIT_CREATED: ConstructionUnit,
            ConstructionEventType.UNIT_SOLD: ConstructionUnit,
            ConstructionEventType.UNIT_STATUS_CHANGED: ConstructionUnit,
        }[event.event_type]
        return await self.session.scalar(select(model).where(
            model.company_id == event.company_id, model.id == event.aggregate_id
        ).with_for_update().execution_options(populate_existing=True))

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
                *scope_conditions(ConstructionProject, self.scope),
            )
        )
        return result.scalars().first()

    async def get_project_by_code(self, *, company_id: UUID, code: str) -> ConstructionProject | None:
        result = await self.session.execute(
            select(ConstructionProject).where(
                ConstructionProject.company_id == company_id,
                ConstructionProject.code == code,
            ).execution_options(include_deleted=True)
        )
        return result.scalars().first()

    async def list_projects(
        self,
        *,
        company_id: UUID,
        search: str | None,
        status: str | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
        buyer_person_id: UUID | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConstructionProject], int]:
        conditions = [
            ConstructionProject.company_id == company_id,
            *scope_conditions(ConstructionProject, self.scope),
        ]
        if search:
            search_pattern = f"%{search}%"
            conditions.append(ConstructionProject.name.ilike(search_pattern) | ConstructionProject.code.ilike(search_pattern))
        if status:
            conditions.append(ConstructionProject.status == status)
        # A tela sempre filtrou por `start_date`, inclusive no campo chamado
        # "Inicio final": e a janela em que a obra COMECOU, nao o fim dela.
        if start_date_from is not None:
            conditions.append(ConstructionProject.start_date >= start_date_from)
        if start_date_to is not None:
            conditions.append(ConstructionProject.start_date <= start_date_to)
        if buyer_person_id is not None:
            conditions.append(
                select(ConstructionUnit.id)
                .where(
                    ConstructionUnit.project_id == ConstructionProject.id,
                    *_buyer_unit_conditions(buyer_person_id),
                )
                .exists()
            )

        total_result = await self.session.execute(select(func.count()).select_from(ConstructionProject).where(*conditions))
        total = int(total_result.scalar_one())
        result = await self.session.execute(
            select(ConstructionProject)
            .where(*conditions)
            # `created_at` NAO desempata: no Postgres o `now()` e o mesmo para a
            # transacao inteira, e as 77 obras da carga do MFCON entraram com o
            # timestamp identico -- medido. Ordenar so por ele deixa o banco
            # livre para devolver qualquer ordem, e com OFFSET a mesma obra
            # aparece na pagina 1 e some na 2. O `code` e UNIQUE por empresa.
            .order_by(ConstructionProject.created_at.desc(), ConstructionProject.code.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_buyer_units(
        self,
        *,
        company_id: UUID,
        project_ids: list[UUID],
        buyer_person_id: UUID,
    ) -> list:
        if not project_ids:
            return []
        result = await self.session.execute(
            select(
                ConstructionUnit.project_id,
                ConstructionUnit.id.label("unit_id"),
                ConstructionUnit.code,
                ConstructionBlock.name.label("block_name"),
                ConstructionUnit.status,
                ConstructionUnit.buyer_person_id.is_distinct_from(buyer_person_id).label("is_secondary_buyer"),
            )
            .outerjoin(ConstructionBlock, ConstructionBlock.id == ConstructionUnit.block_id)
            .where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.project_id.in_(project_ids),
                *_buyer_unit_conditions(buyer_person_id),
            )
            .order_by(ConstructionBlock.name.asc().nulls_first(), ConstructionUnit.code.asc())
        )
        return list(result.all())

    async def get_block(self, *, company_id: UUID, block_id: UUID) -> ConstructionBlock | None:
        result = await self.session.execute(
            select(ConstructionBlock).where(
                ConstructionBlock.company_id == company_id,
                ConstructionBlock.id == block_id,
                *scope_conditions(ConstructionBlock, self.scope),
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
                *scope_conditions(ConstructionBlock, self.scope),
            )
            .order_by(ConstructionBlock.code)
        )
        return list(result.scalars().all())

    async def get_unit(self, *, company_id: UUID, unit_id: UUID) -> ConstructionUnit | None:
        result = await self.session.execute(
            select(ConstructionUnit).where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.id == unit_id,
                *scope_conditions(ConstructionUnit, self.scope),
            )
        )
        return result.scalars().first()

    async def get_unit_sale(self, *, company_id, sale_id, lock=False):
        stmt = select(ConstructionUnitSale).where(
            ConstructionUnitSale.company_id == company_id,
            ConstructionUnitSale.id == sale_id,
            *scope_conditions(ConstructionUnitSale, self.scope),
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def list_unit_sales(self, *, company_id, unit_id):
        result = await self.session.execute(
            select(ConstructionUnitSale)
            .where(
                ConstructionUnitSale.company_id == company_id,
                ConstructionUnitSale.unit_id == unit_id,
                *scope_conditions(ConstructionUnitSale, self.scope),
            )
            .order_by(
                (ConstructionUnitSale.status != "ACTIVE").asc(),
                ConstructionUnitSale.sold_at.desc().nulls_last(),
                ConstructionUnitSale.sequence.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_latest_native_terminated_sale(self, *, company_id, unit_id):
        return await self.session.scalar(
            select(ConstructionUnitSale)
            .where(
                ConstructionUnitSale.company_id == company_id,
                ConstructionUnitSale.unit_id == unit_id,
                ConstructionUnitSale.status == "TERMINATED",
                ConstructionUnitSale.source == "NATIVE",
                ConstructionUnitSale.external_termination_id.is_not(None),
                *scope_conditions(ConstructionUnitSale, self.scope),
            )
            .order_by(
                ConstructionUnitSale.terminated_at.desc().nulls_last(),
                ConstructionUnitSale.sequence.desc(),
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def next_unit_sale_sequence(self, *, company_id, unit_id) -> int:
        return await self._next_scoped_sequence(
            column=ConstructionUnitSale.sequence,
            filters=(
                ConstructionUnitSale.company_id == company_id,
                ConstructionUnitSale.unit_id == unit_id,
            ),
            lock_scope=f"construction_unit_sales:{unit_id}",
        )

    async def lock_unit(self, *, company_id, unit_id):
        return await self.session.scalar(select(ConstructionUnit).where(
            ConstructionUnit.company_id == company_id,
            ConstructionUnit.id == unit_id,
            ConstructionUnit.deleted_at.is_(None),
            *scope_conditions(ConstructionUnit, self.scope),
        ).with_for_update().execution_options(populate_existing=True))

    async def get_company_timezone(self, *, company_id):
        result = await self.session.execute(
            text("SELECT timezone FROM public.companies WHERE id=:company AND deleted_at IS NULL"),
            {"company": company_id},
        )
        return result.scalar_one_or_none()

    async def valid_contract_template(self, company_id, template_id):
        result = await self.session.execute(text("SELECT id FROM public.contract_templates WHERE id=:template AND company_id=:company AND document_type='unit_sale' AND deleted_at IS NULL AND is_active=true AND file_path IS NOT NULL"),
            {"template": template_id, "company": company_id})
        return result.scalar_one_or_none()

    async def valid_receipt_template(self, company_id, template_id):
        result = await self.session.execute(text("SELECT id FROM public.receipt_templates WHERE id=:template AND company_id=:company AND deleted_at IS NULL AND is_active=true"),
            {"template": template_id, "company": company_id})
        return result.scalar_one_or_none()

    async def contract_context(self, company_id, unit_id):
        unit = await self.get_unit(company_id=company_id, unit_id=unit_id)
        if not unit:
            return None
        project = await self.get_project(company_id=company_id, project_id=unit.project_id)
        signals = await self.session.execute(select(ConstructionUnitCommission).where(
            ConstructionUnitCommission.company_id == company_id, ConstructionUnitCommission.unit_id == unit_id,
            self._sale_commission_condition(unit.current_sale_id)))
        documentation = await self.session.execute(select(ConstructionUnitDocumentation).where(
            ConstructionUnitDocumentation.company_id == company_id, ConstructionUnitDocumentation.unit_id == unit_id))
        return {"unit": {key: getattr(unit, key) for key in ("id", "project_id", "code", "description", "sale_price",
                    "discount_amount", "buyer_person_id", "secondary_buyer_person_id", "broker_person_id", "external_contract_id")},
                "project": {key: getattr(project, key) for key in ("id", "name", "contract_template_id", "lot",
                    "registration", "land_area", "expected_end_date", "address_json")},
                "signals": [{"amount": row.amount, "due_date": row.due_date} for row in signals.scalars()],
                "documentation": [{"amount": row.amount} for row in documentation.scalars()]}

    async def get_unit_by_code(self, *, company_id: UUID, project_id: UUID, code: str) -> ConstructionUnit | None:
        result = await self.session.execute(
            select(ConstructionUnit).where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.project_id == project_id,
                ConstructionUnit.code == code,
            ).execution_options(include_deleted=True)
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
                *scope_conditions(ConstructionUnit, self.scope),
            )
        )
        return result.scalars().first()

    async def list_units(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionUnit]:
        result = await self.session.execute(
            select(ConstructionUnit)
            .where(
                ConstructionUnit.company_id == company_id,
                ConstructionUnit.project_id == project_id,
                *scope_conditions(ConstructionUnit, self.scope),
            )
            .order_by(ConstructionUnit.code)
        )
        return list(result.scalars().all())

    async def get_schedule_phase(self, *, company_id: UUID, phase_id: UUID) -> ConstructionSchedulePhase | None:
        result = await self.session.execute(
            select(ConstructionSchedulePhase).where(
                ConstructionSchedulePhase.company_id == company_id,
                ConstructionSchedulePhase.id == phase_id,
                *scope_conditions(ConstructionSchedulePhase, self.scope),
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
                *scope_conditions(ConstructionSchedulePhase, self.scope),
            )
            .order_by(ConstructionSchedulePhase.sequence_order)
        )
        return list(result.scalars().all())

    async def get_measurement(self, *, company_id: UUID, measurement_id: UUID) -> ConstructionMeasurement | None:
        result = await self.session.execute(
            select(ConstructionMeasurement).where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.id == measurement_id,
                *scope_conditions(ConstructionMeasurement, self.scope),
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
        result = await self.session.execute(select(func.max(column)).where(*filters).execution_options(include_deleted=True))
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1

        return int(current_sequence) + 1

    async def get_next_measurement_sequence(self, *, company_id: UUID, unit_id: UUID) -> int:
        return await self._next_scoped_sequence(
            column=ConstructionMeasurement.sequence_number,
            filters=(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.unit_id == unit_id,
            ),
            lock_scope=f"construction_measurements:unit:{unit_id}",
        )

    async def get_next_measurement_code_number(self, *, company_id: UUID, project_id: UUID) -> int:
        return await self._next_scoped_sequence(
            column=cast(func.substring(ConstructionMeasurement.code, 5), Integer),
            filters=(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.project_id == project_id,
                ConstructionMeasurement.code.regexp_match(r"^MED-[0-9]{1,9}$"),
            ),
            lock_scope=f"construction_measurements:code:{project_id}",
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
                *scope_conditions(ConstructionMeasurement, self.scope),
            )
        )
        return result.scalars().first()

    async def list_measurements(self, *, company_id: UUID, project_id: UUID) -> list[ConstructionMeasurement]:
        result = await self.session.execute(
            select(ConstructionMeasurement)
            .where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.project_id == project_id,
                *scope_conditions(ConstructionMeasurement, self.scope),
            )
            .order_by(ConstructionMeasurement.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_measurements_by_ids(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        measurement_ids: list[UUID],
        lock: bool = False,
    ) -> list[ConstructionMeasurement]:
        query = select(ConstructionMeasurement).where(
            ConstructionMeasurement.company_id == company_id,
            ConstructionMeasurement.project_id == project_id,
            ConstructionMeasurement.id.in_(measurement_ids),
            *scope_conditions(ConstructionMeasurement, self.scope),
        )
        if lock:
            query = query.order_by(ConstructionMeasurement.id).with_for_update().execution_options(populate_existing=True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def lock_shared_payable(self, *, company_id: UUID, payable_document_id: UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"shared-payable:{company_id}:{payable_document_id}"},
        )

    async def shared_payable_contract_ids(
        self, *, company_id: UUID, payable_document_id: UUID, exclude_measurement_ids: list[UUID]
    ) -> set[UUID | None]:
        result = await self.session.execute(
            select(func.coalesce(ConstructionMeasurement.subcontract_id, ConstructionMeasurement.global_contract_id))
            .where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.external_accounts_payable_id == payable_document_id,
                ConstructionMeasurement.external_accounts_payable_shared.is_(True),
                ConstructionMeasurement.id.not_in(exclude_measurement_ids),
            )
            .distinct()
        )
        return set(result.scalars().all())

    def _zero_value_measurement_conditions(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        supplier_person_id: UUID | None = None,
        payable_document_id: UUID | None = None,
        block_id: UUID | None = None,
        unit_search: str | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        search: str | None = None,
        subcontract_id: UUID | None = None,
    ) -> list:
        amount = func.coalesce(ConstructionMeasurement.net_amount, ConstructionMeasurement.measured_amount, 0)
        conditions = [
            ConstructionMeasurement.company_id == company_id,
            ConstructionMeasurement.project_id == project_id,
            ConstructionMeasurement.status == ConstructionMeasurementStatus.APPROVED,
            *scope_conditions(ConstructionMeasurement, self.scope),
        ]
        if subcontract_id is not None:
            conditions.extend([
                or_(
                    ConstructionMeasurement.subcontract_id == subcontract_id,
                    ConstructionMeasurement.global_contract_id == subcontract_id,
                ),
                ConstructionMeasurement.reversal_pending.is_(False),
            ])
        elif payable_document_id is None:
            conditions.extend([
                ConstructionMeasurement.subcontract_id.is_(None),
                ConstructionMeasurement.global_contract_id.is_(None),
                amount == 0,
            ])
        if payable_document_id is None:
            conditions.append(ConstructionMeasurement.external_accounts_payable_id.is_(None))
        else:
            conditions.append(ConstructionMeasurement.external_accounts_payable_id == payable_document_id)
            conditions.append(ConstructionMeasurement.external_accounts_payable_shared.is_(True))
        if supplier_person_id is not None:
            conditions.append(ConstructionMeasurement.supplier_person_id == supplier_person_id)
        if block_id is not None:
            conditions.append(ConstructionUnit.block_id == block_id)
        if unit_search:
            pattern = f"%{unit_search.strip()}%"
            conditions.append(or_(ConstructionUnit.code.ilike(pattern), ConstructionUnit.description.ilike(pattern)))
        if due_from is not None:
            conditions.append(ConstructionMeasurement.due_date >= due_from)
        if due_to is not None:
            conditions.append(ConstructionMeasurement.due_date <= due_to)
        if search:
            term = search.strip()
            if term.isdigit():
                conditions.append(
                    or_(
                        ConstructionMeasurement.sequence_number == int(term),
                        ConstructionMeasurement.code == f"OS-{int(term):06d}",
                    )
                )
            else:
                conditions.append(ConstructionMeasurement.code.ilike(f"%{term}%"))
        return conditions

    async def list_zero_value_measurements(
        self,
        *,
        page: int,
        page_size: int,
        **filters,
    ) -> tuple[list[dict], int]:
        conditions = self._zero_value_measurement_conditions(**filters)
        unit_join = ConstructionUnit.id == ConstructionMeasurement.unit_id
        total = await self.session.scalar(
            select(func.count())
            .select_from(ConstructionMeasurement)
            .outerjoin(ConstructionUnit, unit_join)
            .where(*conditions)
        )
        result = await self.session.execute(
            select(
                ConstructionMeasurement,
                ConstructionUnit.code.label("unit_code"),
                ConstructionUnit.description.label("unit_description"),
                ConstructionUnit.block_id.label("block_id"),
                ConstructionBlock.name.label("block_name"),
            )
            .outerjoin(ConstructionUnit, unit_join)
            .outerjoin(ConstructionBlock, ConstructionBlock.id == ConstructionUnit.block_id)
            .where(*conditions)
            .order_by(ConstructionUnit.code, ConstructionMeasurement.sequence_number, ConstructionMeasurement.code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [
            {
                "id": measurement.id,
                "code": measurement.code,
                "sequence_number": measurement.sequence_number,
                "unit_id": measurement.unit_id,
                "unit_code": unit_code,
                "unit_description": unit_description,
                "block_id": block_id,
                "block_name": block_name,
                "due_date": measurement.due_date,
                "competence_date": measurement.competence_date,
                "description": measurement.description,
                "supplier_person_id": measurement.supplier_person_id,
                "external_accounts_payable_id": measurement.external_accounts_payable_id,
                "net_amount": measurement.net_amount if measurement.net_amount is not None else measurement.measured_amount,
            }
            for measurement, unit_code, unit_description, block_id, block_name in result.all()
        ]
        return rows, int(total or 0)

    async def zero_value_measurement_ids(self, *, limit: int, **filters) -> list[UUID]:
        conditions = self._zero_value_measurement_conditions(**filters)
        result = await self.session.execute(
            select(ConstructionMeasurement.id)
            .outerjoin(ConstructionUnit, ConstructionUnit.id == ConstructionMeasurement.unit_id)
            .where(*conditions)
            .order_by(ConstructionUnit.code, ConstructionMeasurement.sequence_number, ConstructionMeasurement.code)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def shared_payable_net_total(
        self, *, company_id: UUID, payable_document_id: UUID, exclude_measurement_ids: list[UUID]
    ) -> Decimal:
        total = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(func.coalesce(ConstructionMeasurement.net_amount, ConstructionMeasurement.measured_amount, 0)),
                    0,
                )
            ).where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.external_accounts_payable_id == payable_document_id,
                ConstructionMeasurement.external_accounts_payable_shared.is_(True),
                ConstructionMeasurement.id.not_in(exclude_measurement_ids),
            )
        )
        return Decimal(total or 0)

    async def zero_value_suppliers(self, *, company_id: UUID, project_id: UUID) -> list[tuple[UUID, int]]:
        conditions = self._zero_value_measurement_conditions(company_id=company_id, project_id=project_id)
        result = await self.session.execute(
            select(ConstructionMeasurement.supplier_person_id, func.count())
            .where(*conditions, ConstructionMeasurement.supplier_person_id.is_not(None))
            .group_by(ConstructionMeasurement.supplier_person_id)
            .order_by(func.count().desc())
        )
        return [(supplier_id, int(count)) for supplier_id, count in result.all()]

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
                *scope_conditions(ConstructionUnitPaymentSource, self.scope),
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
                *scope_conditions(ConstructionUnitDocumentation, self.scope),
            )
            .order_by(ConstructionUnitDocumentation.sequence_number)
        )
        return list(result.scalars().all())

    @staticmethod
    def _sale_commission_condition(sale_id):
        if sale_id is None:
            return ConstructionUnitCommission.sale_id.is_(None)
        return or_(ConstructionUnitCommission.sale_id.is_(None), ConstructionUnitCommission.sale_id == sale_id)

    async def delete_unpaid_unit_commissions(self, *, company_id, unit_id, sale_id):
        commissions = list((await self.session.scalars(
            select(ConstructionUnitCommission).where(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.unit_id == unit_id,
                ConstructionUnitCommission.payment_date.is_(None),
                self._sale_commission_condition(sale_id),
                *scope_conditions(ConstructionUnitCommission, self.scope),
            ).order_by(ConstructionUnitCommission.sequence_number)
        )).all())
        if commissions:
            await self.session.execute(
                update(ConstructionUnitCommission).where(
                    ConstructionUnitCommission.company_id == company_id,
                    ConstructionUnitCommission.id.in_([commission.id for commission in commissions]),
                    ConstructionUnitCommission.deleted_at.is_(None),
                ).values(
                    deleted_at=datetime.now(UTC),
                    deleted_by_user_id=self.session.info.get("actor_user_id"),
                ).execution_options(synchronize_session=False)
            )
        logger.info(
            f"[construction_commission] delete_unpaid: company_id={company_id} "
            f"unit_id={unit_id} sale_id={sale_id} count={len(commissions)}"
        )
        return commissions

    async def restore_unit_commissions(self, *, company_id, unit_id, sale_id, commission_ids):
        if not commission_ids:
            return set()
        result = await self.session.execute(
            update(ConstructionUnitCommission).where(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.unit_id == unit_id,
                ConstructionUnitCommission.id.in_(commission_ids),
                ConstructionUnitCommission.deleted_at.is_not(None),
            ).values(deleted_at=None, deleted_by_user_id=None, sale_id=sale_id)
            .returning(ConstructionUnitCommission.id)
            .execution_options(synchronize_session=False, include_deleted=True)
        )
        restored = set(result.scalars().all())
        logger.info(
            f"[construction_commission] restore: company_id={company_id} unit_id={unit_id} "
            f"sale_id={sale_id} requested={len(commission_ids)} restored={len(restored)}"
        )
        return restored

    async def attach_unit_commissions_to_sale(self, *, company_id, unit_id, sale_id):
        await self.session.execute(
            update(ConstructionUnitCommission).where(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.unit_id == unit_id,
                ConstructionUnitCommission.sale_id.is_(None),
                ConstructionUnitCommission.deleted_at.is_(None),
            ).values(sale_id=sale_id).execution_options(synchronize_session=False)
        )

    async def list_unit_commissions(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        sale_id: UUID | None,
    ) -> list[ConstructionUnitCommission]:
        result = await self.session.execute(
            select(ConstructionUnitCommission)
            .where(
                ConstructionUnitCommission.company_id == company_id,
                ConstructionUnitCommission.unit_id == unit_id,
                ConstructionUnitCommission.unit.has(ConstructionUnit.deleted_at.is_(None)),
                self._sale_commission_condition(sale_id),
                *scope_conditions(ConstructionUnitCommission, self.scope),
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
                ConstructionUnitCommission.unit.has(ConstructionUnit.deleted_at.is_(None)),
                *scope_conditions(ConstructionUnitCommission, self.scope),
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

    @staticmethod
    def _service_template_loaders() -> tuple:
        return (
            selectinload(ConstructionServiceTemplate.sections).selectinload(
                ConstructionServiceTemplateSection.items
            ),
            selectinload(ConstructionServiceTemplate.items),
        )

    async def get_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        include_deleted: bool = False,
    ) -> ConstructionServiceTemplate | None:
        statement = (
            select(ConstructionServiceTemplate)
            .options(*self._service_template_loaders())
            .where(
                ConstructionServiceTemplate.company_id == company_id,
                ConstructionServiceTemplate.id == service_template_id,
            )
        )
        if not include_deleted:
            statement = statement.where(ConstructionServiceTemplate.deleted_at.is_(None))

        # populate_existing is not optional here. The session runs with
        # expire_on_commit=False, so an instance already in the identity map
        # keeps the collections it loaded earlier and selectinload does NOT
        # overwrite them. Re-reading a template right after replacing its
        # sections would hand back the OLD structure -- and the audit snapshot
        # taken from it would state the wrong thing forever.
        result = await self.session.execute(statement.execution_options(populate_existing=True))
        return result.scalars().first()

    async def get_service_template_by_name(
        self,
        *,
        company_id: UUID,
        name: str,
    ) -> ConstructionServiceTemplate | None:
        """Only live services answer here.

        A deleted one keeps its name in the table but no longer reserves it --
        the unique index is partial on deleted_at IS NULL. Matching it would
        block recreating a service that the user already removed.
        """
        result = await self.session.execute(
            select(ConstructionServiceTemplate)
            .options(*self._service_template_loaders())
            .where(
                ConstructionServiceTemplate.company_id == company_id,
                ConstructionServiceTemplate.name == name,
                ConstructionServiceTemplate.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    async def list_service_templates(
        self,
        *,
        company_id: UUID,
        only_active: bool = True,
        search: str | None = None,
        only_deleted: bool = False,
        restrict_to_project_id: UUID | None = None,
    ) -> list[ConstructionServiceTemplate]:
        statement = (
            select(ConstructionServiceTemplate)
            .options(*self._service_template_loaders())
            .where(ConstructionServiceTemplate.company_id == company_id)
        )
        if only_deleted:
            statement = statement.where(ConstructionServiceTemplate.deleted_at.is_not(None))
        else:
            statement = statement.where(ConstructionServiceTemplate.deleted_at.is_(None))
            if only_active:
                statement = statement.where(ConstructionServiceTemplate.is_active.is_(True))

        if search:
            statement = statement.where(ConstructionServiceTemplate.name.ilike(f"%{search}%"))
        if restrict_to_project_id is not None:
            statement = statement.where(
                ConstructionServiceTemplate.id.in_(
                    self._project_service_template_ids_query(
                        company_id=company_id,
                        project_id=restrict_to_project_id,
                    )
                )
            )

        result = await self.session.execute(statement.order_by(ConstructionServiceTemplate.name))
        return list(result.scalars().all())

    @staticmethod
    def _project_service_template_ids_query(*, company_id: UUID, project_id: UUID):
        return (
            select(ConstructionProjectServiceTemplate.service_template_id)
            .join(
                ConstructionServiceTemplate,
                ConstructionServiceTemplate.id == ConstructionProjectServiceTemplate.service_template_id,
            )
            .where(
                ConstructionProjectServiceTemplate.company_id == company_id,
                ConstructionProjectServiceTemplate.project_id == project_id,
                ConstructionProjectServiceTemplate.deleted_at.is_(None),
                ConstructionServiceTemplate.deleted_at.is_(None),
            )
        )

    async def project_service_template_ids(self, *, company_id: UUID, project_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            self._project_service_template_ids_query(company_id=company_id, project_id=project_id)
        )
        return set(result.scalars().all())

    async def list_project_service_templates(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
    ) -> list[ConstructionServiceTemplate]:
        result = await self.session.execute(
            select(ConstructionServiceTemplate)
            .options(*self._service_template_loaders())
            .where(
                ConstructionServiceTemplate.company_id == company_id,
                ConstructionServiceTemplate.id.in_(
                    self._project_service_template_ids_query(company_id=company_id, project_id=project_id)
                ),
            )
            .order_by(ConstructionServiceTemplate.name)
        )
        return list(result.scalars().all())

    async def link_project_service_templates(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        service_template_ids: list[UUID],
        actor_user_id: UUID | None,
    ) -> int:
        if not service_template_ids:
            return 0
        statement = (
            pg_insert(ConstructionProjectServiceTemplate)
            .values(
                [
                    {
                        "id": uuid4(),
                        "company_id": company_id,
                        "project_id": project_id,
                        "service_template_id": service_template_id,
                        "created_by_user_id": actor_user_id,
                    }
                    for service_template_id in dict.fromkeys(service_template_ids)
                ]
            )
            .on_conflict_do_nothing(
                index_elements=["project_id", "service_template_id"],
                index_where=ConstructionProjectServiceTemplate.deleted_at.is_(None),
            )
            .returning(ConstructionProjectServiceTemplate.id)
        )
        result = await self.session.execute(statement)
        return len(result.scalars().all())

    async def unlink_project_service_templates(
        self,
        *,
        company_id: UUID,
        project_id: UUID,
        service_template_ids: list[UUID],
        actor_user_id: UUID | None,
    ) -> int:
        if not service_template_ids:
            return 0
        result = await self.session.execute(
            update(ConstructionProjectServiceTemplate)
            .where(
                ConstructionProjectServiceTemplate.company_id == company_id,
                ConstructionProjectServiceTemplate.project_id == project_id,
                ConstructionProjectServiceTemplate.service_template_id.in_(service_template_ids),
                ConstructionProjectServiceTemplate.deleted_at.is_(None),
            )
            .values(deleted_at=func.now(), deleted_by_user_id=actor_user_id)
        )
        return result.rowcount or 0

    async def get_next_service_template_audit_sequence(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
    ) -> int:
        return await self._next_scoped_sequence(
            column=ConstructionServiceTemplateAudit.sequence_number,
            filters=(
                ConstructionServiceTemplateAudit.company_id == company_id,
                ConstructionServiceTemplateAudit.service_template_id == service_template_id,
            ),
            lock_scope=f"construction_service_template_audits:{service_template_id}",
        )

    async def list_service_template_audits(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
    ) -> list[ConstructionServiceTemplateAudit]:
        result = await self.session.execute(
            select(ConstructionServiceTemplateAudit)
            .where(
                ConstructionServiceTemplateAudit.company_id == company_id,
                ConstructionServiceTemplateAudit.service_template_id == service_template_id,
            )
            .order_by(ConstructionServiceTemplateAudit.sequence_number.desc())
        )
        return list(result.scalars().all())

    async def replace_service_template_sections(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
        sections: list[ConstructionServiceTemplateSection],
    ) -> None:
        """Swaps a template's sections for the new ones.

        Same reason as replace_unit_children: the unit of work emits the INSERTs
        before the DELETEs it schedules itself, and the unique on
        (section, sequence) would blow up when re-editing the same template. Old
        items go away through the FK with ondelete CASCADE -- a DELETE issued as
        a statement does not trigger the ORM cascade.
        """
        await self.session.execute(
            delete(ConstructionServiceTemplateSection).where(
                ConstructionServiceTemplateSection.company_id == company_id,
                ConstructionServiceTemplateSection.service_template_id == service_template_id,
            )
        )
        for section in sections:
            self.session.add(section)

    async def count_measurement_items_by_service_template(
        self,
        *,
        company_id: UUID,
        service_template_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ConstructionMeasurementItem)
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.service_template_id == service_template_id,
            )
        )
        return int(result.scalar_one())

    async def get_measurement_item(
        self,
        *,
        company_id: UUID,
        item_id: UUID,
    ) -> ConstructionMeasurementItem | None:
        result = await self.session.execute(
            select(ConstructionMeasurementItem)
            .options(
                selectinload(ConstructionMeasurementItem.inspections).selectinload(
                    ConstructionMeasurementItemInspection.rounds
                ),
                selectinload(ConstructionMeasurementItem.occurrences),
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.id == item_id,
                *scope_conditions(ConstructionMeasurementItem, self.scope),
            )
        )
        item = result.scalars().first()
        if item is not None:
            await self._attach_service_template_names(company_id=company_id, items=[item])
        return item

    async def _attach_service_template_names(self, *, company_id: UUID, items: list[ConstructionMeasurementItem]) -> None:
        template_ids = {item.service_template_id for item in items if item.service_template_id}
        names = {}
        if template_ids:
            rows = await self.session.execute(
                select(ConstructionServiceTemplate.id, ConstructionServiceTemplate.name).where(
                    ConstructionServiceTemplate.company_id == company_id,
                    ConstructionServiceTemplate.id.in_(template_ids),
                )
            )
            names = dict(rows.all())
        for item in items:
            item.service_template_name = names.get(item.service_template_id)

    async def find_unit_order_with_service(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        exclude_measurement_id: UUID,
        service_template_id: UUID | None,
        description: str,
    ) -> ConstructionMeasurement | None:
        same_service = (
            ConstructionMeasurementItem.service_template_id == service_template_id
            if service_template_id is not None
            else and_(
                ConstructionMeasurementItem.service_template_id.is_(None),
                func.lower(func.trim(ConstructionMeasurementItem.description)) == description.strip().lower(),
            )
        )
        return await self.session.scalar(
            select(ConstructionMeasurement)
            .join(ConstructionMeasurementItem, ConstructionMeasurementItem.measurement_id == ConstructionMeasurement.id)
            .where(
                ConstructionMeasurement.company_id == company_id,
                ConstructionMeasurement.unit_id == unit_id,
                ConstructionMeasurement.id != exclude_measurement_id,
                ConstructionMeasurement.subcontract_id.is_(None),
                or_(
                    ConstructionMeasurement.status != ConstructionMeasurementStatus.REJECTED,
                    ConstructionMeasurement.rejected_at.is_not(None),
                ),
                ConstructionMeasurementItem.company_id == company_id,
                same_service,
                *scope_conditions(ConstructionMeasurement, self.scope),
                *scope_conditions(ConstructionMeasurementItem, self.scope),
            )
            .order_by(ConstructionMeasurement.sequence_number.desc().nulls_last())
            .limit(1)
        )

    async def list_measurement_items(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
    ) -> list[ConstructionMeasurementItem]:
        result = await self.session.execute(
            select(ConstructionMeasurementItem)
            .options(
                selectinload(ConstructionMeasurementItem.inspections).selectinload(
                    ConstructionMeasurementItemInspection.rounds
                ),
                selectinload(ConstructionMeasurementItem.occurrences),
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
                *scope_conditions(ConstructionMeasurementItem, self.scope),
            )
            .order_by(ConstructionMeasurementItem.sequence_number)
        )
        items = list(result.scalars().all())
        await self._attach_service_template_names(company_id=company_id, items=items)
        return items

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
        """Reads the line with its rounds, always from the database.

        populate_existing is not optional here. The session runs with
        expire_on_commit=False, so an instance already in the identity map keeps
        the collection it loaded earlier and selectinload does NOT overwrite it.
        Re-reading right after recording a round would hand back the history
        without the round that was just written -- and the derived status on the
        response would contradict it.
        """
        result = await self.session.execute(
            select(ConstructionMeasurementItemInspection)
            .options(selectinload(ConstructionMeasurementItemInspection.rounds))
            .where(
                ConstructionMeasurementItemInspection.company_id == company_id,
                ConstructionMeasurementItemInspection.id == inspection_id,
                *scope_conditions(ConstructionMeasurementItemInspection, self.scope),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def list_inspection_rounds(
        self,
        *,
        company_id: UUID,
        inspection_id: UUID,
    ) -> list[ConstructionInspectionRound]:
        result = await self.session.execute(
            select(ConstructionInspectionRound)
            .where(
                ConstructionInspectionRound.company_id == company_id,
                ConstructionInspectionRound.inspection_id == inspection_id,
                *scope_conditions(ConstructionInspectionRound, self.scope),
            )
            .order_by(ConstructionInspectionRound.sequence_number)
        )
        return list(result.scalars().all())

    async def get_next_inspection_round_sequence(self, *, company_id: UUID, inspection_id: UUID) -> int:
        return await self._next_scoped_sequence(
            column=ConstructionInspectionRound.sequence_number,
            filters=(
                ConstructionInspectionRound.company_id == company_id,
                ConstructionInspectionRound.inspection_id == inspection_id,
            ),
            lock_scope=f"construction_inspection_rounds:{inspection_id}",
        )

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
                *scope_conditions(ConstructionMeasurementItemInspection, self.scope),
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
        pending, _ = await self.summarize_measurement_inspection_blockers(
            company_id=company_id,
            measurement_id=measurement_id,
        )
        return pending

    async def summarize_measurement_inspection_blockers(
        self,
        *,
        company_id: UUID,
        measurement_id: UUID,
    ) -> tuple[int, int]:
        """Counts, in one trip, what stops the measurement from closing.

        Returns (never verified, failed without an approved reinspection). It
        counts INSPECTION LINES, never the item rollup: a free-text item has no
        line at all and must not block anything -- reading its `pending` rollup
        would deadlock every measurement that has one, with no way out.
        """
        result = await self.session.execute(
            select(
                func.count()
                .filter(ConstructionMeasurementItemInspection.status == ConstructionInspectionStatus.PENDING)
                .label("pending"),
                func.count()
                .filter(ConstructionMeasurementItemInspection.status == ConstructionInspectionStatus.NON_COMPLIANT)
                .label("non_compliant"),
            )
            .select_from(ConstructionMeasurementItemInspection)
            .join(
                ConstructionMeasurementItem,
                ConstructionMeasurementItem.id == ConstructionMeasurementItemInspection.measurement_item_id,
            )
            .where(
                ConstructionMeasurementItem.company_id == company_id,
                ConstructionMeasurementItem.measurement_id == measurement_id,
            )
        )
        pending, non_compliant = result.one()
        return int(pending), int(non_compliant)

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
                *scope_conditions(ConstructionMeasurementItemOccurrence, self.scope),
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
        lock: bool = False,
    ) -> ConstructionProcurementRequest | None:
        query = select(ConstructionProcurementRequest).options(selectinload(ConstructionProcurementRequest.items)).where(
            ConstructionProcurementRequest.company_id == company_id,
            ConstructionProcurementRequest.id == procurement_request_id,
            *scope_conditions(ConstructionProcurementRequest, self.scope),
        )
        if lock:
            query = query.with_for_update()
        result = await self.session.execute(query)
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
            .options(selectinload(ConstructionProcurementRequest.items))
            .where(
                ConstructionProcurementRequest.company_id == company_id,
                ConstructionProcurementRequest.project_id == project_id,
                *scope_conditions(ConstructionProcurementRequest, self.scope),
            )
            .order_by(ConstructionProcurementRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def procurement_for_reconciliation(self):
        rows = await self.session.scalars(select(ConstructionProcurementRequest)
            .options(selectinload(ConstructionProcurementRequest.items))
            .where(ConstructionProcurementRequest.submission_revision > 0))
        return list(rows.all())
