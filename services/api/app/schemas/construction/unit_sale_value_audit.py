from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UnitSaleValueAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_id: UUID
    sale_sequence: int
    actor_user_id: UUID | None
    actor_name: str | None
    reason: str
    old_data: dict
    new_data: dict
    changed_at: datetime


class UnitSaleValueAuditListResponse(BaseModel):
    items: list[UnitSaleValueAuditResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
