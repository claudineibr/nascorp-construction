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
            start_date=request.start_date,
            expected_end_date=request.expected_end_date,
            actual_end_date=request.actual_end_date,
            synthetic_cost_center_id=None,
            analytic_cost_center_id=None,
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
