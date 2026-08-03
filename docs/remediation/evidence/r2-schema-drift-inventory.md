# R2 schema-drift inventory (read-only)

Date: 2026-07-18  
Scope: ordered migrations, the running PostgreSQL catalogue, compatibility views, request-domain SQL in `frontend/**` and `intelligence/**`, and TypeScript/Python request models.  
No schema, application, or database data was changed by this inventory.

## Executive findings

1. The checked-out migration chain ends at `030_r1_profile_ownership.sql`, but the running database's `gdpr_schema_migrations` history ends at `029`. Consequently the live `requests`, `received_data`, and `request_threads` objects do not have `profile_id`; the live `access_requests` view also lacks it. Current authenticated queries that require these columns cannot execute against that database.
2. Neither the ordered source schema nor the live schema contains the R2 request lifecycle contract. `requests` lacks `updated_at`, `sent_at`, `controller_received_at`, identity/clarification timestamps, `response_received_at`, `completed_at`, `deadline_at`, `deadline_basis`, extension timestamps, and `next_action_at`. It has ambiguous legacy `deadline_date` and `next_action_date` instead (`database/migrations/001_legacy_application_schema.sql:34-35`).
3. There is no updated-at trigger for `requests` in migrations and none in the live catalogue. Python nevertheless writes `requests.updated_at` (`intelligence/db/postgres.py:87-90`), and dashboard SQL reads it (`frontend/lib/actions/dashboard.ts:198-215`), so those queries fail even after source migration `030` is applied.
4. `access_requests` is still a primary-read and write dependency. The only compatibility write is `DELETE FROM access_requests` at `frontend/app/api/requests/[id]/route.ts:54`. Primary/ownership reads are listed below. The view is a simple, automatically updatable view in both migration definitions, so it is not actually read-only.
5. Request lifecycle data is split across `requests` and the standalone `request_threads` shadow domain. `request_threads` owns `sent_at` and `response_received_at` (`database/migrations/004_route_schema_reconciliation.sql:16-20`) and the API updates them (`frontend/app/api/request-threads/route.ts:171-196`), but those writes do not update canonical `requests`.
6. Direct request status writes do not create the required immutable transition event. `request_events` has only `event_type`, description, and date (`database/migrations/001_legacy_application_schema.sql:108-113`); it has no actor, prior state, next state, reason, or evidence reference, and it is not append-only.

## Ordered migrations versus live catalogue

### `requests`

The baseline migration defines `id`, company fields, `status`, `request_type`, `progress`, `data_volume_mb`, `next_action_date`, `deadline_date`, data-period fields, `notes`, and `created_at` at `database/migrations/001_legacy_application_schema.sql:25-40`. Source migration `030` adds and constrains `profile_id` at `database/migrations/030_r1_profile_ownership.sql:8,32-36,103,132-134,172`.

Live catalogue evidence:

- Present: the baseline fields through `created_at`.
- Missing: `profile_id` (because live history stops at `029`).
- Missing from both live and ordered source: every distinct R2 lifecycle field except `created_at`; there is no `updated_at` trigger.
- Live `created_at` is nullable even though source baseline says `NOT NULL` (`001:39`). `CREATE TABLE IF NOT EXISTS` did not reconcile the pre-existing table constraint.
- Legacy renames/semantic mismatches: `deadline_date` versus planned `deadline_at`; `next_action_date` versus planned `next_action_at`. Neither legacy field records basis, uncertainty, receipt evidence, or extension evidence.

### `access_requests`

- Baseline view exposes only seven columns at `database/migrations/001_legacy_application_schema.sql:211-212`.
- Source `030` recreates it with `profile_id` at `database/migrations/030_r1_profile_ownership.sql:178-180`.
- Live view still has the baseline seven columns and no `profile_id`, confirming `030` is unapplied.
- Neither definition marks the compatibility object non-canonical or prevents inserts/updates/deletes.

### Related request tables

- `request_events` cannot represent the R2 immutable transition contract (`001:108-113`).
- `request_threads` duplicates company/domain/status and lifecycle timestamps rather than serving purely as a child of `requests`; `request_id` is nullable (`001:195-200`, `004:4-26`), and the route can create a thread with no request link (`frontend/app/api/request-threads/route.ts:95-108`).
- `messages`, `request_chat_messages`, and `request_events` have no direct `profile_id`; ownership must always be proven through a canonical request join.
- `received_data` source gains `profile_id` only in migration `030` (`030:9,38-42,104,136-138,173`); the running object lacks it.

