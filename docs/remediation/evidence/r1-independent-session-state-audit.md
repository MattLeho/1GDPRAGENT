# R1 independent session-state and browser/API convergence final audit

**Audit date:** 18 July 2026  
**Scope:** Independent, read-only audit of the current R1 session authority, protected browser client, protected-state reset, feature-error suppression, logout wiring, proxy/API convergence, focused tests, and the revised Playwright specification.  
**Final verdict:** **PASS**. No remaining session/client source, focused-test, or browser-runtime blocker was found.  
**Runtime acceptance:** **PASS — 4/4** on a fresh empty database with all migrations and a disposable account at `http://localhost:3012`.

## Final result

All defects from the previous independent session-state audit are repaired in the current tree:

- the central client performs one-shot authentication transition, active-request cancellation, post-failure preflight refusal, synchronous protected-state clearing, and redirect;
- both Zustand stores in the repository register production reset callbacks;
- the real request store is seeded and verified to clear synchronously in the focused 401 test;
- the canonical suppression predicate is now adopted by every previously named protected consumer and by the broader reviewed protected dashboard surface;
- concurrent handled-401 and aborted-companion errors are proven not to emit feature feedback;
- desktop and mobile/sidebar controls invoke the canonical logout helper;
- proxy and API guards resolve the same signed, expiring, database-bound authority;
- the active-shell Playwright scenario now triggers a real protected Connectors request after replacing the cookie;
- the Playwright logout scenario clicks the real UI control and observes the central protected-state-clear event.
- the hermetic Playwright run executed all four R1 scenarios successfully: active-shell rejection, connector/graph authorization labeling, immediate profile/header synchronization, and UI logout with central state clearing.

## Prior-finding disposition

| Prior finding | Final result | Evidence |
|---|---|---|
| Request-store personal data survives logout/401 | **PASS — repaired** | `frontend/lib/stores/request-store.ts:134-139` registers `resetRequestState`; `frontend/tests/api-client.test.ts:85-101` seeds real personal request state and proves synchronous clearing on handled 401. |
| Only synthetic reset callbacks are tested | **PASS — repaired** | The focused test imports and asserts the production request store, not only a synthetic callback. Repository scan finds only request and profile Zustand stores, and both register resets. |
| In-flight/later calls continue after 401 | **PASS — repaired** | Controller abort at `frontend/lib/api-client.ts:79-84`; preflight refusal at lines 119-121; repeated-401 test proves only one network dispatch. |
| Logout helper is not wired to UI | **PASS — repaired** | Desktop header and shared sidebar/mobile controls invoke `logout()` at `frontend/components/layout/DashboardLayout.tsx:138-146,239-246`. |
| Feature consumers ignore handled-auth/abort suppression | **PASS — repaired** | All previously named consumers now use `shouldSuppressProtectedRequestError`; detailed source audit confirms each catch that presents feedback is gated. |
| No consumer/concurrency feedback regression test | **PASS — repaired** | `frontend/tests/r1-protected-consumer-feedback.test.ts:22-37` proves handled 401 plus concurrent `AbortError` emit zero feature feedback; ordinary 500 emits once at lines 39-43. |
| Active-shell browser test replaces cookie but triggers no request | **PASS — repaired in specification** | `tests/browser/r1-auth-profile.spec.ts:33-48` replaces the cookie, clicks the Connectors tab, asserts at least one protected request, then asserts redirect and no later protected dispatch. |
| Browser logout bypasses UI / cannot observe reset | **PASS — repaired in specification** | `tests/browser/r1-auth-profile.spec.ts:88-105` installs a reset-event observer, clicks the actual `Sign out` button, and asserts exactly one central clear event, cookie removal, API 401, and proxy rejection. |

## Canonical suppression adoption

Fresh source inspection confirms suppression at all previously failing R1-required surfaces:

- retention load/actions: `frontend/components/settings/RetentionSettingsSection.tsx:49-64`;
- connector load/add/card actions and browser pairing create/revoke: `frontend/components/settings/SourceConnectorsSection.tsx:49-80,245-249,398-417`;
- ID-document load/upload/delete: `frontend/components/settings/IDDocumentsSection.tsx:61-65,104-108,132-136`;
- n8n load/save/test: `frontend/components/settings/N8NWebhooksSection.tsx:177-181,203-207,225-229`;
- API credentials load/save: `frontend/components/settings/APICredentialsSection.tsx:128-132,155-159`;
- AI credentials load/save: `frontend/components/settings/AICredentialsSection.tsx:83-87,106-110`;
- request manual creation/policy scan and request deletion: `frontend/components/requests/AddManualRequestDialog.tsx:102-107,155-160`; `frontend/components/requests/RequestsGrid.tsx:99-103`;
- graph mutations/stats: `frontend/app/dashboard/graph/page.tsx:57-61,90-94`; `frontend/components/graph/InspectorPanel.tsx:307-311`.

