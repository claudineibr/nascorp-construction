# Phase 2 - Database And Event Foundation

Date: 2026-04-28
Status: implemented locally

## Scope Delivered

Phase 2 adds the database and event foundation for the Construction API.

Delivered backend assets:

```text
services/api/alembic.ini
services/api/alembic/env.py
services/api/alembic/versions/20260428_0001_create_event_foundation.py
services/api/app/domain/events
services/api/app/infrastructure/database
services/api/app/infrastructure/events
services/api/app/infrastructure/repository/event_repository.py
```

## Database Foundation

The first migration creates event persistence tables:

- `outbox_events`
- `processed_events`
- `dead_letter_events`

Outbox and dead-letter rows preserve the full event envelope, including `producer`, `correlation_id` and `causation_id`.

The Construction API database foundation is PostgreSQL-only. The migration creates and uses the `construction` schema and fails fast when executed with any other dialect.

Dead-letter events are operational diagnostics, not a long-term business record. Payloads that contain personal data must be redacted before publishing whenever the consumer does not require the raw value, and DLQ retention must be bounded by infrastructure policy. The default target is 30 days unless a shorter product or legal requirement applies; replay tooling in later phases must preserve this retention/redaction boundary.

## Event Foundation

The domain layer defines broker-neutral ports:

- `EventPublisher`
- `EventConsumer`
- `EventSerializer`
- `OutboxRelay`
- `ProcessedEventStore`

Infrastructure adapters added in this phase:

- `JsonEventSerializer`
- `InMemoryEventBus`
- `InMemoryProcessedEventStore`
- `SqsEventBus`
- `DatabaseOutboxRelay`

Domain services do not import broker SDKs.

## Validation

Required commands:

```bash
cd services/api
alembic upgrade head
alembic current
python -m pytest
```

The MFE runtime remains unchanged in this phase, but `npm run build` should still pass after dependency changes.

## Next Phase

Phase 3 adds ERP permission catalog changes and internal contract endpoints required by Construction authorization.