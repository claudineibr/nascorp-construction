from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.constants import (
    ConstructionBlockStatus,
    ConstructionProjectStatus,
    ConstructionSchedulePhaseStatus,
    ConstructionUnitStatus,
)


class ConstructionProjectCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = ConstructionProjectStatus.DRAFT
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None


class ConstructionProjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None
    synthetic_cost_center_id: UUID | None = None
    analytic_cost_center_id: UUID | None = None


class ConstructionProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    code: str
    name: str
    description: str | None = None
    status: str
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None
    synthetic_cost_center_id: UUID | None = None
    analytic_cost_center_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionProjectListResponse(BaseModel):
    items: list[ConstructionProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConstructionBlockCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    status: str = ConstructionBlockStatus.ACTIVE


class ConstructionBlockUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None


class ConstructionBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    code: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ConstructionBlockListResponse(BaseModel):
    items: list[ConstructionBlockResponse]
    total: int


class ConstructionUnitCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    unit_type: str = Field(..., min_length=1, max_length=80)
    block_id: UUID | None = None
    floor: str | None = Field(default=None, max_length=30)
    private_area: Decimal | None = Field(default=None, ge=0)
    total_area: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    status: str = ConstructionUnitStatus.AVAILABLE


class ConstructionUnitUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    unit_type: str | None = Field(default=None, min_length=1, max_length=80)
    block_id: UUID | None = None
    floor: str | None = Field(default=None, max_length=30)
    private_area: Decimal | None = Field(default=None, ge=0)
    total_area: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    status: str | None = None


class ConstructionUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    block_id: UUID | None = None
    code: str
    unit_type: str
    floor: str | None = None
    private_area: Decimal | None = None
    total_area: Decimal | None = None
    sale_price: Decimal | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ConstructionUnitListResponse(BaseModel):
    items: list[ConstructionUnitResponse]
    total: int


class ConstructionSchedulePhaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sequence_order: int = Field(..., ge=1)
    status: str = ConstructionSchedulePhaseStatus.PLANNED
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    progress_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class ConstructionSchedulePhaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence_order: int | None = Field(default=None, ge=1)
    status: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    progress_percent: Decimal | None = Field(default=None, ge=0, le=100)


class ConstructionSchedulePhaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    name: str
    sequence_order: int
    status: str
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    progress_percent: Decimal
    created_at: datetime
    updated_at: datetime


class ConstructionSchedulePhaseListResponse(BaseModel):
    items: list[ConstructionSchedulePhaseResponse]
    total: int
