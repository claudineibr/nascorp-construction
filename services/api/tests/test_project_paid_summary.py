from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.domain.services.construction_project_service import ConstructionProjectService
from tests.test_construction_project_service import _build_summary_scenario, FakeReceivablesSummaryClient


@pytest.mark.asyncio
async def test_overview_uses_erp_shared_title_payment_and_contract_commitments():
    company_id, project, _, repository = _build_summary_scenario()
    client = FakeReceivablesSummaryClient()
    client.get_purchase_totals = AsyncMock(return_value={
        "approved_requisition_amount": "0", "committed_order_amount": "23392.40",
        "committed_total_amount": "1198267.76", "realized_amount": "185469.25",
        "measured_amount": "124.64", "paid_measured_amount": "92.89", "legacy_unknown_amount": "0",
    })
    summary = await ConstructionProjectService(repository=repository, erp_client=client).build_project_summary(
        company_id=company_id, project_id=project.id)
    assert summary["paid_cost_amount"] == Decimal("92.89")
    assert summary["measured_cost_amount"] == Decimal("124.64")
    assert summary["committed_order_amount"] == Decimal("1198267.76")
    assert summary["realized_amount"] == Decimal("185469.25")
