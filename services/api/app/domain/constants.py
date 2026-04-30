class ConstructionProjectStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConstructionBlockStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"


class ConstructionUnitStatus:
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
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
BLOCK_STATUSES = {ConstructionBlockStatus.ACTIVE, ConstructionBlockStatus.INACTIVE}
UNIT_STATUSES = {
    ConstructionUnitStatus.AVAILABLE,
    ConstructionUnitStatus.RESERVED,
    ConstructionUnitStatus.SOLD,
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
