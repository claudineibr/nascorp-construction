from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.core.context import ConstructionContext
from app.infrastructure.clients import EffectivePermissions, ErpPermissionClient


class PermissionClient(Protocol):
    async def get_effective_permissions(self, *, company_id: UUID, user_id: UUID) -> EffectivePermissions:
        raise NotImplementedError


async def get_permission_client() -> PermissionClient:
    return ErpPermissionClient()


async def require_service_key(x_service_key: str = Header(..., alias="X-Service-Key")) -> None:
    if not settings.erp_service_key or not hmac.compare_digest(x_service_key, settings.erp_service_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service key")


async def get_construction_context(
    authorization: str = Header(..., alias="Authorization"),
    x_company_id: UUID = Header(..., alias="X-Company-ID"),
    permission_client: PermissionClient = Depends(get_permission_client),
) -> ConstructionContext:
    token = _extract_bearer_token(authorization=authorization)
    payload = _decode_jwt(token=token)
    user_id = _extract_user_id(payload=payload)
    effective_permissions = await _resolve_permissions(
        permission_client=permission_client,
        company_id=x_company_id,
        user_id=user_id,
    )
    if effective_permissions.company_id != x_company_id or effective_permissions.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission context mismatch")

    return ConstructionContext(
        company_id=x_company_id,
        user_id=user_id,
        person_id=effective_permissions.person_id,
        feature_permissions=effective_permissions.feature_permissions,
    )


def require_permission(feature: str, action: int):
    async def dependency(ctx: ConstructionContext = Depends(get_construction_context)) -> ConstructionContext:
        if not ctx.can(feature=feature, action=action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient Construction permission")

        return ctx

    return dependency


def _extract_bearer_token(*, authorization: str) -> str:
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    return authorization.removeprefix(prefix).strip()


def _decode_jwt(*, token: str) -> dict[str, Any]:
    if not settings.jwt_secret_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWT secret is not configured")

    try:
        header_value, payload_value, signature_value = token.split(".")
        header = json.loads(_base64url_decode(value=header_value))
        payload = json.loads(_base64url_decode(value=payload_value))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    algorithm = header.get("alg")
    if algorithm != settings.jwt_algorithm or algorithm != "HS256":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported token algorithm")

    signed_value = f"{header_value}.{payload_value}".encode()
    expected_signature = hmac.new(settings.jwt_secret_key.encode(), signed_value, hashlib.sha256).digest()
    received_signature = _base64url_decode(value=signature_value)
    if not hmac.compare_digest(expected_signature, received_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    expires_at = payload.get("exp")
    if expires_at is not None and datetime.fromtimestamp(int(expires_at), tz=UTC) <= datetime.now(tz=UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    return payload


def _extract_user_id(*, payload: dict[str, Any]) -> UUID:
    user_value = payload.get("user_id") or payload.get("sub")
    if not user_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token user is missing")

    try:
        return UUID(str(user_value))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token user is invalid") from exc


async def _resolve_permissions(
    *,
    permission_client: PermissionClient,
    company_id: UUID,
    user_id: UUID,
) -> EffectivePermissions:
    try:
        return await permission_client.get_effective_permissions(company_id=company_id, user_id=user_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unable to resolve Construction permissions") from exc


def _base64url_decode(*, value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
