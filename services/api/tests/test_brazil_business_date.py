from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain import business_date, business_clock
from app.domain.exceptions import ConstructionInvalidValueError
from app.domain.services import ConstructionProjectService
from app.domain.services.assistance_service import serialize_summary
from app.infrastructure.database.models import ConstructionUnitCommission
from app.schemas.construction import (
    ConstructionMeasurementItemCreate,
    ConstructionMeasurementItemOccurrenceCreate,
    ConstructionMeasurementItemOccurrenceUpdate,
    ConstructionMeasurementResponse,
    ConstructionUnitCommissionCreate,
    ConstructionUnitCommissionResponse,
    ConstructionUnitReserveRequest,
)
from tests.test_construction_project_service import (
    FakeConstructionRepository,
    FakeErpMeasurementClient,
    _build_item_with_one_line,
    _build_measurement_scenario,
    _verify,
)
from tests.test_unit_commissions import seed_project_and_unit

BRAZIL_TODAY = date(2026, 3, 9)


def _freeze_clock(monkeypatch, instant):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz)

    monkeypatch.setattr(business_date, "datetime", FrozenDatetime)
    monkeypatch.setattr(business_clock, "datetime", FrozenDatetime)


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (datetime(2026, 10, 21, 0, 0, tzinfo=UTC), date(2026, 10, 20)),
        (datetime(2026, 10, 21, 1, 30, tzinfo=UTC), date(2026, 10, 20)),
        (datetime(2026, 10, 21, 2, 59, 59, tzinfo=UTC), date(2026, 10, 20)),
        (datetime(2026, 10, 21, 3, 0, tzinfo=UTC), date(2026, 10, 21)),
        (datetime(2026, 10, 20, 12, 0, tzinfo=UTC), date(2026, 10, 20)),
    ],
)
def test_today_follows_brasilia_when_utc_already_turned_the_day(monkeypatch, instant, expected) -> None:
    _freeze_clock(monkeypatch, instant)

    assert business_date.brazil_today() == expected


@pytest.fixture
def brasilia_today(monkeypatch):
    _freeze_clock(monkeypatch, datetime(2026, 3, 10, 1, 0, tzinfo=UTC))
    return BRAZIL_TODAY


async def test_item_period_accepts_today_and_refuses_tomorrow_in_brasilia(brasilia_today) -> None:
    company_id, measurement, service = await _build_measurement_scenario()

    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(
            description="Servico de hoje",
            amount=Decimal("100.00"),
            start_date=brasilia_today,
            end_date=brasilia_today,
        ),
    )
    assert item.end_date == brasilia_today

    with pytest.raises(ConstructionInvalidValueError) as error:
        await service.create_measurement_item(
            company_id=company_id,
            measurement_id=measurement.id,
            request=ConstructionMeasurementItemCreate(
                description="Servico de amanha",
                amount=Decimal("100.00"),
                start_date=brasilia_today,
                end_date=brasilia_today + timedelta(days=1),
            ),
        )
    assert error.value.message == "A data de fim não pode ser futura."


async def test_occurrence_opens_and_closes_on_the_brasilia_day(brasilia_today) -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item = await service.create_measurement_item(
        company_id=company_id,
        measurement_id=measurement.id,
        request=ConstructionMeasurementItemCreate(description="Esquadrias", amount=Decimal("900.00")),
    )

    occurrence = await service.create_measurement_item_occurrence(
        company_id=company_id,
        item_id=item.id,
        request=ConstructionMeasurementItemOccurrenceCreate(problem="Janela desalinhada"),
    )
    assert occurrence.opened_at == brasilia_today

    resolved = await service.update_measurement_item_occurrence(
        company_id=company_id,
        occurrence_id=occurrence.id,
        request=ConstructionMeasurementItemOccurrenceUpdate(status="resolved", solution="Esquadria reinstalada"),
    )
    assert resolved.closed_at == brasilia_today


