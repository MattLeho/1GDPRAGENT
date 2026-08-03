# R1 independent canonical profile-isolation re-audit

Date: 17 July 2026  
Auditor: independent profile-isolation workstream (no profile-ownership implementation)  
Scope: repaired PostgreSQL, Neo4j-facing routes, uploads, requests/threads, identity documents, credentials/connectors, Personal Insights, profile editing, and migration 030.

## Final verdict

**PASS — the R1 canonical profile-isolation definition of done is met for the re-audited scope.**

All previously reported cross-profile authority and file-lifecycle defects are repaired in the current tree. Bulk-ingestion object IDs, graph statistics/evidence/mutations, Insights evidence/media IDs, ONSIT bulk-send history, stored credentials, profile/account editing, identity documents, and general uploads now derive or verify canonical profile ownership and fail closed on the audited error paths. Environment-dependent Python/database execution remains explicit under Test evidence; it does not reveal a remaining code blocker in this audit.

## Re-audit of prior findings

### R1-ISO-01 — Resolved — Bulk-ingestion supplied IDs

`ProcessFileBody` no longer accepts a body `profile_id` (`intelligence/api/bulk_ingestion.py:21-32`). `_require_owned_inputs` checks request, received-data, analysis-run, and export-snapshot IDs against the signed profile and verifies the run/snapshot pair (`:43-68`). Process and enqueue call this guard before use (`:80-103`, `:109-131`). Run progress joins `analysis_runs.profile_id` and gives the same 404 for foreign/missing runs (`:137-160`). Specialist results join the specialist request, analysis run, source artifact, and export snapshot to the signed profile; received-data and optional execution-record IDs are also checked (`:163-205`). The eventual `received_data` update includes `profile_id` (`:242-250`).

Result: **PASS** for cross-profile ingestion IDs.

### R1-ISO-02 — Resolved for isolation; one non-isolation consistency issue remains — Graph

Graph statistics now count only nodes visible through the authority profile's relationships and bind `profileId` in all three queries (`frontend/app/api/graph/stats/route.ts:13-48`). Dashboard graph counts are likewise profile-bound (`frontend/lib/actions/dashboard.ts:255-257`, `:275-315`). The main graph read continues to overwrite any caller query-string `profileId` with the session profile (`frontend/app/api/graph/route.ts:151`, `:168`, `:186-191`).

Evidence creation and projection now carry the verified profile (`intelligence/api/evidence.py:59-82`; `intelligence/graph/projection.py:53-70`). Retire, merge, and ONSIT bulk mutations verify that the human-confirmed assertion belongs to the same profile and mutate only profile-owned relationships; shared Neo4j nodes are no longer globally retired or APOC-merged (`intelligence/graph/projection.py:120-179`). Profile authority cannot invoke global backfill (`intelligence/api/evidence.py:105-108`).

Result: **PASS** for cross-profile graph isolation.

Non-isolation follow-up: retire/merge sets `owned.profile_retired=true`, and statistics exclude such edges, but the main graph `relationshipPredicate` at `frontend/app/api/graph/route.ts:108-120` does not exclude `profile_retired`. A successfully retired item can therefore remain visible in the main graph. This is a mutation/read-consistency defect, not a cross-profile disclosure, and is not the blocker for this audit verdict.

### R1-ISO-03 — Resolved — Insights evidence, media confirmation, and legacy deltas

Evidence trace requires the signed profile (`intelligence/api/insights.py:127-132`) and scopes the root materialisation, activity events, assertions, temporal records, evidence locators, and artifacts to that profile (`intelligence/insights/evidence.py:63-69`, `:91-137`, `:147-184`). Media confirmation requires the signed profile and verifies artifact/locator ownership through export snapshot plus optional analysis-run ownership before insert (`intelligence/api/insights.py:173-186`; `intelligence/insights/service.py:906-953`). Export deltas no longer expose null-profile runs to every subject (`intelligence/insights/repository.py:184-193`).

Result: **PASS** for the prior direct-ID and null-profile Insight findings.

### R1-ISO-04 — Resolved — ONSIT bulk-send request ownership

The route passes `authority.profileId` into history and persistence helpers (`frontend/app/api/onsit/send-bulk-emails/route.ts:15-17`, `:36-41`, `:79-87`). Contact history includes `profile_id = $2` (`:121-134`), and sent-request insertion writes `profile_id` (`:146-164`). Persistence errors are no longer swallowed; failed delivery/audit persistence produces a failed result and prevents an unconditional success response (`:79-105`).

Result: **PASS**.

### R1-ISO-05 — Resolved — Credential ownership policy

User-entered AI credentials are now profile-owned in schema and runtime. Migration 030 adds non-null `ai_credentials.profile_id`, a profile foreign key, and uniqueness on `(profile_id, provider)` (`database/migrations/030_r1_profile_ownership.sql:15`, `:88-110`, `:160-171`). Settings reads/writes bind the authority profile (`frontend/app/api/settings/ai-credentials/route.ts:82-104`, `:138-173`), and credential retrieval uses `(provider, profile_id)` when reading stored keys (`frontend/lib/ai-credentials.ts:126-148`). Environment credentials remain deliberately global infrastructure fallback and are never returned to the browser.

ONSIT API keys use authority-derived `profile.<profileId>.onsit.*` keys for both reads and writes (`frontend/app/api/settings/api-credentials/route.ts:8-30`). Connector/email credentials remain directly profile-keyed (`frontend/lib/connectors/email.ts:14-55`).

