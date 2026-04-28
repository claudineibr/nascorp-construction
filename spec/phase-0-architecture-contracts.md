# Phase 0 - Architecture Contracts

Date: 2026-04-28
Status: baseline contract before implementation
Repository: https://github.com/claudineibr/nascorp-construction
ERP integration path: `external/nascorp-construction`

## Purpose

This document closes Phase 0 for the Construction product. It defines ownership boundaries, authentication, authorization, event contracts, error behavior and idempotency before any API, frontend, database or worker implementation starts.

The UI product label can remain `Obras`, but technical naming in code, database objects, APIs, events, permissions and repository paths must use English names.

## Phase 0 Non-Goals

Phase 0 does not create runtime code, database migrations, FastAPI skeletons, Vite apps, ERP permissions, menu entries or submodule pins.

Those activities start in Phase 1 or later. This phase only fixes contracts so the implementation has a stable target.

## Repository And Mounting Contract

The Construction product is delivered in a standalone repository:

```text
https://github.com/claudineibr/nascorp-construction
```

The ERP can mount it for local integration and deployment orchestration at:

```text
external/nascorp-construction
```

The mount must behave as an integration boundary, not as a shared codebase. The ERP must not import Python, JavaScript, ORM models, React components or internal services from the Construction repository. The Construction repository must not import ERP internals.

Allowed integration mechanisms:

- HTTP contracts.
- Versioned event contracts.
- Frontend remote loading or subdomain navigation.
- Submodule pinning for local orchestration only.

Forbidden integration mechanisms:

- Direct SQL reads or writes across ERP and Construction schemas.
- Cross-schema foreign keys.
- Python imports between services.
- React imports between host and remote internals.
- Reusing ERP database sessions inside Construction services.

## Bounded Context Ownership

| Capability | Owner | Construction Behavior | ERP Behavior |
|---|---|---|---|
| Companies and tenant access | ERP | Reads company context from JWT and `X-Company-ID` | Source of truth |
| Users and roles | ERP | Reads identity from JWT, never manages users | Source of truth |
| Effective permissions | ERP | Resolves through ERP permission contract and caches briefly | Source of truth |
| Subscription and commercial activation | ERP | Reads activation/limits through ERP contract | Source of truth |
| People, customers and suppliers | ERP | References by ERP ID and may keep lightweight cache | Source of truth |
| Cost centers | ERP | Requests creation through events or HTTP command, stores external IDs only | Source of truth |
| Finance and accounts payable | ERP | Publishes construction events and stores returned external IDs only | Source of truth |
| Contracts and receivables | ERP | Publishes sale events and stores returned external IDs only | Source of truth |
| Construction projects | Construction | Source of truth | Consumes events or summaries only |
| Construction blocks | Construction | Source of truth | No direct ownership |
| Construction units | Construction | Source of truth | Creates contracts/receivables only after event command |
| Construction schedule | Construction | Source of truth | No direct ownership |
| Construction measurements | Construction | Source of truth | Creates payables only after approved measurement event |
| Construction reports | Construction | Source for operational construction reports | ERP remains source for accounting and finance reports |

## Technical Naming Contract

Use English identifiers in technical artifacts:

| Concept | Technical Name |
|---|---|
| Produto/modulo | `construction` |
| Empreendimento | `ConstructionProject` / `construction_projects` |
| Bloco/torre | `ConstructionBlock` / `construction_blocks` |
| Unidade | `ConstructionUnit` / `construction_units` |
| Cronograma | `ConstructionSchedulePhase` / `construction_schedule_phases` |
| Medicao/BM | `ConstructionMeasurement` / `construction_measurements` |
| Referencia de pessoa | `ConstructionPersonReference` / `construction_person_references` |
| Evento de empreendimento criado | `construction.project.created.v1` |

Portuguese labels can be used only in UI copy and customer-facing documentation.

## Auth Contract

### Incoming Requests

Every protected request from the Construction MFE to the Construction API must send:

```http
Authorization: Bearer <erp_jwt>
X-Company-ID: <company_uuid>
```

The Construction API must treat frontend permission checks as UX only. Every protected endpoint must validate authorization server-side.

### JWT Validation

