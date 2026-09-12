from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.constants import (
    ConstructionInspectionStatus,
    ConstructionOccurrenceStatus,
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
        UniqueConstraint(
            "company_id", 
            "code", 
            name="uq_construction_projects_company_code"
            ),
        {
            "schema": CONSTRUCTION_SCHEMA
            },
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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_type: Mapped[str] = mapped_column(String(80), nullable=False)
    typology: Mapped[str | None] = mapped_column(String(80), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    private_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    buyer_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    secondary_buyer_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    broker_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    contract_signature_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sale_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_contract_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    external_contract_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    external_receivable_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    external_receivable_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    analytic_cost_center_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
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
    payment_sources: Mapped[list[ConstructionUnitPaymentSource]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="ConstructionUnitPaymentSource.source_type",
    )
    documentations: Mapped[list[ConstructionUnitDocumentation]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="ConstructionUnitDocumentation.sequence_number",
    )

    @property
    def net_sale_price(self) -> Decimal | None:
        if self.sale_price is None:
            return None

        return self.sale_price - (self.discount_amount or Decimal("0"))


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
    unit_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schedule_phase_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_schedule_phases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measurement_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    competence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    retentions_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    measured_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionMeasurementStatus.DRAFT)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    items: Mapped[list[ConstructionMeasurementItem]] = relationship(
        back_populates="measurement",
        cascade="all, delete-orphan",
        order_by="ConstructionMeasurementItem.sequence_number",
    )


class ConstructionUnitPaymentSource(Base):
    __tablename__ = "construction_unit_payment_sources"
    __table_args__ = (
        UniqueConstraint("unit_id", "source_type", name="uq_construction_unit_payment_sources_type"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    installments: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    generates_installments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    unit: Mapped[ConstructionUnit] = relationship(back_populates="payment_sources")


class ConstructionServiceTemplate(Base):
    __tablename__ = "construction_service_templates"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_construction_service_templates_name"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list[ConstructionServiceTemplateItem]] = relationship(
        back_populates="service_template",
        cascade="all, delete-orphan",
        order_by="ConstructionServiceTemplateItem.sequence_number",
    )


class ConstructionServiceTemplateItem(Base):
    __tablename__ = "construction_service_template_items"
    __table_args__ = (
        UniqueConstraint(
            "service_template_id",
            "sequence_number",
            name="uq_construction_service_template_items_sequence",
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    service_template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_service_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    verification_method: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    service_template: Mapped[ConstructionServiceTemplate] = relationship(back_populates="items")


class ConstructionDocumentationType(Base):
    """Catalogo de tipos de documentacao cobrada do comprador, por empresa.

    No legado a documentacao era quatro colunas fixas mais uma lista de texto
    livre, e as 184 descricoes distintas do dump provam no que isso da. Aqui o
    tipo e uma linha: os quatro do legado nascem semeados, o resto e criado
    pelo proprio combobox da venda.
    """

    __tablename__ = "construction_documentation_types"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "normalized_name",
            name="uq_construction_documentation_types_normalized_name",
        ),
        UniqueConstraint(
            "company_id",
            "system_code",
            name="uq_construction_documentation_types_system_code",
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ConstructionUnitDocumentation(Base):
    __tablename__ = "construction_unit_documentations"
    __table_args__ = (
        UniqueConstraint("unit_id", "documentation_type_id", name="uq_construction_unit_documentations_type"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    documentation_type_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_documentation_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    unit: Mapped[ConstructionUnit] = relationship(back_populates="documentations")
    documentation_type: Mapped[ConstructionDocumentationType] = relationship(lazy="selectin")


class ConstructionMeasurementItem(Base):
    __tablename__ = "construction_measurement_items"
    __table_args__ = (
        UniqueConstraint("measurement_id", "sequence_number", name="uq_construction_measurement_items_sequence"),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    measurement_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    service_template_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_service_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    product_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspector_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    inspection_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ConstructionInspectionStatus.PENDING,
        server_default=ConstructionInspectionStatus.PENDING,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    measurement: Mapped[ConstructionMeasurement] = relationship(back_populates="items")
    inspections: Mapped[list[ConstructionMeasurementItemInspection]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ConstructionMeasurementItemInspection.sequence_number",
    )
    occurrences: Mapped[list[ConstructionMeasurementItemOccurrence]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ConstructionMeasurementItemOccurrence.sequence_number",
    )


class ConstructionMeasurementItemInspection(Base):
    __tablename__ = "construction_measurement_item_inspections"
    __table_args__ = (
        UniqueConstraint(
            "measurement_item_id",
            "sequence_number",
            name="uq_construction_measurement_inspections_sequence",
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    measurement_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurement_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    verification_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspector_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    first_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ConstructionInspectionStatus.PENDING,
        server_default=ConstructionInspectionStatus.PENDING,
    )
    first_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_status_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    second_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ConstructionInspectionStatus.PENDING,
        server_default=ConstructionInspectionStatus.PENDING,
    )
    second_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_status_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    item: Mapped[ConstructionMeasurementItem] = relationship(back_populates="inspections")

    @property
    def is_double_checked(self) -> bool:
        return (
            self.first_status in ConstructionInspectionStatus.RESOLVED_STATUSES
            and self.second_status in ConstructionInspectionStatus.RESOLVED_STATUSES
        )


class ConstructionMeasurementItemOccurrence(Base):
    __tablename__ = "construction_measurement_item_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "measurement_item_id",
            "sequence_number",
            name="uq_construction_measurement_occurrences_sequence",
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    measurement_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurement_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ConstructionOccurrenceStatus.OPEN,
        server_default=ConstructionOccurrenceStatus.OPEN,
    )
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspector_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    registered_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    item: Mapped[ConstructionMeasurementItem] = relationship(back_populates="occurrences")


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
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    needed_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ConstructionProcurementStatus.DRAFT)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
