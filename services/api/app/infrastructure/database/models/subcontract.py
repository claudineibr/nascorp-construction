from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, CONSTRUCTION_SCHEMA


class SubcontractRecord:
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class ConstructionSubcontract(SubcontractRecord, Base):
    __tablename__ = "construction_subcontracts"
    __table_args__ = (
        UniqueConstraint("company_id", "project_id", "code", name="uq_subcontract_project_code"),
        CheckConstraint("status IN ('DRAFT','RELEASED','CLOSED','CANCELED')", name="ck_subcontract_status"),
        CheckConstraint("valid_to >= valid_from", name="ck_subcontract_dates"),
        CheckConstraint("retention_rate BETWEEN 0 AND 100 AND escrow_rate BETWEEN 0 AND 100", name="ck_subcontract_rates"),
        {"schema": CONSTRUCTION_SCHEMA},
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_projects.id"), index=True)
    supplier_person_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    code: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    retention_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, server_default="0")
    escrow_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, server_default="0")
    escrow_due_date: Mapped[date | None] = mapped_column(Date)
    released_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    released_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    closure_reason: Mapped[str | None] = mapped_column(Text)
    closed_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class ConstructionSubcontractItem(SubcontractRecord, Base):
    __tablename__ = "construction_subcontract_items"
    __table_args__ = (
        UniqueConstraint("contract_id", "sequence_number", name="uq_subcontract_item_sequence"),
        CheckConstraint("quantity > 0 AND consumed_quantity >= 0 AND consumed_quantity <= quantity", name="ck_subcontract_quantity"),
        CheckConstraint("material_unit_price >= 0 AND labor_unit_price >= 0", name="ck_subcontract_prices"),
        {"schema": CONSTRUCTION_SCHEMA},
    )
    contract_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_subcontracts.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    description: Mapped[str] = mapped_column(String(500))
    unit_of_measure: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    material_unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    labor_unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    consumed_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ConstructionSubcontractVersion(SubcontractRecord, Base):
    __tablename__ = "construction_subcontract_versions"
    __table_args__ = (UniqueConstraint("contract_id", "version_number", name="uq_subcontract_version"),
        {"schema": CONSTRUCTION_SCHEMA})
    contract_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_subcontracts.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    sheet: Mapped[dict] = mapped_column(JSONB)
    released_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class ConstructionSubcontractConsumption(SubcontractRecord, Base):
    __tablename__ = "construction_subcontract_consumptions"
    __table_args__ = (
        UniqueConstraint("measurement_item_id", "approval_cycle", name="uq_subcontract_consumption_cycle"),
        CheckConstraint("quantity > 0 AND status IN ('POSTED','REVERSED')", name="ck_subcontract_consumption"),
        {"schema": CONSTRUCTION_SCHEMA},
    )
    contract_item_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_subcontract_items.id"), index=True)
    version_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_subcontract_versions.id"))
    measurement_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurements.id"), index=True)
    measurement_item_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurement_items.id"))
    approval_cycle: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    material_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    labor_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="POSTED", server_default="POSTED")
    reversed_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConstructionSubcontractDirectBill(SubcontractRecord, Base):
    __tablename__ = "construction_subcontract_direct_bills"
    __table_args__ = (
        Index("uq_subcontract_direct_bill_document", "company_id", "payable_document_id", unique=True, postgresql_where=text("status='ACTIVE'")),
        CheckConstraint("amount > 0 AND deducted_amount >= 0 AND deducted_amount <= amount", name="ck_subcontract_direct_bill_amount"),
        {"schema": CONSTRUCTION_SCHEMA},
    )
    contract_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_subcontracts.id"), index=True)
    payable_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    deducted_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0")
    verified_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    document_snapshot: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")


class ConstructionSubcontractDeduction(SubcontractRecord, Base):
    __tablename__ = "construction_subcontract_deductions"
    __table_args__ = (
        UniqueConstraint("measurement_id", "direct_bill_id", name="uq_subcontract_deduction_measurement_bill"),
        CheckConstraint("amount > 0 AND status IN ('DRAFT','POSTED','REVERSED')", name="ck_subcontract_deduction"),
        {"schema": CONSTRUCTION_SCHEMA},
    )
    measurement_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurements.id"), index=True)
    direct_bill_id: Mapped[UUID] = mapped_column(ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_subcontract_direct_bills.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
