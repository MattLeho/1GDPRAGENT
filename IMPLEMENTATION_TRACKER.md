# Implementation Tracker

Updated: 2026-07-17

> **R0 baseline status: historical completion marks below are provisional.** See `docs/remediation/R0_BASELINE.md`, `docs/remediation/ledgers/R0_REQUIREMENT_LEDGER.md`, and `docs/remediation/issue-registry.json`. Current code, migrations, automated tests and authenticated runtime are separate evidence classes; no current plan is accepted solely on the historical marks in this tracker.

## Current Focus

- [x] Task 1: establish canonical checksum-protected migrations and one-shot startup migration service.
- [x] Task 1: implement AnalysisRun, ExportSnapshot, ContentBlob, SourceArtifact, EvidenceLocator, Assertion, and provenance joins.
- [x] Task 1: enforce immutable assertion semantics, verified model provenance, supersession, and versioned data artifacts.
- [x] Task 1: replace drifting graph labels with a documented shared ontology and stable UUID node IDs.
- [x] Task 1: route personal graph writes through the Python GraphProjectionService.
- [x] Task 1: demote inference and legacy N8N KG output to assertion candidates.
- [x] Task 1: add disposable PostgreSQL and live Neo4j integration tests.
- [x] Task 1: pass the line-by-line acceptance audit, type checking, linting, production build, and live Compose verification.
- [x] Task 1 follow-up: fix Neo4j driver-6 integer pagination, distinguish an empty connected graph, and remove fabricated graph-statistic fallbacks.
- [x] Task 2: add canonical TaskDefinition/EngineDefinition registries and persisted TaskRoute configuration.
- [x] Task 2: enforce strict-local, local-first, and controlled-cloud execution with per-invocation ExecutionRecord audit.
- [x] Task 2: add explicit deterministic, local ASR/OCR/Ollama, and remote generation adapters with health/capability/discovery behavior.
- [x] Task 2: replace Gemini audio transcription with local Parakeet/Whisper routing, FFmpeg normalization, timestamp provenance, and text-only semantic follow-up.
- [x] Task 2: replace the global workflow backend at runtime with canonical per-workflow definitions/preferences and migrate the legacy choice.
- [x] Task 2: reconcile N8N webhook configuration to one registry and remove N8N as a Next.js startup dependency.
- [x] Task 2: implement built-in encrypted SMTP/IMAP transport, response monitoring/classification, rotation, deletion, and legacy-secret re-entry.
- [x] Task 2: rebuild settings navigation around identity, connectors, task routes, workflows, retention, privacy/audit, and advanced configuration.
- [x] Task 2: document processing, workflow inventory/parity, and settings architecture.
- [x] Task 2: pass 38 Python tests, TypeScript, focused lint, production build, live migration, privacy-route probes, and healthy Compose verification.
- [x] Task 4: deliver `/dashboard/insights` with one point/period/compare selection shared by all modules.
- [x] Task 4: add immutable, versioned insight materialisations, aggregate buckets, evidence indexes, external-context events, temporal-correlation candidates, media-location candidates, and settings.
- [x] Task 4: implement evidence-backed overview, interest, search, AI-conversation, project/era, change, place, media, and contextual-correlation services and APIs.
- [x] Task 4: enforce exposure-versus-interest, occurrence-time, non-causal correlation, media-origin, location-evidence, and strict-local privacy safeguards.
- [x] Task 4: pass all 18 synthetic acceptance scenarios, 77 Task 4 tests, deterministic cold/warm materialisation checks, and zero-call default media privacy verification.
- [x] Task 4: verify authenticated module/empty-state rendering, point-in-time/period/compare URL selection, Quarter granularity, stable controls, and cohesive dark-mode temporal and activity-density surfaces.
- [x] Task 4: fix unstable default timestamps that caused repeated refreshes and protect the memoized URL selection with a frontend runtime contract test.
- [x] Task 4: verify the authenticated evidence-inspector interaction with the isolated local `task4-browser-smoke` subject while leaving the user's empty profile unmodified; retain database fixtures as authority for exact source and locator resolution absent from the narrow browser fixture.
- [x] Task 4: complete and accept the final line-by-line audit without beginning Task 5.

- [x] Review `Audit.md` and `fixes.md`.
- [x] Review original planning docs in `App_Context_and_Plan/`.
- [x] Install frontend GSAP package for animation work.
- [x] Make built-in workflows the default automation path.
- [x] Keep N8N available as an optional workflow backend.
- [ ] Restore knowledge graph ingestion, chat, and identity features.
- [x] Add multi-provider model selection with model search and pricing hints.
- [x] Add upload scan throttling/backoff to reduce provider rate-limit hits.
- [x] Add per-workflow model selection with Flash Lite extraction defaults.

## Audit Follow-Ups

- [ ] Reduce frontend lint warnings.
- [x] Rename `frontend/middleware.ts` to the newer Next.js proxy convention.
- [x] Add health checks for n8n and Celery.
- [x] Consolidate migrations into `database/migrations/` with history, checksums, advisory locking, and startup gating.
- [ ] Add API route tests for auth, uploads, chat, graph, and workflow settings.

Audit follow-up notes:

