# Independent R0 security-invariant audit

**Auditor:** independent security-invariant reviewer (did not implement the R0 gates)  
**Date:** 2026-07-17  
**Scope:** read-only review of the R0 static-invariant tests, runners, workflow, registry, and current source. This is not a final R0 acceptance decision.

## Verdict

**Not sufficient for R0 definition of done.** The gate reliably fails for two currently visible conditions (the direct `GoogleGenAI` use and the runtime Neo4j DDL), but its authority and direct-writer controls are representative/string checks rather than repository-wide invariants. It can therefore pass while protected routes or Neo4j mutation paths remain unguarded.

The R0 plan expressly requires CI to detect a sensitive route without an authority guard, direct provider calls outside approved adapters, and a Neo4j writer outside the projection service. Only the second is substantially covered; the other two have material false negatives.

## Evidence inspected

- `tests/integration/test_r0_architecture_invariants.py`
- `tests/integration/test_r0_ci_contract.py`
- `scripts/r0-static-invariants.sh`, `scripts/r0-run-all.sh`, and the other R0 runners
- `.github/workflows/r0-baseline.yml`
- `docs/remediation/issue-registry.json`
- `docs/remediation/evidence/subagent-static-security-scan.{md,json}`
- Current `frontend/` and `intelligence/` sources, especially the graph, proxy, provider, and authority paths.

An attempt to execute the Python invariant suite locally could not start because this workstation has no `python` executable on `PATH` (Windows application-alias error). This is an environment limitation, not a substitute for the source conclusions below.

## Findings requiring repair

