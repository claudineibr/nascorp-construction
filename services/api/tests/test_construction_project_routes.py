import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core import security as security_module
from app.core.security import get_permission_client
from app.domain.permissions import ConstructionFeature, PermissionAction
from app.infrastructure.clients import EffectivePermissions
from app.main import create_app
from app.presentation.routes.construction_projects import get_project_service


TEST_SECRET = "construction-route-test-secret"


class FakePermissionClient:
    def __init__(self, *, permissions: dict[str, int]) -> None:
        self.permissions = permissions

    async def get_effective_permissions(self, *, company_id: UUID, user_id: UUID) -> EffectivePermissions:
        return EffectivePermissions(
            company_id=company_id,
            user_id=user_id,
            person_id=uuid4(),
            feature_permissions=self.permissions,
        )


class FakeProjectService:
    async def create_project(self, *, company_id: UUID, request, actor_user_id: UUID | None = None):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=uuid4(),
            company_id=company_id,
            code=request.code,
            name=request.name,
            description=request.description,
            status=request.status,
            project_type=request.project_type,
            customer_person_id=None,
            cnpj_spe=None,
            address_json=None,
            start_date=request.start_date,
            expected_end_date=request.expected_end_date,
            actual_end_date=request.actual_end_date,
            synthetic_cost_center_id=None,
            analytic_cost_center_id=None,
            created_at=now,
            updated_at=now,
        )

    async def create_measurement(self, *, company_id: UUID, project_id: UUID, request):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=uuid4(),
            company_id=company_id,
            project_id=project_id,
            code=request.code,
            description=request.description,
            measured_amount=request.measured_amount,
            due_date=request.due_date,
            supplier_person_id=request.supplier_person_id,
            status="draft",
            approved_at=None,
            external_accounts_payable_id=None,
            external_accounts_payable_status=None,
            created_at=now,
            updated_at=now,
        )

    async def reserve_unit(self, *, company_id: UUID, unit_id: UUID, request):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=unit_id,
            company_id=company_id,
            project_id=uuid4(),
            block_id=None,
            code="UNIT-001",
            unit_type="apartment",
            floor="10",
            private_area="85.00",
            total_area="102.00",
            sale_price="450000.00",
            buyer_person_id=request.buyer_person_id,
            reserved_at=now,
            reservation_expires_at=request.reservation_expires_at,
            sold_at=None,
            external_contract_id=None,
            external_contract_status=None,
            external_receivable_id=None,
            external_receivable_status=None,
            status="reserved",
            created_at=now,
            updated_at=now,
        )

    async def confirm_unit_sale(self, *, company_id: UUID, unit_id: UUID, request, actor_user_id=None):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=unit_id,
            company_id=company_id,
            project_id=uuid4(),
            block_id=None,
            code="UNIT-001",
            unit_type="apartment",
            floor="10",
            private_area="85.00",
            total_area="102.00",
            sale_price=request.sale_price or "450000.00",
            buyer_person_id=request.buyer_person_id,
            reserved_at=now,
            reservation_expires_at=None,
            sold_at=now,
            external_contract_id=uuid4(),
            external_contract_status="ACTIVE",
            external_receivable_id=uuid4(),
            external_receivable_status="OPEN",
            status="sold",
            created_at=now,
            updated_at=now,
        )

    async def create_procurement_request(self, *, company_id: UUID, project_id: UUID, request):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=uuid4(),
            company_id=company_id,
            project_id=project_id,
            title=request.title,
            code=request.code or "REQ-FAKE01",
            description=request.description,
            estimated_amount=request.estimated_amount,
            needed_by_date=request.needed_by_date,
            supplier_person_id=request.supplier_person_id,
            status="draft",
            rejection_reason=None,
            approved_by_user_id=None,
            approved_at=None,
            external_procurement_id=None,
            external_procurement_status=None,
            created_at=now,
            updated_at=now,
        )

    async def submit_procurement_request(self, *, company_id: UUID, procurement_request_id: UUID, actor_user_id=None):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=procurement_request_id,
            company_id=company_id,
            project_id=uuid4(),
            code="REQ-FAKE01",
            title="Facade package",
            description=None,
            estimated_amount="65000.00",
            needed_by_date=None,
            supplier_person_id=None,
            status="pending_approval",
            rejection_reason=None,
            approved_by_user_id=None,
            approved_at=None,
            external_procurement_id=None,
            external_procurement_status=None,
            created_at=now,
            updated_at=now,
        )


def create_test_client(*, permissions: dict[str, int]) -> TestClient:
    security_module.settings.jwt_secret_key = TEST_SECRET
    app = create_app()
    app.dependency_overrides[get_permission_client] = lambda: FakePermissionClient(permissions=permissions)
    app.dependency_overrides[get_project_service] = lambda: FakeProjectService()
    return TestClient(app)


