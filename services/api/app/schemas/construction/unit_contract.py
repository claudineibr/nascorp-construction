from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class UnitContractData(BaseModel):
    id: UUID
    project_id: UUID
    code: str
    description: str | None
    sale_price: Decimal | None
    discount_amount: Decimal | None
    buyer_person_id: UUID | None
    secondary_buyer_person_id: UUID | None
    broker_person_id: UUID | None
    external_contract_id: UUID | None


class ProjectContractData(BaseModel):
    id: UUID
    name: str
    contract_template_id: UUID | None
    lot: str | None
    registration: str | None
    land_area: Decimal | None
    expected_end_date: date | None
    address_json: dict[str, Any] | None


class SignalContractData(BaseModel):
    amount: Decimal
    due_date: date


class DocumentationContractData(BaseModel):
    amount: Decimal


class ConstructionUnitContractContextResponse(BaseModel):
    unit: UnitContractData
    project: ProjectContractData
    signals: list[SignalContractData]
    documentation: list[DocumentationContractData]


class UnitSummaryDocumentation(DocumentationContractData):
    label: str


class UnitSummarySignal(SignalContractData):
    payment_date: date | None
    composes_sale_price: bool


class ConstructionUnitSummaryContextResponse(BaseModel):
    project_id: UUID
    project_name: str
    cost_center_id: UUID | None
    unit_code: str
    unit_description: str | None
    buyer_id: UUID
    contract_id: UUID | None
    receivable_id: UUID | None
    sold_at: datetime | None
    sale_price: Decimal | None
    discount: Decimal | None
    sources: dict[str, Decimal]
    documentation: list[UnitSummaryDocumentation]
    signals: list[UnitSummarySignal]
