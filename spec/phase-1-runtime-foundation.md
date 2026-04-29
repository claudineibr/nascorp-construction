# Phase 1 - Repository And Runtime Foundation

Date: 2026-04-28
Status: implemented

## Scope Delivered

Phase 1 creates the executable repository foundation for the standalone Construction product.

Delivered structure:

```text
services/api
ui/construction-mfe
qa/cypress
spec
```

## Backend Runtime

The backend skeleton lives in `services/api` and follows the same clean architecture boundaries used by the ERP:

```text
app/
  presentation/routes
  domain/services
  infrastructure/repository
  schemas
```

The only runtime endpoint in Phase 1 is `GET /v1/health`.

Phase 1 intentionally does not create database models, Alembic migrations, event adapters, authentication dependencies or ERP contract clients.

## Frontend Runtime

The frontend skeleton lives in `ui/construction-mfe` and uses Vite, React and CSS Modules.

The app includes a narrow bridge resolver for future ERP host integration:

```text
window.__NASCORP_CONSTRUCTION_BRIDGE__
```

Phase 1 intentionally does not configure federation, protected routes, ERP menu integration or API mutations.

## Validation

Backend validation:

```bash
cd services/api
python -m pytest
```

Frontend validation:

```bash
cd ui/construction-mfe
npm install
npm run build
```

## Next Phase

Phase 2 adds database and event foundation: schema ownership, Alembic, outbox/inbox tables, event ports and broker adapters.