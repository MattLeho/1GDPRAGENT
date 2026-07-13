---
title: Task 5 Implementation Ledger
date: 2026-07-13
tags:
  - gdpr-agent
  - task-5
  - implementation-ledger
status: wave-8-final-audit
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
| Connector/deletion schema and DTO freeze | 0 | orchestrator | Phase 0 | all 14 plan contracts and enums | `intelligence/connectors`, `intelligence/retention`, shared TS DTOs, migration 021 | verified | 5 contract tests; Python compile; focused TS compile; fresh DB migration | Wave 0 passed | migration 021 idempotent | none |
| Registry and sync-run runtime | 1 | bounded backend + orchestrator reconciliation | Wave 0 | connector definition/instance/run/cursor/raw record | `intelligence/connectors/{registry,repository,runtime,signatures}.py` | verified | canonical metrics, permission maximums, cursor rollback | Wave 1 passed | definitions idempotent; distinct cursor keys | none |
| Canonical raw-record ingestion bridge | 1 | bounded backend + orchestrator review | Task 3, Wave 0 | raw record/permission | `intelligence/connectors/bridge.py` | verified | provenance/dedup/no-graph/DB tests | Wave 1 passed | content-addressed blobs and stable signatures | none |
| Scheduling, lifecycle, retry and health | 1 | bounded backend + orchestrator reconciliation | Task 2 workflow scheduler | connector status/cursor | `intelligence/connectors/lifecycle.py`, `tasks.py`, connector API, migration 026 | verified | pause/resume/retry/restart/health; live queued API | Wave 7 live gate passed | Task 2 `connector.sync` preference; Celery bounded retry | none |
| Synthetic connector gate | 1 | bounded tests + orchestrator | Wave 1 runtime | all connector runtime contracts | `intelligence/connectors/synthetic.py`, `tests/test_task5_connector_runtime.py` | verified | real DB backfill/cursor/pause/reconnect/dedup/evidence | Wave 1 passed | none | none |
| Chromium extension | 2 | orchestrator | Wave 1 protocol | browser visit raw record | `browser-extension/` | verified | 4 Node tests; unpacked build | Wave 2 passed | none | none |
| Native/local bridge | 2 | orchestrator security | Wave 1 | framed pairing/ack protocol | `connectors/browser_bridge.py`, connector API, migration 022 | verified | auth/replay/revocation/DB/evidence tests | Wave 2 passed | local pairing ledger | none |
| Page-content policy | 2 | orchestrator | permissions | connector permission | browser definition/bridge/extension | verified | optional permission; signed page-content rejection | Wave 2 passed | none | none |
| IMAP source connector | 3 | orchestrator | Wave 1, credentials, Task 3A | email scope/cursor/raw record | `connectors/imap.py`, definitions/application | verified | deterministic read-only IMAP/cursor/attachment/event DB gate | Wave 3 passed | legacy monitor replaced by canonical runtime endpoint | none |
| Built-in email transport | 3 | orchestrator | Task 2 workflows/credentials | EmailTransport | `frontend/lib/connectors/{email,smtp-transport}.ts`, migration 023 | verified | draft/review/send state; real local TLS SMTP; N8N independence | Wave 3 passed | encrypted draft bodies | none |
| Evidence-supported email event semantics | 3 | orchestrator | repaired Task 4 signals | email events | `connectors/event_mapping.py`, canonical Task 3 event sink | verified | received/reply/direction/Seen-candidate tests | Wave 3 passed | event-lake partitions materialized | provider click/unsubscribe/archive/delete unavailable unless explicit evidence arrives |
| Bulk/newsletter candidates | 3 | orchestrator | email records | candidate DTOs | `connectors/email_intelligence.py` | verified | header/frequency fixtures | Wave 3 passed | none | none |
| Email engagement decay | 3 | orchestrator | Personal Insights | event mapping | `insights/signals.py`, `service.py` | verified | repeated exposure/no interest; nonnegative half-life decay | Wave 3 passed | current snapshots recompute on demand | none |
| AI conversation import | 4 | orchestrator | parser registry/Task 3 bridge | explicit conversation role | `connectors/ai_conversations.py`, typed event mapping | verified | role/source pointer/parent lineage/restart tests | Wave 4 passed | content-hash cursor | none |
| Photo/media folder connector | 4 | orchestrator | Task 3A/media repair | folder cursor/mode | `connectors/filesystem.py` photo definition | verified | metadata-only/selected visual/sidecar/removal tests | Wave 4 passed | file-hash baseline | none |
| Generic filesystem connector | 4 | orchestrator | Task 3A | scoped folder config | `connectors/filesystem.py` | verified | absolute roots/include/exclude/modify/remove DB gate | Wave 4 passed | file-hash baseline | none |
| Connector parser fixtures | 4 | orchestrator | adapters | known deterministic shapes | `tests/fixtures/task5_connectors` | verified | ChatGPT/Claude/photo sidecar/files | Wave 4 passed | none | none |
| Retention epistemic model | 5 | orchestrator | evidence/run contracts | policy/decision/classes | retention models, `retention/features.py`, migrations 021/024 | verified | important/bulk/unsure and no-interest input | Wave 5 passed | immutable versioned decisions | none |
| Deterministic retention features | 5 | bounded deterministic | email records | feature bundle | `retention/features.py` | verified | invoice/project/bulk/unsure | Wave 5 passed | none | none |
| Minimal semantic adjudication | 5 | bounded execution | Task Router/privacy | adjudication bundle | `retention/adjudication.py` | verified | abstention/strict-local/minimal excerpt | Wave 5 passed | none | provider execution intentionally optional |
| Policy evaluator | 5 | bounded backend | policies/features | RetentionPolicy/Decision | `retention/policy.py` | verified | scope/age/threshold/version/idempotency | Wave 5 passed | migration 024 fixes composite policy version key | none |
| Dry-run DeletionPlan builder | 6 | bounded backend | decisions/capabilities | plan/item | `retention/deletion_plan.py` | verified | protected/uncertain/default dry-run/review gates | Wave 6 passed | plan and reviews audited | none |
| Quarantine/grace state machine | 6 | bounded backend | plan items | staged state | `retention/staging.py` | verified | pure and persisted transitions/time gates | Wave 6 passed | migration 025 | none |
| Source deletion execution | 6 | orchestrator | tested connector capability | execution audit | `retention/source_delete.py`, `connectors/imap_delete.py`, retention API | verified | unsupported denial; real TLS IMAP UID MOVE; audit | Wave 6 passed | source response/audit stored | IMAP MOVE-to-Trash is the only supported provider action |
| Provenance-preserving local purge | 6 | orchestrator | assertions/insights/hypotheses | LocalPurgeExecution | `retention/local_purge.py`, `evidence/purged.py`, evidence inspector | verified | minimised locator resolution/tombstone/full-span refusal | Wave 6 passed | migration 025 | none |
| Controller erasure integration | 6 | bounded integration + orchestrator approval | existing request system | candidate | `retention/controller_erasure.py` | verified | existing `requests` draft/no outbound send | Wave 6 passed | no second request table | none |
| Connector Settings and permission inspector | 7 | bounded frontend | frozen real APIs | connector DTOs | `SourceConnectorsSection.tsx`, connector proxy/API | verified | frontend build; live API 200 and 5 definitions | Wave 7 passed | migration 026 workflow | browser interaction deferred by user |
| Retention Settings and plan review | 7 | bounded frontend | frozen real APIs | retention/deletion DTOs | `RetentionSettingsSection.tsx`, retention proxy/API | verified | frontend build; live API 200; exact confirmations | Wave 7 passed | migrations 024-026 | browser interaction deferred by user |
| Connector synthetic acceptance | 8 | bounded tests + orchestrator | Waves 1-7 | all | Task 5 integration tests | verified | 43-test Task 5 aggregate plus extension 4/4 | Wave 8 code/runtime gate passed | none | browser UI smoke deferred by user |
| Retention/deletion acceptance | 8 | bounded tests + orchestrator | Waves 5-7 | all | retention/deletion integration tests | verified | DB staging/purge/request and real TLS IMAP | Wave 8 code/runtime gate passed | none | none |
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

