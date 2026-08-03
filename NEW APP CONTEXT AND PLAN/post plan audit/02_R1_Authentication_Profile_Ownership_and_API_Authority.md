# R1 — Authentication, Profile Ownership and API Authority

## Goal

Create one verified, expiring and profile-bound authority across the dashboard, settings, requests, graph, Personal Insights, connectors, retention and internal service calls.

The application must never render an authenticated shell while the same session is rejected by protected APIs.


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

- R0 accepted.
- R0 session/browser regressions exist.

## Canonical identity

```text
user_profiles.id
    ↓ default_profile_id
profiles.id
```

The session binds both values. Every protected operation validates the binding and derives authority from it.

## Lead-agent ownership

The lead agent owns the session format, cookie policy, authority type, profile ownership semantics, API guard contract, internal service authority, migration integration and final route-coverage decision.

## Subagent delegation

### A — Session/middleware

Implement:

- canonical `SessionAuthority`;
- signature and age validation;
- invalid-cookie clearing;
- dashboard redirect before protected rendering;
- `/api/auth/session`;
- logout;
- optional explicit renewal policy.

### B — API-route authority inventory

Classify every `frontend/app/api/**` route as:

- public;
- authenticated read;
- authenticated mutation;
- internal only;
- OAuth callback.

Apply the canonical guard to every sensitive route.

### C — Profile-scoped repositories

Audit queries involving users, profiles, requests, uploads, chat, connectors, retention, Insights and graph. Remove ownership shortcuts and create profile-scoped helpers.

### D — Shared profile state

Repair profile load/save and header synchronisation. Username, email, avatar and initials must update without remounting the dashboard.

### E — Internal authority and CSRF

Implement signed `x-gdpr-internal-key` and `x-gdpr-profile-id`, same-origin mutation protection and separate secrets for session signing, internal authority and encryption.

### F — Adversarial tests

Test tampering, expiry, wrong profile, deleted user/profile, cross-profile object IDs, foreign origin, missing internal authority and stale client profile cache.

## Detailed implementation

### 1. Authority contract

```ts
interface SessionAuthority {
  userId: string;
  profileId: string;
  issuedAt: number;
  expiresAt: number;
}
```

Server-only. Never expose signing or encryption material.

### 2. Replace cookie-presence checks

Required behaviour:

```text
no cookie
→ dashboard redirect
→ API 401

invalid/expired/mismatched cookie
→ clear cookie
→ dashboard redirect with reason
→ structured API 401

valid cookie
→ resolved SessionAuthority
```

### 3. Central protected API client

Create one client wrapper that:

- parses structured errors;
- catches `401`;
- clears client stores;
- redirects once;
- prevents repeated toast storms;
- supports cancellation.

Adopt it first in profile, connectors, graph, retention, task routes, workflows, Insights and request chat.

### 4. Profile endpoint repair

The endpoint must:

- resolve the authenticated user;
- preserve password state;
- update exactly that account;
- update the linked canonical profile only where intended;
- avoid accidental duplicate users;
- safely store and replace images;
- invalidate the shared profile state.

Remove `LIMIT 1` behaviour.

### 5. Ownership enforcement

Every profile-owned operation must query by `profile_id` or prove ownership through a parent join. Caller-supplied profile IDs are never authority.

### 6. Personal Insights and graph

- require a valid session;
- derive profile/subject from authority;
- send signed internal headers;
- reject cross-profile IDs;
- remove “first user” fallback.

### 7. Protect settings

Protect profile, AI/API credentials, task routes, processing mode, workflows, connectors, retention, infrastructure and n8n settings.

### 8. Explicit secrets

Require:

```text
SESSION_SIGNING_KEY
INTERNAL_API_KEY
CREDENTIALS_ENCRYPTION_KEY
```

Fail closed in production. Do not alias one secret across unrelated purposes.

## Required tests

### Unit

- valid token;
- malformed token;
- signature mismatch;
- future timestamp;
- expiry;
- profile-binding mismatch;
- cookie clearing.

### API

- every protected route returns `401` without authority;
- mutations reject foreign origin;
- cross-profile IDs do not reveal existence;
- internal Python endpoints reject missing authority.

### Browser

- expired session redirects before dashboard content;
- no protected requests continue after failure;
- connectors do not show a misleading empty selector;
- graph does not mislabel auth failure as Neo4j failure;
- profile changes update the header immediately;
- logout clears protected state.

### Migration

- existing users gain or preserve valid profile bindings;
- no duplicate profile is created;
- representative records remain accessible only to the correct profile.

## Definition of done

- Cookie presence alone cannot open the dashboard.
- Every sensitive route uses canonical authority.
- Personal-data queries are profile-scoped.
- Profile save updates the header without reload.
- Personal Insights and graph use the active profile.
- Next.js-to-Python calls carry internal authority.
- Session, internal and encryption keys are distinct.
- Clean-install, upgrade, API and browser tests pass.
- Independent route-coverage and isolation audits pass.

## Paste-ready `/goal`

```text
Execute R1 — Authentication, Profile Ownership and API Authority.

Audit R0 and repair any blocking regression. Replace cookie-presence authentication with verified, expiring, profile-bound authority. Apply it consistently to all sensitive dashboard, settings, request, upload, graph, Personal Insights, connector and retention routes. Repair profile persistence and immediate header updates. Add signed internal authority for Next.js-to-Python calls and separate session, internal and encryption keys.

Delegate session middleware, route inventory, query scoping, profile UI state, internal authority and adversarial tests to bounded subagents. Keep authority contracts, ownership semantics, migrations, security-critical integration and the final route-coverage decision under the lead agent.

Before completion, run clean-install and upgrade migrations, unauthorised/cross-profile API tests and authenticated Playwright scenarios. Commission independent route and profile-isolation auditors.
```
