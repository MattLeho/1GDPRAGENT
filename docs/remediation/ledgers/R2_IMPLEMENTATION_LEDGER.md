# R2 implementation ledger

**Starting point:** `main` at `67e50b85daa923366d3bec80db6582edcc3ba134`

**Implementation period:** 2026-07-18 to 2026-08-13

**Decision owner:** lead agent

## Acceptance decision

R2 is accepted. Both final independent audits returned PASS: migration/request-domain SQL and lifecycle/deadline semantics. Migration 031 remains byte-for-byte unchanged and its checksum matches the recorded installation.

## Frozen decisions

- `requests` is the sole canonical, profile-owned request root. `access_requests` is read-only compatibility only.
- Lifecycle changes go through one guarded transition path and append immutable provenance events.
- User cancellation retains the request and all evidence; R2 performs no physical request deletion.
- Missing legal dates are never fabricated. `deadline_at` is an explicit, screened effective deadline; `updated_at` is operational metadata only.
- Deadline screening uses Europe/London calendar dates, calendar months, end-of-day, weekends, England/Wales bank holidays, identity and SAR-clarification rules, and validated extension evidence.
- Request-domain SQL, including request children and email drafts, is confined to the TypeScript and Python repositories and is profile scoped.
- Legacy N8N request workflows are inactive and are not selectable by the runtime registry.

## Delivered scope

- Ordered compatibility/preflight and lifecycle hardening migrations: 030a, 032, and 033, without altering applied migration 031.
- Canonical TypeScript and Python request repositories plus service boundary.
- Atomic lifecycle/event provenance and atomic request-thread/lifecycle updates.
- Historical status reconciliation with migration audit events and canonical constraints.
- Evidence-retaining cancellation, grounded dashboard metrics, live response classification, and deadline detail UI.
- Recursive static boundary checks for application and workflow SQL.
- Three-path real-database matrix: clean install, pre-031 historical upgrade, and already-recorded-031 upgrade.

## Final evidence

- Independent migration/SQL audit: PASS.
- Independent lifecycle/deadline audit: PASS; final focused run 48/48.
- Migration fixtures: 4/4 on disposable PostgreSQL databases.
- Real-database query matrix: TypeScript 1/1 and Python 1/1 on each of all three paths.
- Frontend: typecheck passed; full suite 128 passed with the separately executed DB integration intentionally skipped; production build passed.
- Python: 539 passed and 3 skipped in the full run; its only three failures were a host/container Neo4j hostname mismatch, and all three passed when rerun against the mapped localhost endpoint.
- Authenticated browser acceptance used a disposable database and throwaway profile. Home and Requests loaded without browser console errors. No real user account was used.

## Evidence locations

- `scripts/r2-query-matrix.py`
- `tests/migration_fixtures/test_r2_request_lifecycle_migration.py`
- `tests/test_r2_request_domain_static.py`
- `frontend/tests/r2-request-repository.integration.test.ts`
- `frontend/tests/r2-deadline-engine.test.ts`
- `frontend/tests/r2-dashboard-metrics.test.ts`
- `docs/remediation/handoffs/R2_PAUSE_HANDOFF_2026-07-18.md`
