from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.presentation.routes.internal_events import get_project_service


class FakeProjectService:
    def __init__(self) -> None:
        self.received_event = None

    async def apply_cost_center_created_event(self, *, event):
        self.received_event = event
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=event.aggregate_id,
            company_id=event.company_id,
            code="OBRA-001",
            name="Obra Alpha",
            description=None,
            status="draft",
            project_type="residential_vertical",
            customer_person_id=None,
            cnpj_spe=None,
            address_json=None,
            start_date=None,
            expected_end_date=None,
            actual_end_date=None,
            synthetic_cost_center_id=uuid4(),
            analytic_cost_center_id=uuid4(),
            created_at=now,
            updated_at=now,
        )

    async def apply_accounts_payable_updated_event(self, *, event):
        self.received_event = event
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=event.aggregate_id,
            company_id=event.company_id,
            project_id=uuid4(),
            code="MED-001",
            description="Measurement sync",
            measured_amount=Decimal("1200.00"),
            due_date=date(2026, 5, 15),
            supplier_person_id=None,
            status="approved",
            approved_at=now,
            external_accounts_payable_id=uuid4(),
            external_accounts_payable_status="PAID",
            created_at=now,
            updated_at=now,
        )

    async def apply_contract_status_updated_event(self, *, event):
        self.received_event = event
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=event.aggregate_id,
            company_id=event.company_id,
            project_id=uuid4(),
            block_id=None,
            code="UNIT-001",
            unit_type="apartment",
            floor="10",
            private_area=Decimal("85.00"),
            total_area=Decimal("102.00"),
            sale_price=Decimal("450000.00"),
            buyer_person_id=uuid4(),
            reserved_at=now,
            reservation_expires_at=None,
            sold_at=now,
            external_contract_id=uuid4(),
            external_contract_status="CANCELED",
            external_receivable_id=uuid4(),
            external_receivable_status="CANCELED",
            status="available",
            created_at=now,
            updated_at=now,
        )


def make_payload(*, company_id, project_id, event_id):
    return {
        "event_id": str(event_id),
        "event_type": "erp.cost_center.created.v1",
        "event_version": 1,
        "company_id": str(company_id),
        "aggregate_id": str(project_id),
        "aggregate_type": "construction_project",
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "producer": "erp-api",
        "correlation_id": str(event_id),
        "causation_id": None,
        "payload": {
            "construction_project_id": str(project_id),
            "synthetic_cost_center_id": str(uuid4()),
            "analytic_cost_center_id": str(uuid4()),
        },
    }


def make_measurement_payload(*, company_id, measurement_id, event_id):
    return {
        "event_id": str(event_id),
        "event_type": "erp.accounts_payable.updated.v1",
        "event_version": 1,
        "company_id": str(company_id),
        "aggregate_id": str(measurement_id),
        "aggregate_type": "construction_measurement",
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "producer": "erp-api",
        "correlation_id": str(event_id),
        "causation_id": None,
        "payload": {
            "construction_measurement_id": str(measurement_id),
            "accounts_payable_document_id": str(uuid4()),
            "accounts_payable_status": "PAID",
        },
    }


def make_contract_status_payload(*, company_id, unit_id, event_id):
    return {
        "event_id": str(event_id),
        "event_type": "erp.contract.status.updated.v1",
        "event_version": 1,
        "company_id": str(company_id),
        "aggregate_id": str(unit_id),
        "aggregate_type": "construction_unit",
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        "producer": "erp-api",
        "correlation_id": str(event_id),
        "causation_id": None,
        "payload": {
            "construction_unit_id": str(unit_id),
            "external_contract_id": str(uuid4()),
            "contract_status": "CANCELED",
            "external_receivable_id": str(uuid4()),
            "receivable_status": "CANCELED",
        },
    }


def test_internal_event_route_rejects_invalid_service_key() -> None:
    settings.erp_service_key = "expected-key"
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/v1/internal/events/erp-cost-center-created",
        headers={"X-Service-Key": "wrong-key"},
        json=make_payload(company_id=uuid4(), project_id=uuid4(), event_id=uuid4()),
    )

    assert response.status_code == 401


def test_internal_event_route_applies_cost_center_confirmation() -> None:
    settings.erp_service_key = "expected-key"
    fake_service = FakeProjectService()
    app = create_app()
    app.dependency_overrides[get_project_service] = lambda: fake_service
    client = TestClient(app)
    company_id = uuid4()
    project_id = uuid4()
    event_id = uuid4()

    response = client.post(
        "/v1/internal/events/erp-cost-center-created",
        headers={"X-Service-Key": "expected-key"},
        json=make_payload(company_id=company_id, project_id=project_id, event_id=event_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(project_id)
    assert payload["company_id"] == str(company_id)
    assert fake_service.received_event.event_id == event_id
    assert fake_service.received_event.event_type == "erp.cost_center.created.v1"


def test_internal_event_route_applies_accounts_payable_status_update() -> None:
    settings.erp_service_key = "expected-key"
    fake_service = FakeProjectService()
    app = create_app()
    app.dependency_overrides[get_project_service] = lambda: fake_service
    client = TestClient(app)
    company_id = uuid4()
    measurement_id = uuid4()
    event_id = uuid4()

    response = client.post(
        "/v1/internal/events/erp-accounts-payable-updated",
        headers={"X-Service-Key": "expected-key"},
        json=make_measurement_payload(company_id=company_id, measurement_id=measurement_id, event_id=event_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(measurement_id)
    assert payload["company_id"] == str(company_id)
    assert payload["status"] == "approved"
    assert payload["external_accounts_payable_status"] == "PAID"
    assert fake_service.received_event.event_type == "erp.accounts_payable.updated.v1"


def test_internal_event_route_applies_contract_status_update() -> None:
    settings.erp_service_key = "expected-key"
    fake_service = FakeProjectService()
    app = create_app()
    app.dependency_overrides[get_project_service] = lambda: fake_service
    client = TestClient(app)
    company_id = uuid4()
    unit_id = uuid4()
    event_id = uuid4()

    response = client.post(
        "/v1/internal/events/erp-contract-status-updated",
        headers={"X-Service-Key": "expected-key"},
        json=make_contract_status_payload(company_id=company_id, unit_id=unit_id, event_id=event_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(unit_id)
    assert payload["status"] == "available"
    assert payload["external_contract_status"] == "CANCELED"
    assert fake_service.received_event.event_type == "erp.contract.status.updated.v1"
