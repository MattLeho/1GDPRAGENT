# GDPR Agent Codebase Audit

Audit date: 2026-06-01

## Executive Summary

The application is now running again in Docker without colliding with the already-running local stack on ports 3000, 8000, and 5432. The GDPR stack is available on non-overlapping defaults:

- Frontend: http://localhost:3001
- Intelligence API: http://localhost:8001
- Postgres host port: 15432
- n8n: http://localhost:5678
- Neo4j: http://localhost:7474 and bolt://localhost:7687
- Qdrant: http://localhost:6333
- Redis: localhost:6379

The highest-risk issues found were hard-coded host ports, real-looking secrets in publishable files, missing Git ignore rules for private data, schema drift between SQL and application routes, and vulnerable frontend dependencies. Those are fixed.

## What Was Good

- The frontend production build succeeds.
- TypeScript type-checking succeeds.
- The Python intelligence and agent modules compile successfully.
- Docker builds the intelligence image successfully.
- The service split is sensible: Next.js frontend, FastAPI intelligence service, Celery worker, Postgres, Redis, Neo4j, Qdrant, and n8n.
- Database access mostly uses parameterized SQL.
- Uploaded/private runtime data is naturally isolated under local directories that can be ignored.
- The intelligence service exposes a simple `/health` endpoint and reports healthy in Docker.

## High-Risk Findings Fixed

### Docker Port Collisions

The compose file hard-coded `3000:3000`, `8000:8000`, and `5432:5432`, which collided with the existing `taskplanner` containers.

Fixed by making host ports configurable and setting non-overlapping defaults:

- `NEXTJS_HOST_PORT:-3001`
- `INTELLIGENCE_HOST_PORT:-8001`
- `POSTGRES_HOST_PORT:-15432`

### Secrets And GitHub Safety

Real-looking secrets were present in local env files and in the example env file. Local env files are now ignored, and `.env.example` has placeholders instead of live-looking values.

Added root `.gitignore`, root `.dockerignore`, and `intelligence/.dockerignore` to exclude:

- `.env` and `.env.*`
- uploaded files
- private case-data directory
- audio/video files
- virtualenvs, node modules, caches, build output, and logs

Also removed a real-looking API key from documentation and replaced it with instructions to use local env values.

### Predictable Secret Fallbacks

Several credential helpers had hard-coded fallback secrets such as fixed encryption keys or a default Neo4j password.

Fixed by requiring explicit environment variables for:

- `ENCRYPTION_KEY` or `CREDENTIALS_ENCRYPTION_KEY`
- `NEO4J_PASSWORD`

### Database Schema Drift

The application expected tables/columns that the initial Docker schema did not create.

Fixed in `docker/init/01_schema.sql`:

- Added `vendor_lists`
- Added `ai_credentials`
- Aligned `request_chat_messages` with route usage: `sender` and `message`

Also updated the top-level schema copy for consistency.

### Runtime SQL Mismatch

`send-bulk-emails` referenced non-existent `requests.company` and `requests.date_started` columns.

Fixed to use:

- `requests.company_name`
- `requests.created_at`

### Dependency Vulnerabilities

`npm audit` initially reported 12 vulnerabilities, including high and critical transitive issues.

Fixed by:

- Running `npm audit fix`
- Upgrading `next` and `eslint-config-next` to `16.2.7`
- Updating `postcss` to a patched version

Current `npm audit --audit-level=moderate`: 0 vulnerabilities.

## Tests Added

Added `tests/test_audit_static.py` with checks for:

- Compose host ports must be configurable, not hard-coded to occupied defaults.
- Initial schema must include tables used by routes.
- Request routes must use schema-valid columns.
- Chat route and chat schema must agree.
- `.env.example` must not contain live-looking secrets.

## Verification Performed

Passing:

- `python -m pytest tests`
- `npx tsc --noEmit`
- `npm run lint` exits successfully with warnings only
- `npm run build`
- `python -m compileall intelligence agents\python`
- `docker compose config --quiet`
- `npm audit --audit-level=moderate`
- Docker stack starts successfully with all core services healthy
- `http://localhost:8001/health` returns OK
- `http://localhost:3001/login` returns 200

## Remaining Non-Blocking Warnings

The frontend lint run still reports warnings, mainly:

- Existing `any` usage
- Unused imports/variables
- React compiler advisory warnings around set-state-in-effect and render purity
- A few image accessibility warnings
- Deprecation warning: Next.js recommends renaming `middleware.ts` to the newer proxy convention

These warnings do not block build, type-check, lint exit status, or Docker startup, but they are worth cleaning in a later quality pass.

## GitHub Publishing Safety

The repository root was not a Git repository during the audit, though `frontend` has its own `.git` directory. Before publishing from the root, initialize Git only after confirming the ignore rules are active.

The new root `.gitignore` is designed to prevent private local data and secrets from being added accidentally.

