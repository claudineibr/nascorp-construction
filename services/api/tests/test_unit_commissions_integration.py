from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionProject,
    ConstructionUnit,
    ConstructionUnitCommission,
    ConstructionUnitDocumentation,
    ConstructionUnitPaymentSource,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction import (
    ConstructionUnitCommissionCreate,
    ConstructionUnitSaleConfirmRequest,
)
from tests.integration_database import create_reachable_engine_or_skip


class RecordingErpClient:
    def __init__(self) -> None:
        self.events = []

    async def deliver_event(self, *, event):
        self.events.append(event)
        return None


async def seed_project_and_unit(session, *, company_id, commission_receipt_template_id=None):
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code=f"OBRA-SIN-{str(uuid4())[:8]}",
        name="Commission integration project",
        status="active",
        commission_receipt_template_id=commission_receipt_template_id,
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="SIN-101",
        unit_type="house",
        sale_price=Decimal("250000.00"),
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    session.add(project)
    session.add(unit)
    await session.flush()
    return project, unit


async def clean_up(session, *, project_id, unit_id) -> None:
    await session.rollback()
    await session.execute(delete(ConstructionUnitCommission).where(ConstructionUnitCommission.unit_id == unit_id))
    await session.execute(delete(ConstructionUnitDocumentation).where(ConstructionUnitDocumentation.unit_id == unit_id))
    await session.execute(delete(ConstructionUnitPaymentSource).where(ConstructionUnitPaymentSource.unit_id == unit_id))
    await session.execute(delete(ConstructionUnit).where(ConstructionUnit.id == unit_id))
    await session.execute(delete(ConstructionProject).where(ConstructionProject.id == project_id))
    await session.commit()


async def test_the_paid_commission_that_composes_lowers_what_the_buyer_still_owes() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()
    template_id = uuid4()

    async with session_factory() as session:
        project, unit = await seed_project_and_unit(
            session,
            company_id=company_id,
            commission_receipt_template_id=template_id,
        )
        project_id = project.id
        unit_id = unit.id
        erp_client = RecordingErpClient()
        service = ConstructionProjectService(
            repository=ConstructionRepository(session=session),
            erp_client=erp_client,
        )

        try:
            commissions = await service.create_unit_commissions(
                company_id=company_id,
                unit_id=unit_id,
                request=ConstructionUnitCommissionCreate(
                    beneficiary_person_id=uuid4(),
                    amount=Decimal("5000.00"),
                    due_date=date(2026, 3, 10),
                    installments=2,
                    composes_sale_price=True,
                ),
            )
            await service.settle_unit_commission(
                company_id=company_id,
                commission_id=commissions[0].id,
                payment_date=date(2026, 3, 12),
            )
            await service.confirm_unit_sale(
                company_id=company_id,
                unit_id=unit_id,
                request=ConstructionUnitSaleConfirmRequest(
                    buyer_person_id=uuid4(),
                    sale_price=Decimal("250000.00"),
                    first_due_date=date(2026, 4, 10),
                    installments=10,
                ),
            )
            composition = await service.build_unit_sale_composition(company_id=company_id, unit_id=unit_id)

            assert [commission.sequence_number for commission in commissions] == [1, 2]
            assert commissions[0].receipt_template_id == template_id
            assert [commission.due_date for commission in commissions] == [
                date(2026, 3, 10),
                date(2026, 4, 10),
            ]
            assert composition["commission_total"] == Decimal("10000.00")
            assert composition["commission_offset"] == Decimal("5000.00")
            assert composition["installment_total"] == Decimal("245000.00")
            assert erp_client.events[-1].payload["receivable_amount"] == "245000.00"
        finally:
            await clean_up(session, project_id=project_id, unit_id=unit_id)

    await engine.dispose()


async def test_deleting_the_unit_takes_its_commissions_with_it() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    async with session_factory() as session:
        project, unit = await seed_project_and_unit(session, company_id=company_id)
        project_id = project.id
        unit_id = unit.id
        repository = ConstructionRepository(session=session)
        service = ConstructionProjectService(repository=repository)

        try:
            await service.create_unit_commissions(
                company_id=company_id,
                unit_id=unit_id,
                request=ConstructionUnitCommissionCreate(
                    beneficiary_person_id=uuid4(),
                    amount=Decimal("1500.00"),
                    due_date=date(2026, 5, 10),
                ),
            )
            await service.delete_unit(company_id=company_id, unit_id=unit_id)

            remaining = await repository.list_unit_commissions(company_id=company_id, unit_id=unit_id)

            assert remaining == []
        finally:
            await clean_up(session, project_id=project_id, unit_id=unit_id)

    await engine.dispose()
