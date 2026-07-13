---
title: Task 5 Predecessor Audit Ledger
date: 2026-07-13
tags:
  - gdpr-agent
  - task-5
  - predecessor-audit
status: complete
---

# Task 5 Predecessor Audit Ledger

The Phase 0 gate is complete. Every blocking remediation below was reviewed and the consolidated predecessor regression suite passed. Task 6 has not been inspected or started. The user explicitly waived the remaining authenticated Task 4 browser smoke; this ledger does not claim that smoke was run.

## Verification baseline

| Check | Actual result | Status |
|---|---|---|
| Task 4 focused non-database suite | 64 passed; 11 setup errors caused only by missing `DATABASE_URL` | pass after environment correction |
| Selected Task 1/3/4 database-backed suite | 45 passed; 3 Task 1 graph tests initially failed because the host process inherited Docker-only hostname `neo4j` | environment issue, not assertion failure |
| Task 1 graph rerun with host Neo4j endpoint | 3 passed | pass |
| PostgreSQL and Neo4j | Docker services healthy; migrations 000 through 020 applied by database fixtures | pass |
| Task 4 authenticated browser smoke | Not run at user direction | waived/pending; not treated as a Task 5 blocker |
| Consolidated post-remediation predecessor suite | 150 passed, 1 optional skip, 1 existing Pydantic deprecation warning | pass |

## Canonical evidence and ingestion dependencies

| Requirement | Expected implementation | Actual implementation | Status | Tests | Remediation |
|---|---|---|---|---|---|
| SourceArtifact and AnalysisRun | Versioned run/snapshot plus immutable content blob and distinct source occurrence | `intelligence/evidence/ledger.py`; canonical bulk caller in `intelligence/ingestion/bulk.py` | pass | Task 1 DB and Task 3 bulk tests | none |
| Exact EvidenceLocator | Typed mechanically resolvable locator with hash/verification state | `intelligence/evidence/models.py`, `locators.py`, `ledger.py` | pass | locator and DB tests | none |
| Assertion provenance | Accepted assertions require evidence or derivation and remain immutable | ledger plus migrations 002/005/006/008 | pass | Task 1 DB tests | none |
| ActivityEvent, signatures and observations | Stable record signature; logical-event dedup; append-only source observations | `ingestion/models.py`, `parser_runtime.py`, `events.py` | pass | Task 3 wave/event tests | none |
| Event lake | Events and observations written atomically to local partitions and catalogued | `ingestion/events.py`, `storage.py` | pass | Task 3 storage/DB tests | none |
| Parser registry and file families | Central registry and approved parser specs with document/email/media/archive/structured adapters | `ingestion/registry.py`, `schema_registry.py`, `adapters/` | pass with attachment blocker | adapter/registry tests | preserve attachment bytes and child lineage |
| Email attachment lineage | Attachment content must become a child SourceArtifact and retain exact parent lineage | Bounded bytes are dump-excluded; bulk creates idempotent child blob/artifact with parent/member path and parent email locator | remediated | attachment adapter/E2E tests passed | none |
| Pipeline resumability | Completed expensive stages must not rerun after restart | Completed result manifest is guarded by source identity; replay skips hashing, extraction and parser execution; changed input is rejected | remediated | replay spies and changed-source tests passed | none |
| Task Execution Router and privacy modes | Strict-local fail closed; explicit local-first/controlled-cloud; audited routing | `frontend/lib/execution/router.ts` and migration 010 | pass | Task 2 architecture tests | none |
| Encrypted credentials | AES-GCM, server-only decryption, production key enforcement | `frontend/lib/secure-credentials.ts`, `connector_credentials` | pass | Task 2 architecture tests | reuse unchanged in Task 5 |
| Per-workflow backend | Built-in/N8N/hybrid/disabled configured per workflow | `frontend/lib/workflows/registry.ts` | pass | Task 2 architecture tests | Task 5 scheduler must reuse this registry |
| Legacy IMAP monitor | Mail must be durably queued and canonically ingested before acknowledgement | Unsafe legacy monitor is now fail-closed; outbound transport remains available | remediated pending replacement | Task 2 static check plus Task 5 connector integration tests | replace disabled monitor with Task 5 connector runtime; compatibility rows derive after canonical persistence |

## Task 4 dependencies

| Requirement | Expected implementation | Actual implementation | Status | Tests | Remediation |
|---|---|---|---|---|---|
| Personal Insights page and temporal selection | `/dashboard/insights`; coherent point/period/compare query drives all modules | Page, temporal controls, shared query hook and typed APIs exist | pass; browser smoke waived | Task 4 API/contract tests | none for Task 5 |
| Materialised aggregates and canonical dependencies | Snapshot cache invalidates for all consumed canonical sources | Subject/window temporal aggregate token added | remediated | cache invalidation DB test passed | none |
| TopicExposureState, ObservedInterestState, EngagementProfile | Derived evidence-backed states; exposure never automatically becomes interest | Models/service/materialisation exist | pass | Task 4 service/scenario tests | preserve semantics |
| Search and investigation episodes | One-offs weak; recurrence/refinement/project transitions evidence-backed | `insights/search.py` | pass | Task 4 scenarios | none |
| AI conversation roles | Explicit source role must control user/assistant/system/tool/unknown semantics | Explicit canonical role is authoritative; heuristic fallback applies only when absent | remediated | all-role/conflicting-metadata tests passed | none |
| Email exposure/engagement | Received is exposure; only reliable opens weak passive; outbound replies communication | Unqualified opens/replies remain exposure; strict reliable open and outbound authorship rules added | remediated | open/direction tests passed | none |
| Contextual correlations | Change-first bounded retrieval; no automatic causation | Context engine and APIs present | pass | Task 4 context/scenario tests | none |
| Media/location evidence hierarchy | Screenshots/downloads cannot prove presence; landmark remains candidate | Routed output cannot create camera provenance without deterministic corroboration; conflicts remain conservative | remediated | routed-origin conflict and scenarios 08-11 passed | none |
| Subject isolation for media | A subject sees only owned media/location/content evidence | Reads, materialisation and cache tokens now join artifact/snapshot profile ownership | remediated | two-subject database test passed | none |
| Evidence inspector and immutable references | Every derived item traces to exact immutable evidence catalogue/index | Migrations 019/020 and tracer/UI exist | pass | evidence trace tests | Task 5 purge must preserve or tombstone these references |
| Synthetic acceptance | All 18 Task 4 scenarios represented | Scenario suite exists | pass, plus new connector-edge regressions required | focused suite | add blocker regressions above |

## Blocking remediation ownership

| Blocker | Owner | Shared-file boundary | Status |
|---|---|---|---|
| Attachment child artifacts and completed replay manifest | `repair_ingestion` delegate | Task 3 ingestion models/email adapter/bulk/tests only | verified |
| Subject-scoped media, aggregate cache token, safe origin corroboration | `repair_task4_media` delegate | Task 4 repository/service/media/tests only | verified |
| Email and AI role semantics | `repair_task4_signals` delegate | Task 4 signals and focused tests only | verified |
| Legacy IMAP acknowledgement/provenance bypass | orchestrator | legacy path fail-closed; replacement belongs to Task 5 connector runtime | verified safety gate |

## Phase 0 gate

Gate closed on 2026-07-13 after diff review and a 150-pass consolidated regression. No broad predecessor redesign was performed.
