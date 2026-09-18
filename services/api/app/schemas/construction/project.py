from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.constants import (
    ConstructionBlockStatus,
    ConstructionProjectStatus,
    ConstructionProjectType,
    ConstructionSchedulePhaseStatus,
    ConstructionUnitStatus,
)


class ConstructionProjectCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = ConstructionProjectStatus.DRAFT
    project_type: str = ConstructionProjectType.RESIDENTIAL_VERTICAL
    customer_person_id: UUID | None = None
    cnpj_spe: str | None = Field(default=None, max_length=18)
    address_json: dict[str, Any] | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None
    receipt_template_id: UUID | None = None
    commission_receipt_template_id: UUID | None = None


class ConstructionProjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    project_type: str | None = None
    customer_person_id: UUID | None = None
    cnpj_spe: str | None = Field(default=None, max_length=18)
    address_json: dict[str, Any] | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None
    synthetic_cost_center_id: UUID | None = None
    analytic_cost_center_id: UUID | None = None
    receipt_template_id: UUID | None = None
    commission_receipt_template_id: UUID | None = None


class ConstructionProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    code: str
    name: str
    description: str | None = None
    status: str
    project_type: str
    customer_person_id: UUID | None = None
    cnpj_spe: str | None = None
    address_json: dict[str, Any] | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    actual_end_date: date | None = None
    synthetic_cost_center_id: UUID | None = None
    analytic_cost_center_id: UUID | None = None
    receipt_template_id: UUID | None = None
    commission_receipt_template_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionProjectListResponse(BaseModel):
    items: list[ConstructionProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConstructionPersonSummaryResponse(BaseModel):
    id: UUID
    name: str
    document: str | None = None
    primary_phone: str | None = None
    primary_email: str | None = None
    is_active: bool = True


class ConstructionPersonSummaryListResponse(BaseModel):
    items: list[ConstructionPersonSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConstructionBlockCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    status: str = ConstructionBlockStatus.ACTIVE
    floors_count: int | None = Field(default=None, ge=0)


class ConstructionBlockUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    floors_count: int | None = Field(default=None, ge=0)


class ConstructionBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    code: str
    name: str
    status: str
    floors_count: int | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionBlockListResponse(BaseModel):
    items: list[ConstructionBlockResponse]
    total: int


class ConstructionUnitCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    unit_type: str = Field(..., min_length=1, max_length=80)
    typology: str | None = Field(default=None, max_length=80)
    block_id: UUID | None = None
    floor: str | None = Field(default=None, max_length=30)
    private_area: Decimal | None = Field(default=None, ge=0)
    total_area: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    status: str = ConstructionUnitStatus.AVAILABLE


class ConstructionUnitUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    unit_type: str | None = Field(default=None, min_length=1, max_length=80)
    typology: str | None = Field(default=None, max_length=80)
    block_id: UUID | None = None
    floor: str | None = Field(default=None, max_length=30)
    private_area: Decimal | None = Field(default=None, ge=0)
    total_area: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    status: str | None = None


class ConstructionUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    block_id: UUID | None = None
    code: str
    description: str | None = None
    unit_type: str
    typology: str | None = None
    floor: str | None = None
    private_area: Decimal | None = None
    total_area: Decimal | None = None
    sale_price: Decimal | None = None
    buyer_person_id: UUID | None = None
    secondary_buyer_person_id: UUID | None = None
    broker_person_id: UUID | None = None
    discount_amount: Decimal | None = None
    net_sale_price: Decimal | None = None
    contract_signature_date: date | None = None
    sale_notes: str | None = None
    reserved_at: datetime | None = None
    reservation_expires_at: date | None = None
    sold_at: datetime | None = None
    external_contract_id: UUID | None = None
    external_contract_status: str | None = None
    external_receivable_id: UUID | None = None
    external_receivable_status: str | None = None
    analytic_cost_center_id: UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ConstructionUnitListResponse(BaseModel):
    items: list[ConstructionUnitResponse]
    total: int


class ConstructionUnitReserveRequest(BaseModel):
    buyer_person_id: UUID
    reservation_expires_at: date | None = None


#: Apenas o que o usuario informa na confirmacao da venda. O saldo a parcelar
#: nao esta aqui de proposito: ele sai da conta do legado (preco - desconto -
#: entrada - financiamento - FGTS - subsidio), e deixar digita-lo obrigaria o
#: usuario a fazer essa subtracao de cabeca.
ConstructionUnitSalePaymentSourceType = Literal[
    "down_payment",
    "government_subsidy",
    "fgts",
    "financing",
]


class ConstructionUnitSalePaymentSource(BaseModel):
    source_type: ConstructionUnitSalePaymentSourceType
    amount: Decimal = Field(..., gt=0)
    due_date: date
    installments: int = Field(default=1, ge=1, le=120)


class ConstructionUnitSaleDocumentation(BaseModel):
    """Um item de documentacao cobrado do comprador.

    O tipo chega pelo id quando ja existe no catalogo, ou pelo nome digitado no
    combobox -- e nesse caso e criado na hora da confirmacao, nunca antes:
    cancelar o modal nao pode deixar tipo orfao.
    """

    documentation_type_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_type_reference(self) -> "ConstructionUnitSaleDocumentation":
        if self.documentation_type_id is None and not (self.name or "").strip():
            raise ValueError("Informe o tipo da documentação.")

        return self


class ConstructionDocumentationTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ConstructionDocumentationTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class ConstructionDocumentationTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    system_code: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ConstructionDocumentationTypeListResponse(BaseModel):
    items: list[ConstructionDocumentationTypeResponse]
    total: int


class ConstructionUnitSaleConfirmRequest(BaseModel):
    buyer_person_id: UUID
    secondary_buyer_person_id: UUID | None = None
    broker_person_id: UUID | None = None
    sale_price: Decimal | None = Field(default=None, gt=0)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    contract_signature_date: date | None = None
    sale_notes: str | None = None
    first_due_date: date
    installments: int = Field(default=1, ge=1, le=120)
    payment_sources: list[ConstructionUnitSalePaymentSource] | None = None
    #: ``None`` e ``[]`` significam a mesma coisa -- sem documentacao -- porque
    #: a gravacao e replace-all: o que nao vier no request e apagado.
    documentations: list[ConstructionUnitSaleDocumentation] | None = None


class ConstructionUnitInstallmentUpdateRequest(BaseModel):
    """O que a tela da unidade pode alterar numa parcela ja gerada.

    Vencimento e valor nao estao aqui de proposito: quem guarda a parcela e o
    ERP, e la nenhum caminho altera esses dois campos.
    """

    #: ``None`` e a serie da venda; preenchido, aponta a parcela de um aditivo.
    receivable_id: UUID | None = None
    payment_method: str | None = Field(default=None, min_length=1, max_length=30)
    document_number: str | None = Field(default=None, max_length=100)
    observation: str | None = None
    chart_account_id: UUID | None = None
    cost_center_id: UUID | None = None


class ConstructionUnitInstallmentCreateRequest(BaseModel):
    """Parcelas novas numa serie da unidade, no formato da tela do legado.

    ``starting_number`` e o "n da parcela" e ``count`` e o "Repetir 1+": a
    numeracao segue a partir do que foi informado, e o ERP recusa numero que ja
    existe no titulo. O valor sai do saldo que ainda nao virou parcela --
    cobrar a mais e aditivo, nao parcela nova.
    """

    receivable_id: UUID | None = None
    starting_number: int = Field(..., ge=1)
    count: int = Field(default=1, ge=1, le=60)
    first_due_date: date
    amount: Decimal | None = Field(default=None, gt=0)


class ConstructionUnitInstallmentPaymentLine(BaseModel):
    """Uma forma de recebimento da parcela.

    ``amount`` e o dinheiro recebido nesta forma -- o que esta no extrato --,
    nao o principal amortizado: quem deriva o principal e o financeiro.
    """

    payment_method: str = Field(..., min_length=1, max_length=30)
    amount: Decimal = Field(..., gt=0)
    paid_at: datetime | None = None
    document_number: str | None = Field(default=None, max_length=100)
    company_bank_account_id: UUID | None = None


class ConstructionUnitInstallmentPaymentRequest(BaseModel):
    """Baixa de uma parcela da unidade, no mesmo contrato do Contas a Receber.

    ``receivable_id`` ausente significa a série da venda; preenchido, aponta o
    aditivo. Vencimento e valor da parcela continuam fora: a baixa registra o
    que foi pago, não reescreve a parcela.

    A parcela e quitada por N formas de recebimento, e o ERP so aceita quando a
    soma fecha o que ha para receber.
    """

    receivable_id: UUID | None = None
    payments: list[ConstructionUnitInstallmentPaymentLine] = Field(..., min_length=1)
    interest: Decimal | None = Field(default=None, ge=0)
    fine: Decimal | None = Field(default=None, ge=0)
    discount: Decimal | None = Field(default=None, ge=0)
    observation: str | None = None


class ConstructionUnitInstallmentReversalRequest(BaseModel):
    """Estorno da baixa inteira da parcela da unidade.

    Nao ha estorno por linha: com recibo emitido a parcela e imutavel, e a
    correcao e derrubar a baixa toda -- o recibo e cancelado e o numero fica
    queimado.
    """

    receivable_id: UUID | None = None


class ConstructionUnitCommissionCreate(BaseModel):
    """Lancamento do sinal, no formato da tela do legado.

    ``installments`` e o "Repetir 1+": um lancamento gera N linhas com
    vencimento mensal a partir de ``due_date``, cada uma com sua numeracao.
    """

    #: O sinal sempre compoe o valor da venda -- e dinheiro que o comprador
    #: paga pela unidade, pago direto ao corretor. O que ele nao faz e entrar no
    #: contas a receber, porque nao passa pelo caixa da empresa. Nao ha campo
    #: para escolher: era uma decisao que a tela pedia e que nao existe no
    #: negocio.
    beneficiary_person_id: UUID
    amount: Decimal = Field(..., gt=0)
    due_date: date
    installments: int = Field(default=1, ge=1, le=120)
    document_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class ConstructionUnitCommissionUpdate(BaseModel):
    beneficiary_person_id: UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    due_date: date | None = None
    document_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class ConstructionUnitCommissionSettleRequest(BaseModel):
    #: ``None`` estorna a baixa e devolve o sinal para em aberto.
    payment_date: date | None = None


class ConstructionUnitCommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    unit_id: UUID
    beneficiary_person_id: UUID
    sequence_number: int
    amount: Decimal
    due_date: date
    payment_date: date | None = None
    composes_sale_price: bool
    receipt_template_id: UUID | None = None
    document_number: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionUnitCommissionListResponse(BaseModel):
    items: list[ConstructionUnitCommissionResponse]
    total: int


class ConstructionUnitAdjustmentCreate(BaseModel):
    """Aditivo da venda: cobranca extra quando o financiamento sai abaixo.

    Vira um recebivel proprio no ERP, nao uma parcela do recebivel da venda --
    editar a venda refaz as parcelas em aberto e destruiria o aditivo.
    """

    amount: Decimal = Field(..., gt=0)
    installments: int = Field(default=1, ge=1, le=120)
    first_due_date: date
    reason: str | None = Field(default=None, max_length=255)


class ConstructionSchedulePhaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sequence_order: int = Field(..., ge=1)
    status: str = ConstructionSchedulePhaseStatus.PLANNED
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    progress_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class ConstructionSchedulePhaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence_order: int | None = Field(default=None, ge=1)
    status: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    progress_percent: Decimal | None = Field(default=None, ge=0, le=100)


class ConstructionSchedulePhaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    name: str
    sequence_order: int
    status: str
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    progress_percent: Decimal
    created_at: datetime
    updated_at: datetime


class ConstructionSchedulePhaseListResponse(BaseModel):
    items: list[ConstructionSchedulePhaseResponse]
    total: int


class ConstructionMeasurementCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    unit_id: UUID
    schedule_phase_id: UUID
    sequence_number: int | None = Field(default=None, ge=1)
    measurement_type: str | None = Field(default=None, max_length=30)
    competence_date: date | None = None
    description: str | None = Field(default=None, max_length=1000)
    gross_amount: Decimal | None = Field(default=None, gt=0)
    retentions_amount: Decimal | None = Field(default=Decimal("0"), ge=0)
    net_amount: Decimal | None = Field(default=None, gt=0)
    measured_amount: Decimal | None = Field(default=None, gt=0)
    due_date: date
    supplier_person_id: UUID | None = None
    document_type: str | None = Field(default=None, max_length=40)
    document_number: str | None = Field(default=None, max_length=60)


class ConstructionMeasurementUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    unit_id: UUID | None = None
    schedule_phase_id: UUID | None = None
    sequence_number: int | None = Field(default=None, ge=1)
    measurement_type: str | None = Field(default=None, max_length=30)
    competence_date: date | None = None
    description: str | None = Field(default=None, max_length=1000)
    gross_amount: Decimal | None = Field(default=None, gt=0)
    retentions_amount: Decimal | None = Field(default=None, ge=0)
    net_amount: Decimal | None = Field(default=None, gt=0)
    measured_amount: Decimal | None = Field(default=None, gt=0)
    due_date: date | None = None
    supplier_person_id: UUID | None = None
    document_type: str | None = Field(default=None, max_length=40)
    document_number: str | None = Field(default=None, max_length=60)


class ConstructionMeasurementReject(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ConstructionMeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    unit_id: UUID | None = None
    schedule_phase_id: UUID | None = None
    code: str
    sequence_number: int | None = None
    measurement_type: str | None = None
    competence_date: date | None = None
    description: str | None = None
    gross_amount: Decimal | None = None
    retentions_amount: Decimal | None = None
    net_amount: Decimal | None = None
    document_type: str | None = None
    document_number: str | None = None
    measured_amount: Decimal
    due_date: date
    supplier_person_id: UUID | None = None
    supplier_qualification_status: str = "none"
    status: str
    rejection_reason: str | None = None
    created_by_user_id: UUID | None = None
    submitted_by_user_id: UUID | None = None
    submitted_at: datetime | None = None
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    rejected_by_user_id: UUID | None = None
    rejected_at: datetime | None = None
    items_total_amount: Decimal | None = None
    items_count: int | None = None
    pending_inspections_count: int | None = None
    non_compliant_inspections_count: int | None = None
    open_occurrences_count: int | None = None
    external_accounts_payable_id: UUID | None = None
    external_accounts_payable_status: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionMeasurementListResponse(BaseModel):
    items: list[ConstructionMeasurementResponse]
    total: int


ConstructionInspectionStatusLiteral = Literal["pending", "compliant", "non_compliant", "waived"]
#: O que uma RODADA aceita. `pending` fora de propósito: pendente é a
#: ausência de rodada, não um veredito que alguém registra.
ConstructionInspectionRoundStatusLiteral = Literal["compliant", "non_compliant", "waived"]

ConstructionOccurrenceStatusLiteral = Literal["open", "resolved", "cancelled"]


class ConstructionServiceTemplateItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_template_id: UUID
    section_id: UUID
    sequence_number: int
    description: str
    verification_method: str
    requires_comment: bool = False
    requires_photo: bool = False


class ConstructionServiceTemplateSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_template_id: UUID
    sequence_number: int
    name: str
    items: list[ConstructionServiceTemplateItemResponse] = []


class ConstructionServiceTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    product_id: UUID | None = None
    source_file_name: str | None = None
    is_active: bool
    created_by_user_id: UUID | None = None
    updated_by_user_id: UUID | None = None
    deleted_at: datetime | None = None
    deleted_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    sections: list[ConstructionServiceTemplateSectionResponse] = []
    items: list[ConstructionServiceTemplateItemResponse] = []

    @classmethod
    def from_model(cls, template: object) -> "ConstructionServiceTemplateResponse":
        """Builds the response flattening items in section -> item order.

        The flat `items` exists because the frontend already consumes it.
        Letting the ORM fill that field would return items ordered by
        sequence_number alone, which restarts on every section -- the checklist
        would arrive shuffled (1, 2, 1, 2, 3).
        """
        sections = [
            ConstructionServiceTemplateSectionResponse.model_validate(section)
            for section in template.sections
        ]
        return cls(
            id=template.id,
            company_id=template.company_id,
            name=template.name,
            product_id=template.product_id,
            source_file_name=template.source_file_name,
            is_active=template.is_active,
            created_by_user_id=template.created_by_user_id,
            updated_by_user_id=template.updated_by_user_id,
            deleted_at=template.deleted_at,
            deleted_by_user_id=template.deleted_by_user_id,
            created_at=template.created_at,
            updated_at=template.updated_at,
            sections=sections,
            items=[item for section in sections for item in section.items],
        )


class ConstructionServiceTemplateListResponse(BaseModel):
    items: list[ConstructionServiceTemplateResponse]
    total: int


class ConstructionServiceTemplateAuditResponse(BaseModel):
    """Um evento do historico do servico.

    ``actor_name`` e o nome NA EPOCA do evento, gravado junto: a pessoa e
    renomeada, sai da empresa, e o historico continua tendo de ser legivel.
    Vazio quando o ERP nao respondeu na hora da gravacao -- o ``actor_user_id``
    permanece e e ele que identifica o autor.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_template_id: UUID
    service_template_name: str
    sequence_number: int
    event: Literal["created", "updated", "replaced", "activated", "deactivated", "deleted"]
    source: str = "manual"
    actor_user_id: UUID | None = None
    actor_person_id: UUID | None = None
    actor_name: str | None = None
    summary: str | None = None
    snapshot: dict | None = None
    created_at: datetime


class ConstructionServiceTemplateAuditListResponse(BaseModel):
    items: list[ConstructionServiceTemplateAuditResponse]
    total: int


class ConstructionServiceTemplateItemInput(BaseModel):
    sequence_number: int | None = Field(default=None, ge=1)
    description: str = Field(..., min_length=1, max_length=2000)
    verification_method: str = Field(..., min_length=1, max_length=2000)
    requires_comment: bool = False
    requires_photo: bool = False


class ConstructionServiceTemplateSectionInput(BaseModel):
    sequence_number: int | None = Field(default=None, ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    items: list[ConstructionServiceTemplateItemInput] = []


class ConstructionServiceTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    product_id: UUID | None = None
    is_active: bool = True
    sections: list[ConstructionServiceTemplateSectionInput] = []


class ConstructionServiceTemplateReplace(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    product_id: UUID | None = None
    is_active: bool = True
    sections: list[ConstructionServiceTemplateSectionInput] = []


class ConstructionServiceTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    product_id: UUID | None = None
    is_active: bool | None = None


class ConstructionServiceTemplateImportResult(BaseModel):
    file_name: str
    status: Literal["created", "updated", "skipped", "failed"]
    service_template_id: UUID | None = None
    service_name: str | None = None
    items_count: int = 0
    sections_count: int = 0
    message: str | None = None


class ConstructionServiceTemplateImportResponse(BaseModel):
    results: list[ConstructionServiceTemplateImportResult]
    created: int
    updated: int
    skipped: int
    failed: int


class ConstructionMeasurementItemCreate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    amount: Decimal = Field(..., gt=0)
    sequence_number: int | None = Field(default=None, ge=1)
    service_template_id: UUID | None = None
    product_id: UUID | None = None
    product_description: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    inspector_person_id: UUID | None = None


class ConstructionMeasurementItemUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    amount: Decimal | None = Field(default=None, gt=0)
    product_id: UUID | None = None
    product_description: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    inspector_person_id: UUID | None = None
    # `inspection_status` saiu de propósito: é derivado das linhas da FVS, e
    # deixar o cliente escrevê-lo anularia o bloqueio de fechamento inteiro.


class ConstructionMeasurementItemInspectionCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    sequence_number: int | None = Field(default=None, ge=1)
    verification_method: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    inspector_person_id: UUID | None = None


class ConstructionMeasurementItemInspectionUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    verification_method: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    inspector_person_id: UUID | None = None


class ConstructionMeasurementInspectionVerifyRequest(BaseModel):
    """Uma rodada de verificação da linha: a primeira ou uma reinspeção.

    `check_number` é aceito e **ignorado**, deprecated. O número da rodada é do
    servidor; o campo sobrevive um release só para que a ordem de deploy entre a
    API e o MFE deixe de importar.
    """

    status: ConstructionInspectionRoundStatusLiteral
    comment: str | None = Field(default=None, max_length=2000)
    inspector_person_id: UUID | None = None
    inspected_on: date | None = None
    #: Atalho: abre também uma ocorrência com o mesmo motivo. Desmarcado por
    #: padrão -- a rodada reprovada com motivo já é o registro da não
    #: conformidade, e dois ciclos de vida do mesmo fato divergem.
    open_occurrence: bool = False
    check_number: int | None = Field(default=None, deprecated=True)


class ConstructionInspectionRoundResponse(BaseModel):
    """Uma verificação registrada. `inspector_name` e `recorded_by_name` são os
    nomes **na época**: a pessoa é renomeada e sai da empresa, e a ficha continua
    tendo de ser legível. Vazios quando o ERP não respondeu na hora da gravação.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inspection_id: UUID
    sequence_number: int
    status: str
    verified_at: datetime
    inspected_on: date | None = None
    inspector_person_id: UUID | None = None
    inspector_name: str | None = None
    recorded_by_user_id: UUID | None = None
    recorded_by_name: str | None = None
    comment: str | None = None
    source: str = "manual"
    is_inferred: bool = False
    created_at: datetime


class ConstructionInspectionRoundListResponse(BaseModel):
    items: list[ConstructionInspectionRoundResponse]
    total: int


class ConstructionMeasurementItemInspectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    measurement_item_id: UUID
    sequence_number: int
    section_name: str | None = None
    description: str
    verification_method: str | None = None
    requires_comment: bool = False
    requires_photo: bool = False
    start_date: date | None = None
    end_date: date | None = None
    inspector_person_id: UUID | None = None
    status: str
    rounds_count: int = 0
    last_verified_at: datetime | None = None
    approved_after_reinspection: bool = False
    rounds: list[ConstructionInspectionRoundResponse] = []
    # Deprecated: o formato da dupla conferência, derivado das rodadas para o
    # MFE em voo não quebrar entre o restart da API e o build do front. Sai no
    # release seguinte.
    first_status: str
    first_status_at: datetime | None = None
    first_status_by_user_id: UUID | None = None
    second_status: str
    second_status_at: datetime | None = None
    second_status_by_user_id: UUID | None = None
    is_double_checked: bool = False
    created_at: datetime
    updated_at: datetime


class ConstructionMeasurementItemOccurrenceCreate(BaseModel):
    problem: str = Field(..., min_length=1, max_length=2000)
    sequence_number: int | None = Field(default=None, ge=1)
    solution: str | None = Field(default=None, max_length=2000)
    opened_at: date | None = None
    inspector_person_id: UUID | None = None


class ConstructionMeasurementItemOccurrenceUpdate(BaseModel):
    problem: str | None = Field(default=None, min_length=1, max_length=2000)
    solution: str | None = Field(default=None, max_length=2000)
    status: ConstructionOccurrenceStatusLiteral | None = None
    opened_at: date | None = None
    closed_at: date | None = None
    inspector_person_id: UUID | None = None


class ConstructionMeasurementItemOccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    measurement_item_id: UUID
    inspection_id: UUID | None = None
    sequence_number: int
    problem: str
    solution: str | None = None
    status: str
    opened_at: date | None = None
    closed_at: date | None = None
    inspector_person_id: UUID | None = None
    registered_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionMeasurementItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    measurement_id: UUID
    sequence_number: int
    service_template_id: UUID | None = None
    product_id: UUID | None = None
    product_description: str | None = None
    description: str
    amount: Decimal
    start_date: date | None = None
    end_date: date | None = None
    inspector_person_id: UUID | None = None
    inspection_status: str
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    inspections: list[ConstructionMeasurementItemInspectionResponse] = []
    occurrences: list[ConstructionMeasurementItemOccurrenceResponse] = []


class ConstructionMeasurementItemListResponse(BaseModel):
    items: list[ConstructionMeasurementItemResponse]
    total: int
    total_amount: Decimal


class ConstructionProcurementRequestCreate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    estimated_amount: Decimal = Field(..., gt=0)
    needed_by_date: date | None = None
    supplier_person_id: UUID | None = None


class ConstructionProcurementRequestUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    estimated_amount: Decimal | None = Field(default=None, gt=0)
    needed_by_date: date | None = None
    supplier_person_id: UUID | None = None


class ConstructionProcurementRequestReject(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ConstructionProcurementRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    code: str
    title: str
    description: str | None = None
    estimated_amount: Decimal
    needed_by_date: date | None = None
    supplier_person_id: UUID | None = None
    supplier_qualification_status: str = "none"
    status: str
    rejection_reason: str | None = None
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    external_procurement_id: UUID | None = None
    external_procurement_status: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstructionProcurementRequestListResponse(BaseModel):
    items: list[ConstructionProcurementRequestResponse]
    total: int
