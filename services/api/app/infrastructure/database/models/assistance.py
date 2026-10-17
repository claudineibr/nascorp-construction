from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA


class AssistanceRequest(Base):
    __tablename__ = "assistance_requests"
    __table_args__ = (UniqueConstraint("company_id", "project_id", "number"), {"schema": CONSTRUCTION_SCHEMA})

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id"), nullable=False, index=True
    )
    unit_id = Column(
        UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_units.id"), nullable=False, index=True
    )
    customer_person_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    attendant_person_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    analyst_person_id = Column(UUID(as_uuid=True), index=True)
    number = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    opened_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    source_id = Column(Integer, unique=True)
    legacy_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))
    contacts = relationship("AssistanceContact", lazy="selectin")
    complaints = relationship("AssistanceComplaint", lazy="selectin")
    services = relationship("AssistanceService", lazy="selectin")
    history = relationship("AssistanceHistory", lazy="selectin", order_by="AssistanceHistory.created_at")


class AssistanceContact(Base):
    __tablename__ = "assistance_contacts"
    __table_args__ = {"schema": CONSTRUCTION_SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(
        UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.assistance_requests.id"), nullable=False, index=True
    )
    channel = Column(String(20), nullable=False)
    detail = Column(Text)
    deleted_at = Column(DateTime(timezone=True))


class AssistanceComplaint(Base):
    __tablename__ = "assistance_complaints"
    __table_args__ = {"schema": CONSTRUCTION_SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(
        UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.assistance_requests.id"), nullable=False, index=True
    )
    description = Column(Text, nullable=False)
    provenance = Column(String(20), nullable=False, default="pending")
    analyzed_by_person_id = Column(UUID(as_uuid=True), index=True)
    analyzed_at = Column(DateTime(timezone=True))
    original_number = Column(Integer)
    source_id = Column(Integer, unique=True)
    legacy_data = Column(JSONB)
    deleted_at = Column(DateTime(timezone=True))


class AssistanceService(Base):
    __tablename__ = "assistance_services"
    __table_args__ = {"schema": CONSTRUCTION_SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(
        UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.assistance_requests.id"), nullable=False, index=True
    )
    complaint_id = Column(UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.assistance_complaints.id"), index=True)
    description = Column(Text, nullable=False)
    due_date = Column(Date)
    executed_by_person_id = Column(UUID(as_uuid=True), index=True)
    executed_at = Column(DateTime(timezone=True))
    inspected_by_person_id = Column(UUID(as_uuid=True), index=True)
    inspected_at = Column(DateTime(timezone=True))
    original_number = Column(Integer)
    source_id = Column(Integer, unique=True)
    legacy_data = Column(JSONB)
    deleted_at = Column(DateTime(timezone=True))


class AssistanceHistory(Base):
    __tablename__ = "assistance_history"
    __table_args__ = {"schema": CONSTRUCTION_SCHEMA}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(
        UUID(as_uuid=True), ForeignKey(f"{CONSTRUCTION_SCHEMA}.assistance_requests.id"), nullable=False, index=True
    )
    actor_user_id = Column(UUID(as_uuid=True), index=True)
    action = Column(String(30), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AssistanceMigrationState(Base):
    __tablename__ = "assistance_migration_state"
    __table_args__ = {"schema": CONSTRUCTION_SCHEMA}
    company_id = Column(UUID(as_uuid=True), primary_key=True)
    released_at = Column(DateTime(timezone=True))
