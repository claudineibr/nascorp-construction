from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectDocumentPreview(BaseModel):
    kind: Literal["contract", "measurement"]
    file_name: str
    snapshot: dict


class ProjectDocumentResponse(ProjectDocumentPreview):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime | None = None


class ProjectDocumentHistory(BaseModel):
    items: list[ProjectDocumentResponse]
    total: int
    today: date
