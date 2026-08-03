# Independent final R0 browser-harness re-audit

**Auditor:** independent browser verifier (read-only except this report)  
**Date:** 2026-07-17  
**Decision:** **The earlier browser-harness P0 false-pass defects are repaired in the checked-in managed CI path, but browser runtime acceptance remains blocked by a real graph-route compilation failure.**

## Evidence reviewed

- `tests/browser/r0-global-setup.ts` and `r0-authenticated-baseline.spec.ts`
- `frontend/app/api/connectors/[[...path]]/route.ts`, `app/api/graph/route.ts`, and `lib/rlm-agent.ts`
- `scripts/r0-browser.sh`, `frontend/playwright.config.ts`, and `.github/workflows/r0-baseline.yml`
- `database/migrations/001_legacy_application_schema.sql`
- `test-results/playwright-junit.xml`, `test-results/r0-next-final.err.log`, and the retained Playwright `trace.zip`, `video.webm`, screenshots, and HTML report tree.

## P0 false-pass re-audit

| Earlier risk | Current evidence | Finding |
| --- | --- | --- |
| Chat fixture was thought to seed the wrong entity and accepted a 404. | Setup inserts a disposable `requests` row. Canonical migration 001 defines `access_requests` as a compatibility view over `requests`, which is the chat route's lookup surface. `R0-MODEL-001` now requires status 200 and the exact deterministic adapter response. | **Fixed.** The previous 404 acceptance path is removed; a 404/400/500 cannot satisfy this case. |
| Chat could invoke a real/cost-bearing provider. | Workflow sets `R0_TEST_MODE=1`; `getRLMAgent()` returns `R0NoProviderAgent`, which returns a fixed no-tools response and has no provider/tool call. The global setup additionally rejects the named Google/OpenAI/OpenRouter credentials. | **Fixed for the checked-in managed CI path.** The exact response assertion proves that the test-mode adapter, not a text-matched live failure, answered the route. |
| Connector/graph tests needed unavailable Intelligence/Neo4j services. | In `R0_TEST_MODE=1`, authenticated connector GET returns the named `R0 scoped files` fixture and authenticated graph GET returns exact empty graph data with `dbStatus: 'r0-test-double'`; the specs assert those values. | **Fixed as deterministic harness infrastructure.** These are intentionally adapter tests, not a claim that live Intelligence/Neo4j integration works. |
| Profile mutation could poison later tests after a failure. | `R0-PROFILE-001` restores the disposable username in `finally` and asserts restoration succeeds. | **Fixed** for the username mutation path. |
| Responsive/authority checks had weak evidence. | Stale API cookie explicitly expects 401; connector asserts a named fixture option; responsive check asserts document width plus `Add source` bounding-box right edge. | **Substantially repaired.** The narrow check still does not prove the selector trigger/options are themselves in-bounds and operable, so it remains partial rather than complete UI proof. |

## Managed-run evidence

A fresh managed local attempt did invoke the browser matrix: `playwright-junit.xml` records **8 tests, 8 failures, 0 skipped**, and each result references retained screenshot/video/trace material. Thus it supersedes the earlier all-skipped result as evidence that global setup, process startup, and test invocation occurred.

The matrix is not a successful authenticated runtime pass. The first authority case received **500** rather than its expected 401 for unauthenticated `/api/graph`; `r0-next-final.err.log` records the direct cause:

`frontend/lib/graph/ontology.ts` imports `../../../ontology/graph-ontology.json`, which resolves outside the `frontend` root and cannot be compiled by the Next development server. The import is loaded before the route can reach its `R0_TEST_MODE` return. This is a genuine application/runtime topology defect (`GRAPH-006`), not a browser assertion weakness. Subsequent tests then fail at their login precondition, so their failure artifacts do not demonstrate their individual intended contracts.

The same log also exposes the pre-existing `requests.updated_at` database error and a Next development-origin warning. They are baseline evidence, but the ontology compilation blocker prevents a clean test-by-test interpretation of the current matrix.

## Remaining blockers and qualifications

| Severity | Blocker / qualification | Required evidence or repair |
| --- | --- | --- |
| P0 acceptance blocker | Graph route must compile before its authentication guard/test-mode double can execute. | Repair the graph ontology resolution within the Next project boundary (or otherwise make it a correctly bundled checked-in dependency), then rerun the complete managed matrix. |
| P1 | `scripts/r0-browser.sh` does not itself require `R0_TEST_MODE=1`; the workflow supplies it. A manually constructed `CI=true` run could omit it and lose the deterministic no-provider guarantee. | Fail closed in the managed-stack script/setup unless `R0_TEST_MODE=1`; preferably also refuse test mode outside CI/development. |
| P1 | Test-mode doubles validate route authority and UI wiring but do not validate live Graph/Intelligence services. | Keep their status as R0 harness evidence only; live-service functionality remains an R1--R8/runtime concern and must not be classified operational from these tests. |
| P2 | Responsive evidence checks the Add-source button but not the combobox/options' bounding boxes or enabled/interactive state. | Add selector-trigger/options bounding-box and enabled-state assertions after the graph compile blocker is cleared. |
| P2 | The profile API is still globally `LIMIT 1` and not session-authorized. | This does not invalidate the fixture-cleanup proof, but it is a product authority defect and must remain in the issue registry/ledger, not be inferred fixed from the browser test. |

## Conclusion

The deterministic connector, graph, and no-provider adapters resolve the previously identified P0 **harness** false passes in the actual GitHub Actions configuration. The managed execution has now produced non-skipped artifacts, but all eight tests fail because the graph module cannot compile, and later failures cascade from that condition. Browser acceptance is therefore **blocked, not unproven due to skipped setup**. Do not mark R0 browser requirements operational until the ontology import defect is repaired and a new managed run completes with independently interpretable results.
