# Responsive UI/UX Pass Handoff — 2026-08-15

> Continuation update, 2026-09-11: Import now uses one canonical evidence-processing pass and no longer mounts the simulated broker scanner. ONSIT progress/finding contracts, seed validation, and bounded polling failure are repaired. Policy acquisition rejects credentials, non-HTTP schemes, internal/private destinations and unsafe DNS results, with redirects disabled. Migrations 034 and 035 are applied locally: settings/execution state and policy analyses are profile-owned, while persisted policy results are also request-owned. Pre-request wizard analysis is explicitly transient until request creation. The active request modal uses recorded deadlines, resets state per request, rolls back failed chat messages, and does not expose raw API exceptions. N8N Settings no longer exposes environment URLs or offers a dead bulk test. Agent Manager no longer simulates runs or schedules against incompatible endpoints; it is now a responsive set of truthful workflow shortcuts. All eight containers are healthy on localhost:3002; unrelated Hermes PID 25844 still owns port 3000 and was not disturbed.

## Goal

Continue the tracker-driven responsive and functional UX pass for 1GDPR Agent, preserving truthful status and validating the bind-mounted Docker frontend at `http://localhost:3000`.

## Current state

- Local Docker frontend was healthy and authenticated at localhost:3000 during this pass. The frontend and Intelligence internal-authority keys were aligned at container runtime without recording their values.
- Access Requests now reflows at compact widths, uses `Search companies or brokers...`, and provides a `Scan for Brokers` action that opens the real ONSIT workflow.
- Personal Insights has a stable server/client time seed, hydration-safe local date inputs, and progressive module results. All seven module endpoints returned 200 in the live check.
- Shared shell/sidebar breakpoints, page spacing, cards, request overlays, Graph inspector, Settings navigation, Home, and wizard headers received responsive repairs.
- Request chat now rolls back failed optimistic messages; policy scan uses the route's real `{url, company}` contract; fake Export/Complete actions were removed from the active detail modal.
- The living inventory and acceptance status are in `Technical Documentation/Responsive UI UX Improvement Tracker.md`.
- Migration 035 is active: policy reads and writes are profile/request scoped, ambiguous legacy ownership fails closed, and invalid request-route IDs return a normal 404 before reaching PostgreSQL.
- Home Agent Manager is now a manual workflow-shortcut panel; it makes no claims about persisted schedules, worker activity, or last-run state.
- The unused `RequestDetailSheet` and local-only notification bell have been retired. The active modal plus owned direct route are the only remaining request-detail surfaces; the shell no longer advertises a feed that does not exist.
- ONSIT API-key writes now use authenticated AES-GCM in one transaction, but the UI explicitly states that active Intelligence workers do not yet consume those values. The legacy email card now covers credential storage and real IMAP testing only; monitoring belongs to Source Connectors.
- The New Request wizard no longer auto-runs policy analysis while typing. It validates and analyzes only on the explicit action, carries the actual identity/details into submission, encrypts those details server-side, preserves scope/time choices across Back/Next, and distinguishes request creation from drafting/delivery.
- ONSIT task IDs are now reflected in the URL for reload/resume while the local service remains alive. The UI explicitly discloses that scan history is not durable across Intelligence restarts.
- Request cards and the quick workspace now link to the owner-checked direct page as the canonical record. The modal remains available as a labelled quick workspace until its viable chat/policy/file body is extracted into that route.
- The quick workspace no longer simulates upload progress, promises immediate graph projection, offers evidence deletion that the API rejects, or re-runs completed files. New files enter the canonical pipeline sequentially and retry processing is scoped to the current owned request.
- ONSIT export no longer fabricates sample findings on failure and its graph query is profile-scoped. N8N override saves validate credential-free HTTP(S) URLs up front, use one transaction, and expose load failure instead of silently rendering empty state.
- AI provider secrets now use authenticated AES-GCM for all new writes and save atomically. Source Connectors validate runtime configuration, preserve queued task IDs, show profile-scoped health, accept local browser pairing from the active 3002 UI, and no longer expose internal proxy exceptions.
- Settings tabs now preserve their section in the URL and respond to browser Back. Source Connectors exposes a visible retry after load failure instead of leaving an unexplained empty selector.
- No commit, push, branch change, or deployment was performed.

