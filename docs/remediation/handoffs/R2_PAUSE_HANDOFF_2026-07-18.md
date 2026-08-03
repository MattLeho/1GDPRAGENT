# R2 pause handoff — 2026-07-18

## Status

R2 is substantially implemented but **not accepted or complete**. Stop point is after implementation, live migration 031, focused/unit verification, migration-fixture verification, and the first real PostgreSQL execution of the TypeScript repository. Do not mark the goal complete until the remaining gates below pass.

The worktree was already broadly dirty with R0/R1 work when R2 began. Preserve all existing changes. Starting branch was `main`; observed starting commit was `67e50...`.

## Completed implementation

- Audited R0/R1 definitions, protocol, traceability, migrations, schema, and request SQL surfaces.
- Repaired predecessor auth runtime secrets; malformed sessions now return 401 and clear the cookie rather than 503.
- Applied migration 030 and then 031 to the local live PostgreSQL database.
- Added `database/migrations/031_r2_request_lifecycle.sql`:
  - explicit lifecycle/deadline/extension/next-action fields;
  - `updated_at` plus trigger;
  - no fabricated receipt/response/completion/legal dates;
  - read-only `access_requests` compatibility view;
  - guarded canonical transition function;
  - append-only provenance-rich request events.
- Established profile-scoped TypeScript repository/service in `frontend/lib/requests/` and Python repository in `intelligence/request_domain/`.
- Migrated dashboard, list/detail, chat, events, received data, messages, uploads, outbound paths, RLM context, and response classification away from `access_requests` and scattered request SQL.
- Added deterministic calendar-month deadline screening with unknown/disputed dates, identity/clarification pauses, explicit extensions, basis/uncertainties, and human-review output.
- Replaced misleading dashboard privacy/compliance/risk/data-point/fixed-30-day claims with evidence-backed lifecycle, artefact, workflow, and paired-date metrics.
- Added static boundaries preventing canonical application reads/writes through `access_requests` and request SQL outside the two repositories.

## Verification already passed

- TypeScript typecheck: passed before the final integration-only guard edit; rerun once on pickup.
- R2 frontend focused tests: deadline 19/19, repository unit 15/15, dashboard 4/4.
- R2 Python/static tests: 7/7.
- All migration fixtures: 10/10.
- Independent fixture verifier: clean install, repeated migration, historical pre-031 upgrade, preservation of chat/received data/messages/workflows/events, no legal-date fabrication, view write rejection, profile isolation, invalid-transition atomicity, event immutability, and `updated_at` all passed.
- Live migration runner: applied 031 once; immediate second run was a no-op.
- Real PostgreSQL repository integration: the single test body executed every canonical TypeScript repository query successfully with representative data and cross-profile checks (39 focused assertions/tests total passed). The suite exit was nonzero only because teardown attempted to cascade-delete immutable events.

## Important defect found and repaired

The first PostgreSQL run showed that `SELECT (transition_request_state(...)).*` can evaluate the volatile composite function repeatedly. A valid transition therefore retried itself and failed. `RequestRepository.transition` now uses a `WITH ... AS MATERIALIZED` CTE, and a unit regression assertion was added. The subsequent real database test body passed.

## Open semantic decision / blocker

`request_events` rejects DELETE, including a foreign-key cascade from deleting a request. Consequently, physical deletion of a request that has lifecycle events fails. This is consistent with strict immutable audit history but conflicts with the repository/API's current physical `delete()` expectation.

On pickup, make an explicit lead-owned decision and test it:

1. Prefer retained audit history: replace user-facing physical deletion of progressed requests with an allowed terminal transition (`cancelled` or `closed_incomplete`) and clearly define behavior for terminal/completed records; or
2. If product requirements demand physical erasure, add a **new migration 032** with a tightly controlled request-erasure procedure/guard that preserves required audit semantics. Do not edit applied migration 031 because migration checksums are immutable.

Four test profiles created during live integration attempts were removed. Cleanup temporarily disabled only the append-only trigger inside one transaction and targeted profiles named `R2 integration profile` / `R2 other profile`. The integration test now refuses any database whose name does not start with `r2_`; use a disposable database and drop that database after the run.

## Remaining acceptance gates

1. Resolve and test the request deletion/event-immutability policy above.
2. Create disposable clean and historical-upgrade databases named `r2_*`; run `frontend/tests/r2-request-repository.integration.test.ts` against both. This is needed to satisfy “every query on clean and representative upgrade schema,” not merely the live upgraded database.
3. Rerun typecheck, full frontend tests/build, and all R0–R2 Python/API/authority suites.
4. Run authenticated browser checks for Home and Requests and confirm no page/SQL console errors.
5. Audit legacy `agents/*.json` workflow SQL or prove those definitions are not loaded by runtime; canonical static checks currently cover `frontend/` and `intelligence/`.
6. Commission independent read-only audits by agents that did not implement the areas:
   - migration + SQL query audit;
   - lifecycle + deadline-semantics audit.
7. Repair all findings, update `docs/remediation/ledgers/R2_IMPLEMENTATION_LEDGER.md`, and only then mark the active goal complete.

## Useful commands

Bundled runtimes:

- Python: `C:\Users\Jean-Marc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
- pnpm: `C:\Users\Jean-Marc\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd`
- Add Node to PATH: `C:\Users\Jean-Marc\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin`

Focused verification:

```powershell
cd frontend
pnpm run typecheck
pnpm exec vitest run tests/r2-deadline-engine.test.ts tests/r2-request-repository.test.ts tests/r2-dashboard-metrics.test.ts
cd ..
python -m pytest -q tests/test_r2_request_domain_static.py tests/test_r2_python_request_repository.py
python -m pytest -q tests/migration_fixtures
```

For the PostgreSQL integration test, set `R2_TEST_DATABASE_URL` to a disposable migrated database whose database name starts with `r2_`, then run:

```powershell
cd frontend
pnpm exec vitest run tests/r2-request-repository.integration.test.ts
```

## Evidence locations

- `docs/remediation/evidence/r2-schema-drift-inventory.md`
- `docs/remediation/ledgers/R2_IMPLEMENTATION_LEDGER.md`
- `tests/migration_fixtures/test_r2_request_lifecycle_migration.py`
- `frontend/tests/r2-request-repository.integration.test.ts`
- `frontend/tests/r2-deadline-engine.test.ts`
- `frontend/tests/r2-dashboard-metrics.test.ts`
- `tests/test_r2_request_domain_static.py`