The wider reviewed protected surface also gates feedback in profile, processing/security, task routes, workflows, request detail/chat, graph canvas/chat/privacy mode, ONSIT, identity wizard, ZIP importer, agent manager, Personal Insights, and request-store data loading.

## Audit-question disposition

| Question | Result | Evidence |
|---|---|---|
| Can cookie presence alone render dashboard content? | **PASS** | `frontend/proxy.ts:14-27` requires full token verification and database binding before allowing `/dashboard`. |
| Do proxy and APIs resolve one canonical authority? | **PASS** | Both call `resolveSessionAuthority`; `requireApiSession` resolves authentication before mutation CSRF enforcement. |
| Are malformed, expired, tampered, deleted, or mismatched bindings rejected and cleared appropriately? | **PASS** | Token/adversarial/session-enforcement focused tests pass; proxy/API share failure semantics and invalid-cookie clearing. |
| Does the client stop active protected calls after the first 401? | **PASS** | All registered request controllers are aborted during the one-shot transition. |
| Does the client refuse later protected calls before dispatch? | **PASS** | `authenticationFailureHandled` is checked before creating/dispatching a request; test proves one fetch across repeated calls. |
| Are protected client stores cleared synchronously? | **PASS** | Both current Zustand stores register; production request-store personal state is directly tested. |
| Are redirect/reset effects one-shot? | **PASS** | Central guard and focused repeated-401 assertions prove one reset callback and one redirect. |
| Are feature auth-transition errors suppressed? | **PASS** | Canonical helper is adopted across reviewed consumers; concurrency feedback test proves zero emissions for handled 401 plus abort. |
| Does ordinary non-auth failure feedback remain available? | **PASS** | Regression test proves a 500 error reports exactly once. |
| Is logout wired to every shell control? | **PASS** | Desktop and shared sidebar/mobile controls call `logout()`. |
| Does profile save update persistent header state without reload? | **PASS** | Shared profile store publishes save result; `DashboardLayout` subscribes; profile-state tests pass; hermetic browser scenario passed. |
| Is the revised active-shell browser scenario semantically valid? | **PASS** | It explicitly initiates a Connectors protected request after cookie invalidation and checks that dispatch stops after redirect. |
| Is the revised logout browser scenario semantically valid? | **PASS** | It clicks the UI and observes the central clear event plus cookie/API/proxy outcomes. |

## Definition-of-done result

| Session/client-state criterion | Result |
|---|---|
| Verified, expiring, profile-bound server authority | **PASS** |
| Proxy/API authority convergence | **PASS** |
| Invalid authority fails closed and clears invalid cookie | **PASS** |
| Central protected fetch, cancellation, and post-401 preflight shutdown | **PASS** |
| Synchronous reset of all current protected Zustand stores | **PASS** |
| Desktop and mobile/sidebar canonical logout wiring | **PASS** |
| Canonical suppression across required protected consumers | **PASS** |
| Bounded auth-transition feature feedback | **PASS** |
| Immediate shared profile/header update | **PASS — unit and browser** |
| Browser specification quality for active-shell expiry and UI logout | **PASS** |
| Executed hermetic browser acceptance | **PASS — 4/4** |
| Independent session-state implementation audit | **PASS** |

## Fresh verification

- Focused Vitest: **7 files passed, 55 tests passed, 0 failed**. Covered API client, session enforcement, adversarial session/API, adversarial client/profile, profile state, route authority, and protected-consumer feedback.
- `pnpm typecheck`: **passed** (`tsc --noEmit`).
- Zustand inventory: **2 stores found; 2 production reset registrations found**.
- Protected-consumer regression suite: **10 tests passed**, including concurrent handled-401/abort zero-feedback behavior.
- Hermetic R1 Playwright runtime at `http://localhost:3012`: **4 tests passed, 0 failed, 0 skipped** against a fresh empty database, all migrations, and a disposable account.

## Final disposition

The independent R1 session-state audit is **PASS**. The current evidence proves server authority convergence, client cancellation and preflight shutdown, synchronous protected-state clearing, bounded feature feedback, immediate profile/header synchronization, and canonical UI logout in both focused tests and the executed hermetic browser journeys. No session-state remediation item remains open in this audit.
