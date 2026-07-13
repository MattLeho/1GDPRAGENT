---
title: Task 5 Implementation Ledger
date: 2026-07-13
tags:
  - gdpr-agent
  - task-5
  - implementation-ledger
status: wave-0
---

# Task 5 Implementation Ledger

This is the single integration ledger for Task 5. Status values are `pending`, `in-progress`, `blocked`, `delivered`, or `verified`. A UI card, placeholder route, mock-only result, or connector without cursor, deduplication, provenance and restart behaviour is not delivered.

## Frozen cross-cutting invariants

- Every source enters through `SourceConnector` and the canonical SourceArtifact/EvidenceLocator/ActivityEvent pipeline.
- Connectors never write semantic graph truth, user interests, importance or retention decisions directly.
- Credentials remain encrypted and server-side; permissions are enforced maximums.
- Scheduling reuses Task 2 workflow/task routing rather than a second scheduler.
- Retention is independent of Personal Insights; `UNSURE` defaults to keep/review.
- Deletion defaults to dry run and keeps local purge, source deletion, controller erasure and review-only distinct.
- Pause/disconnect never erases historical evidence.
- Task 6 is out of scope.

## Requirements

| Requirement | Wave | Owner | Dependency | Shared contract | Implementation location | Status | Tests | Integration gate | Migration/backfill note | Blocker |
|---|---:|---|---|---|---|---|---|---|---|---|
| Predecessor audit and blocking repairs | Phase 0 | orchestrator + bounded delegates | Tasks 1-4/3A | existing canonical contracts | predecessor modules and Task 5 audit ledger | verified | 150 passed, 1 optional skip | Phase 0 passed | none beyond repairs | none |
| Connector/deletion schema and DTO freeze | 0 | orchestrator | Phase 0 | all 14 plan contracts and enums | `intelligence/connectors`, `intelligence/retention`, shared TS DTOs, migration 021 | delivered | 5 contract tests; Python compile; focused TS compile; fresh DB migration | Wave 0 passed | migration 021 idempotent | none |
| Registry and sync-run runtime | 1 | bounded backend | Wave 0 | connector definition/instance/run/cursor/raw record | connector runtime/repository/API | pending | registry/run metrics | Wave 1 | definitions seeded idempotently | Wave 0 |
| Canonical raw-record ingestion bridge | 1 | bounded backend + orchestrator review | Task 3, Wave 0 | raw record/permission | connector ingestion bridge | pending | provenance/dedup/no-graph tests | Wave 1 | signatures backfill if required | attachments repair |
| Scheduling, lifecycle, retry and health | 1 | bounded backend | Task 2 workflow scheduler | connector status/cursor | connector orchestration jobs/API | pending | pause/resume/retry/restart | Wave 1 | none | Wave 0 |
| Synthetic connector gate | 1 | bounded tests | Wave 1 runtime | all connector runtime contracts | tests/fixtures | pending | backfill/cursor/pause/reconnect/dedup | Wave 1 | none | runtime |
| Chromium extension | 2 | bounded extension | Wave 1 protocol | browser visit raw record | isolated extension package | pending | build/backfill/incremental/queue | Wave 2 | none | protocol |
| Native/local bridge | 2 | bounded bridge + orchestrator security | Wave 1 | framed pairing/ack protocol | isolated bridge + local API | pending | auth/replay/queue/health smoke | Wave 2 | install manifest | protocol |
| Page-content policy | 2 | orchestrator | permissions | connector permission | policy/config | pending | default-off/denied fields | Wave 2 | none | none |
| IMAP source connector | 3 | bounded adapter | Wave 1, credentials, Task 3A | email scope/cursor/raw record | connector adapters/email | pending | deterministic IMAP/cursor/attachment | Wave 3 | legacy monitor transition | Wave 1 |
| Built-in email transport | 3 | bounded transport + orchestrator integration | Task 2 workflows/credentials | EmailTransport | email transport/workflow handler | pending | draft/review/send without N8N | Wave 3 | none | credentials/test server |
| Evidence-supported email event semantics | 3 | bounded semantics | repaired Task 4 signals | email events | connector email mapper | pending | open/click/reply direction | Wave 3 | none | signal repair |
| Bulk/newsletter candidates | 3 | bounded deterministic | email records | candidate DTOs | connector email features | pending | header/frequency fixtures | Wave 3 | none | none |
| Email engagement decay | 3 | bounded semantics | Personal Insights | event mapping | Task 4 signal integration | pending | repeated exposure/no interest | Wave 3 | recompute affected windows | signal repair |
| AI conversation import | 4 | bounded adapter | parser registry | explicit conversation role | connector parsers/fixtures | pending | role/source locator tests | Wave 4 | none | role repair |
| Photo/media folder connector | 4 | bounded adapter | Task 3A/media repair | folder cursor/mode | connector adapters/folder | pending | metadata-only/no visual/removal | Wave 4 | file baseline | media repair |
| Generic filesystem connector | 4 | bounded adapter | Task 3A | scoped folder config | connector adapters/folder | pending | roots/include/exclude/modify | Wave 4 | file baseline | Wave 1 |
| Connector parser fixtures | 4 | bounded fixtures | adapters | parser registry specs | tests/fixtures | pending | known AI/sidecar/files | Wave 4 | none | chosen formats |
| Retention epistemic model | 5 | orchestrator | evidence/run contracts | policy/decision/classes | retention models/migration/service | pending | invariants/no-interest input | Wave 5 | versioned decisions | Wave 0 |
| Deterministic retention features | 5 | bounded deterministic | email records | feature bundle | retention/features.py | pending | invoice/project/bulk/unsure | Wave 5 | none | email connector |
| Minimal semantic adjudication | 5 | bounded execution | Task Router/privacy | adjudication bundle | retention/adjudication | pending | abstention/strict-local | Wave 5 | none | router route |
| Policy evaluator | 5 | bounded backend | policies/features | RetentionPolicy/Decision | retention/policy.py | pending | scope/age/idempotency | Wave 5 | policy version | Wave 0 |
| Dry-run DeletionPlan builder | 6 | bounded backend | decisions/capabilities | plan/item | retention/deletion_plan.py | pending | protected/uncertain/default dry-run | Wave 6 | immutable plans | Wave 5 |
| Quarantine/grace state machine | 6 | bounded backend | plan items | staged state | retention/staging.py | pending | transitions/time gates | Wave 6 | state migration | Wave 5 |
| Source deletion execution | 6 | orchestrator | tested connector capability | execution audit | destructive service/API | pending | unsupported denial/Trash/audit | Wave 6 | execution audit | provider capability |
| Provenance-preserving local purge | 6 | orchestrator | assertions/insights/hypotheses | LocalPurgeExecution | destructive service/API | pending | locator preservation/tombstone | Wave 6 | purge metadata | evidence dependency map |
| Controller erasure integration | 6 | bounded integration + orchestrator approval | existing request system | candidate | retention/request adapter | pending | existing workflow/no autosend | Wave 6 | none | request API contract |
| Connector Settings and permission inspector | 7 | bounded frontend | frozen real APIs | connector DTOs | Settings components/routes | pending | real controls/permission parity | Wave 7 | none | API freeze |
| Retention Settings and plan review | 7 | bounded frontend | frozen real APIs | retention/deletion DTOs | Settings/review components | pending | UNSURE visible/confirmation safety | Wave 7 | none | API freeze |
| Connector synthetic acceptance | 8 | bounded tests + orchestrator | Waves 1-7 | all | integration tests | pending | all 13 plan scenarios | Wave 8 | none | implementation |
| Retention/deletion acceptance | 8 | bounded tests + orchestrator | Waves 5-7 | all | integration tests | pending | all 10 plan scenarios | Wave 8 | none | implementation |
| Line-by-line audit and final verification | 8 | orchestrator | all waves | all frozen contracts | final audit/report | pending | full command matrix/runtime logs | final | migrations through Task 5 | all waves |

