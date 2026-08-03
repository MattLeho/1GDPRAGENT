# Independent R0 browser/runtime audit

**Auditor:** independent browser verifier (read-only review except this report)  
**Date:** 2026-07-17  
**Decision:** **BLOCK R0 acceptance.** The checked-in Playwright specification is a useful starting point, but it is not yet a reproducible authenticated-runtime gate and several cases can pass without proving their named contract.

## Material reviewed

- `tests/browser/r0-authenticated-baseline.spec.ts`
- `tests/browser/README.md`
- `frontend/playwright.config.ts`
- `scripts/r0-browser.sh`, `scripts/r0-run-all.sh`, and `scripts/r0-frontend.sh`
- `.github/workflows/r0-baseline.yml`
- Relevant current routes/components, including `proxy.ts`, `lib/api-session.ts`, the graph/connectors/chat routes, settings/profile, dashboard home, and `DashboardLayout.tsx`.

## Execution evidence

1. The local test listing could not start because `node` is not on this execution environment's PATH (`pnpm exec playwright test -c playwright.config.ts --list` reports `node is not recognized`). This is an **environment-dependent** observation, not a repository failure claim.
2. The browser dependency and config are checked in, and the configuration resolves `testDir` to `../tests/browser`, has a Chromium project, and retains trace/video/screenshot on failure.
3. There is no checked-in browser profile/request fixture or stack-starting command. Repository search found only environment variables and README prose for `R0_USERNAME`, `R0_PASSWORD`, and `R0_REQUEST_ID`; it found no browser seed/provisioning implementation.

## Blocking findings

| ID | Severity | Evidence | Finding / consequence |
|---|---:|---|---|
| `R0-BROWSER-AUDIT-001` | P0 | Workflow lines 30-37 and 64-79; `scripts/r0-browser.sh` lines 8-13 | CI starts only Postgres. It neither migrates/starts Next.js, Intelligence, Neo4j, nor creates the disposable browser user and request. `R0_BASE_URL`, credentials, and request ID are unreproducible repository/external secrets. On normal PRs missing secrets make the browser gate exit 2; populated external secrets still do not demonstrate the tested commit's clean migrated stack. This does not meet the required reproducible authenticated browser gate. |
| `R0-BROWSER-AUDIT-002` | P0 | Browser spec lines 96-105; `UserProfileSection.tsx` updates username; every later test runs `beforeEach` login with unchanged `R0_USERNAME` | The profile test permanently changes the sole login username and has no cleanup. Later tests will attempt login with the now-invalid original username, producing cascading failures. This makes ordered results non-independent and destroys baseline evidence. |
| `R0-BROWSER-AUDIT-003` | P0 | Browser spec lines 117-125; `app/api/request-threads/[id]/chat/route.ts` lines 34-105 | The chat probe invokes a real agent, writes two messages on success, and can invoke external providers/cost-bearing tools. It has no disposable-record assertion, cleanup, dry-run adapter, network block, or explicit consent-safe test mode. It is unsafe for a reusable authenticated test account. |
| `R0-BROWSER-AUDIT-004` | P1 | Browser spec lines 89-94, 107-115, 117-125 | Three named failures are under-specified: graph only rejects 401 (404/500/503 pass); the DB check only watches browser console while `dashboard/home` runs its data queries server-side (a server 500/error page can leave the console array empty); chat treats 400/404/any non-5xx response as success. These are false-pass paths, not proofs of graph availability, `requests.updated_at` compatibility, or provider routing. |
| `R0-BROWSER-AUDIT-005` | P1 | Browser spec lines 128-135 | The narrow-layout check detects document-level overflow only. It does not check the connector selector/options or Add source button bounding boxes against the viewport, scroll the relevant container, or require the button to be enabled. A clipped descendant / disabled connector path can pass. |
| `R0-BROWSER-AUDIT-006` | P1 | Browser spec lines 60-78; `frontend/proxy.ts` lines 8-25; `lib/api-session.ts` | This is the strongest current case and should be retained, but it combines API authority and UI redirect without recording the responses/redirect chain. The proxy accepts any present token for dashboard navigation, while route authority validates it. Failure evidence is captured, but successful execution would not prove that all protected UI/API paths have a consistent invalid-session response. At minimum record response status/location and test a route that passes through the API authorization guard. |
| `R0-BROWSER-AUDIT-007` | P1 | Browser spec lines 81-87 | The connector case establishes only that some option is rendered. It does not prove definitions came from the authenticated connector API, that the selector is populated for the seeded profile, or that a selected definition is usable. It can pass against stale/mock/static data. Capture `/api/connectors` response and assert expected seeded definition(s), then select one and assert the form/action state. |
| `R0-BROWSER-AUDIT-008` | P1 | Workflow lines 68-76; config lines 4-15; artifact upload lines 81-91 | Playwright browser installation is `continue-on-error`, and the configured reporter is list + JUnit only. The upload names `tests/browser/playwright-report/`, but no HTML reporter produces that directory. Failure attachments/traces should be beneath `tests/browser/test-results`, but there is no verified run/artifact manifest proving they were retained. Browser-install failure is ultimately visible because the gate later fails; it is nevertheless not a reliable evidence-producing setup. |

