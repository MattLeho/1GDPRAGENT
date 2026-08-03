# R0 authenticated browser baseline

`r0-authenticated-baseline.spec.ts` is the R0 regression baseline for the July 2026 authenticated-runtime audit. It deliberately asserts the desired signed-in contracts, so failures on the pre-remediation branch are evidence, not a reason to weaken the checks.

## Prerequisites

1. Start a clean, migrated application stack using the R0 migration fixture.
2. The checked-in global setup registers one disposable browser-test profile and seeds one request in the isolated browser database.
3. Install Playwright in the frontend test toolchain and install the Chromium browser. The CI runner uses `R0_MANAGED_BROWSER_STACK=1`, applies canonical migrations to its empty service database, starts a local Next.js process and tears it down afterward.
4. Optionally export `R0_BASE_URL`; it defaults to `http://127.0.0.1:3000`. Never provide external model-provider credentials to this suite.

Example PowerShell invocation once the test runner configuration exists:

```powershell
$env:R0_BASE_URL = 'http://127.0.0.1:3000'
$env:R0_MANAGED_BROWSER_STACK = '1' # CI only; requires CI=true and an empty disposable DATABASE_URL
Set-Location frontend
pnpm exec playwright test ../tests/browser/r0-authenticated-baseline.spec.ts
```

The suite skips authenticated checks when the required environment is absent. This avoids accidental runs against a developer profile while still making missing runtime evidence visible in the test report.

## Captured evidence

Every failed test stores a full-page `failure.png` and attaches `console-and-network.json`. The JSON records browser console output and every `/api/` response (method, URL and status). Playwright tracing/video/screenshot retention should be configured by CI as `trace: 'retain-on-failure'`, `video: 'retain-on-failure'`, and `screenshot: 'only-on-failure'`.

The cases cover missing/malformed/stale session handling, connector-selector population, authenticated graph 401, profile header refresh, the `requests.updated_at` console failure, request-chat Google fallback, 390px container overflow, and literal `System Online` health wording.