## Wave 0 contract freeze

The following interfaces are frozen for Wave 1 delegation:

`SourceConnectorDefinition`, `ConnectorInstance`, `ConnectorSyncRun`, `ConnectorCursor`, `ConnectorRawRecord`, `ConnectorPermission`, `EmailTransport`, `RetentionPolicy`, `RetentionDecision`, `DeletionPlan`, `DeletionPlanItem`, `SourceDeletionExecution`, `LocalPurgeExecution`, and `ControllerErasureCandidate`.

Frozen enum values are the exact values in the Task 5 plan. Public connector configuration rejects secret-like keys; secrets must be referenced through the existing encrypted `connector_credentials` store. Raw-record payload bytes are excluded from model dumps. Destructive contracts mechanically enforce dry-run default, protected/uncertain stage exclusion, connector capability for source deletion, preserved locators for local purge, and reviewed approval before automatic controller-erasure execution.

Wave 0 verification:

- `tests/test_task5_contracts.py`: 5 passed; `tests/test_task5_database_contracts.py`: 1 passed.
- Connector/retention Python compilation: passed.
- Focused TypeScript DTO compilation: passed.
- Migration 021 applied through the canonical migration runner in a fresh database and the idempotency test passed.
- Task 2 architecture plus Task 5 contract regression: 14 passed after the unsafe legacy inbox monitor was failed closed.
- Full frontend type checking remains deferred to the wave gate because the running Next dev server has malformed generated `.next/dev/types` files; new source DTOs compile independently.