async def test_occurrence_opened_by_a_failed_inspection_uses_the_brasilia_day(brasilia_today) -> None:
    company_id, measurement, service = await _build_measurement_scenario()
    item, inspection = await _build_item_with_one_line(service, company_id, measurement)

    await _verify(service, company_id, inspection.id, "non_compliant", comment="camada solta", open_occurrence=True)

    reloaded = await service.get_measurement_item(company_id=company_id, item_id=item.id)
    assert reloaded.occurrences[0].opened_at == brasilia_today


async def test_reservation_expires_seven_days_after_the_brasilia_day(brasilia_today) -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=FakeErpMeasurementClient())

    reserved = await service.reserve_unit(
        company_id=company_id,
        unit_id=unit.id,
        request=ConstructionUnitReserveRequest(buyer_person_id=uuid4()),
    )

    assert reserved.reservation_expires_at == date(2026, 3, 16)


async def test_unpaid_commission_due_before_today_is_overdue(brasilia_today) -> None:
    company_id = uuid4()
    repository = FakeConstructionRepository()
    _, unit = seed_project_and_unit(repository, company_id=company_id)
    service = ConstructionProjectService(repository=repository, erp_client=FakeErpMeasurementClient())
    for due_date in (date(2026, 3, 8), date(2026, 3, 9), date(2026, 3, 1)):
        await service.create_unit_commissions(
            company_id=company_id,
            unit_id=unit.id,
            request=ConstructionUnitCommissionCreate(
                beneficiary_person_id=uuid4(),
                amount=Decimal("1000.00"),
                due_date=due_date,
            ),
        )
    paid = next(
        commission
        for commission in await service.list_unit_commissions(company_id=company_id, unit_id=unit.id)
        if commission.due_date == date(2026, 3, 1)
    )
    await service.settle_unit_commission(company_id=company_id, commission_id=paid.id, payment_date=date(2026, 3, 2))

    composition = await service.build_unit_sale_composition(company_id=company_id, unit_id=unit.id)

    statuses = {row["due_date"]: row["status"] for row in composition["commissions"]}
    assert statuses == {date(2026, 3, 8): "overdue", date(2026, 3, 9): "open", date(2026, 3, 1): "paid"}


@pytest.mark.parametrize(
    ("due_date", "payment_date", "expected"),
    [
        (date(2026, 3, 8), None, "overdue"),
        (date(2026, 3, 9), None, "open"),
        (date(2026, 3, 10), None, "open"),
        (date(2026, 3, 8), date(2026, 3, 9), "paid"),
    ],
)
def test_commission_response_carries_the_status_by_due_date(brasilia_today, due_date, payment_date, expected) -> None:
    commission = ConstructionUnitCommission(
        id=uuid4(),
        company_id=uuid4(),
        unit_id=uuid4(),
        beneficiary_person_id=uuid4(),
        sequence_number=1,
        amount=Decimal("1000.00"),
        due_date=due_date,
        payment_date=payment_date,
        composes_sale_price=True,
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
        updated_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    assert ConstructionProjectService.to_commission_response(commission).status == expected


@pytest.mark.parametrize(("due_date", "expected"), [(date(2026, 3, 9), False), (date(2026, 3, 8), True)])
def test_assistance_service_due_today_is_not_overdue_at_night_in_brasilia(brasilia_today, due_date, expected) -> None:
    row = SimpleNamespace(
        id=uuid4(),
        company_id=uuid4(),
        project_id=uuid4(),
        unit_id=uuid4(),
        customer_person_id=None,
        attendant_person_id=None,
        analyst_person_id=None,
        number=1,
        status="open",
        opened_at=datetime(2026, 3, 1, tzinfo=UTC),
        completed_at=None,
        complaints=[],
        services=[SimpleNamespace(deleted_at=None, due_date=due_date, executed_at=None)],
    )

    assert serialize_summary(row)["overdue"] is expected


def test_measurement_response_does_not_expose_the_stale_payable_status() -> None:
    assert "external_accounts_payable_status" not in ConstructionMeasurementResponse.model_fields