Initial implementation can validate the ERP JWT locally using shared signing material. The validation must be hidden behind an auth verifier port so the mechanism can later move to JWKS/asymmetric keys, token introspection or a Construction-scoped token without changing domain services.

Required token information:

| Field | Purpose |
|---|---|
| `sub` or user ID claim | Authenticated user identity |
| user email/name claims when available | Audit display only |
| role IDs or role source claim when available | Permission resolution input |
| issued/expiration timestamps | Token validity |

The `X-Company-ID` header is mandatory. The Construction API must confirm that the authenticated user can access that company. If this cannot be proven from JWT claims, the API must call an ERP company-access contract before authorizing the request.

### Refresh Behavior

The Construction API does not refresh ERP tokens. Token refresh remains owned by the ERP host/auth layer. If the MFE runs inside the ERP shell, it requests token refresh through the frontend bridge. If it runs as a subdomain, it follows the same ERP login/refresh contract through shared auth endpoints.

Expired or invalid tokens return the standard error contract with HTTP 401.

## Permission Contract

Construction permission keys are English and map to the ERP bitmask model:

| Key | Label | Actions |
|---|---|---|
| `construction_projects` | Obras - Empreendimentos | READ, CREATE, UPDATE, DELETE |
| `construction_units` | Obras - Unidades | READ, CREATE, UPDATE, DELETE |
| `construction_schedule` | Obras - Cronograma | READ, CREATE, UPDATE, DELETE |
| `construction_measurements` | Obras - Medicoes | READ, CREATE, UPDATE, DELETE |
| `construction_procurement` | Obras - Compras | READ, CREATE, UPDATE, DELETE |
| `construction_reports` | Obras - Relatorios | READ |

Action values must match the ERP permission bitmask:

| Action | Value |
|---|---:|
| READ | 1 |
| CREATE | 2 |
| UPDATE | 4 |
| DELETE | 8 |
| FULL | 15 |

The ERP remains the source of truth for permission catalog, plan features, role permissions and effective permissions.

### Effective Permission Lookup

The Construction API must resolve permissions through an ERP contract equivalent to:

```http
GET /v1/internal/permissions/effective
Authorization: Bearer <erp_jwt>
X-Company-ID: <company_uuid>
```

Expected response shape:

```json
{
  "plan_code": "professional",
  "feature_permissions": {
    "construction_projects": 15,
    "construction_units": 15,
    "construction_schedule": 7,
    "construction_measurements": 15,
    "construction_procurement": 1,
    "construction_reports": 1
  },
  "plan_features": {
    "construction_projects": 15,
    "construction_units": 15,
    "construction_schedule": 15,
    "construction_measurements": 15,
    "construction_procurement": 1,
    "construction_reports": 1
  }
}
```

The endpoint can be implemented in the ERP during Phase 3. Until then, Phase 1 and Phase 2 implementation can define the client port and test doubles only.

### Permission Cache

Construction API may cache effective permissions for up to 300 seconds, matching the ERP effective permission TTL pattern. Cache keys must include company ID and user/role identity. Permission denial must fail closed when the ERP permission endpoint is unavailable and no fresh cache exists.

## Module Activation Contract

Commercial activation must reuse ERP subscription and plan-feature ownership. Do not create a parallel `tenant_modules` source of truth in Phase 0.

Construction availability is derived from ERP plan features and effective permissions. Operational settings can be added later only if they represent module configuration, not commercial authorization.

## Cost Center Classification Contract

Cost centers created for Construction must distinguish synthetic and analytic nodes:

| Classification | Behavior |
|---|---|
| `synthetic` | Aggregates child cost centers and cannot receive postings |
| `analytic` | Receives postings and can be used by financial documents |

The current ERP `CostCenter.type` field is a generic text field. Phase 0 does not change the ERP schema. Phase 5 must decide whether `type` is sufficient or whether a dedicated migration is required for `classification` or `is_analytic`.

Construction never creates cost centers by direct database write. It requests cost center creation through event or HTTP command and stores only ERP external IDs.

## Event Architecture Contract

Production starts with AWS SQS and DLQ. SNS plus SQS is used when multiple consumers need the same event. Redis Streams can be a local/dev adapter only. RabbitMQ remains the portability alternative. Kafka is not part of the first implementation unless high-volume replay becomes a hard requirement.

