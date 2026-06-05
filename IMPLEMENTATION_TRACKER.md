# Implementation Tracker

Updated: 2026-06-05

## Current Focus

- [x] Review `Audit.md` and `fixes.md`.
- [x] Review original planning docs in `App_Context_and_Plan/`.
- [x] Install frontend GSAP package for animation work.
- [x] Make built-in workflows the default automation path.
- [x] Keep N8N available as an optional workflow backend.
- [ ] Restore knowledge graph ingestion, chat, and identity features.
- [x] Add multi-provider model selection with model search and pricing hints.

## Audit Follow-Ups

- [ ] Reduce frontend lint warnings.
- [x] Rename `frontend/middleware.ts` to the newer Next.js proxy convention.
- [x] Add health checks for n8n and Celery.
- [ ] Consolidate migrations into a single startup source of truth.
- [ ] Add API route tests for auth, uploads, chat, graph, and workflow settings.

Audit follow-up notes:

- Lint warning reduction started: removed unused imports/catch bindings and typed request detail chat/log state. Targeted lint on `RequestDetailSheet` now has one remaining React compiler advisory (`set-state-in-effect`).
- Proxy convention complete: `frontend/proxy.ts` now exports `proxy`; `frontend/middleware.ts` has been removed.
- Health checks complete: n8n uses `/healthz/readiness`; Celery uses `celery inspect ping` against the in-container worker hostname.
- Migration source-of-truth assessment: schema currently exists in `docker/init/01_schema.sql`, `02_DATABASE_SCHEMA.sql`, `migrations/*.sql`, `database/migrations/*.sql`, and route-level inline DDL. Consolidation needs an owner decision before moving startup DDL.
- API route test assessment: no frontend route test runner or `test` script is configured yet. Target coverage should include auth, upload/process/scan, graph/chat/nodes, and workflow settings routes.

## Workflow Backend

- [x] Identify current split between N8N routes and built-in agent routes.
- [x] Add setting for workflow backend: built-in, N8N, or hybrid.
- [x] Default new installs to built-in workflows.
- [x] Update request submission to use selected workflow backend.
- [x] Add workflow logs for both built-in and N8N executions.
- [x] Implement built-in email sending or clearly expose N8N as the email transport fallback.
- [ ] Translate remaining N8N agents into built-in services where appropriate.
  - [ ] Port inbox monitor/response parser after the SMTP/IMAP transport choice is settled.
  - [ ] Port KG/identity/hybrid RAG workflows through existing intelligence services once graph interfaces are ready.

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
- [x] Normalize provider aliases and credential environment fallbacks.
- [x] Add bounded model discovery timeouts and explicit fallback responses.
- [x] Keep selector state valid when provider model lists change.
- [ ] Replace static OpenAI/Google pricing hints with a versioned or live pricing source.
- [ ] Add clear/delete/rotate controls for stored provider credentials.
- [ ] Expose clean runtime provider adapters for non-Google generation and tool-calling.

## Knowledge Graph

- [x] Locate graph API, graph UI, and Neo4j driver.
- [x] Fix graph chat to avoid unsafe string interpolation in Cypher.
- [x] Make graph chat use selected provider/model when Google is selected.
- [x] Add manual graph node upsert/delete/merge APIs.
- [x] Add graph search and node type filters.
- [x] Add double-click neighbor expansion.
- [x] Ensure identity saving reliably writes to Neo4j.
- [x] Connect file ingestion to graph ingestion.
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