## Query/schema incompatibilities

These are concrete missing-column or renamed-column failures against the ordered schema (and therefore also against the observed live schema unless noted):

| Consumer | Finding |
|---|---|
| `frontend/lib/actions/dashboard.ts:198-215` | Reads missing `requests.updated_at`; also treats `updated_at-created_at` as response duration and fixed 30-day compliance evidence. |
| `intelligence/db/postgres.py:87-90` | Writes missing `requests.updated_at`; write is unscoped by `profile_id`. |
| `frontend/lib/rlm/tools.ts:71-73` | Reads `access_requests.policy_url` and `access_requests.deadline`; neither exists. The nearest legacy request field is `deadline_date`, while `policy_url` exists only on `request_threads`. Query is unscoped. |
| `frontend/lib/rlm/tools.ts:82` | Reads `policy_analyses.request_id`, which no migration defines. |
| `frontend/lib/rlm/tools.ts:257-264,402-408` | Reads `received_data.file_size` and `graph_synced`; schema names are `file_size_mb` and `graph_ingested`. Queries are unscoped. |
| `frontend/lib/rlm/retriever.ts:195-215` | Reads missing `received_data.entities` and `received_data.created_at`; schema has competing `entities_extracted` and `extracted_entities`, and only `date_received`. Query is unscoped. |
| `frontend/lib/actions/data.ts:29,74-87` | TS model and insert require missing `received_data.download_url`. |
| All queries requiring `requests.profile_id`, `received_data.profile_id`, `request_threads.profile_id`, or `access_requests.profile_id` | Valid against checked-out source only after `030`; invalid against the currently running database because live migration history stops at `029`. |

## `access_requests` consumers

Read consumers:

- `frontend/lib/rlm/tools.ts:71-73` — primary request-detail read; unscoped and selects nonexistent columns.
- `frontend/app/api/upload/route.ts:33` — ownership/existence read.
- `frontend/app/api/requests/[id]/route.ts:31` — ownership/existence read before deletion.
- `frontend/app/api/requests/[id]/logs/route.ts:45` — ownership/existence read.
- `frontend/app/api/request-threads/[id]/chat/route.ts:17,67` — ownership/existence reads for GET and POST.

Write consumers:

- `frontend/app/api/requests/[id]/route.ts:54` — canonical delete is performed through the compatibility view. This violates the R2 no-write requirement. Child deletes at lines 43-48 are separately unscoped and are not wrapped with the ownership check in one transaction.

There are no Python `access_requests` consumers.

## Scope and repository-boundary drift

Profile-scoped canonical request reads/writes exist in `frontend/lib/actions/requests.ts`, `request-detail.ts`, `messages.ts`, `dashboard.ts`, `policy-analysis.ts`, `requests/submit.ts`, `frontend/lib/connectors/email.ts`, the upload routes, and several Python APIs. However, there is no single request repository/service boundary; SQL remains distributed across actions, API routes, connector code, RLM tools, ingestion, retention, and privacy hypotheses.

Concrete unscoped or indirectly scoped request-domain operations include:

- `intelligence/db/postgres.py:64-70,87-94` — message insert and request update accept only a request UUID; no profile authority is required.
- `intelligence/privacy/hypotheses.py:73-85` — transaction creates `requests` without `profile_id`; after migration `030` this violates the non-null constraint even though the hypothesis itself has a profile.
- `intelligence/ingestion/bulk.py:384-394` — received-data update by ID without `profile_id`.
- `frontend/lib/rlm/tools.ts:71-89,257-264,309-312,402-408` and `frontend/lib/rlm/retriever.ts:205-216` — all request/file reads are unscoped.
- `frontend/app/api/requests/[id]/route.ts:43-48` — child-table deletes use only caller-supplied request ID after a separate view lookup; no transaction prevents a check/use race.
- `frontend/app/api/requests/[id]/logs/route.ts:53-78` and `frontend/app/api/request-threads/[id]/chat/route.ts:26-28,80-81,103-110` — child reads/writes rely on a preceding separate ownership query instead of a scoped join/insert-select or repository transaction.

## Lifecycle and model mismatches