Domain services must depend on ports, not broker SDKs:

- `EventPublisher`
- `EventConsumer`
- `EventSerializer`
- `OutboxRelay`

Infrastructure adapters can implement SQS, SNS/SQS, LocalStack, Redis Streams or in-memory behavior. Domain services must not import `boto3`, Redis clients, RabbitMQ clients or Kafka clients.

### Event Envelope

Every event must use this envelope:

```json
{
  "event_id": "018f8a30-6b2e-7ad4-bd72-3a7a8bfb8a10",
  "event_type": "construction.project.created.v1",
  "event_version": 1,
  "company_id": "018f8a31-22ba-76e7-9e80-54d05d62b3a2",
  "aggregate_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
  "aggregate_type": "construction_project",
  "occurred_at": "2026-04-28T15:30:00Z",
  "producer": "construction-api",
  "correlation_id": "018f8a31-bb08-76e4-a7ef-2c0f5367de63",
  "causation_id": null,
  "payload": {}
}
```

Required envelope fields:

| Field | Rule |
|---|---|
| `event_id` | Globally unique and immutable |
| `event_type` | Dot-separated English event name with version suffix |
| `event_version` | Integer schema version |
| `company_id` | Tenant isolation key |
| `aggregate_id` | Root aggregate affected by the event |
| `aggregate_type` | Stable aggregate type string |
| `occurred_at` | UTC ISO timestamp |
| `producer` | Producing service name |
| `correlation_id` | Same value across the business workflow |
| `causation_id` | Previous event or command ID when applicable |
| `payload` | Versioned business payload |

### Initial Event Catalog

#### `construction.project.created.v1`

Producer: Construction API
Consumer: ERP API
Purpose: request ERP cost center and optional CRM/project linkage after a construction project is created.

```json
{
  "event_id": "018f8a30-6b2e-7ad4-bd72-3a7a8bfb8a10",
  "event_type": "construction.project.created.v1",
  "event_version": 1,
  "company_id": "018f8a31-22ba-76e7-9e80-54d05d62b3a2",
  "aggregate_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
  "aggregate_type": "construction_project",
  "occurred_at": "2026-04-28T15:30:00Z",
  "producer": "construction-api",
  "correlation_id": "018f8a31-bb08-76e4-a7ef-2c0f5367de63",
  "causation_id": null,
  "payload": {
    "project_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
    "project_code": "CON-2026-0001",
    "project_name": "Residencial Jardim Norte",
    "project_kind": "apartment_condominium",
    "customer_erp_id": "018f8a32-2408-7b5f-9c77-8e653474179d",
    "start_date": "2026-05-01",
    "expected_end_date": "2027-11-30"
  }
}
```

#### `erp.cost_center.created.v1`

Producer: ERP API
Consumer: Construction API
Purpose: return ERP cost center IDs created for a construction project.

```json
{
  "event_id": "018f8a36-492d-73a6-9025-7b2cb732d09c",
  "event_type": "erp.cost_center.created.v1",
  "event_version": 1,
  "company_id": "018f8a31-22ba-76e7-9e80-54d05d62b3a2",
  "aggregate_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
  "aggregate_type": "construction_project",
  "occurred_at": "2026-04-28T15:31:00Z",
  "producer": "erp-api",
  "correlation_id": "018f8a31-bb08-76e4-a7ef-2c0f5367de63",
  "causation_id": "018f8a30-6b2e-7ad4-bd72-3a7a8bfb8a10",
  "payload": {
    "project_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
    "root_cost_center_erp_id": "018f8a36-b9b7-7458-8e69-a9395ff4c216",
    "root_cost_center_code": "9.01",
    "classification": "synthetic",
    "analytic_cost_centers": [
      {
        "cost_center_erp_id": "018f8a37-5302-7a1c-8607-f0161de22625",
        "code": "9.01.001",
        "description": "Foundation",
        "classification": "analytic"
      }
    ]
  }
}
```

#### `construction.measurement.approved.v1`

Producer: Construction API
Consumer: ERP API
Purpose: request creation of an accounts payable document after a measurement is approved.

