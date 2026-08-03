# R0 managed browser local attempt

**Date:** 2026-07-17  
**Disposition:** initial direct-Turbopack attempt invalidated; configured-Webpack rerun reached the graph handler.

## Controlled setup

- Created the exact disposable PostgreSQL database `r0_browser_final`, applied migrations 000--029, and dropped it immediately after the run.
- Started a local Next instance on port 3102 with `R0_TEST_MODE=1`, the no-provider adapter, deterministic connector/graph doubles, and disposable session/credential keys.
- Ran all eight Chromium specifications with `R0_EXECUTE_BROWSER=1`.

## Evidence

- Registration and the first canonical login returned 200.
- The missing-session connector call returned 401.
- The initial direct `next dev` invocation selected Turbopack and could not resolve the repository-root ontology. The configured command (`pnpm dev`, which uses Webpack) resolves it: unauthenticated graph calls returned 401 and authenticated R0 test-mode graph calls returned 200.
- The run produced `test-results/playwright-junit.xml` and retained per-test trace, video, screenshot, error-context, console, and network artifacts under `tests/browser/test-results/` (ignored from source control).

## Interpretation

This is genuine authenticated-runtime evidence. The ontology symptom was a noncanonical direct-server invocation, not a product defect. The matrix subsequently reached profile, database, chat, and UI coverage; existing product regressions still prevent R0 acceptance.
