# R0 static architecture and security scan

Audited commit: `67e50b85daa923366d3bec80db6582edcc3ba134` on 17 July 2026. This is a source-only baseline; it does not set final issue severity or acceptance status.

## Results

The detailed machine-readable report is `subagent-static-security-scan.json`. It records nine candidate findings and candidate CI invariants.

| Finding | Static evidence | Suggested owner |
| --- | --- | --- |
| Unauthenticated Next routes | 61 route files were inventoried; only five import/call `requireApiSession`, while settings, request, upload and graph mutation routes do not. | R1 |
| Unguarded Python routers | Only connectors, extract, query and retention declare `require_internal_request`; evidence, execution, ingestion, insights and ONSIT routers do not. | R1 |
| Unauthorised internal proxies | Graph node and insight proxies forward to Python without browser or internal authority headers. | R1 |
| Active legacy model preferences | `frontend/lib/model-preferences.ts` reads/writes `model_preferences`, with Google defaults for multiple purposes. | R3 |
| Provider paths outside task routing | `discover-dpo` directly builds `GoogleGenAI`; Python Gemini paths are not visibly routed/recorded. | R3 |
| Graph mutation/DDL concerns | Evidence mutations are unguarded; `GraphProjectionService.ensure_schema()` executes Neo4j DDL at runtime. | R1/R7 |
| First-profile lookups | Profile settings, password, insights and connector settings use `LIMIT 1` instead of authority scope. | R1 |
| Candidate unscoped personal-data paths | Request, upload, identity-document and thread routes have no authority guard. | R1/R2 |
| Health and secrets | The shell renders literal `System Online`; AES-GCM, AES-CBC and XOR/base64 secret schemes coexist. | R5/R7 and R3/R7 |

## Required R0 invariants

- Require `requireApiSession` for every non-public Next API route and `require_internal_request` for every non-health Python router.
- Require the trusted profile identifier in every personal-data route and intelligence-service forward.
- Allow provider generation only via the Task Router; make exceptions explicit and test execution-record creation.
- Prohibit runtime Cypher DDL and direct Neo4j writers outside the projection service.
- Prohibit `LIMIT 1` profile lookup, literal health state, CBC/XOR credential persistence and legacy `model_preferences` runtime reads.

The lead agent should incorporate these as stable registry entries only after cross-checking runtime and migration evidence.
