from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA
from app.infrastructure.database.history import PreservedHistory


class ConstructionUnitBuyerHistory(PreservedHistory, Base):
    __tablename__ = 'unit_buyer_history'
    __table_args__ = (
        Index('uq_unit_buyer_history_source', 'company_id', 'source_id', unique=True),
        Index('ix_unit_buyer_history_unit', 'company_id', 'unit_id', 'included_at'),
        {'schema': CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    unit_id: Mapped[UUID] = mapped_column(ForeignKey(
        f'{CONSTRUCTION_SCHEMA}.construction_units.id', ondelete='RESTRICT'), nullable=False, index=True)
    buyer_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    included_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    excluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    included_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    excluded_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    included_by_name: Mapped[str | None] = mapped_column(String(255))
    excluded_by_name: Mapped[str | None] = mapped_column(String(255))
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    source_payload = mapped_column(JSONB, nullable=True)

    @property
    def origin_label(self):
        return 'Sistema anterior' if self.source_id.startswith('mfcon:') else 'ONAVE'