- The canonical TS `Request` interface at `frontend/lib/actions/requests.ts:6-21` encodes only legacy states (`draft`, `scheduled`, `processing`, `action_required`, `completed`) and legacy `next_action_date`/`deadline_date`. It omits `profile_id`, `updated_at`, every explicit lifecycle timestamp, deadline basis, and extension evidence.
- `ManualRequestInput` at `frontend/lib/actions/requests.ts:109-117` uses `date_started`, but `createManualRequest` writes it to `created_at` at lines 129-148. A start/sent date is therefore collapsed into creation time.
- `RequestPayload` at `frontend/lib/actions/requests/submit.ts:21-28` contains no explicit receipt/lifecycle evidence. Submission calculates `now + 30 days` at lines 124-126 and stores it in `deadline_date` at lines 130-158, rather than using calendar-month arithmetic from an evidence-backed controller receipt date.
- Status writes at `frontend/lib/actions/request-detail.ts:36-50`, `frontend/lib/actions/requests/submit.ts:284,367,407`, and Python request creation paths bypass a state-transition service and do not create immutable transition events.
- No Python model represents the canonical request lifecycle. Python request models found under `intelligence/api/**` are transport/job request bodies, not the persisted GDPR request domain.
- `request_threads.status` uses a separate vocabulary (`initialized`, `drafted`, `sent`, etc.) and is advanced independently at `frontend/app/api/request-threads/route.ts:118-219`; there is no mapping or synchronization with `requests.status`.

## Unsupported dashboard semantics

- `frontend/lib/actions/dashboard.ts:184-190` defines company compliance as request completion rate, derives data minimization from the count of top holders, and folds both into a privacy score.
- `frontend/lib/actions/dashboard.ts:146-157` treats request row counts as data points and converts those counts to holder risk.
- `frontend/lib/actions/dashboard.ts:192-221` uses `updated_at-created_at` as response time and a fixed `>30` days test as missed-deadline evidence.
- `frontend/lib/actions/dashboard.ts:252-253` reports every completed request as a deadline met unless included in the contradictory missed count.
- `frontend/components/dashboard/ComplianceGauge.tsx:21-35` labels those derived values “GDPR Compliance” and hardcodes a 30-day limit.

## Suggested static invariants

1. Fail if application code outside a named compatibility adapter contains `access_requests`; separately fail on every `INSERT`, `UPDATE`, or `DELETE` targeting the view.
2. Fail if SQL touching canonical request roots is outside one repository directory. Permit only migrations, fixtures, and repository tests.
3. Extract/prepare every registered Next.js and Python request SQL statement against both a clean migrated schema and historical upgrade fixtures; fail on missing columns or parameter-count mismatch.
4. Assert the canonical request column set, types, nullability, indexes, foreign key, and updated-at trigger from `information_schema`/`pg_catalog` after clean and upgrade migrations.
5. Assert migration filenames are strictly ordered, checksums of applied migrations are stable, the latest source migration appears in history, and a second application produces no schema/data diff.
6. Fail on direct `UPDATE requests SET status` outside the transition repository; require a transaction that inserts an event with actor, old state, new state, timestamp, reason, and optional evidence reference.
7. Make request events append-only in schema and assert application roles cannot update/delete them.
8. Fail request-domain SQL lacking `profile_id` authority or an ownership join through `requests`; include child reads, writes, and deletes.
9. Fail on fixed-day deadline arithmetic (`setDate(... + 30)`, `INTERVAL '30 days'`, or equivalent) and on use of `updated_at`/local completion as legal receipt, response, completion, or compliance evidence.
10. Contract-test TS and Python lifecycle/status models against one shared canonical state/field fixture, including preservation/mapping of historical states.
11. Assert the compatibility view is explicitly read-only (privileges and/or trigger), exposes only documented transition columns, and is never treated as canonical.
12. Fail dashboard code that labels request counts/completion ratios as risk, privacy, compliance, data points, response time, or deadlines met without a grounded deadline-engine/artefact/execution record.

## Verification performed

- Static recursive searches with `rg` across `database/**`, `frontend/**`, `intelligence/**`, and `tests/**`.
- Read-only live PostgreSQL catalog queries for columns, view definition, triggers, object kinds, request status counts, and migration history.
- Live evidence showed `gdpr_schema_migrations` through `029`, no `requests` triggers, and the seven-column baseline `access_requests` view.
- An existing static pytest selection was attempted. Host Python is unavailable (Windows Store stub). Running tests inside the existing intelligence container used `/tests` without the repository sibling paths expected by those tests, producing invalid path-root failures; an isolated image lacked pytest. No test result is therefore claimed from that attempt.

