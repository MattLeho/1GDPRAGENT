# R1 independent API route-authority coverage audit

Audited and re-audited: 17 July 2026

Scope: every exported HTTP method below `frontend/app/api/**`, `docs/remediation/ledgers/R1_ROUTE_AUTHORITY_INVENTORY.md`, `frontend/lib/api-session.ts`, route/static verifiers, internal authority call sites, and the four repairs requested after the initial audit. This was a read-only implementation audit; only this report was updated.

## Final verdict

**PASS for R1 route-authority coverage.** The current source contains 62 route modules and 87 exported HTTP methods, exactly matching the ledger. All **83/83 sensitive methods across 58/58 sensitive route modules** await the canonical guard, return its rejection, and run it before request parsing, database access, or network work. All sensitive mutations reach same-origin/CSRF enforcement through `requireApiSession`; all three public mutations call it directly.

The four initial findings are resolved. No open route-authority blocker remains in this audit scope. This is not an overall R1 completion claim; profile isolation, session/browser state, migrations, and other independent audits retain separate verdicts.

## Repair re-audit

### R1-ROUTE-01 — RESOLVED — Public registration overexposure

`frontend/app/api/auth/register/route.ts:37-57` begins a transaction, takes `pg_advisory_xact_lock(hashtext('gdpr-agent-initial-registration'))`, checks for an existing account while holding that transaction-scoped lock, returns `409` without inserting when setup is complete, and creates the initial profile/account only after the empty-install check.

`frontend/tests/r1-registration-bootstrap.test.ts:37-53` verifies both existing-account rejection without inserts and lock-before-check-before-create ordering. PostgreSQL transaction-scoped advisory locking serializes racing bootstrap attempts, so only the first transaction can observe an empty account table and create the initial account. The stale comment at registration line 33 still says “allow multiple users now”; it should be cleaned up, but it does not affect enforcement.

### R1-ROUTE-02 — RESOLVED — Protected server self-fetch

The self-fetch to `/api/gdpr-agent/draft` is absent. `frontend/lib/actions/requests/submit.ts:106` resolves canonical server authority and lines 257-263 call `executeTask` directly with that `profileId`. Lines 264-285 validate the routed result and persist only against the same profile. The workflow no longer depends on browser cookies or a fabricated CSRF request for server-side work.

### R1-ROUTE-03 — RESOLVED — Partial signed-call allow-list

`frontend/tests/r1-internal-authority-call-sites.test.ts:7-54` now recursively discovers TypeScript candidates under `app` and `lib`, propagates Intelligence-target taint through declarations, counts discovered Intelligence fetches, and requires the signed-header count to equal the fetch count for each candidate. The previously omitted connector, policy-analysis, graph-chat, and retention proxies are discovered automatically and pass.

This is conservative static analysis rather than a complete semantic data-flow proof, but it removes the prior hard-coded file allow-list and fails ordinary newly added unsigned Intelligence fetches. The source scan found no unsigned Next-to-Intelligence call.

### R1-ROUTE-04 — RESOLVED — Route alias/export discovery

`frontend/tests/r1-route-authority.test.ts:50-78` uses the TypeScript AST to inventory direct exported functions, exported variables, and named ESM re-exports. Lines 80-111 resolve direct bodies, `export const METHOD = handler`, and `export { handler as METHOD }`; lines 125-145 enforce guard await, rejection return, and guard-before-work for every classified sensitive method.

The independent Python method-order scan recognizes direct, const-alias, and ESM-alias exports at `tests/integration/r1_sensitive_security_test.py:18-50`. Its current-tree run covers the connector, retention, and profile aliases missed by the initial version. A new route or exported method fails the explicit TypeScript route/method comparison until classified.

## Public classification

| Route | Methods | Result |
|---|---:|---|
| `auth/check-setup` | GET | PASS — setup boolean only. |
| `auth/login` | POST | PASS — credential exchange with direct same-origin/CSRF enforcement. |
| `auth/logout` | POST | PASS — idempotent cookie clear with direct same-origin/CSRF enforcement. |
| `auth/register` | POST | PASS — direct same-origin/CSRF enforcement plus atomic bootstrap-only creation. |

There are no current `internal only` or OAuth-callback Next route modules, matching the ledger.

## Every sensitive route