## Files changed

See `git status --short`. Main areas are:

- `frontend/components/layout`, `frontend/app/globals.css`, and `frontend/components/ui/card.tsx`
- Access Requests pages/components and both detail surfaces
- Personal Insights page/components/hook
- Graph page and controls
- Home widgets, Settings page plus retention/ID sections
- New Request page, Identity Builder, and Scope Selector
- focused tests under `frontend/tests`, R0 browser/CI assertions, issue registry, and the responsive tracker

Do not modify or discard `intelligence/celerybeat-schedule`; it was pre-existing unrelated user state.

## Decisions made

- Use CSS viewport/container width and browser zoom, not physical screen inches, for responsive acceptance.
- Keep the desktop sidebar below `lg`; use `xl` for layouts such as the Graph inspector that need more working width.
- The broker-scan entry point routes to ONSIT. `DatabrokerScanner.tsx` remains a known simulation and must not be represented as evidence.
- Product controls must not claim success without a working server action. The hardcoded green `System Online` claim and request-detail toast-only actions were removed/replaced.
- Preserve later-plan scope and disclose unfinished functionality instead of treating layout-only work as feature completion.

## Validation completed

- Direct TypeScript check: `frontend\\node_modules\\.bin\\tsc.cmd --noEmit --pretty false` — passed after the final code edits.
- `git diff --check` — passed.
- Earlier focused Vitest: 5 tests passed across `insights-query.test.ts` and `responsive-core-contract.test.ts`.
- Earlier Python CI contract: 10 passed, 2 skipped using a workspace-local basetemp.
- Live 1024px checks showed no page overflow on Requests, Home, Settings, New Request, ONSIT, Import, Insights, and Graph before the final small settings/wizard edits.
- Current focused frontend contracts pass 36/36, including invalid-request-ID handling; TypeScript passes.
- Docker migration 035 is recorded with zero unowned policy rows and both profile/request indexes present.
- After restarting only `gdpr_nextjs`, live Requests and New Request step 1 render at 467px without page overflow; Requests contains the requested search placeholder and all three actions. A fresh invalid detail URL returns 404 instead of 500.
- Agent Manager truthfulness contracts pass 3/3; live Home at 467px shows all five labelled shortcuts with no horizontal overflow or synthetic idle state.
- Focused duplicate-detail/shell regression slices pass 11/11 and 9/9 respectively after retiring the unsafe sheet and empty notification affordance.
- Settings credential/profile/N8N contracts pass 11/11; at a live 467px viewport, Connectors and Advanced show the corrected capability disclosures without page overflow.
- Wizard identity/analysis/state contracts pass 8/8; combined wizard/public-URL/policy checks pass 23/23. Live wizard step 1 at 467px renders the explicit-analysis/transient-state disclosure without overflow.
- Focused ONSIT/wizard/credential checks pass 14/14 after adding service-bound URL resume and stable error handling.
- Consolidated continuation gate: 59/59 focused tests across 13 files; final edited-surface ESLint and TypeScript checks pass with zero diagnostics.
- Source Connectors/Settings URL contracts pass 5/5, and five focused configuration/origin assertions pass inside the real Intelligence container. Project TypeScript and focused connector ESLint are clean; all eight Docker containers remain healthy.
- After an isolated `gdpr_nextjs` restart, the connector deep link, tab URL updates, and Back navigation were live-verified. At a 363px viewport the filesystem form had no horizontal overflow, exposed the current Intelligence-container path contract, and rejected a relative path before persistence.
- The final localhost review tab was left open. A full post-final-edit browser matrix was intentionally not run because the user asked to stop soon.

## Files still needing in-depth review

Highest priority:

