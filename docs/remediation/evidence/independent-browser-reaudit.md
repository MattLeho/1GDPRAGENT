# Independent R0 browser re-audit (after repairs)

**Auditor:** independent browser verifier.  
**Date:** 2026-07-17.  
**Scope:** Read-only review of the browser global setup, R0 managed CI stack, Playwright specifications, relevant routes, and retained local artefacts. This report makes no code changes outside this file.

## Decision

**R0 browser-runtime evidence remains blocked / unproven.** The current files are a material improvement over the earlier unprovisioned suite: the CI job has a disposable PostgreSQL service, runs canonical migrations, starts a local Next development server, registers a timestamped profile, and prevents the browser setup from running with the three named external provider credentials. These facts are static evidence only. There is no successful run of this repaired configuration in the checked-out artefacts, and review finds a fixture mismatch that makes the request-chat contract a false pass.

## Material reviewed

- `.github/workflows/r0-baseline.yml`
- `scripts/r0-run-all.sh` and `scripts/r0-browser.sh`
- `frontend/playwright.config.ts`
- `tests/browser/r0-global-setup.ts` and `tests/browser/r0-authenticated-baseline.spec.ts`
- `frontend/app/api/connectors/[[...path]]/route.ts`, `frontend/app/api/graph/route.ts`, `frontend/proxy.ts`, and `frontend/lib/api-session.ts`
- `frontend/app/api/request-threads/[id]/chat/route.ts`, `frontend/app/api/settings/profile/route.ts`, and the relevant settings components
- `database/migrations/001_legacy_application_schema.sql` and retained `test-results/playwright-junit.xml`.

## Positive evidence

| Area | Evidence | Assessment |
| --- | --- | --- |
| CI-local database | GitHub Actions supplies a disposable PostgreSQL 16 service and `DATABASE_URL`; `r0-browser.sh` applies `database/migrate.py`. | Implemented; not executed in the available evidence. |
| Local UI stack | `r0-browser.sh` starts `pnpm dev`, polls `/login`, and uses `R0_MANAGED_BROWSER_STACK=1` only with `CI=true`. | Implemented; process cleanup is incomplete (below). |
| Auth fixture | Global setup registers a unique profile with the real registration endpoint, then logs in with the real login endpoint in each test. | Better than external credentials/storage-state injection, but requires successful execution evidence. |
| External credentials | Setup rejects `GOOGLE_API_KEY`, `OPENAI_API_KEY`, and `OPENROUTER_API_KEY`. | Partial safety control; it does not itself prevent all outbound traffic/provider mechanisms. |
| Failure artefacts | The spec captures a full-page screenshot and console/network JSON on unexpected failure; config retains trace/video/screenshot and emits JUnit. | Implemented, but not proven by a run of this revision. |
| Session cases | Missing and malformed cookie API calls, then cookie-cleared and invalid-token dashboard navigation, are all asserted. | Meaningful regression specification, subject to the proxy/API-authority caveat below. |

## Blocking findings

