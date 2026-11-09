from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA


class ConstructionProjectDocument(Base):
    __tablename__ = "construction_project_documents"
    __table_args__ = (
        UniqueConstraint("company_id", "identity", name="uq_construction_project_document_identity"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column()
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id", ondelete="CASCADE"), index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16))
    identity: Mapped[str] = mapped_column(String(160))
    sha256: Mapped[str] = mapped_column(String(64))
    file_name: Mapped[str] = mapped_column(String(255))
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
