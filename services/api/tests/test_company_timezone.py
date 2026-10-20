from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.business_clock import business_clock_scope, current_business_timezone, get_business_today
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionUnitCommission


def test_commission_is_not_overdue_until_the_company_day_changes():
    commission = ConstructionUnitCommission(
        id=uuid4(),
        company_id=uuid4(),
        unit_id=uuid4(),
        beneficiary_person_id=uuid4(),
        sequence_number=1,
        amount=Decimal("100"),
        due_date=date(2026, 10, 20),
        payment_date=None,
        composes_sale_price=True,
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        updated_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    instant = datetime(2026, 10, 21, 3, 30, tzinfo=timezone.utc)
    with business_clock_scope("America/Campo_Grande", instant=instant):
        assert get_business_today(current_business_timezone()) == date(2026, 10, 20)
        assert ConstructionProjectService.to_commission_response(commission).status == "open"
    with business_clock_scope("America/Sao_Paulo", instant=instant):
        assert ConstructionProjectService.to_commission_response(commission).status == "overdue"
