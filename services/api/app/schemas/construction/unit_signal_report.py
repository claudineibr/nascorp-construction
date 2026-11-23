from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


UnitSignalStatusFilter = Literal["all", "unpaid", "open", "overdue", "paid"]


class UnitSignalReportRow(BaseModel):
    project_id: UUID
    project_name: str
    unit_id: UUID
    unit_code: str
    unit_description: str | None
    beneficiary_person_id: UUID
    sequence_number: int
    amount: Decimal
    due_date: date
    payment_date: date | None
    status: Literal["open", "overdue", "paid"]


class UnitSignalProjectOption(BaseModel):
    id: UUID
    name: str


class UnitSignalProjectOptions(BaseModel):
    items: list[UnitSignalProjectOption]
    beneficiary_id: UUID | None


class UnitSignalReportResponse(BaseModel):
    reference_date: date
    items: list[UnitSignalReportRow]
    project_name: str | None