1. `frontend/components/requests/RequestDetailModal.tsx` and `frontend/app/dashboard/requests/[id]/page.tsx` — canonical links and truthful upload processing are complete. Next progressively extract/reuse the modal's viable chat/policy/files/log client body in the owned route, then exercise owned/foreign request success/failure with real request data. The unsafe sheet is gone.
2. `frontend/components/settings/N8NWebhooksSection.tsx` and `frontend/app/api/settings/n8n-webhooks/route.ts` — dead Test All, raw environment disclosure, profile ownership, clearing semantics, compact wrapping, reveal-button accessibility, server URL validation, atomic saves, and visible load failure are repaired. Add real per-webhook health checks.
3. Recurring workflow scheduling and real run-state surfaces — Agent Manager is now truthful navigation only. Build persisted scheduling/status only inside an owned workflow contract; do not restore the removed generic Run controls.
4. `frontend/lib/actions/policy-analysis.ts`, `frontend/app/api/gdpr-agent/analyze-policy/route.ts`, and `frontend/lib/rlm/tools.ts` — ownership and migration are complete; add a live valid-public-URL canary on an owned request, verify provenance/execution linkage, and confirm provider failure handling without persisting partial evidence.
5. `frontend/components/settings/TaskRoutesSection.tsx`, `AICredentialsSection.tsx`, `SourceConnectorsSection.tsx`, and `PrivacySecuritySection.tsx` — AI credential transactions and Source Connector configuration/task/health visibility are repaired. Next verify real connector create/sync/revoke flows at narrow widths, then finish Task Routes and Privacy Security non-optimistic saves. ONSIT key storage is AES-GCM but still needs a signed runtime-consumption path.
6. `frontend/components/onsit/ProgressTracker.tsx`, `VendorDiscoverySection.tsx`, `frontend/app/dashboard/onsit/page.tsx`, and the Intelligence ONSIT orchestrator — replace service-memory task history with a profile-owned run/finding schema and Celery-owned lifecycle, reconcile vendor endpoints, and require explicit outreach review. URL-based resume still works only while the service remains alive. The export route is now fail-closed and profile-scoped.
7. `frontend/components/wizard/UrlAnalyzer.tsx`, `IdentityBuilder.tsx`, `ScopeSelector.tsx`, and `frontend/lib/stores/request-store.ts` — add request cancellation/abort, durable draft persistence, atomic request+identity persistence, and a complete step 2/3 phone/zoom browser flow. Explicit analysis, real identity handoff, server encryption, and truthful delivery language are implemented.
8. Notification capability — the empty local-only bell has been removed. Reintroduce it only with a profile-scoped feed plus persisted read/dismiss behavior; continue keyboard/touch review of the remaining shell controls.
9. `frontend/components/dashboard/DataVolumeChart.tsx`, `RequestsTimeline.tsx`, `ReviewQueue.tsx`, and `ReviewDetailModal.tsx` — chart resize/no-data behavior, 320px/400%-zoom actions, keyboard flow, and persisted read state.
10. `frontend/app/dashboard/graph/page.tsx` and `PrivacyGraphControls.tsx` — verify the new below-`xl` inspector sheet by selecting a real node; verify resize and keyboard behavior.

Secondary inventory is already enumerated component-by-component in the tracker; resume from rows still marked `in-progress`, `backlog`, or `truthfulness-defect`.

## Open risks / questions

- ONSIT discovery is the real scan path but scan history/results are currently page-memory only.
- The New Request action returns delivered/draft/queued truthfully now, but the full wizard draft is not recoverable after reload.
- The internal-authority alignment was applied to the running containers. Recreating Compose without supplying the required signing/internal keys may reintroduce authentication failures.
- Historical R0 evidence remains historical; do not rewrite it as proof of this unfinished broad UX pass.

## Next recommended step

Canonicalize the duplicated request-detail surfaces next, using the owned, deep-linkable direct route as the base and a real owned request to exercise chat and policy success/failure. Retire `RequestDetailSheet`; do not copy its toast-only actions. Then continue ONSIT persistence/resume. Run the remaining browser matrix sequentially at 320/375/768/1024/1366/1920 plus 200%/400% zoom to avoid another CPU spike.
