from dataclasses import dataclass
from uuid import UUID

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class EffectivePermissions:
    company_id: UUID
    user_id: UUID
    person_id: UUID | None
    feature_permissions: dict[str, int]


class ErpPermissionClient:
    async def get_effective_permissions(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
    ) -> EffectivePermissions:
        if not settings.erp_service_key:
            raise RuntimeError("ERP service key is not configured for Construction permission lookup.")

        headers = {
            "X-Service-Key": settings.erp_service_key,
            "X-Company-ID": str(company_id),
            "X-User-ID": str(user_id),
        }
        async with httpx.AsyncClient(base_url=settings.erp_api_url, timeout=10) as client:
            response = await client.get("/v1/internal/construction/permissions", headers=headers)
            response.raise_for_status()
            payload = response.json()

        return EffectivePermissions(
            company_id=UUID(payload["company_id"]),
            user_id=UUID(payload["user_id"]),
            person_id=UUID(payload["person_id"]) if payload.get("person_id") else None,
            feature_permissions={key: int(value) for key, value in payload.get("feature_permissions", {}).items()},
        )