| Route | Exported methods | Authority coverage |
|---|---:|---|
| `auth/session` | GET | PASS |
| `connectors/[[...path]]` | GET, POST, PUT, DELETE | PASS |
| `execution` | POST | PASS |
| `gdpr-agent/analyze-policy` | POST | PASS |
| `gdpr-agent/draft` | POST | PASS |
| `graph` | GET | PASS |
| `graph/chat` | POST | PASS |
| `graph/nodes` | POST, PUT, DELETE | PASS |
| `graph/nodes/bulk` | POST | PASS |
| `graph/nodes/merge` | POST | PASS |
| `graph/stats` | GET | PASS |
| `graph/upsert-identity` | POST | PASS |
| `identities` | GET | PASS |
| `identities/account` | POST | PASS |
| `ingestion/benchmark-invoke` | POST | PASS |
| `ingestion/feature-adjudication` | POST | PASS |
| `ingestion/schema-interpretation` | POST | PASS |
| `insights/[module]` | GET | PASS |
| `insights/context-events` | POST | PASS |
| `insights/evidence/[id]` | GET | PASS |
| `insights/media-analysis` | GET, POST | PASS |
| `insights/media-location-confirmations` | POST | PASS |
| `n8n/analyze-policy` | POST | PASS |
| `n8n/test-imap` | POST | PASS |
| `onsit/bulk` | POST | PASS |
| `onsit/discover` | POST | PASS |
| `onsit/discover-dpo` | POST | PASS |
| `onsit/export` | GET | PASS |
| `onsit/extract-vendors` | POST | PASS |
| `onsit/findings/[id]` | GET, DELETE | PASS |
| `onsit/send-bulk-emails` | POST | PASS |
| `onsit/status/[taskId]` | GET | PASS |
| `onsit/vendor-bulk-email` | POST | PASS |
| `onsit/vendor-domain-search` | POST | PASS |
| `onsit/vendor-dpo-discovery` | POST | PASS |
| `policy/check` | POST | PASS |
| `request-threads` | GET, POST | PASS |
| `request-threads/[id]/chat` | GET, POST | PASS |
| `requests/[id]` | DELETE | PASS |
| `requests/[id]/logs` | GET | PASS |
| `retention/[[...path]]` | GET, POST | PASS |
| `settings/ai-credentials` | GET, POST | PASS |
| `settings/ai-models` | GET | PASS |
| `settings/api-credentials` | GET, POST | PASS |
| `settings/engine-health/[engineId]` | GET | PASS |
| `settings/execution-audit` | GET | PASS |
| `settings/id-documents` | GET, POST, DELETE | PASS |
| `settings/model-preferences` | GET, POST | PASS |
| `settings/n8n-webhooks` | GET, POST | PASS |
| `settings/processing` | GET, POST | PASS |
| `settings/profile` | GET, POST, PUT | PASS |
| `settings/profile/password` | POST | PASS |
| `settings/task-routes` | GET, POST | PASS |
| `settings/workflows` | GET, POST | PASS |
| `upload` | GET, POST, PATCH, DELETE | PASS |
| `upload/process` | POST, PUT | PASS |
| `upload/scan` | POST | PASS |
| `workflows/inbox-monitor` | POST | PASS |

## Guard, CSRF, and internal-authority results

- Guard await/return: PASS; no current guard is ignored or un-awaited.
- Guard order: PASS; the guard precedes request body/form parsing, database access, and route-local network calls.
- Sensitive mutations: PASS through `requireApiSession` and `enforceSameOriginMutation`.
- Public mutations: PASS through direct `enforceSameOriginMutation` calls; registration also has bootstrap authorization.
- Next-to-Intelligence calls: PASS; all discovered calls use `intelligenceAuthorityHeaders` with canonical authority-derived profile IDs.
- Server-side request drafting: PASS; it uses the authority-aware task router directly.
- New-route behavior: PASS; an added route or method fails until the explicit ledger map is updated.

## Fresh verification evidence

- `pnpm exec vitest run tests/r1-registration-bootstrap.test.ts tests/r1-route-authority.test.ts tests/r1-internal-authority-call-sites.test.ts tests/r1-internal-authority.test.ts tests/r1-adversarial-session-api.test.ts` — PASS, 5 files / 26 tests.
- `pnpm typecheck` — PASS.
- Bundled Python `tests/integration/r1_route_coverage_test.py` via `unittest` — PASS, 3 tests.
- All three functions in `tests/integration/r1_sensitive_security_test.py` executed directly with the bundled Python — PASS.
- Full Python `pytest` collection was not rerun because the available bundled Python lacks `pytest`. This is an environment limitation, not a hidden pass; the focused TypeScript route, bootstrap, signed-call, adversarial-session, and typecheck evidence above all completed successfully.

## Final disposition

All four route-coverage repairs were implemented and independently verified. **Final route-authority verdict: PASS.**
