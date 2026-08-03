# Independent R0 static-invariant re-audit

**Auditor:** independent reviewer (read-only except this evidence record)  
**Date:** 2026-07-17  
**Scope:** current worktree route inventory and the R0 static-invariant implementation. This is not the R0 acceptance decision.

## Verdict

**The static architecture/security gate is still not adequate evidence for R0.** Its present source will fail on real defects, which is useful truthful-baseline evidence, but it does not yet meet the plan's requirement for a reproducible, repository-wide, fail-closed authority/provider/Neo4j invariant suite with executable negative controls.

The local workstation cannot execute the Python suite: `python` resolves to the Windows application-alias executable, not an installed interpreter. The conclusions below are therefore source-inventory evidence, not a substitute for a CI test result.

## Current route inventory

The inventory finds 61 Next `route.ts` files. With the invariant's own sensitive-root definition (`settings`, `requests`, `request-threads`, `upload`, `execution`, `identities`, `graph`, `insights`, and `onsit`), 46 are sensitive. Only two contain an awaited `requireApiSession` call; **44 do not**. The present invariant's `test_sensitive_next_routes_have_an_explicit_authority_contract` should consequently fail. It only checks the presence of the token in source, rather than a parsed/callable awaited guard, so it is still vulnerable to comments, imports, dead code, and a non-awaited call.

Representative unguarded sensitive routes include:

- `frontend/app/api/graph/nodes/route.ts`, `graph/nodes/bulk/route.ts`, `graph/nodes/merge/route.ts`, and `graph/upsert-identity/route.ts`. These proxy privileged requests to Intelligence with only a content-type header.
- `frontend/app/api/insights/context-events/route.ts`, `insights/evidence/[id]/route.ts`, `insights/media-location-confirmations/route.ts`, and `insights/[module]/route.ts`.
- All reviewed ONSIT routes except none: `discover-dpo`, `export`, `bulk`, discovery/vendor routes, findings, status, and email routes are unguarded.
- Requests, request-thread, upload, identity, execution, and nearly all settings routes are also unguarded.

There are 12 FastAPI modules containing `APIRouter`. Four (`connectors`, `extract`, `query`, and `retention`) declare `Depends(require_internal_request)`; eight do not. One is the documented `health` route, leaving seven non-health routers currently lacking the required dependency: `bulk_ingestion`, `evidence`, `execution`, `ingest`, `insights`, `onsit`, and `validate`.

## Invariant coverage assessment

| Control | Current coverage | False-negative / remaining blocker |
| --- | --- | --- |
| Next authority | Repository walk over selected sensitive roots; only looks for the literal `requireApiSession`. | Does not prove an awaited/canonical invocation, does not enforce profile-scoped Intelligence headers on proxy routes, and lacks a complete documented public/exception inventory. Current source has 44 detected unguarded sensitive routes. |
| Python authority | Walks `intelligence/api` and finds `APIRouter` files lacking a `require_internal_request` substring. | Does not require `Depends(require_internal_request)`, distinguish comments/imports from router dependencies, or prove trusted profile scope. It will correctly flag the seven non-health routers above, but is not semantically robust. |
| Provider calls | Literal marker scan for `GoogleGenAI`, `genai.Client`, `GenerativeModel`, and `OpenAI(` outside two allowlisted files. | It catches the current `discover-dpo` and `intelligence/llm/gemini.py` direct calls, but misses import aliases, `new OpenAI`, Anthropic/Azure/OpenRouter and HTTP completion endpoints. `settings/ai-models` performs OpenAI/Google HTTP API calls but will not be classified. It also does not establish Task Router use or execution-record persistence for allowlisted adapters. |
| Neo4j mutations | Regex matches literal `session.run("... mutation ...")` only; `projection.py` is allowlisted and `frontend/lib/graph.ts` entirely exempt. | The actual canonical writer uses `self.neo4j.execute(...)`, including f-string/variable Cypher. A direct external `neo4j.execute("... SET ...")`, transaction `execute_write`, `execute_query`, variable Cypher, or a mutation in `frontend/lib/graph.ts` will evade the test. `frontend/app/api/onsit/export/route.ts` directly uses `session.run`, another path the scanner must classify accurately. |
| Runtime Neo4j DDL | Text scan across frontend/intelligence source. | It correctly identifies the current runtime `CREATE CONSTRAINT` and `CREATE INDEX` in `intelligence/graph/projection.py`, keeping the baseline red. The migration/bootstrap replacement boundary is not yet evidenced. |

## Negative-control feasibility

There is no extracted verifier module or fixture-tree test. The current tests operate directly over `ROOT`, so adding a forbidden temporary route/provider/writer would alter the repository under test and can conflict with parallel work. A meaningful negative control requires refactoring the scanners into parameterised functions accepting a source root, then testing positive and synthetic fixture trees. Until that exists, the CI-contract test's string checks are not behavioural proof that the static gates fail as intended.

## Precise R0 blockers

1. Repair or explicitly preserve the detected authority failures, then make the Next and Python checks semantic and fail closed (awaited guard/dependency plus reviewed exceptions).
2. Require `intelligenceAuthorityHeaders(authority.profileId, ...)` for every Intelligence proxy and verify this by route inventory.
3. Expand provider detection to SDK imports/constructors and completion endpoints, with a narrow documented allowlist and evidence of Task Router execution-record creation.
4. Detect all graph client invocation APIs and Cypher values; remove the broad `frontend/lib/graph.ts` exemption; constrain mutations to the projection implementation.
5. Add executable positive and synthetic negative-control tests for every invariant category and run them under CI with a real Python interpreter.
6. Preserve the current DDL failure as baseline evidence until runtime DDL is moved to a validated migration/bootstrap path.

R0 must not rely on a green static-invariant claim until these gates have been repaired, run, and independently re-audited.