## Coverage assessment by requested runtime symptom

| Symptom | Current test | Assessment |
|---|---|---|
| Missing/malformed/stale session | `R0-AUTH-001` | Meaningful regression intent, but needs independent API/UI response evidence and reproducible fixtures. |
| Empty connector selector | `R0-AUTH-002` | Partial; nonzero option count is insufficient. |
| Graph API 401 | `R0-AUTH-003` | Partial/false-pass-prone; non-401 failure passes. |
| Profile change does not update header | `R0-PROFILE-001` | Intended assertion is appropriate, but it corrupts the login fixture for subsequent tests. |
| Missing `requests.updated_at` | `R0-DB-001` | Not proven; a server-side error is not reliably a browser console event. |
| Request chat defaults to Google | `R0-MODEL-001` | Unsafe and false-pass-prone; a 404/400 is accepted. |
| Narrow-container breakage | `R0-UI-001` | Partial; document overflow alone misses clipped/inoperable controls. |
| Literal always-online health | `R0-OPS-001` | It directly detects the current literal label, but is a UI wording check rather than a real health-state test. |

## Evidence-retention assessment

`capture()` correctly writes a full-page screenshot and attaches console/network JSON when an unexpected test result occurs. Playwright-level trace/video/screenshot retention is configured. However, this has not been demonstrated by an executed run; there is no HTML reporter despite the CI upload path, no clean fixture artifact, and the current workflow cannot reach a checked-out local app. Therefore artifact retention is **implemented but unproven**, not operational evidence.

## Required repairs before an R0 pass claim

1. Build a CI-local, clean migrated stack and create a per-run disposable profile/request through checked-in fixture code; do not use externally hosted authenticated secrets as the evidence target.
2. Isolate mutation: create/delete a profile per test or restore its original name in `finally`; use a disposable request and transaction/cleanup for chat.
3. Replace loose negative assertions with endpoint-specific expected status/body contracts. For the DB case, inspect the server/API response or a deterministic diagnostic endpoint rather than only page console output.
4. Use a deterministic request-chat adapter/recording fake that proves route choice and prohibits real provider calls; assert no Google fallback through observable routing evidence, not just response text.
5. Make the responsive assertion verify element bounding boxes, operability, and expected connector API data at 390px.
6. Make Chromium installation blocking, produce an HTML report (or stop uploading an uncreated path), and add a post-run artifact manifest/check that proves screenshots, trace, video, console/network JSON, and JUnit were generated for an intentionally exercised failure/smoke result.

Until these repairs and a successful CI-local authenticated run are evidenced, all browser-runtime claims remain **UNPROVEN / ENVIRONMENT_DEPENDENT**, and R0 must not be marked complete.