- Lint warning reduction started: removed unused imports/catch bindings and typed request detail chat/log state. Targeted lint on `RequestDetailSheet` now has one remaining React compiler advisory (`set-state-in-effect`).
- Proxy convention complete: `frontend/proxy.ts` now exports `proxy`; `frontend/middleware.ts` has been removed.
- Health checks complete: n8n uses `/healthz/readiness`; Celery uses `celery inspect ping` against the in-container worker hostname.
- Migration consolidation complete: `database/migrations/` and `database/migrate.py` are operational authority; legacy schema locations are clearly marked compatibility references and runtime DDL has been removed.
- API route test assessment: no frontend route test runner or `test` script is configured yet. Target coverage should include auth, upload/process/scan, graph/chat/nodes, and workflow settings routes.

## Workflow Backend

- [x] Identify current split between N8N routes and built-in agent routes.
- [x] Replace the legacy global backend with built-in, N8N, hybrid, or disabled preference per workflow.
- [x] Default new installs to built-in workflows.
- [x] Update request submission to use selected workflow backend.
- [x] Add workflow logs for both built-in and N8N executions.
- [x] Implement built-in email sending or clearly expose N8N as the email transport fallback.
- [x] Translate shipped core N8N agents into built-in handlers without duplicating Python intelligence services.
  - [x] Port SMTP/IMAP testing, transport, incremental inbox monitoring, response matching/classification, and parsing handoff.
  - [x] Register KG/identity/grounded extraction/hybrid retrieval against existing Task 1 intelligence and graph services.

## RLM Agent

- [x] Locate current RLM implementation in `frontend/lib/rlm-agent.ts`.
- [x] Stop hard-wiring RLM to Gemini only.
- [x] Route RLM through selected model provider and model.
- [x] Preserve tool-calling support where providers expose compatible APIs.
- [x] Add fallback behavior for providers without tool calling.

## Model Providers

- [x] Add OpenAI credential support.
- [x] Add Ollama local model discovery.
- [x] Add Google Gemini model discovery.
- [x] Add OpenRouter model discovery with pricing.
- [x] Add Hugging Face model discovery.
- [x] Add NVIDIA model discovery.
- [x] Add searchable model selector in settings.
- [x] Store preferred provider and model in app settings.
- [x] Store per-workflow model choices for default/RLM, drafting, extraction, graph, and policy.
- [x] Make extraction default to Flash Lite and graph/policy/drafting default to Flash instead of Pro.
- [x] Normalize provider aliases and credential environment fallbacks.
- [x] Add bounded model discovery timeouts and explicit fallback responses.
- [x] Keep selector state valid when provider model lists change.
- [x] Allow local-development credential saving without a manually configured encryption key.
- [ ] Replace static OpenAI/Google pricing hints with a versioned or live pricing source.
- [ ] Add clear/delete/rotate controls for stored provider credentials.
- [x] Expose explicit runtime provider adapters for task-routed generation; existing RLM tool-calling adapters remain available.

## Knowledge Graph

- [x] Locate graph API, graph UI, and Neo4j driver.
- [x] Fix graph chat to avoid unsafe string interpolation in Cypher.
- [x] Make graph chat use selected provider/model when Google is selected.
- [x] Add manual graph node upsert/delete/merge APIs.
- [x] Add graph search and node type filters.
- [x] Add double-click neighbor expansion.
- [x] Ensure identity saving reliably writes to Neo4j.
- [x] Connect file ingestion to graph ingestion.
- [x] Route graph chat and graph extraction through the graph model preference.
- [x] Add MAKGED validation before risky graph writes.
- [ ] Add GIVE-style inference nodes and dashboard alerts.

## UI And Frontend

- [x] Install `gsap` because no installable Codex GSAP/GASP skill exists in the current skill catalog.
- [x] Add GSAP-backed animation helpers where they improve state transitions.
- [x] Improve settings layout responsiveness for dense provider lists.
- [x] Add accessible loading, empty, and error states for model fetching.
- [x] Keep controls compact and operational rather than marketing-style.

## Original Idea Backlog

- [x] Dashboard: real data volume by company from `received_data`.
- [ ] Dashboard: real review queue read/unread handling. UI-local read state is implemented; DB-backed unread state still needs schema/API support.
- [x] New request wizard: account detail injection into `request_details`.
- [ ] Request detail page: replace remaining mock request data. Account detail badges, complete action, export link, and review metadata now use real data; reply/send still needs backend wiring.
- [ ] Scheduling: recurring DSAR cadence with date-range awareness. Needs recurrence storage, scheduler worker, and last-response date lookup.
- [ ] ONSIT: data broker crawler. Triage points to a Python/Scrapy or N8N crawler feeding request targets.
- [ ] ONSIT: cookie banner vendor extraction. Needs browser/headless extraction of IAB TCF vendor lists before request creation.
- [ ] ONSIT: breach and OSINT cross-reference. Needs external breach-provider credentials and retention policy.
- [ ] Hybrid RAG: Qdrant client and source chunk tracking. Needs Qdrant service, embedding provider choice, and chunk-to-graph provenance IDs.
- [ ] Shadow profile report: proactive risk briefings. Depends on graph inference/RAG provenance and scheduled risk jobs.
- [ ] NAS/home-lab deployment hardening. Needs Compose profile, Tailscale/reverse-proxy plan, backup/restore, and health checks.
