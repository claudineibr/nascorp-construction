from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints


class AssistanceInputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ContactInput(AssistanceInputModel):
    id: UUID | None = None
    channel: Literal["whatsapp", "phone", "in_person"]
    detail: str | None = Field(default=None, max_length=2000)


class ComplaintInput(AssistanceInputModel):
    id: UUID | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(max_length=8000)
    provenance: Literal["pending", "valid", "invalid"] = "pending"
    analyzed_by_person_id: UUID | None = None
    analyzed_at: AwareDatetime | None = None


class ServiceInput(AssistanceInputModel):
    id: UUID | None = None
    complaint_id: UUID | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(max_length=8000)
    due_date: date | None = None
    executed_by_person_id: UUID | None = None
    executed_at: AwareDatetime | None = None
    inspected_by_person_id: UUID | None = None
    inspected_at: AwareDatetime | None = None


class AssistanceInput(AssistanceInputModel):
    project_id: UUID
    unit_id: UUID
    customer_person_id: UUID
    attendant_person_id: UUID
    analyst_person_id: UUID | None = None
    opened_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=8000)
    contacts: list[ContactInput] = Field(default_factory=list, max_length=100)
    complaints: list[ComplaintInput] = Field(default_factory=list, max_length=1000)
    services: list[ServiceInput] = Field(default_factory=list, max_length=1000)


class ReopenInput(AssistanceInputModel):
    justification: str = Field(min_length=10, max_length=2000)


class AssistanceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    project_id: UUID
    unit_id: UUID
    customer_person_id: UUID
    attendant_person_id: UUID
    analyst_person_id: UUID | None
    number: int
    status: Literal["open", "completed"]
    opened_at: datetime
    completed_at: datetime | None
    pending_stage: str
    overdue: bool
    project_name: str | None = None
    unit_code: str | None = None
    customer_name: str | None = None
    attendant_name: str | None = None


class AssistanceResponse(AssistanceSummary):
    notes: str | None
    source_id: int | None
    legacy_data: dict | None
    contacts: list[dict]
    complaints: list[dict]
    services: list[dict]
    history: list[dict]


class AssistancePrintResponse(BaseModel):
    sat: AssistanceResponse
    people: dict[UUID, str]
    city: str | None = None
    zip_code: str | None = None
    company_name: str | None = None
    company_logo_url: str | None = None


class AssistanceListResponse(BaseModel):
    items: list[AssistanceSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class AssistanceReference(BaseModel):
    id: UUID
    name: str
    buyer_person_id: UUID | None = None


class AssistanceReferenceList(BaseModel):
    items: list[AssistanceReference]
