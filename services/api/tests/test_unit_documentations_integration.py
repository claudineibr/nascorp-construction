from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import (
    ConstructionDocumentationType,
    ConstructionProject,
    ConstructionUnit,
    ConstructionUnitDocumentation,
    ConstructionUnitPaymentSource,
)
from app.infrastructure.repository.construction_repository import ConstructionRepository
from app.schemas.construction import ConstructionUnitSaleConfirmRequest
from tests.integration_database import create_reachable_engine_or_skip


class RecordingErpClient:
    def __init__(self) -> None:
        self.events = []

    async def deliver_event(self, *, event):
        self.events.append(event)
        return None


async def seed_project_and_unit(session, *, company_id):
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code=f"OBRA-DOC-{str(uuid4())[:8]}",
        name="Documentation integration project",
        status="active",
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code="DOC-101",
        unit_type="house",
        sale_price=Decimal("300000.00"),
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    session.add(project)
    session.add(unit)
    await session.flush()
    return project, unit


async def clean_up(session, *, project_id, unit_id, company_id) -> None:
    """Apaga o que o cenario criou.

    Recebe ids, nao entidades: o rollback expira os objetos e ler ``unit.id``
    depois dispararia um lazy load em sessao async (MissingGreenlet). Cada
    teste usa um ``company_id`` proprio, entao os DELETE ficam presos ao que
    ele mesmo inseriu.
    """
    await session.rollback()
    await session.execute(
        delete(ConstructionUnitDocumentation).where(ConstructionUnitDocumentation.unit_id == unit_id)
    )
    await session.execute(
        delete(ConstructionUnitPaymentSource).where(ConstructionUnitPaymentSource.unit_id == unit_id)
    )
    await session.execute(delete(ConstructionUnit).where(ConstructionUnit.id == unit_id))
    await session.execute(delete(ConstructionProject).where(ConstructionProject.id == project_id))
    await session.execute(
        delete(ConstructionDocumentationType).where(ConstructionDocumentationType.company_id == company_id)
    )
    await session.commit()


async def test_the_plan_scenario_lands_the_balance_the_buyer_still_owes() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    try:
        async with session_factory() as session:
            project, unit = await seed_project_and_unit(session, company_id=company_id)
            project_id, unit_id = project.id, unit.id
            service = ConstructionProjectService(
                repository=ConstructionRepository(session=session),
                erp_client=RecordingErpClient(),
            )
            request = ConstructionUnitSaleConfirmRequest(
                buyer_person_id=uuid4(),
                sale_price=Decimal("300000.00"),
                first_due_date=date(2026, 10, 10),
                installments=12,
                payment_sources=[
                    {
                        "source_type": "financing",
                        "amount": Decimal("200000.00"),
                        "due_date": date(2026, 11, 10),
                        "installments": 1,
                    },
                    {
                        "source_type": "down_payment",
                        "amount": Decimal("20000.00"),
                        "due_date": date(2026, 10, 10),
                        "installments": 1,
                    },
                ],
                documentations=[
                    {"name": "Cartório", "amount": Decimal("2521.40")},
                    {"name": "SANESUL", "amount": Decimal("298.20")},
                ],
            )

            try:
                await service.confirm_unit_sale(company_id=company_id, unit_id=unit_id, request=request)

                composition = await service.build_unit_sale_composition(
                    company_id=company_id,
                    unit_id=unit_id,
                )
                balance_source = next(
                    source for source in composition["sources"] if source["source_type"] == "balance"
                )

                assert balance_source["amount"] == Decimal("82819.60")
                assert composition["documentation_total"] == Decimal("2819.60")
                assert composition["total_charged"] == Decimal("302819.60")
                assert [item["name"] for item in composition["documentations"]] == ["Cartório", "SANESUL"]
            finally:
                await clean_up(session, project_id=project_id, unit_id=unit_id, company_id=company_id)
    finally:
        await engine.dispose()


async def test_editing_the_sale_keeping_the_same_documentation_type_does_not_violate_the_unique() -> None:
    engine = await create_reachable_engine_or_skip()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    company_id = uuid4()

    def build_request(*, sanesul_amount):
        documentations = [{"name": "Cartório", "amount": Decimal("2521.40")}]
        if sanesul_amount is not None:
            documentations.append({"name": "SANESUL", "amount": sanesul_amount})

        return ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("300000.00"),
            first_due_date=date(2026, 10, 10),
            installments=12,
            payment_sources=[
                {
                    "source_type": "financing",
                    "amount": Decimal("200000.00"),
                    "due_date": date(2026, 11, 10),
                    "installments": 1,
                },
            ],
            documentations=documentations,
        )

    try:
        async with session_factory() as session:
            project, unit = await seed_project_and_unit(session, company_id=company_id)
            project_id, unit_id = project.id, unit.id
            service = ConstructionProjectService(
                repository=ConstructionRepository(session=session),
                erp_client=RecordingErpClient(),
            )

            try:
                await service.confirm_unit_sale(
                    company_id=company_id,
                    unit_id=unit_id,
                    request=build_request(sanesul_amount=Decimal("298.20")),
                )

                # Editar a venda mantendo "Cartório" e removendo "SANESUL" e o
                # caso que estoura o unique quando o INSERT sai antes do DELETE.
                await service.confirm_unit_sale(
                    company_id=company_id,
                    unit_id=unit_id,
                    request=build_request(sanesul_amount=None),
                )

                composition = await service.build_unit_sale_composition(
                    company_id=company_id,
                    unit_id=unit_id,
                )
                balance_source = next(
                    source for source in composition["sources"] if source["source_type"] == "balance"
                )

                assert [item["name"] for item in composition["documentations"]] == ["Cartório"]
                assert composition["documentation_total"] == Decimal("2521.40")
                assert balance_source["amount"] == Decimal("102521.40")
            finally:
                await clean_up(session, project_id=project_id, unit_id=unit_id, company_id=company_id)
    finally:
        await engine.dispose()
