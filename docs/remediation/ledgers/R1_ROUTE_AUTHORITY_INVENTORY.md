# R1 Route Authority Inventory

Audited 17 July 2026 against every `frontend/app/api/**/route.ts` module. The machine-enforced copy of this inventory is `frontend/tests/r1-route-authority.test.ts`; a new route or exported method fails that test until classified.

Classification meanings:

- **public**: no session authority required. Public mutations still require their route-specific abuse/same-origin controls.
- **authenticated read**: canonical `requireApiSession` authority is required before reading state.
- **authenticated mutation**: canonical `requireApiSession` authority is required before work or mutation.
- **internal only**: callable only with service authority, never a browser session.
- **OAuth callback**: validates provider state/code rather than a pre-existing app session.

No current Next.js route is an internal-only endpoint or OAuth callback. Intelligence-service proxy routes below are authenticated browser endpoints; their downstream service calls remain subject to the separate internal-authority workstream.

## Method-level inventory

| Route | Method classification | Rationale |
|---|---|---|
| `auth/check-setup` | GET — public | Login/bootstrap discovery; returns setup state only. |
| `auth/login` | POST — public | Establishes a session from credentials. |
| `auth/logout` | POST — public | Idempotently clears even malformed sessions; same-origin enforcement remains required. |
| `auth/register` | POST — public | Creates the initial account/session. |
| `auth/session` | GET — authenticated read | Resolves current canonical authority. |
| `connectors/[[...path]]` | GET — authenticated read; POST/PUT/DELETE — authenticated mutation | Profile-owned connector definitions, instances and operations. |
| `execution` | POST — authenticated mutation | Invokes model/task execution and creates audit state. |
| `gdpr-agent/analyze-policy` | POST — authenticated mutation | Runs analysis and writes provenance. |
| `gdpr-agent/draft` | POST — authenticated mutation | Uses user identity/instructions and invokes the task router. |
| `graph` | GET — authenticated read | Reads the active profile's graph projection. |
| `graph/chat` | POST — authenticated mutation | Runs profile-bound typed graph queries/model work. |
| `graph/nodes` | POST/PUT/DELETE — authenticated mutation | Creates, updates or retires graph evidence. |
| `graph/nodes/bulk` | POST — authenticated mutation | Bulk graph evidence creation. |
| `graph/nodes/merge` | POST — authenticated mutation | Merges graph identities. |
| `graph/stats` | GET — authenticated read | Reveals graph state. |
| `graph/upsert-identity` | POST — authenticated mutation | Writes identity candidates. |
| `identities` | GET — authenticated read | Returns personal identity records. |
| `identities/account` | POST — authenticated mutation | Creates/updates an identity account. |
| `ingestion/benchmark-invoke` | POST — authenticated mutation | Invokes processing and reads execution records. |
| `ingestion/feature-adjudication` | POST — authenticated mutation | Mutates evidence adjudication state. |
| `ingestion/schema-interpretation` | POST — authenticated mutation | Runs ingestion interpretation. |
| `insights/[module]` | GET — authenticated read | Reads Personal Insights for the authority-derived profile. |
| `insights/context-events` | POST — authenticated mutation | Imports profile context events. |
| `insights/evidence/[id]` | GET — authenticated read | Reads evidence underlying Personal Insights. |
| `insights/media-analysis` | GET — authenticated read; POST — authenticated mutation | Reads settings or launches/persists media analysis. |
| `insights/media-location-confirmations` | POST — authenticated mutation | Confirms profile media/location evidence. |
| `n8n/analyze-policy` | POST — authenticated mutation | Invokes configured workflow infrastructure. |
| `n8n/test-imap` | POST — authenticated mutation | Tests stored mail infrastructure/credentials. |
| `onsit/bulk` | POST — authenticated mutation | Runs bulk discovery work. |
| `onsit/discover` | POST — authenticated mutation | Runs controller discovery. |
| `onsit/discover-dpo` | POST — authenticated mutation | Runs DPO discovery/model work. |
| `onsit/export` | GET — authenticated read | Exports stored ONSIT findings. |
| `onsit/extract-vendors` | POST — authenticated mutation | Extracts/persists vendor findings. |
| `onsit/findings/[id]` | GET — authenticated read; DELETE — authenticated mutation | Reads or removes a finding. |
| `onsit/send-bulk-emails` | POST — authenticated mutation | Sends external email and records state. |
| `onsit/status/[taskId]` | GET — authenticated read | Reads task and finding state. |
| `onsit/vendor-bulk-email` | POST — authenticated mutation | Sends external vendor email. |
| `onsit/vendor-domain-search` | POST — authenticated mutation | Uses configured discovery credentials. |
| `onsit/vendor-dpo-discovery` | POST — authenticated mutation | Uses configured discovery/model services. |
| `policy/check` | POST — authenticated mutation | Acquires and analyses a user-supplied policy URL. |
| `request-threads` | GET — authenticated read; POST — authenticated mutation | Reads/updates GDPR request lifecycle conversations. |
| `request-threads/[id]/chat` | GET — authenticated read; POST — authenticated mutation | Reads/writes chat for an authority-owned request. |
| `requests/[id]` | DELETE — authenticated mutation | Deletes an authority-owned request and children. |
| `requests/[id]/logs` | GET — authenticated read | Reads activity for an authority-owned request. |
| `retention/[[...path]]` | GET — authenticated read; POST — authenticated mutation | Reads or changes profile retention state. |
| `settings/ai-credentials` | GET — authenticated read; POST — authenticated mutation | Reveals presence or stores secret AI credentials. |
| `settings/ai-models` | GET — authenticated read | Discovers models using configured credentials. |
| `settings/api-credentials` | GET — authenticated read; POST — authenticated mutation | Reveals presence or stores ONSIT credentials. |
| `settings/engine-health/[engineId]` | GET — authenticated read | Reveals configured execution infrastructure. |
| `settings/execution-audit` | GET — authenticated read | Reads model execution audit records. |
| `settings/id-documents` | GET — authenticated read; POST/DELETE — authenticated mutation | Profile-owned identity documents. |
| `settings/model-preferences` | GET — authenticated read; POST — authenticated mutation | Reads/changes model preferences. |
| `settings/n8n-webhooks` | GET — authenticated read; POST — authenticated mutation | Reads/changes workflow infrastructure URLs. |
| `settings/processing` | GET — authenticated read; POST — authenticated mutation | Reads/changes processing mode. |
| `settings/profile` | GET — authenticated read; POST/PUT — authenticated mutation | Canonical account/profile data (owned by profile workstream). |
| `settings/profile/password` | POST — authenticated mutation | Changes the authenticated account password. |
| `settings/task-routes` | GET — authenticated read; POST — authenticated mutation | Reads/changes execution routing. |
| `settings/workflows` | GET — authenticated read; POST — authenticated mutation | Reads/changes workflow preferences. |
| `upload` | GET — authenticated read; POST/PATCH/DELETE — authenticated mutation | Reads or changes uploaded personal data. |
| `upload/process` | POST/PUT — authenticated mutation | Processes an uploaded personal-data artifact. |
| `upload/scan` | POST — authenticated mutation | Batch-processes pending uploaded data. |
| `workflows/inbox-monitor` | POST — authenticated mutation | Reads mailbox data and changes workflow state. |

