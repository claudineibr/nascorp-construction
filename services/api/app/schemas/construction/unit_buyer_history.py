from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UnitBuyerHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    buyer_person_id: UUID | None = None
    buyer_name: str | None = None
    included_at: datetime | None = None
    excluded_at: datetime | None = None
    included_by_name: str | None = None
    excluded_by_name: str | None = None
    reason: str | None = None
    origin_label: str


class UnitBuyerHistoryList(BaseModel):
    items: list[UnitBuyerHistoryResponse]
    total: int
    page: int = 1
    page_size: int
    total_pages: int
