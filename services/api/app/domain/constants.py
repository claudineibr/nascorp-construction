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
    APPROVED = "approved"
    REJECTED = "rejected"


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
    ConstructionMeasurementStatus.APPROVED,
    ConstructionMeasurementStatus.REJECTED,
}
PROCUREMENT_STATUSES = {
    ConstructionProcurementStatus.DRAFT,
    ConstructionProcurementStatus.PENDING_APPROVAL,
    ConstructionProcurementStatus.APPROVED,
    ConstructionProcurementStatus.REJECTED,
    ConstructionProcurementStatus.SENT_TO_ERP,
}

CONSTRUCTION_PROCUREMENT_APPROVAL_THRESHOLD = 50000
