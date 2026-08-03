# R0 CI and test infrastructure evidence

## Scope and status

This evidence records the CI contract added for R0. It does not claim a green
pipeline: the lead has now declared the frontend runner scripts, Vitest, and
Playwright, but the authenticated runtime still requires disposable CI
credentials and a running clean-migrated application instance.

## Entry points

| Gate | Reproducible command | Evidence / failure behaviour |
| --- | --- | --- |
| Compose syntax | `bash scripts/r0-compose-validate.sh` | Runs `docker compose config --quiet`; missing Docker fails explicitly. |
| Clean and historical migration fixtures | `bash scripts/r0-migration-fixtures.sh` | Requires `DATABASE_URL`; pytest fixture creates/drops uniquely named databases and runs migrations twice. |
| Python suite | `bash scripts/r0-python-suite.sh` | Requires pytest/pytest-asyncio and executes `tests`. |
| Architecture/security invariants | `bash scripts/r0-static-invariants.sh` | Executes static audit, Task 2 architecture, graph-projection policy, CI contract, and fail-closed R0 security invariants. |
| TypeScript, lint, build | `bash scripts/r0-frontend.sh {typecheck,lint,build}` | Requires installed frontend dependencies. |
| Frontend unit/components | `bash scripts/r0-frontend.sh unit` | Runs the lead-owned `pnpm run test` (Vitest); a missing runner fails explicitly. |
| Authenticated browser baseline | `bash scripts/r0-browser.sh` | Requires a declared Playwright dependency, `test:browser` package script, and `R0_BASE_URL`, `R0_USERNAME`, `R0_PASSWORD`, `R0_REQUEST_ID`; collects reports/screenshots through the workflow. |

`.github/workflows/r0-baseline.yml` installs dependencies from lockfiles, starts
PostgreSQL 16, invokes every gate through `r0-run-all.sh` even if earlier gates
fail, and uploads browser/JUnit/pytest artefacts on both success and failure.

## Lead-owned configuration required

The CI subtask was not authorised to modify `frontend/package.json` or either
lockfile. The lead has since declared and locked:

1. `@playwright/test` plus the required `test:browser` command; and
2. a frontend unit/component runner (recommended Vitest with a `test` script)
   and a `typecheck` package script.

The repository/CI maintainer must also provide the four `R0_*` GitHub secrets
for a disposable, clean-migrated authenticated runtime.  The CI job has no
authorisation to create production credentials or seed an application profile.

After those manifest changes, run `pnpm install --frozen-lockfile` in `frontend`, then rerun every R0
command above. The remaining blocker to a complete authenticated-browser CI
run is the disposable runtime and the four required secrets, not an implicit
skip.

`tests/integration/test_r0_architecture_invariants.py` deliberately exposes the
known unauthorised `discover-dpo` route, direct provider paths, and runtime
Neo4j schema DDL. Those are baseline facts assigned to R1/R3/R7, not failures
masked by R0.
