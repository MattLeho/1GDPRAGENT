# R4 — Connector Onboarding and Live Synchronisation

## Goal

Turn the connector framework into secure, usable onboarding for browser history, Gmail, Outlook/Microsoft 365 and advanced IMAP/SMTP, with resumable backfill, incremental sync, token rotation, workers and truthful operational status.


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

- R0–R2 accepted.
- R1 authority is stable.
- R3 credential interface is frozen or merged before OAuth token storage.

## Lead-agent ownership

The lead agent owns connector lifecycle, permission semantics, OAuth state/token security, credential integration, ingestion-bridge invariants, cursor/scheduler semantics, destructive-capability separation and cross-service integration.

## Subagent delegation

### A — Lifecycle/contracts

Define provider-neutral states, permissions, cursors, health and errors.

### B — Gmail

Implement OAuth and Gmail API acquisition.

### C — Outlook

Implement OAuth/PKCE and Microsoft Graph mail acquisition.

### D — Browser extension

Package, guide installation, pair and test the Chromium extension/local bridge.

### E — Advanced IMAP/SMTP

Retain standards-based setup with clear scopes and provider presets.

### F — Celery/scheduler

Repair encryption-key propagation, recurring dispatch, retries, locks and next-sync state.

### G — Connector settings UX

Build guided provider cards, permission review and recovery states.

### H — Security/protocol tests

Own OAuth replay, revocation, scope and provider fixture tests.

## Lifecycle states

```text
not_configured
authorising
authentication_required
connecting
connected
syncing
degraded
paused
revoked
disconnected
```

Expose:

```text
last_successful_sync
last_attempted_sync
next_sync
backfill_status
cursor_summary
records_ingested
bytes_ingested
last_error
credential_status
permission_summary
```

## Gmail OAuth and sync

Implement:

- authorisation code flow;
- PKCE where applicable;
- signed state bound to profile and connector intent;
- strict callback validation;
- server-side token exchange;
- encrypted refresh token;
- access-token rotation;
- revoked-token handling.

Collection levels:

```text
metadata only
headers and subject
text body
attachments
```

Use least privilege. A read connector must not request send/delete scopes.

Synchronisation:

- bounded initial backfill;
- Gmail history continuation;
- label/mailbox selection;
- message and attachment lineage;
- provider-ID and content-hash deduplication;
- resumable checkpoints;
- rate-limit handling.

## Outlook/Microsoft 365

Implement:

- Microsoft identity OAuth;
- PKCE;
- delegated Graph permissions;
- folder selection;
- initial pagination;
- delta continuation;
- message/attachment lineage;
- refresh and revoked-consent handling;
- retry and rate-limit behaviour.

## Browser history

A webpage cannot read history directly. The extension must request History permission.

Guided flow:

```text
Connect browser history
→ detect supported Chromium browser where possible
→ obtain packaged extension
→ guided install or Load unpacked
→ create one-time pairing
→ transfer pairing payload where technically possible
→ request History permission inside extension
→ verify local bridge
→ initial backfill
→ display imported visits and last sync
```

Keep bridge localhost-only by default. Page content, forms, passwords, payments and cookies remain excluded.

## IMAP/SMTP

Retain as Advanced:

- provider presets;
- app-password guidance;
- secure TLS defaults;
- explicit read scope;
- SMTP transport separation;
- connection testing;
- credential rotation;
- authentication-required state.

Do not represent IMAP as OAuth.

## Folder/export connectors

Do not imply that a browser text field can access any host path in Docker. Use approved upload/import, mounted-root selection or a local helper.

## Worker credential repair

Next.js, Python and Celery must use the same production `CREDENTIALS_ENCRYPTION_KEY`. Remove fallback secrets. Migrate old ciphertext or mark `needs_reentry`.

## Ingestion invariant

```text
provider record
→ ConnectorRawRecord
→ ConnectorIngestionBridge
→ SourceArtifact / EvidenceLocator / ActivityEvent
→ cursor advances only after durable ingestion
```

No connector writes interests or graph facts.

## Scheduler

Implement recurring dispatch, backoff, per-instance lock, idempotent retry, missed-run recovery, profile scope, pause/resume and visible next-run state.

## Settings UX

Top cards:

```text
Gmail
Outlook / Microsoft 365
Browser history
IMAP / SMTP — Advanced
AI conversation exports
Files and folders
Photos and media
```

Show collection scope, exclusions, privacy implications, connect action, state, last sync, recovery and disconnect consequences.

## Required tests

### OAuth

- state tampering;
- replay;
- wrong profile;
- expired state;
- token rotation;
- revoked refresh token;
- scope mismatch;
- reconnect.

### Gmail

- backfill;
- history continuation;
- duplicates;
- attachment lineage;
- rate limit;
- permission reduction.

### Microsoft

- pagination;
- delta continuation;
- changed/removed items;
- attachments;
- refresh;
- revoked consent.

### Browser

- extension build;
- one-time pairing;
- replay rejection;
- permission denial;
- queue persistence;
- reconnect;
- backfill/incremental;
- page-content rejection.

### Worker

- Celery decrypts the credential;
- scheduled sync runs;
- cursor waits for durable ingestion;
- retry does not duplicate;
- restart resumes.

### Browser UI

- stale session redirects;
- provider cards load;
- OAuth buttons start correct flows;
- browser setup is understandable;
- errors and last sync are visible;
- disconnect explains retained evidence.

## Definition of done

- Gmail and Outlook connect without database editing.
- Browser history has a guided extension flow.
- IMAP/SMTP remains a clear advanced option.
- Worker decryption and scheduling work with production keys.
- Backfill and incremental sync are resumable and audited.
- Status reflects reality.
- No connector bypasses profile scope or the ingestion bridge.
- Independent OAuth, extension and scheduler audits pass.

## Paste-ready `/goal`

```text
Execute R4 — Connector Onboarding and Live Synchronisation.

Audit R0–R3 first. Preserve the connector-to-ingestion bridge. Implement secure guided onboarding for Gmail OAuth, Outlook/Microsoft 365 OAuth, Chromium browser history and advanced IMAP/SMTP. Repair worker credential-key propagation, cursor semantics, recurring scheduling, retry/idempotency and operational health. Make permissions and collected data explicit.

Delegate Gmail, Microsoft, browser extension, IMAP/SMTP, scheduler, lifecycle, UI and security tests to bounded subagents. Keep OAuth security, permission semantics, credentials, ingestion invariants, migrations and final cross-service integration under the lead agent.

Before completion, run provider fixtures, OAuth adversarial tests, extension build/pairing/backfill, Celery restart/resume and authenticated browser onboarding. Commission independent OAuth, extension and scheduler audits.
```
