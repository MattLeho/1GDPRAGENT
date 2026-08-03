# Task 2 Acceptance Audit

> **PROVISIONAL — superseded by R0 evidence pending revalidation (2026-07-17).** Historical evidence is retained below but does not prove current integrated or authenticated runtime behaviour.

Audited: 2026-07-10 against current code, migration 010, disposable PostgreSQL, production build output, and the live Compose stack.

## Requirement audit

| Requirement | Code evidence | Test/runtime evidence | Result |
|---|---|---|---|
| Canonical TaskDefinition and TaskRoute | `frontend/lib/execution/registry.ts`, `router.ts`, `task_routes` | registry tests; live registry HTTP 200 | Pass |
| Engine registry/adapters | deterministic, intelligence-service, Ollama and five explicit remote adapters | unsupported pairing HTTP 400; health endpoints | Pass |
| Local transcription separated from semantics | upload ASR route, Python Parakeet/Whisper adapters, `transcript_artifacts` | static acceptance test; Python compile | Pass |
| Privacy execution policy | `processing_settings` and pre-invocation policy gates | strict-local external invocation HTTP 403; deterministic local success | Pass |
| Per-workflow definitions/preferences | canonical 18-workflow registry and migration | independent N8N/built-in live modes; disposable DB test | Pass |
| Workflow inventory/parity | workflow registry plus inventory document | every core definition has a built-in handler test | Pass |
| Built-in email operation | TLS SMTP, IMAP test/search/fetch/checkpoint, response match/classification | architecture tests and production compilation | Pass |
| Secure email credentials | versioned AES-256-GCM connector credential store | browser/base64/secrets static tests; migration test | Pass |
| Settings information architecture | seven-section settings navigation and task/workflow/audit components | production build includes `/dashboard/settings` | Pass |
| Execution audit | `execution_records` linked to `AnalysisRun` and source IDs | disposable DB FK test; live blocked-external audit record | Pass |
| Documentation/ledger | README, three architecture documents, tracker, this audit | file audit | Pass |

## Required test cases

- Every TaskDefinition resolves to a capability-compatible default: registry validation and architecture test.
- Unsupported engine/task: rejected by route validator; live HTTP 400.
- Strict local blocks external: live HTTP 403 and a `blocked` ExecutionRecord.
- Local-first local success stops before external fallback: candidate loop returns on first success; architecture test.
- External fallback/audit: every candidate creates an ExecutionRecord before invocation; database and architecture tests.
- Non-Google selection does not call Google: provider must match the engine definition; draft, policy, graph, and vendor paths use the router.
- Speech does not call a general LLM: ASR capability is restricted to Parakeet/Whisper; upload test.
- Summary receives transcript text: upload route test.
- Every core workflow has built-in handler: 18-definition parity test.
- N8N-disabled built-in request chain: built-in drafting, SMTP sending, and IMAP monitor are independently registered and invoked by submission/monitor paths; Next.js no longer depends on N8N startup.
- Per-workflow mixed modes: disposable DB and live API test.
- Legacy global workflow setting: migration 010 initialises every per-workflow row safely.
- Legacy email base64: migration marks it `needs_reentry` and clears verification; it is never promoted to canonical ciphertext.
- Browser never receives connector secrets: public connector query/action excludes ciphertext/password.

## Exact verification

- `tsc --noEmit`: pass.
- Targeted Task 2 ESLint: 0 errors (final focused run; legacy unrelated settings warnings excluded).
- Next.js 16.2.10 production build: pass, 54 static pages generated; all Task 2 routes present.
- Full Python suite: **38 passed**, 2 non-failing warnings (Pydantic deprecation and read-only pytest cache).
- Disposable PostgreSQL Task 1 + Task 2 integration: **8 passed**; migration 010 applied after all Task 1 migrations.
- Live migration: `010_task_execution_router.sql` applied successfully.
- Live runtime: all Compose services healthy; task/workflow APIs HTTP 200; strict-local test HTTP 403; unsupported route HTTP 400; deterministic temporal route succeeded.
- Local tool health after image rebuild: Tesseract healthy; ExifTool healthy; FFmpeg installed.

## Environment-dependent items

The Parakeet and Whisper adapters are implemented and health-checked, but their optional model runtimes/weights are not bundled into the base image: current health reports both unavailable until the operator installs NeMo ASR or `intelligence/requirements-asr.txt`. This is reported in Settings and does not cause a hidden cloud fallback. No Task 2 acceptance item is represented as operational when its dependency is absent.

No Personal Insights or Task 3 implementation was started.
