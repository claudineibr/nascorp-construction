from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.constants import (
    ConstructionBlockStatus,
    ConstructionProjectStatus,
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
    floor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    private_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
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
