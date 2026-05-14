class EventStatus:
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class ConstructionIntegrationMode:
    SYNC_HTTP = "sync_http"
    ASYNC_IN_MEMORY = "async_in_memory"
    ASYNC_SQS = "async_sqs"

    ALL_MODES = {SYNC_HTTP, ASYNC_IN_MEMORY, ASYNC_SQS}
    ASYNC_MODES = {ASYNC_IN_MEMORY, ASYNC_SQS}


class EventProducer:
    CONSTRUCTION_API = "construction-api"
    ERP_API = "erp-api"


class ConstructionEventType:
    PROJECT_CREATED = "construction.project.created.v1"
    UNIT_CREATED = "construction.unit.created.v1"
    MEASUREMENT_APPROVED = "construction.measurement.approved.v1"
    UNIT_SOLD = "construction.unit.sold.v1"
    PROCUREMENT_REQUESTED = "construction.procurement.requested.v1"


class ErpEventType:
    COST_CENTER_CREATED = "erp.cost_center.created.v1"
    ACCOUNTS_PAYABLE_CREATED = "erp.accounts_payable.created.v1"
    ACCOUNTS_PAYABLE_UPDATED = "erp.accounts_payable.updated.v1"
    CONTRACT_RECEIVABLE_CREATED = "erp.contract.receivable.created.v1"
    CONTRACT_STATUS_UPDATED = "erp.contract.status.updated.v1"
    PROCUREMENT_REQUEST_ACCEPTED = "erp.procurement.request.accepted.v1"


class ConstructionAggregateType:
    PROJECT = "construction_project"
    MEASUREMENT = "construction_measurement"
    UNIT = "construction_unit"
    PROCUREMENT_REQUEST = "construction_procurement_request"


class ConstructionConsumerName:
    COST_CENTER_CREATED = "construction.cost_center_created"
    ACCOUNTS_PAYABLE_UPDATED = "construction.accounts_payable_updated"
    CONTRACT_STATUS_UPDATED = "construction.contract_status_updated"