## Wave 1 integration freeze

Connector adapters now return opaque `ConnectorRawRecord` batches only. They cannot report or manufacture ActivityEvents. `ConnectorRuntime` requires the canonical ingestion bridge and advances a cursor only after every payload has been durably bridged; an ingestion failure leaves the previous cursor in place and records a failed run. Stable signatures are shared by the synthetic source and bridge, permission grants are maximum-bounded, permission changes are audited, and successful/failed outcomes update connector health state without deleting cursor/history.

Wave 1 verification:

- Combined connector contracts, lifecycle, registry/runtime, bridge, migrated-PostgreSQL gate, and Task 2 architecture: **30 passed**.
- Real synthetic gate: sync and separate backfill cursor, duplicate reuse, pause/resume, disconnect/reconnect, cursor preservation, two raw records, two SourceArtifacts, and two verified EvidenceLocators.
- Python compile for all connector modules and Wave 1 tests: passed.
- Review correction: the initial registry draft could enqueue metadata then discard payload. It was replaced with mandatory bridge ingestion before cursor advancement, so no success path can bypass canonical ingestion.
- No connector module imports or writes Neo4j, graph assertions, interests, importance, or retention decisions.

## Wave 2 integration freeze

The extension is an isolated Manifest V3 package. History is an optional permission requested from its options page; page content is absent from its capture surface and the server rejects any page-content field even when the frame is correctly signed. The queue is persistent, signature-deduplicated and bounded at 5,000 without silent loss. The local HTTP bridge uses protocol version 1, bearer pairing tokens stored only as SHA-256 hashes, exact frame-hash replay protection, acknowledgements, revocation, and a 250-record frame bound. Browser visits map through a verified locator into `BROWSER_VISIT` ActivityEvents in the Task 3 event lake and never write interest/graph truth.

Wave 2 verification: extension **4/4** tests and build passed; Python browser bridge plus migrated database gate passed; migration 022 idempotency passed; cross-runtime visit signature fixture matched exactly.

## Wave 3 integration freeze

