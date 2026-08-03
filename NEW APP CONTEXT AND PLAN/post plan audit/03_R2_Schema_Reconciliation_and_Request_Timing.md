# R2 — Schema Reconciliation and Deterministic Request Timing

## Goal

Eliminate migration/query drift, make `requests` the canonical profile-scoped request domain and replace ambiguous response/deadline calculations with explicit lifecycle dates.


## Programme rules

- Current code and runtime behaviour outrank previous completion reports.
- Preserve user data, provenance and migration history.
- PostgreSQL remains canonical; Neo4j remains a rebuildable projection.
- Model output cannot silently become graph truth.
- Every model call must use the canonical Task Router and create an execution record.
- Every protected operation must be scoped to the authenticated canonical profile.
- Distinguish unknown, unconfigured, unavailable, blocked and failed.
- Do not introduce hardcoded Google execution, synthetic graph data or invented compliance metrics.
- Implementation agents cannot be the sole final auditors of their own work.


## Dependencies

- R0 and R1 accepted.
- Canonical `profile_id` authority is available.

## Lead-agent ownership

The lead agent owns request schema, migration/backfill policy, compatibility-view policy, state semantics, deadline semantics, data preservation and removal of misleading metrics.

## Subagent delegation

### A — Schema drift inventory

Compare live schema, ordered migrations, all SQL strings, compatibility views and TypeScript/Python models. Return every missing, renamed or semantically mismatched field.

### B — Request migration

Add canonical ownership, timestamps, triggers, indexes and conservative backfills. The lead reviews every defaulting or destructive decision.

### C — Request repository

Create one request-domain service/repository and migrate dashboard, list, detail, chat, events, uploads, outbound messages and response processing.

### D — Deadline engine

Implement evidence-backed UK GDPR timing as a screening tool, preserving unknowns.

### E — Dashboard repair

Execute and repair all dashboard SQL. Remove unsupported risk/compliance calculations.

### F — Fixtures/tests

Build clean, legacy and current fixtures with realistic lifecycle dates and related rows.

## Canonical request fields

Audit names before final migration, but implement equivalent semantics:

```text
id
profile_id
company_name
company_url
domain
request_type
status
progress
created_at
updated_at
sent_at
controller_received_at
identity_requested_at
identity_verified_at
clarification_requested_at
clarification_resolved_at
response_received_at
completed_at
deadline_at
deadline_basis
extension_notified_at
extension_deadline_at
next_action_at
notes
```

Use `TIMESTAMPTZ`.

Do not backfill missing legal dates by treating `updated_at` as controller receipt or response.

## State model

Define and validate transitions such as:

```text
draft
ready_for_review
scheduled
sent
awaiting_response
identity_action_required
clarification_action_required
response_received
processing_response
completed
closed_incomplete
cancelled
```

Preserve historical statuses through a mapping layer.

Every transition records immutable actor, previous state, next state, timestamp, reason and evidence reference where available.

## Updated-at trigger

Create a shared trigger and apply it to mutable operational tables. `updated_at` remains an operational field, not a legal-domain timestamp.

## Compatibility view

`access_requests` may remain temporarily as read-only compatibility.

Requirements:

- document non-canonical status;
- remove write consumers;
- keep required read columns while migrating;
- add a static invariant that new canonical code targets `requests`.

## Deadline engine

Inputs must be explicit. Output:

```text
deadline_state
deadline_at
basis
input_dates
uncertainties
human_review_required
```

States:

```text
known
estimated
paused_identity
paused_clarification
extended
overdue
completed_on_time
completed_late
unknown
```

Use calendar-month arithmetic, not a fixed `30` days. Extension requires recorded evidence. Never infer company compliance from local completion status.

## Dashboard changes

Remove or relabel:

- request-count-derived risk;
- completion-rate-as-compliance;
- request count as data-point count;
- every completed request as deadline met;
- `updated_at - created_at` as response time.

Use grounded replacements only:

- requests by state;
- known upcoming deadlines;
- responses actually received;
- real artefact volume;
- unknown deadline count;
- failed workflows.

## Required tests

### Migration

- clean install applies twice;
- legacy request without `updated_at`;
- completed request with only `created_at`;
- related chat, received data, messages, workflow logs and events survive;
- ownership is backfilled safely.

### Query execution

- execute every request-domain SQL query against the migrated schema;
- authenticated Home loads without console SQL errors;
- no canonical write targets `access_requests`;
- profile scope is enforced.

### Deadline edge cases

- calendar-month boundaries;
- month-end;
- leap year;
- identity pause;
- clarification pause;
- extension;
- missing received date;
- completed on time/late;
- disputed dates.

## Definition of done

- No query references a missing request column.
- `requests` is canonical.
- One repository/service owns request-domain access.
- `updated_at` is trigger-maintained.
- Legal dates are distinct.
- Home loads on clean and upgraded databases.
- Misleading metrics are removed or replaced.
- Deadline outputs expose basis and uncertainty.
- Independent migration and semantics audits pass.

## Paste-ready `/goal`

```text
Execute R2 — Schema Reconciliation and Deterministic Request Timing.

Audit R0 and R1 first. Compare the migrated schema, every migration and every SQL query. Establish `requests` as the canonical profile-scoped request table, add distinct lifecycle timestamps and an updated-at trigger, preserve historical data, repair compatibility views and move request access behind one repository/service boundary.

Implement a deterministic evidence-backed deadline engine using calendar-month arithmetic. Remove or relabel dashboard metrics that infer compliance, risk or response time from unrelated fields.

Delegate schema inventory, migration, repository refactoring, deadline logic, dashboard repair and fixtures to bounded subagents. Keep migration policy, backfills, state semantics and final data-preservation judgement under the lead agent.

Before completion, execute all request queries against clean and upgraded databases, run deadline edge cases, load Home in authenticated Playwright and commission independent migration and semantics audits.
```
