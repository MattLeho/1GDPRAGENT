---
title: Task 5 Final Self-Audit
date: 2026-07-13
tags: [gdpr-agent, task-5, self-audit]
status: predecessor-repair-in-progress
---

# Task 5 Final Self-Audit

> **PROVISIONAL — R0 revalidation required (2026-07-17).** The existing predecessor warning remains historical evidence; this report does not prove current authenticated integration.

> [!warning] Superseded completion determination
> The mandatory Task 6 predecessor audit found that this report overstated integrated completion. Source deletion lacked a separately granted destructive permission; live retention evaluation and recurring dispatch were disconnected; destructive APIs lacked signed profile-scoped authority; and controller-erasure drafting could precede the grace gate. Repairs are recorded in [[Task 6 Predecessor Audit Ledger]]. This document must not be used as current completion evidence until the repaired full suite and runtime gate are recorded.

## 1. Predecessor audit

The complete audit and remediations are recorded in [[Task 5 Predecessor Audit Ledger]]. The consolidated predecessor gate passed 150 tests with one optional dependency skip before Task 5 implementation. Repairs were limited to provenance, replay safety, legacy IMAP fail-closed behaviour, Task 4 subject scope/cache/signals/AI-role/media semantics, and evidence preservation required by Task 5.

## 2. Delegation map

- Orchestrator: shared contracts, migrations, credentials, permission limits, retention epistemics, destructive semantics, integration and acceptance.
- Wave 1 bounded agents: registry/runtime, lifecycle/scheduling helpers and canonical bridge; all diffs were reconciled into the mandatory bridge-before-cursor contract.
- Later connector, retention, UI and test leaves were integrated under the frozen contracts; security and destructive operations remained orchestrator-owned.
- Shared ownership and gates are recorded in [[Task 5 Implementation Ledger]].

## 3. Connector architecture

`SourceConnectorDefinition → ConnectorInstance → ConnectorSyncRun/ConnectorCursor → ConnectorRawRecord → ConnectorIngestionBridge → SourceArtifact/EvidenceLocator/ActivityEvent` is the sole path. Cursors advance only after durable canonical ingestion. Signatures, permission maximums, sync metrics, pause/resume/disconnect, authentication-required/degraded health, Celery retry/backoff and next-sync state are implemented. Searches confirm connector/retention modules have no Neo4j or `INTERESTED_IN` writes.

## 4. Connector implementations

Five built-ins are published: Chromium history, IMAP email, AI conversation snapshots, scoped filesystem, and photo/media folders. Synthetic and migrated-PostgreSQL gates verify backfill, incremental cursor continuation, pause/reconnect, deduplication and durable provenance. Disconnecting preserves raw records, artefacts, locators and event partitions.

## 5. Browser extension and bridge

The isolated Manifest V3 package provides explicit optional history permission, deterministic initial backfill/incremental visits, a persistent bounded queue, acknowledgement and reconnect. The local bridge uses versioned signed frames, hashed pairing tokens, replay protection, revocation and bounded batches with no cloud relay. Page content/form/password/payment capture is absent and signed page-content frames are rejected. Installation is documented in `browser-extension/README.md`.

## 6. Email source/transport split

IMAP source acquisition is read-only (`readonly=True`, `BODY.PEEK[]`) with UIDVALIDITY/UID cursors and four scopes. Identifiers, references, participants, time, headers, bodies and attachment lineage are preserved according to scope; attachments use Task 3A. SMTP transport separately persists encrypted drafts, requires review, sends over TLS and records metadata without an N8N dependency. N8N remains optional per workflow.

## 7. AI/photo/filesystem connectors

ChatGPT, Claude and generic exports preserve conversations, turns, roles, timestamps, services, models, titles and JSON source pointers. User turns alone become direct behavioural signals. Photo/filesystem sources require absolute selected roots, enforce scopes, hash new/modified content, record removals without erasing history, and default photos to metadata-only with no visual call.

## 8. Retention architecture

The exact nine classes and four actions are implemented. Retention inputs reject interest fields. Deterministic financial/legal/security/education/employment/project/conversation/personal evidence takes precedence. Only unresolved cases receive a bounded privacy-mode-aware adjudication bundle; abstention resolves to `UNSURE`. Policies and decisions are immutable/versioned/idempotent by policy version and analysis run.

## 9. Deletion staging and safeguards

Every plan begins as a dry run and exposes eligible/protected/uncertain groups with reasons. Exact review/approval confirmations are required, and plan approval is blocked until every eligible decision is approved. Persisted staging enforces review, quarantine, grace expiry and eligibility. IMAP source deletion is capability-gated, UIDVALIDITY-checked, reversible Trash `MOVE` only and audited. Local purge verifies the connector-owned blob, reference count and hash; retains required minimised locator bytes; records a tombstone; refuses full-source retention; and leaves accepted assertion/historical insight/event/media provenance resolvable. Controller erasure produces an existing-system draft and sends nothing.

