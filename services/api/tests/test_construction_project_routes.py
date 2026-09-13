import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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

    async def build_measurement_items_summary(self, *, company_id: UUID, measurement_id: UUID):
        return {
            "items_total_amount": Decimal("0"),
            "items_count": 0,
            "pending_inspections_count": 0,
            "open_occurrences_count": 0,
        }

    async def create_measurement(self, *, company_id: UUID, project_id: UUID, request, actor_user_id=None):
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
            created_by_user_id=actor_user_id,
            submitted_by_user_id=None,
            submitted_at=None,
            approved_by_user_id=None,
            approved_at=None,
            rejected_by_user_id=None,
            rejected_at=None,
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

    def __init__(self) -> None:
        self.paid_installments: list[dict] = []
        self.reversed_installments: list[dict] = []
        self.deleted_installments: list[dict] = []
        self.deleted_adjustments: list[dict] = []

    async def pay_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        request,
        receivable_id=None,
        user_id=None,
    ) -> dict:
        self.paid_installments.append(
            {
                "unit_id": unit_id,
                "installment_number": installment_number,
                "receivable_id": receivable_id,
                # A tela manda N formas: capturar so a primeira faria o teste
                # passar com metade do pagamento perdido no caminho.
                "payments": [line.model_dump(mode="json") for line in request.payments],
            }
        )
        return {"id": str(uuid4()), "installment_number": installment_number, "status": "PAID"}

    async def reverse_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        receivable_id=None,
        user_id=None,
    ) -> dict:
        self.reversed_installments.append(
            {
                "unit_id": unit_id,
                "installment_number": installment_number,
                "receivable_id": receivable_id,
            }
        )
        return {"id": str(uuid4()), "installment_number": installment_number, "status": "OPEN"}

    async def delete_unit_installment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        installment_number: int,
        receivable_id=None,
        user_id=None,
    ) -> None:
        self.deleted_installments.append(
            {
                "unit_id": unit_id,
                "installment_number": installment_number,
                "receivable_id": receivable_id,
            }
        )

    async def delete_unit_adjustment(
        self,
        *,
        company_id: UUID,
        unit_id: UUID,
        receivable_id: UUID,
        reason: str,
        user_id=None,
    ) -> None:
        self.deleted_adjustments.append(
            {"unit_id": unit_id, "receivable_id": receivable_id, "reason": reason}
        )

    def _fake_commission(self, *, company_id: UUID, commission_id: UUID, unit_id: UUID, payment_date=None):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=commission_id,
            company_id=company_id,
            unit_id=unit_id,
            beneficiary_person_id=uuid4(),
            sequence_number=1,
            amount="5000.00",
            due_date="2026-06-10",
            payment_date=payment_date,
            composes_sale_price=False,
            receipt_template_id=None,
            document_number=None,
            notes=None,
            created_at=now,
            updated_at=now,
        )

    async def list_unit_commissions(self, *, company_id: UUID, unit_id: UUID):
        return [self._fake_commission(company_id=company_id, commission_id=uuid4(), unit_id=unit_id)]

    async def create_unit_commissions(self, *, company_id: UUID, unit_id: UUID, request):
        return [
            self._fake_commission(company_id=company_id, commission_id=uuid4(), unit_id=unit_id)
            for _ in range(request.installments)
        ]

    async def update_unit_commission(self, *, company_id: UUID, commission_id: UUID, request):
        return self._fake_commission(company_id=company_id, commission_id=commission_id, unit_id=uuid4())

    async def settle_unit_commission(self, *, company_id: UUID, commission_id: UUID, payment_date):
        return self._fake_commission(
            company_id=company_id,
            commission_id=commission_id,
            unit_id=uuid4(),
            payment_date=payment_date,
        )

    async def delete_unit_commission(self, *, company_id: UUID, commission_id: UUID) -> None:
        return None

    async def create_unit_adjustment(self, *, company_id: UUID, unit_id: UUID, request, user_id=None):
        return {
            "construction_unit_id": str(unit_id),
            "contract_id": str(uuid4()),
            "receivable_id": str(uuid4()),
            "receivable_status": "OPEN",
            "total_amount": str(request.amount),
            "installments": request.installments,
        }

    async def list_documentation_types(self, *, company_id: UUID, only_active=True, search=None):
        now = datetime.now(tz=UTC)
        return [
            SimpleNamespace(
                id=uuid4(),
                company_id=company_id,
                name="Cartório",
                system_code="NOTARY",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        ]

    async def create_documentation_type(self, *, company_id: UUID, request):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=uuid4(),
            company_id=company_id,
            name=request.name,
            system_code=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    async def update_documentation_type(self, *, company_id: UUID, documentation_type_id: UUID, request):
        now = datetime.now(tz=UTC)
        return SimpleNamespace(
            id=documentation_type_id,
            company_id=company_id,
            name=request.name or "Cartório",
            system_code="NOTARY",
            is_active=True if request.is_active is None else request.is_active,
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


def create_test_client(*, permissions: dict[str, int], service: "FakeProjectService | None" = None) -> TestClient:
    security_module.settings.jwt_secret_key = TEST_SECRET
    app = create_app()
    project_service = service or FakeProjectService()
    app.dependency_overrides[get_permission_client] = lambda: FakePermissionClient(permissions=permissions)
    app.dependency_overrides[get_project_service] = lambda: project_service
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
            "unit_id": str(uuid4()),
            "schedule_phase_id": str(uuid4()),
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


def test_list_documentation_types_requires_units_read_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.CREATE})

    response = client.get(
        "/v1/construction/documentation-types",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 403


def test_list_documentation_types_accepts_units_read_permission() -> None:
    company_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.get(
        "/v1/construction/documentation-types",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(company_id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Cartório"
    assert payload["items"][0]["system_code"] == "NOTARY"


def test_create_documentation_type_requires_units_update_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        "/v1/construction/documentation-types",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"name": "SANESUL"},
    )

    assert response.status_code == 403


def test_create_documentation_type_accepts_units_update_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE})

    response = client.post(
        "/v1/construction/documentation-types",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"name": "SANESUL"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "SANESUL"


def test_update_documentation_type_requires_units_update_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.patch(
        f"/v1/construction/documentation-types/{uuid4()}",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"is_active": False},
    )

    assert response.status_code == 403