```json
{
  "event_id": "018f8a39-510e-78df-b9e0-b8b3f02d57a4",
  "event_type": "construction.measurement.approved.v1",
  "event_version": 1,
  "company_id": "018f8a31-22ba-76e7-9e80-54d05d62b3a2",
  "aggregate_id": "018f8a39-8d5d-7003-9dbe-b59f1b81510a",
  "aggregate_type": "construction_measurement",
  "occurred_at": "2026-04-28T16:10:00Z",
  "producer": "construction-api",
  "correlation_id": "018f8a39-d0a5-779c-b5f1-65dcda8fc42d",
  "causation_id": null,
  "payload": {
    "measurement_id": "018f8a39-8d5d-7003-9dbe-b59f1b81510a",
    "project_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
    "supplier_erp_id": "018f8a3a-2182-71b8-9066-50967e49fc1a",
    "analytic_cost_center_erp_id": "018f8a37-5302-7a1c-8607-f0161de22625",
    "gross_amount": "125000.00",
    "retention_amount": "6250.00",
    "net_amount": "118750.00",
    "due_date": "2026-05-15",
    "document_number": "BM-00042"
  }
}
```

#### `erp.accounts_payable.created.v1`

Producer: ERP API
Consumer: Construction API
Purpose: return the accounts payable document created from a measurement.

```json
{
  "event_id": "018f8a3c-c806-778d-92bd-c07e96b9c30c",
  "event_type": "erp.accounts_payable.created.v1",
  "event_version": 1,
  "company_id": "018f8a31-22ba-76e7-9e80-54d05d62b3a2",
  "aggregate_id": "018f8a39-8d5d-7003-9dbe-b59f1b81510a",
  "aggregate_type": "construction_measurement",
  "occurred_at": "2026-04-28T16:11:00Z",
  "producer": "erp-api",
  "correlation_id": "018f8a39-d0a5-779c-b5f1-65dcda8fc42d",
  "causation_id": "018f8a39-510e-78df-b9e0-b8b3f02d57a4",
  "payload": {
    "measurement_id": "018f8a39-8d5d-7003-9dbe-b59f1b81510a",
    "accounts_payable_erp_id": "018f8a3d-1298-7002-a863-c276b517b7f0",
    "document_number": "BM-00042",
    "status": "open",
    "due_date": "2026-05-15",
    "amount": "118750.00"
  }
}
```

#### `construction.unit.sold.v1`

Producer: Construction API
Consumer: ERP API
Purpose: request contract and receivable creation after a unit sale is confirmed.

```json
{
  "event_id": "018f8a3f-8a0a-76e2-8383-2f3c0c971d53",
  "event_type": "construction.unit.sold.v1",
  "event_version": 1,
  "company_id": "018f8a31-22ba-76e7-9e80-54d05d62b3a2",
  "aggregate_id": "018f8a40-060c-7f6a-b3a2-4c8c79a62107",
  "aggregate_type": "construction_unit",
  "occurred_at": "2026-04-28T17:00:00Z",
  "producer": "construction-api",
  "correlation_id": "018f8a40-72a7-74ac-9fb1-6c2cf44406f2",
  "causation_id": null,
  "payload": {
    "unit_id": "018f8a40-060c-7f6a-b3a2-4c8c79a62107",
    "project_id": "018f8a31-9c02-7166-b987-8b8a69f3a14d",
    "buyer_erp_id": "018f8a41-a4ac-7c05-9651-d02ca0977733",
    "unit_code": "T1-1204",
    "sale_amount": "680000.00",
    "down_payment_amount": "68000.00",
    "installment_count": 120,
    "first_due_date": "2026-06-10"
  }
}
```

## Error Contract

Construction API must follow the ERP global error response shape:

```json
{
  "success": false,
  "message": "Acesso negado",
  "error_code": "FORBIDDEN",
  "details": null
}
```

Recommended error codes:

| HTTP | Error Code | Use Case |
|---:|---|---|
| 400 | `INVALID_REQUEST` | Malformed command or unsupported query |
| 401 | `UNAUTHORIZED` | Missing, expired or invalid token |
| 403 | `FORBIDDEN` | Valid token without required company or feature permission |
| 404 | `NOT_FOUND` | Resource not found inside the current company scope |
| 409 | `CONFLICT` | Duplicate command, invalid state transition or idempotency conflict |
| 422 | `VALIDATION_ERROR` | Field-level validation failure |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected server failure |
| 503 | `DEPENDENCY_UNAVAILABLE` | Required ERP contract or broker unavailable |

