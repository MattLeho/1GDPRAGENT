# Fixes And Follow-Up Backlog

## Completed Fixes

- Made Docker host ports configurable and changed defaults to avoid local port collisions.
- Removed obsolete compose `version` field.
- Added root `.gitignore`.
- Added root `.dockerignore`.
- Added `intelligence/.dockerignore`.
- Scrubbed `.env.example` so it contains placeholders only.
- Removed a real-looking API key from documentation.
- Removed hard-coded credential fallback secrets from frontend credential helpers.
- Required explicit `NEO4J_PASSWORD` instead of falling back to `password`.
- Added missing `vendor_lists` table to database bootstrap schema.
- Added missing `ai_credentials` table to database bootstrap schema.
- Aligned `request_chat_messages` schema with chat route usage.
- Fixed bulk-email route to use valid `requests` columns.
- Added static audit tests for Docker, schema, route, and secret guardrails.
- Fixed a hook-order issue in `RequestsGrid`.
- Fixed `prefer-const` lint failures.
- Upgraded vulnerable frontend dependencies until `npm audit --audit-level=moderate` reports 0 vulnerabilities.
- Restarted Docker services and verified the stack is healthy.

## Remaining Cleanup Tasks

1. Reduce frontend lint warnings.
   - Replace broad `any` types with proper route/component interfaces.
   - Remove unused imports and variables.
   - Fix image `alt` warnings.
   - Review React compiler advisory warnings rather than suppressing them permanently.

2. Rename `middleware.ts` to the modern Next.js proxy convention.
   - Next 16.2.7 warns that the middleware file convention is deprecated.

3. Improve Docker production posture.
   - Replace dev `npm install && npm run dev` with a production image path for deployment.
   - Avoid installing dependencies on every container start.
   - Add explicit healthchecks for n8n and Celery.

4. Improve secret management.
   - Generate new local secrets after the audit because old values may have existed in local files.
   - Rotate any API keys that were previously stored in publishable files.
   - Prefer a secrets manager or local uncommitted `.env` workflow.

5. Consolidate database migrations.
   - There are multiple schema/migration locations.
   - Choose a single migration source of truth and make startup apply migrations idempotently.

6. Add real unit and integration tests.
   - Current added tests are static guardrails.
   - Add API route tests for auth, uploads, chat, and ONSIT bulk actions.
   - Add database migration tests against a disposable Postgres container.

7. Review frontend dependency footprint.
   - npm still reports many packages looking for funding and a large dependency tree.
   - Keep `npm audit` in CI after GitHub publishing.

8. Decide repository layout before publishing.
   - Root currently contains app code, private ignored data, docs, and a nested `frontend/.git`.
   - For GitHub, prefer one clean root Git repository and remove or ignore nested Git metadata intentionally.

