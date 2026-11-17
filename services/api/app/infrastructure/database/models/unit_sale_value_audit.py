from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import mapped_column

from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA


class ConstructionUnitSaleValueAudit(Base):
    __tablename__ = "construction_unit_sale_value_audits"
    __table_args__ = (
        Index("ix_unit_sale_value_audit_history", "company_id", "unit_id", "changed_at", "id"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = mapped_column(UUID(as_uuid=True), nullable=False)
    unit_id = mapped_column(UUID(as_uuid=True), nullable=False)
    sale_id = mapped_column(UUID(as_uuid=True), nullable=False)
    sale_sequence = mapped_column(Integer, nullable=False)
    actor_user_id = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_name = mapped_column(String(255), nullable=True)
    reason = mapped_column(Text, nullable=False)
    old_data = mapped_column(JSONB, nullable=False)
    new_data = mapped_column(JSONB, nullable=False)
    changed_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