Validation details should be structured as field errors when possible:

```json
{
  "success": false,
  "message": "Invalid request data",
  "error_code": "VALIDATION_ERROR",
  "details": [
    {
      "field": "body -> project_name",
      "message": "Field required",
      "type": "missing"
    }
  ]
}
```

## HTTP Idempotency Contract

HTTP commands that create external side effects must support an `Idempotency-Key` header. This includes commands that publish events or request ERP-side creation.

Required behavior:

1. Same user, company, route and idempotency key with the same request body returns the original result.
2. Same key with a different request body returns HTTP 409 `CONFLICT`.
3. Idempotency records expire only after the business workflow is no longer retryable.
4. Read operations do not require idempotency keys.

The implementation can persist command idempotency in a dedicated table during Phase 2 or Phase 4, depending on when command endpoints begin.

## Event Idempotency Contract

Every consumer must be idempotent. The minimum processed-event key is:

```text
consumer_name + event_id
```

For ERP side effects, consumers must also protect business uniqueness, for example:

```text
company_id + external_origin_type + external_origin_id
```

Required behavior:

1. Duplicate events do not create duplicate cost centers, payables, contracts or receivables.
2. Processing status is stored before acknowledging the message.
3. Recoverable failures increment retry count and keep the event available for retry.
4. Non-recoverable failures move to DLQ with `last_error`, original payload and correlation ID.
5. Manual replay must preserve the original `event_id` and `correlation_id`.

## Outbox And Inbox Contract

Construction-owned events are first written to an outbox in the same transaction as the aggregate change. A relay publishes pending events to the broker and marks them published only after broker acknowledgement.

Consumers write processed-event records before acknowledging messages. This applies to both Construction consumers and ERP consumers.

Minimum outbox fields for Phase 2:

| Field | Rule |
|---|---|
| `event_id` | Unique event identifier |
| `event_type` | Versioned event type |
| `event_version` | Integer version |
| `aggregate_id` | Aggregate UUID |
| `company_id` | Tenant UUID |
| `payload` | JSON payload |
| `status` | pending, published, failed, dead_letter |
| `retry_count` | Starts at 0 |
| `occurred_at` | Event creation timestamp |
| `published_at` | Null until published |
| `last_error` | Last relay or broker error |

## Construction MFE Bridge Contract

The MFE must use a narrow bridge when mounted inside the ERP host. It must not access ERP contexts, services or stores directly.

Allowed bridge capabilities:

```ts
type ConstructionBridge = {
  getAccessToken: () => Promise<string | null>
  getCompanyId: () => string | null
  getUser: () => { id: string; name?: string; email?: string } | null
  getTheme: () => "light" | "dark"
  navigateToErp: (path: string) => void
  notify: {
    success: (message: string) => void
    error: (message: string) => void
    warning: (message: string) => void
  }
}
```

The bridge does not expose API clients, permission contexts, React routers or internal ERP objects.

## Phase 0 Definition Of Done

Phase 0 is complete when:

1. This architecture contract exists in the Construction repository under `spec/`.
2. Ownership boundaries are explicit for ERP and Construction.
3. JWT, `X-Company-ID`, company access and permission lookup behavior are documented.
4. Permission keys are defined in English and aligned with the ERP bitmask model.
5. Initial event catalog includes envelope fields and payload examples.
6. Error response shape follows the ERP `ErrorResponse` contract.
7. HTTP command idempotency and event consumer idempotency are documented.
8. No runtime implementation has been created before these contracts are accepted.

## Open Decisions For Phase 1

1. Whether the local development mount will be a Git submodule immediately or a plain clone until the first commit is stable.
2. Whether Construction API should use `services/api` or `services/construction-api` inside its own repository. Current recommendation is `services/api` to mirror the ERP monorepo shape.
3. Whether the first local broker adapter will use LocalStack SQS or an in-memory adapter for contract tests.
4. Whether JWT verification starts with shared secret in development and moves to JWKS before production.
5. Whether ERP implements the effective-permission endpoint exactly as documented or exposes an equivalent internal route name during Phase 3.
