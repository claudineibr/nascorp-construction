from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.constants import (
    ConstructionBlockStatus,
    ConstructionMeasurementStatus,
    ConstructionProcurementStatus,
    ConstructionProjectStatus,
    ConstructionProjectType,
    ConstructionSchedulePhaseStatus,
    ConstructionUnitStatus,
)
from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA


class ConstructionProject(Base):
    __tablename__ = "construction_projects"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_construction_projects_company_code"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionProjectStatus.DRAFT)
    project_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=ConstructionProjectType.RESIDENTIAL_VERTICAL,
    )
    customer_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    cnpj_spe: Mapped[str | None] = mapped_column(String(18), nullable=True)
    address_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    synthetic_cost_center_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    analytic_cost_center_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    blocks: Mapped[list[ConstructionBlock]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    units: Mapped[list[ConstructionUnit]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    schedule_phases: Mapped[list[ConstructionSchedulePhase]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    measurements: Mapped[list[ConstructionMeasurement]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    procurement_requests: Mapped[list[ConstructionProcurementRequest]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ConstructionBlock(Base):
    __tablename__ = "construction_blocks"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_construction_blocks_project_code"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionBlockStatus.ACTIVE)
    floors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ConstructionProject] = relationship(back_populates="blocks")
    units: Mapped[list[ConstructionUnit]] = relationship(back_populates="block")


class ConstructionUnit(Base):
    __tablename__ = "construction_units"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_construction_units_project_code"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_blocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(80), nullable=False)
    typology: Mapped[str | None] = mapped_column(String(80), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    private_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    buyer_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_contract_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    external_contract_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    external_receivable_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    external_receivable_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionUnitStatus.AVAILABLE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ConstructionProject] = relationship(back_populates="units")
    block: Mapped[ConstructionBlock | None] = relationship(back_populates="units")


class ConstructionSchedulePhase(Base):
    __tablename__ = "construction_schedule_phases"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence_order", name="uq_construction_schedule_project_sequence"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionSchedulePhaseStatus.PLANNED)
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ConstructionProject] = relationship(back_populates="schedule_phases")


class ConstructionMeasurement(Base):
    __tablename__ = "construction_measurements"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_construction_measurements_project_code"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionMeasurementStatus.DRAFT)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_accounts_payable_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    external_accounts_payable_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ConstructionProject] = relationship(back_populates="measurements")


class ConstructionProcurementRequest(Base):
    __tablename__ = "construction_procurement_requests"
    __table_args__ = (
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionProcurementStatus.DRAFT)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_procurement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    external_procurement_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ConstructionProject] = relationship(back_populates="procurement_requests")