## Guard and authority changes

- Applied `requireApiSession` before work in every sensitive route in this inventory. Public authentication/bootstrap routes are the only exceptions.
- Replaced the Personal Insights `ORDER BY created_at LIMIT 1` subject fallback. `subject_id` is now always overwritten with `authority.profileId`, so a caller-supplied subject cannot become authority.
- Scoped ID-document list/create/delete operations directly by `authority.profileId`.
- Scoped request delete, request logs, and request chat through `access_requests.profile_id`. A foreign object ID returns the same not-found result as an absent ID.
- Scoped `received_data` list/create/update/delete/process/scan operations by `authority.profileId`, and verifies any caller-supplied request parent before associating an upload.
- Scoped `request_threads` lookup/create/final reads by `authority.profileId`; standalone thread inserts derive ownership from authority.
- Graph reads already bind Cypher queries to `authority.profileId`; connector and retention proxies already derive downstream profile headers from authority.

## Explicit unresolved ownership and proxy concerns

These were not weakened or hidden to satisfy the guard test:

1. Several authenticated proxies still call the intelligence service without `intelligenceAuthorityHeaders`, notably legacy graph mutation and Personal Insights proxy routes. Internal-authority wiring is owned by the separate R1 internal-service task; browser session guards here do not substitute for it.
2. Global settings/data roots (`app_settings`, execution/model/workflow preferences, `insight_settings`, and parts of ONSIT) are installation-wide in the current schema. They are authenticated, but making them profile-specific would require product policy and shared schema decisions.

## Verification

- `pnpm typecheck` — passed (`tsc --noEmit`, exit 0, 5.1 s).
- `pnpm exec vitest run tests/r1-route-authority.test.ts` — passed: 1 file, 3 tests, 0 failures (875 ms).
- The Python mirror `tests/integration/r1_route_coverage_test.py` was added for repository-level CI but was not runnable in this shell because no Python runtime is installed.
