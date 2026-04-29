# NASCORP Construction

Independent Construction product for NASCORP, delivered as a standalone repository and optionally mounted in the ERP workspace as `external/nascorp-construction`.

The customer-facing product label can be `Obras`, but technical names in code, APIs, database objects, events, permissions and repository paths use English names.

## Repository Shape

```text
services/
	api/                    # FastAPI backend
ui/
	construction-mfe/        # Vite/React micro frontend
qa/
	cypress/                 # E2E test workspace placeholder
spec/                      # Architecture contracts and phase notes
```

## Local Development

### Backend

```bash
cd services/api
pip install -r requirements.txt
pip install -r dev_requirements.txt
python run.py
```

The API starts on `http://127.0.0.1:8010` and exposes `GET /v1/health`.

### Frontend

```bash
cd ui/construction-mfe
npm install
npm run dev
```

The MFE starts on `http://127.0.0.1:8011`.

## Root Scripts

```bash
npm run api:dev
npm run api:test
npm run mfe:dev
npm run mfe:build
```

## Phase Notes

- Phase 0: architecture contracts only.
- Phase 1: repository and runtime foundation only.
- Phase 2: database and event foundation.
- Phase 3: ERP permission and contract endpoints.

No ERP internals are imported by this repository. Integration must happen through HTTP contracts, versioned events and the frontend bridge/remote loading boundary.
