# R2 completion handoff — updated 2026-08-13

## Status

R2 is implemented and independently accepted. This file replaces the July pause state and is the pickup point for the next remediation stage. The worktree still contains the broader pre-existing R0/R1 changes; preserve them.

## What is now true

- `requests` is the canonical profile-scoped request model; the compatibility view is read-only.
- Explicit lifecycle timestamps, guarded transitions, and immutable provenance events are enforced.
- Historical/null/unknown request states are reconciled by migration 032 without fabricating legal dates.
- Migration 033 stores extension justification separately. Applied migration 031 is unchanged and checksum-compatible.
- The deadline engine uses UK-local calendar semantics, working-day adjustments, identity/clarification rules, and complete validated extension evidence.
- Valid extensions atomically persist the screened effective `deadline_at` used by the dashboard.
- Cancellation retains request history and evidence. No physical request deletion remains.
- Request, child-record, request-thread, outbound, and email-draft SQL is behind the canonical repositories and profile scoped.
- All legacy N8N JSON workflows are explicitly inactive; request adapters are not selectable.

## Acceptance evidence

- Independent migration/request-domain SQL audit: **PASS**.
- Independent lifecycle/deadline audit: **PASS** (48/48 focused checks).
- Disposable migration fixtures: **4/4 passed**.
- Query matrix passed against:
  1. a clean database;
  2. a representative pre-031 historical upgrade;
  3. a database with migration 031 already recorded.
- On every matrix path, TypeScript and Python real-PostgreSQL repository integration passed.
- Authenticated browser acceptance passed for Home and Requests against a disposable database with no console errors.
- Frontend typecheck, 128-test full suite, and production build passed. The one gated repository integration is covered by the three-path matrix.
- The Python full run produced 539 passes and 3 skips. Its three graph failures were solely an unresolved container hostname from the host runner; rerunning those exact tests against mapped local Neo4j passed 3/3.
- No real account or real request data was used; the offered `test` credentials were deliberately not touched.

## Safe pickup

Proceed to the next plan stage only after reviewing `docs/remediation/ledgers/R2_IMPLEMENTATION_LEDGER.md`. Do not edit historical migration 031. Use `scripts/r2-query-matrix.py` whenever request-domain SQL or migrations change; it creates only guarded `r2_query_*` databases and drops them afterward.

## Key files

- `docs/remediation/ledgers/R2_IMPLEMENTATION_LEDGER.md`
- `database/migrations/030a_r2_legacy_request_preflight.sql`
- `database/migrations/032_r2_request_lifecycle_hardening.sql`
- `database/migrations/033_r2_deadline_extension_evidence.sql`
- `frontend/lib/requests/`
- `intelligence/request_domain/repository.py`
- `scripts/r2-query-matrix.py`
