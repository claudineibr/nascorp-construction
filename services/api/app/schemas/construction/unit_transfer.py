from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConstructionUnitTransferRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target_unit_id: UUID
    reason: str = Field(min_length=5, max_length=1000)
    source_sale_id: UUID | None = None

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError('Informe um motivo com pelo menos 5 caracteres.')
        return value


class ConstructionUnitTransferResponse(BaseModel):
    transfer_id: UUID | None = None
    source_unit_id: UUID
    source_sale_id: UUID | None = None
    target_unit_id: UUID
    source_label: str
    target_label: str
    status: str
    occurred_at: datetime | None = None
    reason: str
    financial: dict = Field(default_factory=dict)


class ConstructionUnitTransferTarget(BaseModel):
    id: UUID
    code: str
    description: str | None = None
    project_id: UUID
    project_name: str
    project_code: str
    label: str


class ConstructionUnitTransferTargetList(BaseModel):
    items: list[ConstructionUnitTransferTarget]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConstructionUnitTransferList(BaseModel):
    items: list[ConstructionUnitTransferResponse]
    total: int
    page: int = 1
    page_size: int = 100
    total_pages: int = 1
