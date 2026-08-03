# R2 implementation ledger

**Branch / starting commit:** `main` / `67e50b85daa923366d3bec80db6582edcc3ba134`  
**Start date:** 2026-07-18  
**Decision owner:** lead agent

## Canonical decisions

- `requests` is the sole canonical profile-owned GDPR request root. `access_requests` is a temporary read-only compatibility view and canonical application code must not depend on it.
- `updated_at` is operational metadata maintained by a database trigger. It is never evidence of sending, controller receipt, response receipt, completion, or legal timeliness.
- No missing legal or lifecycle timestamp is fabricated. Legacy `deadline_date` is retained but is not copied into `deadline_at`; legacy `next_action_date` may be copied to `next_action_at` because it has the same operational meaning.
- Canonical states are `draft`, `ready_for_review`, `scheduled`, `sent`, `awaiting_response`, `identity_action_required`, `clarification_action_required`, `response_received`, `processing_response`, `completed`, `closed_incomplete`, and `cancelled`.
- Historical `processing` and `action_required` values are preserved and mapped at the service boundary; they are not bulk rewritten.
- Every state transition is atomic and creates an append-only event with actor, previous state, next state, timestamp, reason, and optional evidence reference.
- Deadline screening uses one calendar month from explicit controller receipt evidence. A sent-only result is estimated. Identity and clarification pauses remain distinct. Extensions require both notice and deadline records. Response receipt, not local completion, is used for timeliness screening.

## Delegation map

| Workstream | Bounded owner | Owned paths | Lead-retained decisions |
|---|---|---|---|
| Schema drift inventory | `schema_inventory` | read-only repository and live catalogue; evidence report | canonical schema and interpretation |
| Predecessor audit | `predecessor_audit` | read-only R0/R1 tests/runtime probes | blocking-regression decision and repairs |
| Request access inventory | `request_surface` | read-only frontend/Python request surfaces | repository boundary and migration order |
| Ordered migration and fixtures | `schema_inventory` follow-up | migration 031 and R2 migration fixture | migration order, backfill, compatibility, lifecycle semantics |
| Deadline engine | `request_surface` follow-up | deadline module and focused tests | legal-screening semantics |
| Request repository core | `request_surface` follow-up | canonical repository/service/types and focused tests | cross-service wiring and call-site acceptance |
| Dashboard repair | `dashboard_repair` | dashboard action, Home components, focused tests | final dashboard claim review |
| Clean/upgrade/lifecycle verification | pending bounded assignment | focused fixtures/tests | final acceptance |
| Independent audits | pending non-implementing agents | evidence reports only | repairs and final judgement |

## Predecessor evidence

- R1 frontend authority/session/profile tests: 57 focused checks passed in the lead run; the independent predecessor run reported all 87 frontend tests passing.
- Focused R1 Python/static integration: 38 passed and 7 database-dependent skips before a database URL was supplied; migration fixtures then reported 6 passed and the expected R2 `updated_at` xfail.
- Live migration history initially stopped at 029. Ordered migration 030 was applied successfully through `database/migrate.py` before R2 implementation.
- The existing runtime lacked distinct usable R1 secrets and returned 503 for malformed sessions. Affected local containers were recreated with three distinct generated test secrets; protected probes then returned 401 and cleared the invalid cookie.
- R0 remains formally unaccepted in its historical acceptance document because managed browser/full-suite evidence is incomplete. The known later-plan static failures remain explicit and are not reclassified as R2 work.

## Evidence ledger

| Requirement | Code/migration evidence | Automated evidence | Runtime evidence | Status |
|---|---|---|---|---|
| Schema/query inventory | `docs/remediation/evidence/r2-schema-drift-inventory.md` | static recursive inventory | live catalogue compared through migration 029, then 030 applied | COMPLETE |
| Explicit lifecycle schema and trigger | pending migration 031 | pending clean/upgrade fixtures | pending | IN PROGRESS |
| Canonical repository and compatibility policy | pending | pending | pending | IN PROGRESS |
| Immutable transition events | pending | pending | pending | IN PROGRESS |
| Deterministic deadline engine | `frontend/lib/requests/deadline.ts` | 19 focused Vitest checks; typecheck passed | pure deterministic engine | COMPLETE |
| Grounded dashboard metrics | pending | pending | pending authenticated Home | IN PROGRESS |
| Clean install, upgrade and query execution | pending | pending | pending | NOT STARTED |
| Independent migration/SQL/lifecycle/deadline audits | pending | pending | n/a | NOT STARTED |