| ID | Severity | Evidence | Consequence / required repair |
| --- | ---:| --- | --- |
| `R0-BROWSER-REAUDIT-001` | P0 | `r0-global-setup.ts` inserts into `requests`; `app/api/request-threads/[id]/chat/route.ts` queries `access_requests` before invoking the agent. | The seeded request ID is not a chat request. The chat route returns 404, and `R0-MODEL-001` expressly accepts every status below 500. It never proves routing, no-Google behaviour, or chat safety. Seed the actual route's authoritative entity (or make the endpoint consistently use the intended entity), then require the deterministic expected response and observable selected-provider evidence. |
| `R0-BROWSER-REAUDIT-002` | P0 | The chat POST invokes `getRLMAgent().chat(...)`; the only controls are rejection of three environment keys and a response-text negative match. | This is not a hermetic provider test. Existing persisted credentials, other provider environment variables, tool calls, or a future adapter can still produce outbound/cost-bearing work. Add an explicit checked-in R0 test adapter/route-selection recorder enabled only in the managed disposable stack and failing closed for all network providers. Assert its recorded no-provider/no-Google outcome. |
| `R0-BROWSER-REAUDIT-003` | P1 | The CI starts only PostgreSQL and Next. `/api/connectors` proxies to `http://intelligence:8000` by default; `/api/graph` opens Neo4j. | The managed stack cannot prove a usable connector selector or successful graph endpoint: absent services produce a 503/500 independently of session behaviour. Either provision hermetic local substitutes/services or define route-level deterministic test doubles. The current graph assertion requires 200, but no Neo4j is available to make that a meaningful graph smoke test. |
| `R0-BROWSER-REAUDIT-004` | P1 | `R0-AUTH-003` checks only status 200 and absence of literal UI text; `R0-DB-001` observes page console/text; `R0-MODEL-001` accepts 400/404; connector assertion only requires a non-empty rendered option. | Several tests are not symptom-specific runtime proof. In particular, a server-render failure need not generate a browser console `updated_at` message, and an arbitrary static option can satisfy connector coverage. Assert expected API payloads/diagnostics, status classes and data source; for narrow UI, select an expected seeded definition and verify usable form state. |
| `R0-BROWSER-REAUDIT-005` | P1 | The profile test restores the username only after the header assertion; profile route reads/updates `LIMIT 1` without API session authority. | On its expected failure path, it skips restoration and contaminates later login attempts in a reused local database. Wrap restoration in `try/finally` or use a new test profile for the mutation. Also record that profile identity isolation/authority is presently not represented by this test. |
| `R0-BROWSER-REAUDIT-006` | P1 | `r0-browser.sh` kills only the `pnpm dev` parent PID. | Next/pnpm descendants can survive a failed or completed run, causing port contamination and non-reproducible local/CI retries. Start a dedicated process group and terminate/wait for the group, preserving its log before exit. |
| `R0-BROWSER-REAUDIT-007` | P1 | `proxy.ts` redirects dashboard navigation based on cookie presence; `requireApiSession` validates token on protected routes. | The stale-token test correctly expects the eventual dashboard redirect, but it does not capture the redirect chain/status nor establish consistent authority for all protected API paths. Retain/capture API response headers/status and explicitly test a route guarded by `requireApiSession` (the graph case is suitable once its service dependency is hermetic). |
| `R0-BROWSER-REAUDIT-008` | P2 | Current local `test-results/playwright-junit.xml` says 8 skipped, dated before this re-audit; no log/HTML report/manifest proves the repaired managed path ran. | The only retained result is not authenticated-runtime evidence. Add a post-run manifest (JUnit counts plus paths/hashes for log and Playwright failure artefacts) and retain a successful CI run URL/artifact. Configure an HTML report if it continues to be uploaded, or remove that nonexistent upload path. |

## Requested-symptom coverage after this re-audit

| Required symptom | Current status |
| --- | --- |
| Stale session | Partial regression specification; not executed and redirect/API evidence is incomplete. |
| Empty connector selector | Blocked by absent Intelligence service and weak option assertion. |
| Graph API 401 | Blocked by absent Neo4j; current test cannot distinguish graph availability from infrastructure failure. |
| Profile header stale after save | Partial; intended assertion exists but mutation cleanup is not failure-safe. |
| `requests.updated_at` | Unproven; page console inspection is not a server-query diagnostic. |
| Request chat defaults to Google | **Not exercised** because fixture seeds the wrong table and accepted 404 is a false pass; also unsafe without a hermetic adapter. |
| Narrow-container UI | Partial; document-width check and visible button do not prove selector/control bounding boxes and operability. |

## Execution constraint

This audit environment has no `node` executable on `PATH`, so it could not run `pnpm exec playwright ...`. That is an environment limitation, not a claim about the repository. The checked-in JUnit result independently confirms only an earlier all-skipped run, not this repaired managed browser stack.

## Acceptance condition for this workstream

Do not treat browser R0 as operational until all P0/P1 findings are repaired, the managed stack has no live dependency on external providers, and a fresh CI-local run provides authenticated pass/fail evidence and retained artefact manifest. Until then, the browser-related ledger items should remain **implemented but unintegrated**, **partial**, or **environment-dependent** rather than operational.
