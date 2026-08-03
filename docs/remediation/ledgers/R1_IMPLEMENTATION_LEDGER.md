# R1 implementation ledger

**Branch / starting commit:** `main` / `67e50b85daa923366d3bec80db6582edcc3ba134`  
**Start date:** 2026-07-17  
**Decision owner:** lead agent

## Frozen authority contract

```ts
export interface SessionAuthority {
  userId: string;
  profileId: string;
  issuedAt: number;
  expiresAt: number;
}
```

- The browser session is a versioned HMAC-SHA256 token signed only with `SESSION_SIGNING_KEY`.
- Both issuance and absolute expiry are encoded and verified. Future-issued, expired, malformed, tampered, deleted-user and mismatched-profile sessions fail closed.
- The canonical ownership binding is `user_profiles.id -> user_profiles.default_profile_id -> profiles.id`.
- Caller-supplied user/profile identifiers are filters only; they never establish authority.
- API failures use one structured error shape and invalid sessions clear `gdpr-session`.
- Browser mutations require same-origin/CSRF validation.
- Next.js-to-Intelligence calls carry server-generated internal authority derived from the session profile.
- `SESSION_SIGNING_KEY`, `INTERNAL_API_KEY`, and `CREDENTIALS_ENCRYPTION_KEY` have no cross-purpose fallback.

## Delegation map

| Workstream | Bounded owner | Owned surface | Lead-retained decisions |
|---|---|---|---|
| Session middleware and verification | `r1_session_authority` | Auth libraries, proxy, auth routes, focused tests | Token format, cookie policy, authority type |
| Sensitive API inventory and guards | `r1_route_inventory` | Non-auth/non-profile Next API routes, route ledger/tests | Public-route policy, final coverage judgement |
| Profile ownership and SQL scoping | `r1_profile_ownership` | Profile APIs, selected repositories/actions, focused tests | Ownership semantics and migrations |
| Shared profile/header synchronisation | bounded R1 profile-state workstream | Profile store/provider and UI consumers | Shared browser API contract |
| Internal authority and CSRF | bounded R1 internal-authority workstream | Intelligence authority dependency and focused integration | Secret contract and cross-service wiring |
| Adversarial/browser tests | bounded R1 acceptance workstream | R1 API/browser tests only | Acceptance decision and repairs |

## Requirement evidence

| Requirement | Code | Tests | Runtime evidence | Status |
|---|---|---|---|---|
| Verified expiring profile-bound session | `frontend/lib/auth-session.ts`, `frontend/lib/api-session.ts` | `auth-session.test.ts`, `r1-adversarial-session-api.test.ts` | malformed/tampered active-shell Playwright case | PASS |
| Pre-render invalid-session redirect and cookie clearing | `frontend/proxy.ts`, `frontend/app/api/auth/session/route.ts` | session/API adversarial suites | Playwright active-shell rejection before protected content | PASS |
| Complete sensitive-route authority coverage | 58 sensitive route modules | 83/83 sensitive methods in route inventory tests | independent route audit | PASS |
| Profile-scoped personal-data access | migration 030 plus request/upload/graph/Insights/connector repositories | ownership, SQL-scope, object-isolation and Python profile suites | independent isolation audit | PASS |
| Immediate profile/header synchronisation | `frontend/lib/stores/profile-store.ts`, profile/header components | `r1-profile-state.test.ts`, `r1-profile-ownership.test.ts` | authenticated browser edit without reload | PASS |
| Central protected browser API client | `frontend/lib/api-client.ts`, protected consumer feedback helper | client and protected-consumer suites | active-shell 401 and UI logout cases | PASS |
| Signed internal Intelligence authority | TS signer, Python verifier/middleware, Redis replay store | 23 frontend and 44 Python focused checks | independent internal-authority audit | PASS |
| Same-origin/CSRF mutation protection | canonical Next API guard and public mutation guards | route-authority/adversarial API suites | foreign-origin cases exercised | PASS |
| Three distinct production secrets | `.env.example`, Compose, session/internal/credential libraries | internal-authority/static contract checks | production build fails closed when required | PASS |
| Clean install and legacy upgrade | `database/migrations/030_r1_profile_ownership.sql` | migration fixtures: 6 passed, 1 expected failure | empty PostgreSQL 000-030 apply succeeded | PASS |
| Adversarial API/browser acceptance | R1 Vitest/Python/Playwright suites | frontend 87/87; focused Python 44/44 and 25/25 | Playwright 4/4 on disposable stack | PASS |
| Independent audits | four reports under `docs/remediation/evidence` | fresh auditor executions | route, profile, session and internal verdicts PASS | PASS |

## Initial observed defects

- `auth-session.ts` aliases signing material and has no encoded `expiresAt`.
- `proxy.ts` treats cookie presence as authentication and redirects `/login` on any cookie.
- `api-session.ts` returns only `profileId`, aliases internal secrets, and does not clear invalid cookies.
- profile and password routes select the first account.
- 61 Next API route files have no complete reviewed authority inventory.
- protected UI consumers use fragmented raw `fetch` calls and independent profile state.
- Docker/environment configuration aliases `INTERNAL_API_KEY` to `CREDENTIAL_KEY` and does not expose the complete three-secret contract.
