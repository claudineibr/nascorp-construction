from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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
    ConstructionInspectionRoundSource,
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
    receipt_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    commission_receipt_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
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
    commissions: Mapped[list[ConstructionUnitCommission]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="ConstructionUnitCommission.sequence_number",
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
    # Status QUE VALIA quando a medicao foi criada, nao o de hoje: a
    # qualificacao pode vencer depois, e isso nao pode reescrever o passado.
    supplier_qualification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="none", default="none"
    )
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
    # Partial unique: a soft-deleted service releases its name, two live ones
    # still cannot share it.
    __table_args__ = (
        Index(
            "uq_construction_service_templates_live_name",
            "company_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sections: Mapped[list[ConstructionServiceTemplateSection]] = relationship(
        back_populates="service_template",
        cascade="all, delete-orphan",
        order_by="ConstructionServiceTemplateSection.sequence_number",
    )
    items: Mapped[list[ConstructionServiceTemplateItem]] = relationship(
        viewonly=True,
        order_by="ConstructionServiceTemplateItem.sequence_number",
    )


class ConstructionServiceTemplateSection(Base):
    __tablename__ = "construction_service_template_sections"
    __table_args__ = (
        UniqueConstraint(
            "service_template_id",
            "sequence_number",
            name="uq_construction_service_template_sections_sequence",
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    service_template: Mapped[ConstructionServiceTemplate] = relationship(back_populates="sections")
    items: Mapped[list[ConstructionServiceTemplateItem]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="ConstructionServiceTemplateItem.sequence_number",
    )


class ConstructionServiceTemplateItem(Base):
    __tablename__ = "construction_service_template_items"
    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "sequence_number",
            name="uq_construction_service_template_items_section_sequence",
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
    section_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_service_template_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    verification_method: Mapped[str] = mapped_column(Text, nullable=False)
    requires_comment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    requires_photo: Mapped[bool] = mapped_column(
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

    section: Mapped[ConstructionServiceTemplateSection] = relationship(back_populates="items")


class ConstructionServiceTemplateAudit(Base):
    """One row per mutation of a catalog service: who, when, and what it became.

    The author columns on the template only ever hold the LAST write. A sheet is
    revised more than once, so without this table a revision would erase the
    previous author -- and the FVS exists precisely to prove the trail.

    Name and actor are denormalized: the service gets renamed, people get
    renamed and leave the company, and the trail still has to read years later.
    """

    __tablename__ = "construction_service_template_audits"
    __table_args__ = (
        UniqueConstraint(
            "service_template_id",
            "sequence_number",
            name="uq_construction_service_template_audits_sequence",
        ),
        Index(
            "ix_construction_service_template_audits_template",
            "service_template_id",
            "sequence_number",
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    service_template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_service_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Numero da revisao da ficha. E ele que ordena o historico: `created_at`
    #: sozinho empata quando dois eventos caem na mesma transacao.
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default=text("'manual'"))
    actor_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


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


class ConstructionUnitCommission(Base):
    """O sinal do legado: a comissao do corretor, paga pelo comprador.

    Nao e conta a receber da construtora -- o dinheiro vai direto ao corretor.
    Quando ``composes_sale_price`` esta marcado, o valor compoe o preco da
    unidade e reduz o saldo a parcelar; desmarcado, e cobranca por fora e nao
    toca o saldo.
    """

    __tablename__ = "construction_unit_commissions"
    __table_args__ = (
        UniqueConstraint("unit_id", "sequence_number", name="uq_construction_unit_commissions_sequence"),
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
    beneficiary_person_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    composes_sale_price: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    receipt_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    unit: Mapped[ConstructionUnit] = relationship(back_populates="commissions")


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
    section_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    verification_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_comment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    requires_photo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Inspetor padrao da linha, herdado do item. E apenas o VALOR INICIAL das
    #: rodadas novas -- quem foi a campo de verdade esta em cada rodada.
    inspector_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    #: Derivadas das rodadas, mantidas pelo servico. Existem para que o rollup do
    #: item e o bloqueio de fechamento nao precisem de uma window function por
    #: linha -- a camada de servico nao pode montar query.
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ConstructionInspectionStatus.PENDING,
        server_default=ConstructionInspectionStatus.PENDING,
    )
    rounds_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    item: Mapped[ConstructionMeasurementItem] = relationship(back_populates="inspections")
    rounds: Mapped[list[ConstructionInspectionRound]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
        order_by="ConstructionInspectionRound.sequence_number",
    )

    @property
    def approved_after_reinspection(self) -> bool:
        """O `AR` do MFCON, calculado em vez de gravado.

        Um quarto valor de status obrigaria toda comparacao `== COMPLIANT` do
        codigo a aprender um segundo "aprovado" -- que e exatamente a classe de
        bug que este plano veio consertar.
        """
        return self.status == ConstructionInspectionStatus.COMPLIANT and self.rounds_count > 1

    # --- Compatibilidade: campos do modelo de dupla conferencia ------------
    # Deprecated. Existem so para o MFE em voo nao quebrar entre o restart da
    # API e o build do front; saem no release seguinte. Derivam das rodadas,
    # nunca de coluna -- coluna que ninguem escreve diverge do historico.

    @property
    def first_status(self) -> str:
        rounds = self.rounds or []
        return rounds[0].status if rounds else ConstructionInspectionStatus.PENDING

    @property
    def first_status_at(self) -> datetime | None:
        rounds = self.rounds or []
        return rounds[0].verified_at if rounds else None

    @property
    def first_status_by_user_id(self) -> UUID | None:
        rounds = self.rounds or []
        return rounds[0].recorded_by_user_id if rounds else None

    @property
    def second_status(self) -> str:
        rounds = self.rounds or []
        return rounds[1].status if len(rounds) > 1 else ConstructionInspectionStatus.PENDING

    @property
    def second_status_at(self) -> datetime | None:
        rounds = self.rounds or []
        return rounds[1].verified_at if len(rounds) > 1 else None

    @property
    def second_status_by_user_id(self) -> UUID | None:
        rounds = self.rounds or []
        return rounds[1].recorded_by_user_id if len(rounds) > 1 else None

    @property
    def is_double_checked(self) -> bool:
        """Passou a significar "esta linha esta resolvida".

        E o uso real que o MFE faz do campo (badge de concluido), entao o
        comportamento visivel nao muda -- so a semantica.
        """
        return self.status in ConstructionInspectionStatus.RESOLVED_STATUSES


class ConstructionInspectionRound(Base):
    """Uma verificacao de uma linha da FVS: a primeira ou uma reinspecao.

    Append-only de proposito, e por isso nao tem `updated_at`: a coluna
    convidaria um UPDATE e o historico deixaria de ser historico. Corrigir uma
    rodada errada e registrar outra, que fica ao lado da anterior.

    `status` nunca e `pending`: pendente deixou de ser valor gravado e passou a
    ser a AUSENCIA de rodada.
    """

    __tablename__ = "construction_inspection_rounds"
    __table_args__ = (
        UniqueConstraint(
            "inspection_id",
            "sequence_number",
            name="uq_construction_inspection_rounds_sequence",
        ),
        CheckConstraint(
            "status IN ('compliant', 'non_compliant', 'waived')",
            name="ck_construction_inspection_rounds_status",
        ),
        Index(
            "ix_construction_inspection_rounds_inspection",
            "inspection_id",
            "sequence_number",
        ),
        {"schema": CONSTRUCTION_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    inspection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurement_item_inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Desnormalizado: poupa um join no bloqueio de submit/approve, que roda por
    #: medicao inteira, e nunca muda -- inspecao nao migra de item.
    measurement_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurement_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    #: Quando foi lancado no sistema.
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: Quando a pessoa esteve em campo. Nulo quando nao se sabe -- e o caso de
    #: toda reinspecao vinda do MFCON, cuja data nunca foi gravada.
    inspected_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspector_person_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    #: Nomes congelados na data da rodada: a pessoa e renomeada e sai da empresa,
    #: e a ficha continua tendo de ser legivel anos depois.
    inspector_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    recorded_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ConstructionInspectionRoundSource.MANUAL,
        server_default=text("'manual'"),
    )
    #: Rodada deduzida na carga do legado, nao registrada por ninguem. So a ETL
    #: escreve; e o que permite separar depois o que foi medido do que foi
    #: inferido.
    is_inferred: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    inspection: Mapped[ConstructionMeasurementItemInspection] = relationship(back_populates="rounds")


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
    #: A linha da FVS que originou a ocorrencia, quando houve uma. SET NULL e
    #: nao CASCADE: apagar a linha da ficha nao pode apagar o registro do
    #: problema encontrado.
    inspection_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{CONSTRUCTION_SCHEMA}.construction_measurement_item_inspections.id", ondelete="SET NULL"),
        nullable=True,
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
    supplier_qualification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="none", default="none"
    )
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
