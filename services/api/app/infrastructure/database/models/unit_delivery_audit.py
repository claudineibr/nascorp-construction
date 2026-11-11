from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA


class ConstructionUnitDeliveryAudit(Base):
    __tablename__ = "construction_unit_delivery_audits"
    __table_args__ = {"schema": CONSTRUCTION_SCHEMA}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    unit_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sale_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    previous_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