def test_update_documentation_type_accepts_units_update_permission() -> None:
    documentation_type_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE})

    response = client.patch(
        f"/v1/construction/documentation-types/{documentation_type_id}",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"is_active": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(documentation_type_id)
    assert payload["is_active"] is False


def test_list_unit_commissions_requires_units_read_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.PROJECTS: PermissionAction.FULL})

    response = client.get(
        f"/v1/construction/units/{uuid4()}/commissions",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 403


def test_list_unit_commissions_accepts_units_read_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.get(
        f"/v1/construction/units/{uuid4()}/commissions",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_create_unit_commissions_requires_units_create_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/units/{uuid4()}/commissions",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={
            "beneficiary_person_id": str(uuid4()),
            "amount": "5000.00",
            "due_date": "2026-06-10",
            "installments": 2,
        },
    )

    assert response.status_code == 403


def test_settle_unit_commission_requires_units_update_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/commissions/{uuid4()}/settle",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"payment_date": "2026-06-12"},
    )

    assert response.status_code == 403


def test_settle_unit_commission_accepts_units_update_permission() -> None:
    commission_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE})

    response = client.post(
        f"/v1/construction/commissions/{commission_id}/settle",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"payment_date": "2026-06-12"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(commission_id)
    assert payload["payment_date"] == "2026-06-12"


def test_create_unit_adjustment_requires_units_create_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/units/{uuid4()}/adjustments",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"amount": "8000.00", "installments": 2, "first_due_date": "2026-06-10"},
    )

    assert response.status_code == 403


def test_create_unit_adjustment_accepts_units_create_permission() -> None:
    unit_id = uuid4()
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.CREATE})

    response = client.post(
        f"/v1/construction/units/{unit_id}/adjustments",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"amount": "8000.00", "installments": 2, "first_due_date": "2026-06-10"},
    )

    assert response.status_code == 200
    assert response.json()["construction_unit_id"] == str(unit_id)


def test_pay_unit_installment_requires_units_update_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/units/{uuid4()}/installments/1/pay",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"payment_method": "PIX"},
    )

    assert response.status_code == 403


def test_pay_unit_installment_carries_the_adjustment_receivable() -> None:
    """Sem o ``receivable_id`` da série, o ERP baixaria a parcela homônima da
    venda em vez da do aditivo."""
    unit_id = uuid4()
    receivable_id = uuid4()
    service = FakeProjectService()
    client = create_test_client(
        permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE},
        service=service,
    )

    response = client.post(
        f"/v1/construction/units/{unit_id}/installments/2/pay",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={
            "receivable_id": str(receivable_id),
            "payments": [{"payment_method": "PIX", "amount": "4000.00"}],
        },
    )

    assert response.status_code == 200
    assert service.paid_installments[0]["receivable_id"] == receivable_id
    assert service.paid_installments[0]["installment_number"] == 2


