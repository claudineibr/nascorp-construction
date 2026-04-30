class EventStatus:
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class EventProducer:
    CONSTRUCTION_API = "construction-api"
    ERP_API = "erp-api"


class ConstructionEventType:
    PROJECT_CREATED = "construction.project.created.v1"


class ErpEventType:
    COST_CENTER_CREATED = "erp.cost_center.created.v1"


class ConstructionAggregateType:
    PROJECT = "construction_project"


class ConstructionConsumerName:
    COST_CENTER_CREATED = "construction.cost_center_created"