def make_authorization_header(*, user_id: UUID) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(user_id), "exp": int((datetime.now(tz=UTC) + timedelta(minutes=10)).timestamp())}
    header_value = base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_value = base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signed_value = f"{header_value}.{payload_value}".encode()
    signature = hmac.new(TEST_SECRET.encode(), signed_value, hashlib.sha256).digest()
    signature_value = base64url_encode(signature)
    return f"Bearer {header_value}.{payload_value}.{signature_value}"


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def test_create_project_rejects_invalid_jwt() -> None:
    client = create_test_client(permissions={ConstructionFeature.PROJECTS: PermissionAction.FULL})

    response = client.post(
        "/v1/construction/projects",
        headers={"Authorization": "Bearer invalid-token", "X-Company-ID": str(uuid4())},
        json={"code": "OBRA-001", "name": "Obra Alpha"},
    )

    assert response.status_code == 401


def test_create_project_requires_company_header() -> None:
    user_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.PROJECTS: PermissionAction.FULL})

    response = client.post(
        "/v1/construction/projects",
        headers={"Authorization": make_authorization_header(user_id=user_id)},
        json={"code": "OBRA-001", "name": "Obra Alpha"},
    )

    assert response.status_code == 422


def test_project_routes_accept_browser_preflight_from_erp_host() -> None:
    client = create_test_client(permissions={ConstructionFeature.PROJECTS: PermissionAction.FULL})

    response = client.options(
        "/v1/construction/projects?page=1&page_size=20",
        headers={
            "Origin": "http://127.0.0.1:8001",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-company-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8001"


def test_create_project_denies_missing_create_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.PROJECTS: PermissionAction.READ})

    response = client.post(
        "/v1/construction/projects",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={"code": "OBRA-001", "name": "Obra Alpha"},
    )

    assert response.status_code == 403


def test_create_project_accepts_jwt_company_and_create_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.PROJECTS: PermissionAction.FULL})

    response = client.post(
        "/v1/construction/projects",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={"code": "OBRA-001", "name": "Obra Alpha", "status": "draft"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["company_id"] == str(company_id)
    assert payload["code"] == "OBRA-001"
    assert payload["name"] == "Obra Alpha"
    assert payload["status"] == "draft"


def test_create_measurement_denies_missing_create_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    project_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.MEASUREMENTS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/projects/{project_id}/measurements",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={
            "code": "MED-001",
            "measured_amount": "1200.00",
            "due_date": "2026-05-15",
        },
    )

    assert response.status_code == 403


def test_create_measurement_accepts_valid_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    project_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.MEASUREMENTS: PermissionAction.CREATE})

    response = client.post(
        f"/v1/construction/projects/{project_id}/measurements",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={
            "code": "MED-001",
            "description": "Medição fase fundação",
            "measured_amount": "1200.00",
            "due_date": "2026-05-15",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["company_id"] == str(company_id)
    assert payload["project_id"] == str(project_id)
    assert payload["code"] == "MED-001"
    assert payload["status"] == "draft"


def test_reserve_unit_requires_update_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    unit_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/units/{unit_id}/reserve",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={"buyer_person_id": str(uuid4())},
    )

    assert response.status_code == 403


def test_confirm_unit_sale_returns_external_contract_snapshot() -> None:
    user_id = uuid4()
    company_id = uuid4()
    unit_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE})

    response = client.post(
        f"/v1/construction/units/{unit_id}/confirm-sale",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={
            "buyer_person_id": str(uuid4()),
            "sale_price": "450000.00",
            "first_due_date": "2026-06-10",
            "installments": 12,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(unit_id)
    assert payload["company_id"] == str(company_id)
    assert payload["status"] == "sold"
    assert payload["external_contract_status"] == "ACTIVE"
    assert payload["external_receivable_status"] == "OPEN"


def test_create_procurement_request_requires_create_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    project_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.PROCUREMENT: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/projects/{project_id}/procurement-requests",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
        json={
            "title": "Concrete package",
            "estimated_amount": "12000.00",
        },
    )

    assert response.status_code == 403


def test_submit_procurement_request_accepts_update_permission() -> None:
    user_id = uuid4()
    company_id = uuid4()
    procurement_request_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.PROCUREMENT: PermissionAction.UPDATE})

    response = client.post(
        f"/v1/construction/procurement-requests/{procurement_request_id}/submit",
        headers={
            "Authorization": make_authorization_header(user_id=user_id),
            "X-Company-ID": str(company_id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(procurement_request_id)
    assert payload["company_id"] == str(company_id)
    assert payload["status"] == "pending_approval"