def test_pay_unit_installment_carries_every_payment_line() -> None:
    """A parcela e quitada por N formas: o que a tela compos tem de chegar
    inteiro ao ERP, cada linha com a sua conta bancaria e a sua data."""
    unit_id = uuid4()
    bank_account_id = uuid4()
    service = FakeProjectService()
    client = create_test_client(
        permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE},
        service=service,
    )

    response = client.post(
        f"/v1/construction/units/{unit_id}/installments/1/pay",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={
            "payments": [
                {
                    "payment_method": "PIX",
                    "amount": "2500.00",
                    "paid_at": "2026-09-10T00:00:00",
                    "company_bank_account_id": str(bank_account_id),
                },
                {"payment_method": "TRANSFER", "amount": "1500.00", "paid_at": "2026-09-13T00:00:00"},
            ],
        },
    )

    assert response.status_code == 200
    lines = service.paid_installments[0]["payments"]
    assert [line["payment_method"] for line in lines] == ["PIX", "TRANSFER"]
    assert [line["amount"] for line in lines] == ["2500.00", "1500.00"]
    assert lines[0]["company_bank_account_id"] == str(bank_account_id)
    assert lines[1]["company_bank_account_id"] is None


def test_pay_unit_installment_refuses_a_payment_without_lines() -> None:
    """Baixa sem forma de recebimento nao existe -- o contrato recusa antes de
    chegar ao ERP."""
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE})

    response = client.post(
        f"/v1/construction/units/{uuid4()}/installments/1/pay",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"payments": []},
    )

    assert response.status_code == 422


def test_reverse_unit_installment_carries_the_adjustment_receivable() -> None:
    """O estorno da unidade existe para o operador nao depender do Contas a
    Receber -- e precisa acertar a serie, como a baixa."""
    unit_id = uuid4()
    receivable_id = uuid4()
    service = FakeProjectService()
    client = create_test_client(
        permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE},
        service=service,
    )

    response = client.post(
        f"/v1/construction/units/{unit_id}/installments/2/reverse",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={"receivable_id": str(receivable_id)},
    )

    assert response.status_code == 200
    assert service.reversed_installments[0]["receivable_id"] == receivable_id
    assert service.reversed_installments[0]["installment_number"] == 2


def test_reverse_unit_installment_requires_units_update_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.READ})

    response = client.post(
        f"/v1/construction/units/{uuid4()}/installments/1/reverse",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
        json={},
    )

    assert response.status_code == 403


def test_delete_unit_installment_requires_units_delete_permission() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.UPDATE})

    response = client.delete(
        f"/v1/construction/units/{uuid4()}/installments/1",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 403


def test_delete_unit_installment_accepts_units_delete_permission() -> None:
    receivable_id = uuid4()
    service = FakeProjectService()
    client = create_test_client(
        permissions={ConstructionFeature.UNITS: PermissionAction.DELETE},
        service=service,
    )

    response = client.delete(
        f"/v1/construction/units/{uuid4()}/installments/3?receivable_id={receivable_id}",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 204
    assert service.deleted_installments[0]["receivable_id"] == receivable_id


def test_delete_unit_adjustment_requires_a_reason() -> None:
    client = create_test_client(permissions={ConstructionFeature.UNITS: PermissionAction.DELETE})

    response = client.delete(
        f"/v1/construction/units/{uuid4()}/adjustments/{uuid4()}",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 422


def test_delete_unit_adjustment_accepts_units_delete_permission() -> None:
    receivable_id = uuid4()
    service = FakeProjectService()
    client = create_test_client(
        permissions={ConstructionFeature.UNITS: PermissionAction.DELETE},
        service=service,
    )

    response = client.delete(
        f"/v1/construction/units/{uuid4()}/adjustments/{receivable_id}?reason=lancado%20por%20engano",
        headers={
            "Authorization": make_authorization_header(user_id=uuid4()),
            "X-Company-ID": str(uuid4()),
        },
    )

    assert response.status_code == 204
    assert service.deleted_adjustments[0]["reason"] == "lancado por engano"