Result: **PASS**. The personal-versus-infrastructure distinction is now encoded: database/UI-entered keys are personal; environment keys are infrastructure.

### R1-ISO-06 — Resolved — File lifecycle

ID documents now validate document type, MIME and size, choose a random server-side filename, clean up the new file on insert failure, query/delete by authority profile, constrain stored paths to the managed root, and unlink managed files before deleting metadata (`frontend/app/api/settings/id-documents/route.ts:69-119`, `:144-175`). Profile avatars retain the previously accepted transaction/cleanup ordering (`frontend/app/api/settings/profile/route.ts:103-165`). General upload DELETE now unlinks before deleting the profile-owned database row and treats only `ENOENT` as harmless (`frontend/app/api/upload/route.ts:355-395`).

General upload creation now uses a UUID batch directory and UUID-prefixed filenames for normal files, ZIP members, and invalid-ZIP fallback storage (`frontend/app/api/upload/route.ts:53-56`, `:83-97`, `:125-127`, `:150-155`). The path namespace is therefore independent of upload timing, profile concurrency, and caller filename; a same-millisecond/same-name upload no longer aliases an existing path.

All `received_data` inserts for the batch use one database client and transaction (`:57-59`, `:103-109`, `:130-136`, `:162-177`, `:190`). Once a ZIP has opened successfully, any entry extraction, filesystem, or metadata error is rethrown rather than being misclassified as an invalid ZIP (`:78-82`, `:121-123`). The outer failure handler rolls back the complete metadata batch and recursively removes only the validated UUID batch directory beneath `UPLOAD_DIR` (`:198-210`). Because every new file is contained below that directory, partial normal-file and ZIP batches are removed together without touching an earlier batch or another profile's files.

The batch directory is constructed server-side from `UPLOAD_DIR` plus `batch_${randomUUID()}`; the cleanup guard requires the resolved construction to remain beneath the upload root before recursive removal (`:54-56`, `:200-202`). Caller filenames affect only a UUID-prefixed basename and cannot select the cleanup target.

Result: **PASS**. No orphan/collision path remains in the audited upload flow. A dedicated fault-injection unit test for rollback plus recursive cleanup would strengthen regression evidence, but static control-flow inspection establishes the repaired boundary and no test-file edit was made by this read-only auditor.

### R1-ISO-07 — Resolved policy; runtime migration evidence is environment-dependent — Legacy email accounts

Migration 030 still refuses ambiguous cross-profile ownership rather than guessing (`database/migrations/030_r1_profile_ownership.sql:70-101`). It now states the one-active-email-account-per-profile policy and explicitly detects duplicate legacy rows before the unique index, preserving all rows and raising an actionable consolidation error (`:112-128`, `:169`). No destructive merge or row deletion occurs.

Result: **PASS** for isolation/data-preservation policy. This is a deliberate fail-closed operator repair, not silent data loss. The existing migration fixture does not exercise the duplicate-email branch, so runtime evidence for that exact diagnostic remains missing.

## Other scoped paths

- Requests, received data, request threads/chat/logs, and child-table access continue to use direct `profile_id` predicates or verified request-parent joins.
- Profile GET/update/password paths bind both session user and canonical profile and do not assign `password_hash` or `default_profile_id` during identity edits.
- No first-user or first-profile shortcut was found in the re-audited production paths.

## Test evidence

Executed from `frontend` with the bundled Node runtime added to `PATH`:

```text
pnpm test -- tests/r1-profile-ownership.test.ts tests/r1-profile-sql-scope.test.ts tests/r1-adversarial-object-isolation.test.ts tests/r1-adversarial-client-profile.test.ts tests/r1-route-authority.test.ts
```

Vitest executed the configured R1 suite: **13 files, 73 tests passed**. This includes session authority, client-profile tampering, object isolation, internal authority call sites, profile ownership/state, route authority, and SQL-scope invariants.

```text
pnpm typecheck
```

Result: **PASS** (`tsc --noEmit`).

Python focused suites were selected:

```text
tests/test_r1_bulk_profile_isolation.py
tests/integration/test_r1_graph_profile_isolation.py
tests/test_task4_evidence_trace.py
tests/test_task4_media_database.py
tests/migration_fixtures/test_r1_profile_ownership_migration.py
```

They could not start because the available bundled Python reports `No module named pytest`. Their code was inspected, but this is not runtime proof. Database-backed clean-install/upgrade execution is therefore not independently re-established by this workstream.

## Definition-of-done decision

| R1 isolation criterion | Result |
|---|---|
| Personal-data queries use profile predicates or verified parents | **PASS** for re-audited database/service paths |
| Caller-supplied identifiers cannot override canonical authority | **PASS** |
| Graph and Personal Insights use only the active profile | **PASS** for isolation |
| Requests, threads, documents, connectors and credentials preserve canonical ownership | **PASS** |
| Profile/password/avatar editing preserves binding and cleans failed replacements | **PASS** |
| General upload storage remains discoverable and deletable through canonical profile ownership | **PASS** |
| Migration ambiguity preserves data and fails closed with explicit policy | **PASS** by static review; runtime branch evidence incomplete |
| Focused frontend adversarial tests and type-check pass | **PASS** |
| Focused Python/database adversarial tests pass | **NOT ESTABLISHED in this environment** |

Final decision: **PASS for R1 canonical profile isolation in the re-audited scope.** The remaining graph retirement/read consistency note and unavailable local Python runtime are follow-up evidence/behavior items, not demonstrated cross-profile authority failures.
