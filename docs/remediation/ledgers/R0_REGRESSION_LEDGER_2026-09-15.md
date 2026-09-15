# R0 regression ledger — September 2026 head

**Accepted baseline:** `4e7e62448e8fd8e837113279dc668bc3528cadcf` (hosted run [31833659810](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810), recorded in `docs/remediation/R0_ACCEPTANCE_DECISION.md`)
**Regressed head inspected:** `674f111` ("tests") on `main`; hosted run [34961266200](https://github.com/MattLeho/1GDPRAGENT/actions/runs/34961266200) failed four of nine gates (migration fixtures, Python suite, static invariants, browser).
**Regressing commits:** `faec751` ("Front end enhancement and checks.") and `674f111` ("tests"), which introduced migrations 034/035, twenty new frontend contract tests and the tracked pnpm store without re-running the R0 gate.
**Decision owner:** lead agent. Bounded subagents repaired items 2, 3 and 4 under explicit path ownership; migrations, registry, ledger, gate execution and the acceptance judgement stayed with the lead.
**Scope:** restore the accepted R0 baseline only. No R3--R8 product work, no new architecture, no weakening of R1 profile isolation or R2 request-lifecycle contracts.

## Regressions

### 1. SETTINGS-002 migration fails closed on clean install and multi-profile upgrade

- **Failure.** `database/migrations/034_settings_profile_ownership.sql` raised `SETTINGS-002 cannot infer canonical ownership for 1 row(s) in processing_settings` in six migration fixtures, the Task 1 database fixture and the managed browser stack.
- **Root cause.** Migration 010 unconditionally seeds `processing_settings(id = 1)` as a global singleton. On a clean install no profile exists when 034 runs, and on a two-profile upgrade the row belongs to nobody, so 034's fail-closed guard fires on a row that carries no configuration at all. A second defect in 034: it keeps 010's `CHECK (id = 1)` singleton guard while switching `id` to a sequence, so the second profile to save settings receives `id = 2` and is rejected. Per-profile settings could therefore never work on a multi-profile installation.
- **Files changed.** `database/migrations/033a_settings_seed_preflight.sql` (new, ordered before 034), `database/migrations/036_settings_singleton_guard_removal.sql` (new), `tests/migration_fixtures/test_settings_profile_ownership_migration.py` (new). Migration 034 is byte-for-byte unchanged because the local development database has already applied it and applied migrations are immutable (the same convention R2 used with 030a/032/033 around applied 031).
- **Why invariants hold.** 033a deletes only a row that is still at every migration-010 default (`local_first`, fallback off, no approved engines) and has no owner. Such a row is indistinguishable from "no row": `getProcessingSettings` in `frontend/lib/execution/router.ts` returns exactly those defaults when a profile has no row, so nothing is lost and nothing is assigned. A modified singleton is left for 034, which still assigns it only when exactly one profile exists and still fails closed for two or more profiles. 036 drops only the singleton `CHECK`; ownership uniqueness stays enforced by `processing_settings_profile_uidx` and `processing_settings_profile_id_fkey` from 034, and `profile_id` stays `NOT NULL`. Both new migrations are idempotent and safe on installations where 034 already ran.
- **Test proving closure.** `tests/migration_fixtures/test_settings_profile_ownership_migration.py`: clean install has zero ownerless rows and two profiles each own one row through the router's `ON CONFLICT(profile_id)` upsert; a modified legacy singleton with one profile is assigned to that profile; a pristine singleton with two profiles is removed, not assigned; a modified singleton with two profiles still raises `SETTINGS-002` and leaves the row and migration history untouched; an installation that applied 034 before 033a existed gains 033a and 036 without changing the owned row. All eleven pre-existing migration fixtures pass again.

### 2. Static invariants classify a Vitest migration-shape test as runtime DDL

- **Failure.** `tests/test_audit_static.py::test_application_code_contains_no_runtime_ddl` and `tests/integration/test_r0_architecture_invariants.py::test_neo4j_schema_ddl_is_not_executed_at_runtime` reported `frontend/tests/policy-analysis-migration.test.ts`.
- **Root cause.** That file is a Vitest test that reads migration 035 and asserts on its text with regexes that quote `ALTER TABLE`, `DROP CONSTRAINT` and `CREATE ... INDEX` literally. Neither scanner distinguished test-only sources from runtime sources, so quoted DDL in a test counted as a runtime schema owner.
- **Files changed.** `tests/integration/test_r0_architecture_invariants.py` (shared `is_test_only_source` classifier applied in `source_files`, negative-control assertions, policy assertion), `tests/test_audit_static.py` (uses the shared `source_files`, gains a positive control), `docs/remediation/evidence/r0-runtime-root-policy.json` (`non_runtime_source_patterns` recorded as reviewed policy), new fixtures under `tests/fixtures/r0_architecture_invariants/frontend/` (`lib/runtime-ddl.ts` positive control, `tests/schema-shape.test.ts` and `lib/__tests__/ddl.test.ts` negative controls). The Vitest test itself and `r0-expected-static-findings.json` were not touched.
- **Why invariants hold.** The rule "runtime application code may not own schema DDL" and both DDL regexes are unchanged. Only the definition of "runtime source" changed: files under `tests/`, `__tests__/`, `test-results/`, `e2e/` or named `*.test.*` / `*.spec.*` are test-only. The classification is declared in the runtime-root policy and asserted to match the constants the scanners use, and a further assertion guarantees no registered expected finding (`MODEL-008`) can hide behind it.
- **Test proving closure.** `test_verifiers_reject_synthetic_negative_controls` now requires `frontend/lib/runtime-ddl.ts` to remain reported while the two byte-identical test-path fixtures are absent; `test_application_code_contains_no_runtime_ddl` asserts the same positive control before scanning the real tree. The full static gate (`scripts/r0-static-invariants.sh`) passes.

### 3. Task 1/2 database integration test writes `execution_records` without `profile_id`

- **Failure.** `tests/test_task1_database_integration.py::test_task2_routes_audit_and_per_workflow_preferences_extend_task1` raised `NotNullViolationError` on `execution_records.profile_id`.
- **Root cause.** The test predates SETTINGS-002 and inserted `analysis_runs` and `execution_records` rows with no owner; 034 made `execution_records.profile_id` mandatory and profile-bound.
- **Files changed.** `tests/test_task1_database_integration.py` only.
- **Why invariants hold.** `profile_id` stays `NOT NULL`. The test resolves the canonical owner through the R1 binding `user_profiles.default_profile_id -> profiles.id` for the single legacy user the fixture seeds, passes it to both inserts and asserts the persisted record carries that profile. That is the R1 authority contract, not a caller-supplied identifier.
- **Test proving closure.** The same test, executed against a disposable database in the full Python gate.

### 4. Task 4 temporal-selection contract disagrees with the implementation

- **Failure.** `tests/test_task4_frontend_runtime_contract.py::test_default_temporal_selection_is_stable_for_one_url_state` asserted the exact one-argument call `parseInsightSelection(new URLSearchParams(searchParamsKey))`.
- **Root cause.** The original contract (commit `2b826df`) only guaranteed that the default "now" instant is stable across renders for one URL state, to stop a seven-module refetch loop. Commit `faec751` implemented tracker item INS-001 ("server and first client render share one time snapshot"): the server component `frontend/app/dashboard/insights/page.tsx` takes `initialNow` once per request and the hook memoizes `parseInsightSelection(new URLSearchParams(searchParamsKey), new Date(initialNow))` on `[initialNow, searchParamsKey]`. That is a strict strengthening of the same invariant, but the test had pinned the call shape rather than the invariant.
- **Files changed.** `tests/test_task4_frontend_runtime_contract.py` only; no TypeScript changed. Audit confirmed `PersonalInsightsDashboard.tsx` only forwards the prop, the hook contains no bare `new Date()`, and the only clock reads in `TemporalControl.tsx` are inside user-initiated handlers that write to the URL.
- **Why invariants hold.** The rewritten test asserts both halves of the invariant: the hook takes `initialNow`, memoizes on `[initialNow, searchParamsKey]`, never reads the wall clock (`new Date()` with no argument is rejected by regex), and the page is a server component that passes `initialNow` once. Reintroducing a per-render clock, dropping the memo dependency, or converting the page to a client component fails it. The pre-`faec751` hook was verified to fail the new test.
- **Test proving closure.** `tests/test_task4_frontend_runtime_contract.py` (three tests) and `frontend/tests/insights-query.test.ts`.

### 5. Authenticated browser baseline blocked

- **Failure.** `scripts/r0-browser.sh` failed before Playwright started because `python database/migrate.py` on the managed stack hit regression 1.
- **Root cause.** Same as regression 1; no browser-side change was needed.
- **Files changed.** None beyond regression 1.
- **Test proving closure.** The full managed-stack browser gate (`R0_MANAGED_BROWSER_STACK=1`) recorded below.

### 6. `.pnpm-store/` committed

- **Failure.** 293 files under `.pnpm-store/v11/` were tracked (292 copies of `frontend/` sources under `projects/<hash>/` plus `index.db`) and the path was not ignored.
- **Root cause.** A pnpm store was created at the repository root and swept into commit `faec751`.
- **Files changed.** `.gitignore` (adds `.pnpm-store/`); the 293 tracked store files are removed from the index with `git rm --cached` and remain on disk.
- **Why nothing is lost.** Every one of the 292 project files was hashed against its `frontend/` counterpart before removal: 292 identical, 0 differing, 0 without a counterpart. `index.db` is pnpm store metadata.
- **Test proving closure.** `git ls-files .pnpm-store` is empty and `git check-ignore .pnpm-store/v11/index.db` matches the new rule.

## Gate results on the repaired head

Local execution used Python 3.11.16 in `.venv`, Node 24 with pnpm 11.9.0 through corepack, disposable `postgres:16-alpine` and `neo4j:5-community` containers on ports 15433/7688, and the CI sentinel environment from `.github/workflows/r0-baseline.yml` (`CI=true`, `R0_TEST_MODE=1`, `R0_MANAGED_BROWSER_STACK=1`, no provider credentials). The pnpm shim and a `setsid` pass-through shim were local-only tooling outside the repository. Two local deviations from the hosted layout, neither of which touches repository code: the Python suite used `NEO4J_URI=bolt://localhost:7475` because the Python client derives its HTTP endpoint by rewriting port 7687 and the disposable container sits on non-default ports, and the browser gate ran on port 3100 against its own `gdpr_browser` database because port 3000 was occupied by an unrelated local server. The hosted run below is the acceptance evidence.

| Gate | Command | Local result |
|---|---|---|
| Compose configuration | `scripts/r0-compose-validate.sh` | pass (exit 0) |
| Migration fixtures | `scripts/r0-migration-fixtures.sh` | pass, 16 passed (11 pre-existing + 5 new) |
| Complete Python suite | `scripts/r0-python-suite.sh` | pass, 562 passed, 4 skipped |
| Static/security invariants | `scripts/r0-static-invariants.sh` | pass, 70 passed |
| Frontend typecheck | `scripts/r0-frontend.sh typecheck` | pass (exit 0) |
| Frontend lint | `scripts/r0-frontend.sh lint` | pass, 0 errors, 76 pre-existing warnings |
| Frontend unit/component | `scripts/r0-frontend.sh unit` | pass, 216 passed, 1 skipped (Vitest) |
| Frontend production build | `scripts/r0-frontend.sh build` | pass (exit 0) |
| Authenticated browser | `scripts/r0-browser.sh` | pass, 8 passed, 4 skipped (R1 hermetic specs skip by design without `R1_HERMETIC_BROWSER`) |

**Hosted evidence:** repaired head `54dc370596aed0713d624b9d38205c86d57310e0` passed hosted run [34983024742](https://github.com/MattLeho/1GDPRAGENT/actions/runs/34983024742) (workflow `r0-baseline.yml`, job `r0-baseline`, conclusion `success`). The `r0-baseline-artefacts` artefact contains `test-results/r0-gates.json` recording exit status 0 for all nine gates in the table above, in CI order. This is the acceptance evidence; the local column is preflight only.

## Explicit boundaries

- `MODEL-008` and `OPS-001` remain open later-plan findings exactly as recorded in the R0 acceptance decision.
- No production deployment, external provider call, live connector or production data migration is evidenced here.
- The local development database had applied 034 and 035 before this repair; it gains 033a and 036 on its next `python database/migrate.py` without touching its owned settings row (proven by the post-034 fixture).
