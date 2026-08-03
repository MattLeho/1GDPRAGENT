# R1 profile and SQL ownership audit

Audited owned production paths:

- `frontend/app/api/settings/profile/**`
- `frontend/lib/actions/**`
- `frontend/lib/connectors/email.ts`

## Implemented authority boundaries

Profile GET, PUT/POST and password changes resolve `userId` and `profileId` from the canonical session authority. Queries bind `user_profiles.id` to `user_profiles.default_profile_id`/`profiles.id`; no endpoint accepts a profile identifier or creates a replacement account/profile. Identity updates change only username, email, the optional picture URL and the linked `profiles.identity_name`. They never assign `password_hash` or `default_profile_id`. Password changes update only the authority-bound account.

Avatar uploads allow JPEG, PNG, WebP and GIF up to 5 MB, ignore the caller filename, use an exclusive random filename, remove the new file when the transaction fails, and remove a superseded managed file only after commit. External or malformed old URLs are never treated as filesystem paths. Existing data files were not destructively cleaned up.

Server actions now resolve authority internally. `requests` and `received_data` are directly owned roots. `messages`, `request_details`, `request_events` and email drafts prove ownership through an `EXISTS`, `JOIN`, or `INSERT ... SELECT` against `requests.profile_id`. Request and received-data creation write the session profile directly. Reads and mutations return no row for a foreign object ID and therefore do not distinguish a foreign ID from a missing one.

Email settings and connector credentials are directly keyed by `profile_id`. Credential rotation uses `(profile_id, connector_key, account_key)` and all settings/credential reads, updates and deletes include the canonical profile. The public settings shape excludes ciphertext and decrypted secrets.

`policy_analyses` remains a shared company-policy cache rather than personal/profile-owned data. Its server actions require authentication. The request-to-policy lookup first resolves the request with `requests.profile_id`, then reads the shared cache.

## Schema decisions owned by the lead

The implementation depends on `database/migrations/030_r1_profile_ownership.sql` adding non-null ownership to `requests`, `received_data`, `request_threads`, `id_documents`, `connector_credentials` and `email_settings`, plus the composite connector credential uniqueness contract. This subtask did not edit migrations.

The following tables do not have direct `profile_id` and are intentionally scoped through a verified request parent: `messages`, `request_details`, `request_events`, `workflow_logs`, `email_transport_drafts`, and `outbound_messages`. Adding redundant direct ownership to those tables is a lead schema decision, not required for isolation while their request foreign key remains authoritative.

Neo4j totals in `frontend/lib/actions/dashboard.ts` are not SQL and the graph model's profile-label/property contract is outside this subtask. The lead should confirm that the graph projection/query workstream supplies profile-isolated counts before treating those two dashboard fields as accepted.

## Static audit result

No `LIMIT 1` first-user/first-profile shortcut remains in the owned production paths. Remaining `LIMIT` clauses select a bounded latest policy analysis, request history, or activity list after the relevant authority boundary; they are not ownership resolution.

Focused tests:

- `frontend/tests/r1-profile-ownership.test.ts`
- `frontend/tests/r1-profile-sql-scope.test.ts`

The local PowerShell execution attempt on 17 July 2026 could not start Vitest or TypeScript because `node` was not available on `PATH` (`'node' is not recognized as an internal or external command`). The exact attempted commands were `pnpm test -- tests/r1-profile-ownership.test.ts` and `pnpm typecheck`; both exited 1 before loading project code. These tests still require execution in the lead's Node-enabled environment.
