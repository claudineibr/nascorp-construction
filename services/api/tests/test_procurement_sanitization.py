from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.domain.constants import ConstructionProcurementStatus
from app.domain.exceptions import ConstructionDomainError, ConstructionIntegrationUnconfirmedError
from app.domain.services.construction_project_service import ConstructionProjectService
from app.infrastructure.database.models import ConstructionProcurementRequest


def scenario(status="draft"):
    request = ConstructionProcurementRequest(
        id=uuid4(), company_id=uuid4(), project_id=uuid4(), code="RC-TEST",
        title="Compra", estimated_amount=Decimal("20"), discount_amount=Decimal("0"),
        supplier_person_id=uuid4(), created_by_user_id=uuid4(), status=status,
    )
    request.items = []
    repository = AsyncMock()
    repository.get_procurement_request.return_value = request
    client = SimpleNamespace(validate_procurement_products=AsyncMock(return_value=[]),
                             get_procurement_statuses=AsyncMock(return_value=[]))
    dispatcher = SimpleNamespace(dispatch=AsyncMock())
    service = ConstructionProjectService(repository=repository, erp_client=client,
                                         integration_dispatcher=dispatcher)
    service.get_project = AsyncMock(return_value=SimpleNamespace(code="OB-1", name="Obra"))
    return service, repository, client, dispatcher, request


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ConnectTimeout])
async def test_connection_failure_rolls_back_submission(error_type):
    service, repository, _, dispatcher, request = scenario()
    dispatcher.dispatch.side_effect = error_type("offline")
    with pytest.raises(ConstructionDomainError) as error:
        await service.submit_procurement_request(company_id=request.company_id,
            procurement_request_id=request.id, actor_user_id=uuid4())
    assert error.value.error_code == "CONSTRUCTION_ERP_UNAVAILABLE"
    repository.rollback.assert_awaited_once()
    repository.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_status", ["draft", "rejected"])
async def test_read_timeout_commits_pending_and_allows_resubmission(initial_status):
    service, repository, _, dispatcher, request = scenario(initial_status)
    if initial_status == "rejected":
        request.external_procurement_id = uuid4()
        request.external_procurement_status = "REJECTED"
    dispatcher.dispatch.side_effect = httpx.ReadTimeout("response lost")
    with pytest.raises(ConstructionIntegrationUnconfirmedError):
        await service.submit_procurement_request(company_id=request.company_id,
            procurement_request_id=request.id, actor_user_id=uuid4())
    assert request.status == ConstructionProcurementStatus.PENDING_APPROVAL
    assert request.external_procurement_id is None
    repository.commit.assert_awaited_once()
    repository.rollback.assert_not_awaited()
    dispatcher.dispatch.side_effect = None
    dispatcher.dispatch.return_value = SimpleNamespace(response_event=None)
    await service.submit_procurement_request(company_id=request.company_id,
        procurement_request_id=request.id, actor_user_id=uuid4())
    assert dispatcher.dispatch.await_count == 2
    first, second = [call.kwargs["event"] for call in dispatcher.dispatch.await_args_list]
    assert first.aggregate_id == second.aggregate_id
    assert first.payload["items"] == second.payload["items"]
    assert first.payload["created_by_user_id"] == str(request.created_by_user_id)


@pytest.mark.asyncio
async def test_resubmit_links_existing_purchase_without_dispatch():
    service, repository, client, dispatcher, request = scenario("pending_approval")
    external_id = uuid4()
    client.get_procurement_statuses.return_value = [{
        "source_id": str(request.id), "external_procurement_id": str(external_id),
        "external_procurement_status": "APPROVED",
    }]
    result = await service.submit_procurement_request(company_id=request.company_id,
        procurement_request_id=request.id, actor_user_id=uuid4())
    assert result.external_procurement_id == external_id
    assert result.status == ConstructionProcurementStatus.APPROVED
    dispatcher.dispatch.assert_not_awaited()
    repository.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_status_snapshot_keeps_unconfirmed_purchase_locked():
    service, _, _, _, request = scenario("pending_approval")
    await service.sync_procurement_statuses(company_id=request.company_id,
        actor_user_id=uuid4(), items=[request])
    assert request.status == ConstructionProcurementStatus.PENDING_APPROVAL
    assert request.external_procurement_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout])
async def test_validation_transport_failure_does_not_send(error_type):
    service, repository, client, dispatcher, request = scenario()
    client.validate_procurement_products.side_effect = error_type("offline")
    with pytest.raises(ConstructionDomainError) as error:
        await service.submit_procurement_request(company_id=request.company_id,
            procurement_request_id=request.id, actor_user_id=uuid4())
    assert error.value.error_code == "CONSTRUCTION_ERP_UNAVAILABLE"
    assert request.status == ConstructionProcurementStatus.DRAFT
    dispatcher.dispatch.assert_not_awaited()
    repository.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_counts_only_erp_approved_purchases():
    service, repository, _, _, request = scenario()
    repository.list_units.return_value = []
    repository.list_measurements.return_value = []
    repository.list_procurement_requests.return_value = [
        SimpleNamespace(status=local, external_procurement_status=external,
                        estimated_amount=Decimal(amount))
        for local, external, amount in [
            ("draft", None, "100"), ("approved", None, "200"),
            ("pending_approval", "PENDING_APPROVAL", "300"),
            ("draft", "APPROVED", "20"), ("sent_to_erp", "ORDER_CREATED", "30"),
            ("rejected", "REJECTED", "400"),
        ]
    ]
    result = await service.build_project_summary(company_id=request.company_id, project_id=request.project_id)
    assert result["planned_cost_amount"] == Decimal("50")
    assert result["procurement_approved_count"] == 2
    assert "cost_difference_amount" not in result
