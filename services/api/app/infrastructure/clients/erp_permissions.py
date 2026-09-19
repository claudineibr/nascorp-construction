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
    #: Quais obras este ator enxerga. Vem resolvido do ERP, que e dono da
    #: tabela de concessoes -- Obras nao tem como recalcular isso, e nem
    #: deveria: `role_ids` e descartado neste contrato, entao MASTER nao e
    #: deduzivel aqui. Por isso o ERP manda a resposta pronta, e nao os
    #: insumos para deduzi-la.
    record_access_unrestricted: bool = True
    allowed_project_ids: frozenset[UUID] = frozenset()


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
            # Campo AUSENTE e irrestrito, de proposito: ERP anterior ao plano 23
            # nao manda nada aqui, e fail-closed nesse caso trancaria Obras
            # inteira para todo mundo numa subida fora de ordem. Presente e
            # False, manda -- a lista vazia entao nega, e e o que tem de ser.
            record_access_unrestricted=bool(payload.get("record_access_unrestricted", True)),
            allowed_project_ids=frozenset(UUID(str(value)) for value in payload.get("allowed_project_ids", ())),
        )