| ID | Severity | Finding | Evidence and impact | Required R0 infrastructure repair |
| --- | --- | --- | --- | --- |
| R0-INV-001 | high | Authority invariant checks only one route. | `test_sensitive_dpo_discovery_route_has_canonical_api_authority_guard` checks only `onsit/discover-dpo`. Current unguarded sensitive routes include `frontend/app/api/graph/upsert-identity/route.ts`, `graph/nodes/route.ts`, `graph/nodes/bulk/route.ts`, `graph/nodes/merge/route.ts`, `onsit/bulk/route.ts`, and `insights/[module]/route.ts`; several proxy to intelligence with only `content-type`. The test passes if the representative route is guarded while these remain exposed. | Implement a complete Next route inventory with an explicit, reviewed public/auth allowlist. Require both an awaited `requireApiSession` and `intelligenceAuthorityHeaders(authority.profileId, ...)` on intelligence proxies. Add a negative-control fixture/test proving a newly unguarded sensitive route fails the verifier. |
| R0-INV-002 | high | No executable Python-router authority invariant. | The static-scan evidence inventories unguarded `intelligence/api/evidence.py`, `execution.py`, `ingest.py`, `insights.py`, etc. `test_r0_architecture_invariants.py` has no inspection of Python router dependencies or trusted profile scope. | Add a fail-closed FastAPI router inventory: each non-health router must use `Depends(require_internal_request)` (or a documented exemption), and frontend-to-intelligence proxies must send authority headers. Include an explicit test fixture/negative control. |
| R0-INV-003 | high | Neo4j mutation detection misses the repository's actual writer API and bypass styles. | The regex only matches literal `session.run("... CREATE/MERGE/SET/DELETE/REMOVE/DROP ...")`. It does not inspect `self.neo4j.execute(...)`, `.execute_write`, `.execute_query`, transaction variables, or Cypher held in a variable/f-string. `GraphProjectionService` itself uses `self.neo4j.execute`; another writer using the same API outside `projection.py` would not be detected. `frontend/lib/graph.ts` is entirely exempt, so a mutation added there would be invisible. | Scan all runtime graph-client invocation APIs and literals/variables passed to them, with no broad `frontend/lib/graph.ts` exemption. Constrain all mutating Cypher to the named projection implementation; add a synthetic negative-control source or mutation-test assertion that an external `neo4j.execute("... SET ...")` is rejected. |
| R0-INV-004 | high | Provider invariant is too narrow and does not prove routing or execution recording. | It finds the present `GoogleGenAI` and `genai.Client` usage, so it will flag `discover-dpo` and `intelligence/llm/gemini.py`. But it misses common provider surfaces (`OpenAI` imports/clients other than `OpenAI(`, Anthropic, Azure/OpenRouter HTTP completion calls, dynamic imports/aliases), and it allows `frontend/lib/rlm/provider-adapters.ts` without asserting an execution record. The plan requires every model call to use the Task Router and create one. | Define an exhaustive provider-SDK/import and completion-URL policy with a narrow adapter allowlist. For allowed adapters, add tests showing every invocation receives canonical router context and persists an execution record. Keep discovery-only calls in a separately documented, non-generation allowlist if intended. |
| R0-INV-005 | medium | The DDL test detects current runtime DDL but leaves the baseline CI permanently red and has no migration/bootstrap boundary. | `test_neo4j_schema_ddl_is_not_executed_at_runtime` correctly finds `intelligence/graph/projection.py:29-30`, including the supposedly canonical writer. It has no approved bootstrap/migration mechanism to validate instead. R0 may truthfully report a failed baseline, but cannot describe the gate as a passing reproducible acceptance pipeline until later remediation moves DDL. | Retain the failing regression evidence and registry entry, but document the expected baseline failure explicitly. When remediated, validate the replacement migration/bootstrap path separately and require absence of DDL from all application runtime directories. |
| R0-INV-006 | medium | CI browser job is not self-contained and its browser installation failure is ignored. | `.github/workflows/r0-baseline.yml` marks Playwright Chromium installation `continue-on-error: true`; later `r0-browser.sh` fails closed, so the job ultimately fails but produces no browser evidence if the install fails. It also relies on four externally seeded secrets and does not start a frontend/runtime fixture. | Remove `continue-on-error` for browser installation. Either provision a disposable authenticated app/profile/request in CI or explicitly classify this job as an environment-dependent authenticated gate, with a separately runnable scheduled/protected-environment workflow that uploads actual browser artifacts. |
| R0-INV-007 | medium | CI contract tests prove string presence, not gate behaviour. | `test_r0_ci_contract.py` only searches script/workflow text. It does not execute commands or inject a forbidden route/provider/writer. It cannot establish that runners, shell dependencies, or matching rules work. | Keep the structural contract tests, but add verifier unit tests with positive and negative fixture trees and run those independently of the full repository baseline. |

## What the current gate does detect

- Runtime Neo4j `CREATE CONSTRAINT` and `CREATE INDEX` textual DDL in `intelligence/graph/projection.py`; this should make the static invariant fail at the current source state.
- Direct `GoogleGenAI` in `frontend/app/api/onsit/discover-dpo/route.ts` and `genai.Client` in `intelligence/llm/gemini.py`, because neither is in the two-file allowlist.
- The chosen `discover-dpo` route having an awaited `requireApiSession` call.

These are useful baseline signals, but they do not support an assertion that CI detects all three required categories.

## Registry assessment

The registry is valid JSON and has stable IDs, severity, root cause, affected paths and plan assignments. It already records broad authority (`AUTH-003`), provider (`MODEL-001`/`MODEL-002`), and runtime DDL (`R0-STATIC-NEO4J-DDL`) concerns. It should additionally contain stable R0 infrastructure findings for the verifier gaps above, or map them explicitly to existing QA entries, so a future green run cannot be misread as proof of controls it never tested.

## Acceptance implication

Do not mark R0 complete or the static-invariant definition-of-done item evidenced until R0-INV-001 through R0-INV-004 are repaired and exercised with negative controls. R0-INV-005 and R0-INV-006 must at minimum be explicitly evidenced/classified as current baseline failures or environment-dependent gates rather than represented as a successful CI/browser run.
