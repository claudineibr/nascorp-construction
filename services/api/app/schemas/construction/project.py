from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.constants import (
    ConstructionBlockStatus,
    ConstructionProjectStatus,
    ConstructionProjectType,
    ConstructionSchedulePhaseStatus,
    ConstructionUnitStatus,
)


class ConstructionProjectCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = ConstructionProjectStatus.DRAFT
    project_type: str = ConstructionProjectType.RESIDENTIAL_VERTICAL
    customer_person_id: UUID | None = None
    cnpj_spe: str | None = Field(default=None, max_length=18)
    address_json: dict[str, Any] | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None


class ConstructionProjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    project_type: str | None = None
    customer_person_id: UUID | None = None
    cnpj_spe: str | None = Field(default=None, max_length=18)
    address_json: dict[str, Any] | None = None
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
    project_type: str
    customer_person_id: UUID | None = None
    cnpj_spe: str | None = None
    address_json: dict[str, Any] | None = None
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
    floors_count: int | None = Field(default=None, ge=0)


class ConstructionBlockUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    floors_count: int | None = Field(default=None, ge=0)


class ConstructionBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    code: str
    name: str
    status: str
    floors_count: int | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionBlockListResponse(BaseModel):
    items: list[ConstructionBlockResponse]
    total: int


class ConstructionUnitCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    unit_type: str = Field(..., min_length=1, max_length=80)
    typology: str | None = Field(default=None, max_length=80)
    block_id: UUID | None = None
    floor: str | None = Field(default=None, max_length=30)
    private_area: Decimal | None = Field(default=None, ge=0)
    total_area: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    status: str = ConstructionUnitStatus.AVAILABLE


class ConstructionUnitUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    unit_type: str | None = Field(default=None, min_length=1, max_length=80)
    typology: str | None = Field(default=None, max_length=80)
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
    typology: str | None = None
    floor: str | None = None
    private_area: Decimal | None = None
    total_area: Decimal | None = None
    sale_price: Decimal | None = None
    buyer_person_id: UUID | None = None
    reserved_at: datetime | None = None
    reservation_expires_at: date | None = None
    sold_at: datetime | None = None
    external_contract_id: UUID | None = None
    external_contract_status: str | None = None
    external_receivable_id: UUID | None = None
    external_receivable_status: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ConstructionUnitListResponse(BaseModel):
    items: list[ConstructionUnitResponse]
    total: int


class ConstructionUnitReserveRequest(BaseModel):
    buyer_person_id: UUID
    reservation_expires_at: date | None = None


class ConstructionUnitSaleConfirmRequest(BaseModel):
    buyer_person_id: UUID
    sale_price: Decimal | None = Field(default=None, gt=0)
    first_due_date: date
    installments: int = Field(default=1, ge=1, le=120)


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


class ConstructionMeasurementCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    measured_amount: Decimal = Field(..., gt=0)
    due_date: date
    supplier_person_id: UUID | None = None


class ConstructionMeasurementUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    measured_amount: Decimal | None = Field(default=None, gt=0)
    due_date: date | None = None
    supplier_person_id: UUID | None = None


class ConstructionMeasurementReject(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ConstructionMeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    code: str
    description: str | None = None
    measured_amount: Decimal
    due_date: date
    supplier_person_id: UUID | None = None
    status: str
    approved_at: datetime | None = None
    external_accounts_payable_id: UUID | None = None
    external_accounts_payable_status: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionMeasurementListResponse(BaseModel):
    items: list[ConstructionMeasurementResponse]
    total: int


class ConstructionProcurementRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    estimated_amount: Decimal = Field(..., gt=0)


class ConstructionProcurementRequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    estimated_amount: Decimal | None = Field(default=None, gt=0)


class ConstructionProcurementRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    title: str
    description: str | None = None
    estimated_amount: Decimal
    status: str
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    external_procurement_id: UUID | None = None
    external_procurement_status: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionProcurementRequestListResponse(BaseModel):
    items: list[ConstructionProcurementRequestResponse]
    total: int
