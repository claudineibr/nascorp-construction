from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.exceptions import ConstructionDomainError, ConstructionInvalidValueError
from app.domain.services import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProject, ConstructionUnit
from app.schemas.construction import (
    ConstructionUnitAdjustmentCreate,
    ConstructionUnitCommissionCreate,
    ConstructionUnitCommissionUpdate,
    ConstructionUnitSaleConfirmRequest,
)
from tests.test_construction_project_service import FakeConstructionRepository, FakeErpMeasurementClient


class RecordingAdjustmentErpClient(FakeErpMeasurementClient):
    def __init__(self) -> None:
        super().__init__()
        self.adjustments: list[dict] = []

    async def create_unit_adjustment(self, **kwargs):
        self.adjustments.append(kwargs)
        return {
            "construction_unit_id": str(kwargs["construction_unit_id"]),
            "contract_id": str(kwargs["contract_id"]),
            "receivable_id": str(uuid4()),
            "receivable_status": "OPEN",
            "total_amount": str(kwargs["amount"]),
            "installments": kwargs["installments"],
        }


def seed_project_and_unit(
    repository: FakeConstructionRepository,
    *,
    company_id,
    sale_price=Decimal("250000.00"),
    commission_receipt_template_id=None,
    receipt_template_id=None,
    unit_code="A-101",
):
    project = ConstructionProject(
        id=uuid4(),
        company_id=company_id,
        code=f"OBRA-{str(uuid4())[:6]}",
        name="Commission project",
        status="active",
        analytic_cost_center_id=uuid4(),
        receipt_template_id=receipt_template_id,
        commission_receipt_template_id=commission_receipt_template_id,
    )
    unit = ConstructionUnit(
        id=uuid4(),
        company_id=company_id,
        project_id=project.id,
        code=unit_code,
        unit_type="apartment",
        sale_price=sale_price,
        analytic_cost_center_id=uuid4(),
        status="available",
    )
    repository.projects[(company_id, project.id)] = project
    repository.units[(company_id, unit.id)] = unit
    return project, unit


async def test_repeating_the_commission_generates_one_row_per_month() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository)

    commissions = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("1500.00"),
            due_date=date(2026, 1, 31),
            installments=3,
        ),
    )

    assert [commission.sequence_number for commission in commissions] == [1, 2, 3]
    assert [commission.due_date for commission in commissions] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert {commission.amount for commission in commissions} == {Decimal("1500.00")}


async def test_commission_numbering_of_one_unit_does_not_collide_with_another() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    _, first_unit = seed_project_and_unit(repository, company_id=company_id, unit_code="A-101")
    _, second_unit = seed_project_and_unit(repository, company_id=company_id, unit_code="A-102")
    service = ConstructionProjectService(repository=repository)
    request = ConstructionUnitCommissionCreate(
        beneficiary_person_id=uuid4(),
        amount=Decimal("2000.00"),
        due_date=date(2026, 5, 10),
        installments=2,
    )

    await service.create_unit_commissions(company_id=company_id, unit_id=first_unit.id, request=request)
    second = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=second_unit.id,
        request=request,
    )

    assert [commission.sequence_number for commission in second] == [1, 2]


def _balance_amount(payload) -> str:
    """O saldo devedor do payload da venda.

    Antes estes testes liam ``receivable_amount``, que valia o mesmo numero
    porque o saldo virava parcela. Hoje o saldo nao vira parcela, entao ele so
    aparece na propria fonte -- e e nela que o abatimento do sinal se observa.
    """
    balance = next(
        source
        for source in payload["payment_sources"]
        if source["source_type"] == "balance"
    )
    return str(balance["amount"])


async def test_paid_commission_that_composes_reduces_the_balance_the_buyer_owes() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    commissions = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("5000.00"),
            due_date=date(2026, 3, 10),
        ),
    )
    await service.settle_unit_commission(
        company_id=company_id,
        commission_id=commissions[0].id,
        payment_date=date(2026, 3, 12),
    )

    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("250000.00"),
            first_due_date=date(2026, 4, 10),
            installments=10,
        ),
    )

    sale_event = erp_client.events[-1]
    assert _balance_amount(sale_event.payload) == "245000.00"
    assert sale_event.payload["commission_offset"] == "5000.00"


async def test_commission_that_composes_reduces_the_balance_before_being_paid() -> None:
    """Lancar o sinal ja tira o valor do saldo, sem esperar a baixa.

    Enquanto so o sinal pago abatia, o mesmo dinheiro ficava em dois lugares
    ate alguem dar baixa: cobrado no sinal e ainda somado no saldo devedor.
    """
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("5000.00"),
            due_date=date(2026, 3, 10),
        ),
    )

    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("250000.00"),
            first_due_date=date(2026, 4, 10),
            installments=10,
        ),
    )

    sale_event = erp_client.events[-1]
    assert _balance_amount(sale_event.payload) == "245000.00"
    assert sale_event.payload["commission_offset"] == "5000.00"


async def test_every_commission_composes_the_sale_even_if_the_request_says_otherwise() -> None:
    """Nao existe mais sinal "cobrado por fora".

    O sinal e dinheiro que o comprador paga pela unidade: ele sempre compoe a
    venda. O que ele nao faz e entrar no contas a receber, porque e pago direto
    ao corretor e nao passa pelo caixa da empresa. A escolha saiu da tela e do
    schema, e um request antigo que ainda mande a chave nao reabre a excecao.
    """
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    commissions = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate.model_validate(
            {
                "beneficiary_person_id": str(uuid4()),
                "amount": "5000.00",
                "due_date": "2026-03-10",
                "composes_sale_price": False,
            }
        ),
    )

    assert commissions[0].composes_sale_price is True

    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("250000.00"),
            first_due_date=date(2026, 4, 10),
            installments=10,
        ),
    )

    assert _balance_amount(erp_client.events[-1].payload) == "245000.00"