Email source and email transport are separate. `email.imap` uses read-only mailbox selection and `BODY.PEEK[]`, UIDVALIDITY/UID cursors, four exact scopes, server-only Task 2 credential decryption, and stable record signatures. Full messages route through the repaired Task 3A email adapter so attachment bytes become child SourceArtifacts with parent/member lineage. Typed mapping creates only evidence-supported received/sent/reply and IMAP Seen *candidate* events; no unsupported open fact is fabricated. Bulk/newsletter outputs remain candidates and never become automatic spam.

The built-in SMTP path remains the default Task 2 workflow handler and has no N8N dependency. It now persists an encrypted draft, requires an explicit reviewed state, then sends over TLS and records transport metadata. A real local TLS SMTP server accepted the complete AUTH/MAIL/DATA flow, including CRLF normalization and dot-stuffing. Frontend and Python credential implementations were verified cross-runtime.

Wave 3 focused verification: combined Task 5 connector/email suite **29 passed** before the final TLS and credential smokes; both additional real transport smokes passed; focused Task 5 TypeScript project compiled cleanly.

## Wave 4 integration freeze

AI imports are snapshot/file based—no authenticated scraping. Known ChatGPT, Claude and generic export shapes are deterministically normalised to conversation/turn/service/title/model/timestamp/role records. The immutable export is ingested first through Task 3 fingerprinting; each grounded turn is a child SourceArtifact carrying its original JSON pointer and maps to a role-explicit ActivityEvent. Only `user` turns become direct investigation signals; assistant output remains exposure, with system/tool/unknown preserved.

Filesystem connectors require absolute user-selected roots, resolve every candidate back under its root, apply include/exclude/type/size scopes, and content-hash files. New and modified bytes route through Task 3A; removal produces a separate observation while every earlier SourceArtifact remains immutable. The photo variant defaults to metadata-only, has explicit selected/full visual modes, recognises adjacent sidecars, and requests visual tasks only when the displayed permission and path policy allow them. Media observations explicitly do not prove physical presence, and file changes do not establish semantic project meaning.

Wave 4 verification: **4 passed** including migrated-PostgreSQL AI and filesystem gates, restart cursors, role-aware Personal Insights classification, two immutable file versions plus removal observation, parent turn lineage, photo modes, and sidecar fixture handling. Connector modules compiled cleanly.

## Wave 5 integration freeze

Retention consumes only retention-specific, deterministic evidence. Its input model forbids interest fields; protective evidence takes precedence over bulk signals, and unresolved cases remain `UNSURE`. Only unresolved candidates may receive the bounded `email.retention_adjudication` bundle, which supports abstention and becomes local-only under strict-local processing. Policy scope, connector, data class, age, threshold, action, schedule, grace period and configuration are persisted by immutable `(policy_id, policy_version)` and decisions are idempotent per source/policy/version/run.

Wave 5 verification: important financial mail, low-value repeated bulk mail, uncertain mail, strict-local minimal bundles, abstention and version/idempotency passed against migrated PostgreSQL. Migration 024 safely corrected the legacy policy primary key to its versioned composite contract.

## Wave 6 integration freeze

All plans begin as dry runs and preserve eligible/protected/uncertain groups with reasons. Approval requires exact confirmation and every eligible decision to have an explicit approved review. Persisted staging enforces candidate → review → quarantine → grace expiry → eligible-for-delete. Source deletion is allowed only for a plan/decision/connector triple that independently passes every gate; the sole initial adapter uses reversible IMAP `UID MOVE` to Trash and records provider acknowledgement.

Local purge is limited to the connector-owned content-addressed copy. It verifies hash/reference count, resolves required accepted assertion, historical insight, event observation and media-candidate locators, stores minimised evidence segments, records a tombstone and refuses a purge that would retain the full source. Existing locators continue resolving through retained segments; unretained spans fail explicitly. The evidence inspector displays `content_purged_at` and full-source unavailability. Controller erasure creates a reviewed draft in the existing `requests` table and never sends it.

Wave 6 verification: **5 deletion-safety tests passed** plus the broader retention suite. A deterministic real TLS IMAP server verified `UID MOVE`, UIDVALIDITY matching and the absence of `EXPUNGE`/`STORE`. Local purge preservation and full-span refusal passed against PostgreSQL and real local files.

## Wave 7 integration freeze

The Python APIs are the sole destructive orchestrator. Next.js routes only proxy typed requests. Connector settings list real definitions/instances, displayed permissions and data classes, page-content non-collection, status, last/next sync, pause/resume, Celery-queued sync/backfill and disconnect-without-erasure. Email source and SMTP transport remain visibly and operationally separate. Retention settings expose decisions including `UNSURE`, policy age/action, dry-run summaries, reasons, exact plan approval, quarantine/grace staging and reviewed execution.

Wave 7 verification: focused TypeScript compile and the full Next.js production build passed. Migration 026 registered `connector.sync` in the Task 2 workflow preferences. Live migrations 021–026 were applied idempotently; direct service and Next.js proxy checks returned HTTP 200, with five built-in connector definitions. No browser interaction was performed because the user explicitly deferred it.
