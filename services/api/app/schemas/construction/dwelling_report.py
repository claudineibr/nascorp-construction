from datetime import date
from uuid import UUID

from pydantic import BaseModel


class DwellingReportRow(BaseModel):
    unit_id: UUID
    project_id: UUID
    project_name: str
    code: str
    description: str | None = None
    buyer_person_id: UUID | None = None
    correspondent: str | None = None
    correspondent_date: date | None = None
    client_situation: str | None = None
    client_situation_date: date | None = None
    process_status: str | None = None
    process_status_date: date | None = None


class DwellingReportResponse(BaseModel):
    project_name: str | None = None
    items: list[DwellingReportRow]
    total: int


class DwellingOption(BaseModel):
    id: str
    name: str


class DwellingReportOptions(BaseModel):
    items: list[DwellingOption]
    total: int
    page: int = 1
    page_size: int = 100
    total_pages: int = 1