## 10. Settings and review UI

`Settings → Connectors` uses real APIs for definition/instance status, displayed permissions, data classes, backfill, sync, pause/resume and disconnect. Chromium instances also expose one-time pairing creation and revocation, show the local bridge URL and instance ID, and display the token only in the creation response; the token is stored only as a hash server-side. `Settings → Data Retention` exposes policies, decision reviews including `UNSURE`, plan groups/reasons, dry-run/review state, exact destructive approval and staged actions. The evidence inspector explicitly shows when full source content was purged and minimised evidence remains.

## 11. Migrations and credentials

Migrations 021–026 add connector/retention contracts, browser pairing, email transport, versioned policies, deletion/minimised-evidence audit and the Task 2 `connector.sync` workflow. They pass the canonical second-run idempotency test and were applied to the live database. Secrets remain AES-256-GCM ciphertext in `connector_credentials`; public connector configuration rejects secret-like keys; pairing tokens are stored only as hashes server-side.

## 12. Exact verification results

- `python -m compileall -q intelligence` — passed.
- `python -m pytest -q` with host PostgreSQL/Neo4j/Qdrant/Redis addresses — **377 passed, 2 skipped**, 4 warnings.
- Current complete Task 5 aggregate — **45 passed** with one deprecation warning; deletion-safety scenarios are included.
- Canonical migration idempotency test — **1 passed**; live migrations 021–026 applied successfully.
- `pnpm run build` in `frontend` — passed, 61 routes/pages generated.
- `pnpm run lint` — exit 0, 135 warnings and no errors; warnings are predominantly pre-existing, with no build/type failure.
- Authenticated in-app browser smoke on `localhost:3001` — Settings Connectors and Data Retention loaded and interacted with successfully; live API-backed controls rendered and browser logs contained no warnings or errors. This smoke exposed the missing pairing-token UI, which was added and then production-build verified.
- Browser extension `pnpm test` — **4 passed**; `pnpm run build` — passed.
- Real TLS SMTP smoke — passed; TLS/auth/data/dot-stuffing accepted.
- Real TLS IMAP deletion smoke — passed; `UID MOVE` observed, no `EXPUNGE` or `STORE`.
- AI import, attachment ingestion, photo metadata-only, filesystem sync, cursor/reconnect/dedup, retention/staging/purge/request routing — passed in the full suite.
- Docker: PostgreSQL, Redis, Neo4j, Qdrant, intelligence, Celery, Next.js and N8N healthy. Intelligence published 71 file formats and 5 connector definitions. Celery registered `intelligence.connectors.sync`. Backend and Next.js connector/retention APIs returned HTTP 200. Live migration history ends at 026 with all Task 5 migrations 021–026 recorded.

## 13. Unsupported connector/provider capabilities

- Source deletion is supported only for IMAP servers that advertise `MOVE`, using reversible Trash semantics. Permanent expunge is deliberately unsupported.
- IMAP does not prove link clicks, unsubscribe actions, archive/delete actions or legal controller erasure. Such events are emitted only if a future source provides explicit evidence.
- Browser page content is unsupported in this version by design.
- Provider-native Gmail/Outlook APIs, remote photo libraries and authenticated AI scraping are not implemented; standards/local export and selected-folder paths are the supported MVPs.

## 14. Security limitations

- A local user/process with access to the configured credential-encryption key and database can decrypt connector credentials; OS account and secret-file protection remain deployment responsibilities.
- The browser bridge is local bearer-token pairing over the configured local HTTP endpoint. Tokens are hashed server-side, but endpoint exposure beyond localhost must be prevented by deployment/network configuration.
- IMAP/SMTP rely on provider TLS validation and provider-issued credentials. Controller legal erasure is never inferred from source absence.
- A crash after a provider Trash acknowledgement but before the final audit update can leave an `initiated` execution requiring manual reconciliation; automatic replay is refused to avoid duplicate destructive action.

## 15. Incomplete or deferred requirements

- Optional external production validation beyond the Wave 8 gate remains deferred: a real personal-Chromium history round trip can be run later by loading `browser-extension/dist`, creating its one-time pairing in Settings and approving the optional History permission. The required deterministic backfill, incremental, deduplication, reconnect/queue, bridge, database and build acceptance tests all pass; the plan does not require access to the user's personal browser profile for completion.
- No safe real third-party mailbox credentials were supplied. Acquisition uses deterministic protocol doubles plus migrated end-to-end ingestion; destructive IMAP uses a real local TLS protocol server. A provider-account smoke requires a disposable IMAP account/app password and permission to create/move a test message.
- Lint has 135 warnings and zero errors. Cleaning unrelated legacy warnings is outside Task 5 and was not used to hide any Task 5 failure.

## 16. Scope confirmation

Only Task 5 was executed. Task 6 was not read, started or modified.
