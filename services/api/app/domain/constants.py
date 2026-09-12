class ConstructionProjectStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConstructionProjectType:
    RESIDENTIAL_VERTICAL = "residential_vertical"
    RESIDENTIAL_HORIZONTAL = "residential_horizontal"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"
    INFRASTRUCTURE = "infrastructure"
    INDUSTRIAL = "industrial"


class ConstructionBlockStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"


class ConstructionUnitStatus:
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    DELIVERED = "delivered"
    TERMINATED = "terminated"
    UNAVAILABLE = "unavailable"


class ConstructionSchedulePhaseStatus:
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConstructionMeasurementStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_APPROVAL = "in_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class ConstructionUnitPaymentSource:
    DOWN_PAYMENT = "down_payment"
    BALANCE = "balance"
    #: Nome antigo do saldo, mantido apenas para ler vendas gravadas antes de o
    #: saldo passar a ser calculado. Nao aceite mais este valor na entrada.
    DIRECT_BUILDER = "direct_builder"
    GOVERNMENT_SUBSIDY = "government_subsidy"
    FGTS = "fgts"
    FINANCING = "financing"

    ALL_SOURCES = {DOWN_PAYMENT, BALANCE, DIRECT_BUILDER, GOVERNMENT_SUBSIDY, FGTS, FINANCING}

    #: O saldo nao e informado pelo usuario: sai da conta do legado, do que
    #: sobra do preco depois das outras fontes e do desconto.
    COMPUTED_SOURCES = {BALANCE, DIRECT_BUILDER}

    #: Fontes que o usuario informa na confirmacao da venda.
    INFORMED_SOURCES = {DOWN_PAYMENT, GOVERNMENT_SUBSIDY, FGTS, FINANCING}

    INSTALLMENT_SOURCES = {DOWN_PAYMENT, BALANCE, DIRECT_BUILDER}

    SETTLEMENT_SOURCES = {GOVERNMENT_SUBSIDY, FGTS, FINANCING}

    LABELS = {
        DOWN_PAYMENT: "Entrada",
        BALANCE: "Saldo devedor",
        DIRECT_BUILDER: "Saldo devedor",
        GOVERNMENT_SUBSIDY: "Subsídio",
        FGTS: "FGTS",
        FINANCING: "Financiamento",
    }


class ConstructionDocumentationType:
    """Tipos de documentacao semeados por empresa.

    A identidade estavel e o ``system_code``, nao o nome: renomear "Avaliacao"
    nao pode duplicar o seed nem quebrar o de-para do ETL.
    """

    DEFAULT_TYPES = (
        ("APPRAISAL", "Avaliação"),
        ("CITY_HALL", "Prefeitura"),
        ("NOTARY", "Cartório"),
        ("IPTU", "IPTU"),
    )

    @staticmethod
    def clean_name(value: str) -> str:
        """Nome como o usuario digitou, sem espaco sobrando -- e o que vai ao contrato."""
        return " ".join((value or "").split())

    @staticmethod
    def normalize_name(value: str) -> str:
        return ConstructionDocumentationType.clean_name(value).upper()


class ConstructionInspectionStatus:
    PENDING = "pending"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"

    ALL_STATUSES = {PENDING, COMPLIANT, NON_COMPLIANT}
    RESOLVED_STATUSES = {COMPLIANT, NON_COMPLIANT}


class ConstructionOccurrenceStatus:
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"

    ALL_STATUSES = {OPEN, RESOLVED, CANCELLED}


class ConstructionProcurementStatus:
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_TO_ERP = "sent_to_erp"


PROJECT_STATUS_TRANSITIONS = {
    ConstructionProjectStatus.DRAFT: {ConstructionProjectStatus.ACTIVE, ConstructionProjectStatus.CANCELLED},
    ConstructionProjectStatus.ACTIVE: {
        ConstructionProjectStatus.PAUSED,
        ConstructionProjectStatus.COMPLETED,
        ConstructionProjectStatus.CANCELLED,
    },
    ConstructionProjectStatus.PAUSED: {ConstructionProjectStatus.ACTIVE, ConstructionProjectStatus.CANCELLED},
    ConstructionProjectStatus.COMPLETED: set(),
    ConstructionProjectStatus.CANCELLED: set(),
}

PROJECT_STATUSES = set(PROJECT_STATUS_TRANSITIONS)
PROJECT_TYPES = {
    ConstructionProjectType.RESIDENTIAL_VERTICAL,
    ConstructionProjectType.RESIDENTIAL_HORIZONTAL,
    ConstructionProjectType.COMMERCIAL,
    ConstructionProjectType.MIXED_USE,
    ConstructionProjectType.INFRASTRUCTURE,
    ConstructionProjectType.INDUSTRIAL,
}
BLOCK_STATUSES = {ConstructionBlockStatus.ACTIVE, ConstructionBlockStatus.INACTIVE}
UNIT_STATUSES = {
    ConstructionUnitStatus.AVAILABLE,
    ConstructionUnitStatus.RESERVED,
    ConstructionUnitStatus.SOLD,
    ConstructionUnitStatus.DELIVERED,
    ConstructionUnitStatus.TERMINATED,
    ConstructionUnitStatus.UNAVAILABLE,
}
SCHEDULE_PHASE_STATUSES = {
    ConstructionSchedulePhaseStatus.PLANNED,
    ConstructionSchedulePhaseStatus.IN_PROGRESS,
    ConstructionSchedulePhaseStatus.COMPLETED,
    ConstructionSchedulePhaseStatus.CANCELLED,
}
MEASUREMENT_STATUSES = {
    ConstructionMeasurementStatus.DRAFT,
    ConstructionMeasurementStatus.SUBMITTED,
    ConstructionMeasurementStatus.IN_APPROVAL,
    ConstructionMeasurementStatus.APPROVED,
    ConstructionMeasurementStatus.REJECTED,
    ConstructionMeasurementStatus.PAID,
}
PROCUREMENT_STATUSES = {
    ConstructionProcurementStatus.DRAFT,
    ConstructionProcurementStatus.PENDING_APPROVAL,
    ConstructionProcurementStatus.APPROVED,
    ConstructionProcurementStatus.REJECTED,
    ConstructionProcurementStatus.SENT_TO_ERP,
}

CONSTRUCTION_PROCUREMENT_APPROVAL_THRESHOLD = 50000
