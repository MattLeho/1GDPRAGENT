# Independent final re-audit: parameterised static invariants

**Auditor:** independent reviewer (did not implement the verifier)  
**Date:** 2026-07-17  
**Scope:** `tests/integration/test_r0_architecture_invariants.py` and its synthetic fixture tree only, plus read-only comparison with current production sources. This is not a claim that the product security defects are fixed.

## Verdict

**Improved but not yet adequate as R0's complete static-security gate.** The suite is now parameterised by source root and has a real synthetic negative-control assertion. That is a material repair: it demonstrates that the four scanners can reject the particular fixture cases, independently of the current red production baseline.

However, the negative controls are too narrow and the scanners still have material, demonstrable false negatives for the authority, provider, and Neo4j-writer policies. It would be inaccurate to call the R0 static-gate infrastructure fully adequate merely because the current product findings make the production-root tests red.

The local workstation still has no usable `python` interpreter (the `python` command is the Windows Store application alias), so this review is source evidence and does not replace an executed pytest result.

## What is now proven

- `next_authority_offenders`, `python_authority_offenders`, `provider_offenders`, `neo4j_mutation_offenders`, and `runtime_ddl_offenders` accept a root parameter rather than being hardwired to the repository.
- `test_verifiers_reject_synthetic_negative_controls` uses a separate fixture tree and expects a forbidden Next route, unprotected Python router, direct OpenAI client, direct `session.run('CREATE INDEX ...')`, and runtime DDL to be reported.
- The expected-red production tests are separate from that fixture assertion. Therefore a production failure does not by itself prove, or mask, the synthetic control result.
- The current product baseline is **not fixed** by this infrastructure work: the production scan continues to identify unguarded routes/routers, direct provider usage, and runtime DDL. No product-security remediation is claimed here.

## Remaining verifier false negatives

| Policy | Remaining gap | Why the present synthetic control does not prove the policy |
| --- | --- | --- |
| Next authority | The scanner considers only nine path segments sensitive and has no complete reviewed route classification/exception manifest. `gdpr-agent`, `policy`, `n8n`, and `workflows` routes are outside the policy even though their sensitivity is not demonstrated as public. It only matches an awaited token, not an imported canonical guard bound to the request/session outcome. | The fixture only proves that one unguarded `graph` route is caught; it does not prove an excluded route, an authority-looking local function, or a proxy without profile authority headers is rejected. |
| Intelligence proxy scope | No verifier requires `intelligenceAuthorityHeaders(authority.profileId, ...)` after a Next authority guard. | No fixture represents a guarded proxy that omits internal authority/profile headers. |
| Python authority | It requires the dependency text only in a module containing `APIRouter`; it does not ensure the dependency is actually applied to the router/endpoints, that imported `Depends` is FastAPI's, or that `require_profile_id` scopes requests. | The fixture only omits the text. A dead import or unused dependency would pass. |
| Provider policy | The marker list is broader, including common OpenAI/Anthropic and endpoint strings, but cannot exhaust provider SDK aliases, dynamic imports, generic `fetch`/HTTP clients, Azure endpoints, or a renamed provider wrapper. It also does not prove canonical Task Router use or execution-record persistence inside the allowlisted adapters. | The fixture covers a literal `OpenAI` constructor and not alternate SDK/HTTP or execution-record bypasses. |
| Neo4j mutation policy | The regex is restricted to literal quoted Cypher passed as `session.run`, `neo4j.execute`, or two named execute methods. It does not detect variables/f-strings built before the call, `tx.run`, arbitrary graph-client aliases, `execute_read`/driver transactions, or a mutation inside the broad projection-file allowlist. | The fixture has one literal `session.run('CREATE INDEX ...')`; it does not prove detection of the actual abstraction style (`self.neo4j.execute(cypher, ...)`) when used outside the projection service. |

## Required completion evidence

Before the static gate can be called adequate for R0, it needs:

1. A reviewed machine-readable inventory for **all** Next routes and FastAPI routers, including explicit public/exempt reasons, and checks for both canonical session authority and proxy profile headers.
2. Semantic/structural tests that distinguish an active guard/dependency from a mere import, comment, or dead code.
3. Provider fixtures for aliased SDK imports and completion HTTP endpoints, plus an assertion that approved generation paths reach the Task Router and record execution.
4. Neo4j fixtures for variable Cypher, f-string/transaction/alias calls, and a writer outside projection using the same abstraction as the projection service.
5. Executed local or CI pytest evidence showing all fixture controls pass while the intended current product findings remain red and explicitly recorded.

Until then, classify the parameterised suite as **partial R0 audit infrastructure**: a meaningful improvement over the former root-only strings, but not a complete acceptance gate.