async def test_settling_a_commission_does_not_reemit_the_sale_event() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)
    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("250000.00"),
            first_due_date=date(2026, 4, 10),
            installments=10,
        ),
    )
    events_after_sale = len(erp_client.events)
    commissions = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("5000.00"),
            due_date=date(2026, 5, 10),
            composes_sale_price=True,
        ),
    )

    await service.settle_unit_commission(
        company_id=company_id,
        commission_id=commissions[0].id,
        payment_date=date(2026, 5, 12),
    )

    assert len(erp_client.events) == events_after_sale


async def test_clearing_a_required_field_is_refused_instead_of_breaking_the_row() -> None:
    """A tela manda as seis chaves sempre, inclusive as vazias.

    `exclude_unset` so diz que a chave veio -- nao que veio preenchida. Sem esta
    recusa, o `None` ia direto para uma coluna NOT NULL e virava IntegrityError:
    500 generico, sem dizer ao usuario qual campo ele apagou.
    """
    company_id = uuid4()
    repository = FakeConstructionRepository()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository)
    commissions = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("5000.00"),
            due_date=date(2026, 3, 10),
        ),
    )

    for field_name in ("beneficiary_person_id", "amount", "due_date"):
        with pytest.raises(ConstructionInvalidValueError) as error:
            await service.update_unit_commission(
                company_id=company_id,
                commission_id=commissions[0].id,
                request=ConstructionUnitCommissionUpdate.model_validate({field_name: None}),
            )

        assert error.value.error_code == "CONSTRUCTION_UNIT_COMMISSION_REQUIRED_FIELD"
        assert field_name in error.value.message

    # O que nao e obrigatorio continua podendo ser limpo.
    updated = await service.update_unit_commission(
        company_id=company_id,
        commission_id=commissions[0].id,
        request=ConstructionUnitCommissionUpdate(document_number=None, notes=None),
    )
    assert updated.document_number is None
    assert updated.amount == Decimal("5000.00")


async def test_commission_copies_the_project_template_and_keeps_it_after_the_project_changes() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    original_template_id = uuid4()
    project, unit = seed_project_and_unit(
        repository,
        company_id=company_id,
        commission_receipt_template_id=original_template_id,
    )
    service = ConstructionProjectService(repository=repository)

    commissions = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("3000.00"),
            due_date=date(2026, 7, 10),
        ),
    )
    project.commission_receipt_template_id = uuid4()

    stored = await service.list_unit_commissions(company_id=company_id, unit_id=unit.id)

    assert commissions[0].receipt_template_id == original_template_id
    assert stored[0].receipt_template_id == original_template_id


async def test_the_sale_carries_the_project_receipt_template_to_the_erp() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = FakeErpMeasurementClient()
    template_id = uuid4()
    _, unit = seed_project_and_unit(repository, company_id=company_id, receipt_template_id=template_id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)

    await service.confirm_unit_sale(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitSaleConfirmRequest(
            buyer_person_id=uuid4(),
            sale_price=Decimal("250000.00"),
            first_due_date=date(2026, 4, 10),
            installments=10,
        ),
    )

    assert erp_client.events[-1].payload["receipt_template_id"] == str(template_id)


async def test_sale_composition_exposes_the_commission_totals() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository)
    composing = await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("5000.00"),
            due_date=date(2026, 3, 10),
        ),
    )
    await service.create_unit_commissions(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitCommissionCreate(
            beneficiary_person_id=uuid4(),
            amount=Decimal("1000.00"),
            due_date=date(2026, 4, 10),
        ),
    )
    await service.settle_unit_commission(
        company_id=company_id,
        commission_id=composing[0].id,
        payment_date=date(2026, 3, 12),
    )

    composition = await service.build_unit_sale_composition(company_id=company_id, unit_id=unit.id)

    assert composition["commission_total"] == Decimal("6000.00")
    # Baixado so o primeiro: "pago" e "abatido do saldo" sao numeros diferentes
    # desde que o sinal passou a abater no lancamento, e nao na baixa.
    assert composition["commission_paid_total"] == Decimal("5000.00")
    assert composition["commission_offset"] == Decimal("6000.00")
    assert len(composition["commissions"]) == 2


async def test_adjustment_is_refused_while_the_unit_has_no_contract() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = RecordingAdjustmentErpClient()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)

    with pytest.raises(ConstructionDomainError):
        await service.create_unit_adjustment(
            company_id=company_id,
            unit_id=unit.id,
            request=ConstructionUnitAdjustmentCreate(
                amount=Decimal("8000.00"),
                installments=2,
                first_due_date=date(2026, 6, 10),
                reason="Financiamento aprovado abaixo do previsto",
            ),
        )

    assert erp_client.adjustments == []


async def test_adjustment_reaches_the_erp_with_the_unit_contract_and_cost_center() -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    erp_client = RecordingAdjustmentErpClient()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    unit.external_contract_id = uuid4()
    service = ConstructionProjectService(repository=repository, erp_client=erp_client)

    await service.create_unit_adjustment(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitAdjustmentCreate(
            amount=Decimal("8000.00"),
            installments=2,
            first_due_date=date(2026, 6, 10),
            reason="Financiamento aprovado abaixo do previsto",
        ),
    )

    dispatched = erp_client.adjustments[0]
    assert dispatched["contract_id"] == unit.external_contract_id
    assert dispatched["cost_center_id"] == unit.analytic_cost_center_id
    assert dispatched["amount"] == Decimal("8000.00")
    assert dispatched["unit_code"] == unit.code
