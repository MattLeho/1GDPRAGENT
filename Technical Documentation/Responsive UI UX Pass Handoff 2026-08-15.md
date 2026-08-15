# Responsive UI/UX Pass Handoff — 2026-08-15

## Goal

Continue the tracker-driven responsive and functional UX pass for 1GDPR Agent, preserving truthful status and validating the bind-mounted Docker frontend at `http://localhost:3000`.

## Current state

- Local Docker frontend was healthy and authenticated at localhost:3000 during this pass. The frontend and Intelligence internal-authority keys were aligned at container runtime without recording their values.
- Access Requests now reflows at compact widths, uses `Search companies or brokers...`, and provides a `Scan for Brokers` action that opens the real ONSIT workflow.
- Personal Insights has a stable server/client time seed, hydration-safe local date inputs, and progressive module results. All seven module endpoints returned 200 in the live check.
- Shared shell/sidebar breakpoints, page spacing, cards, request overlays, Graph inspector, Settings navigation, Home, and wizard headers received responsive repairs.
- Request chat now rolls back failed optimistic messages; policy scan uses the route's real `{url, company}` contract; fake Export/Complete actions were removed from the active detail modal.
- The living inventory and acceptance status are in `Technical Documentation/Responsive UI UX Improvement Tracker.md`.
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
- The final localhost review tab was left open. A full post-final-edit browser matrix was intentionally not run because the user asked to stop soon.

## Files still needing in-depth review

Highest priority:

1. `frontend/components/dashboard/ZipImporter.tsx` and `frontend/app/api/upload/process/route.ts` — stale completed-file state, nonexistent `result.content`, and false “Knowledge graph updated” messaging. Repair the actual evidence-review/projection flow.
2. `frontend/components/dashboard/DatabrokerScanner.tsx` — random/local simulation. Remove it from the operational Import page or replace it with a profile-owned persisted ONSIT job.
3. `frontend/components/dashboard/AgentManager.tsx` — local-only schedules and several run buttons target endpoints that cannot perform the labelled action.
4. `frontend/components/requests/RequestDetailModal.tsx`, `RequestDetailSheet.tsx`, and `RequestsGrid.tsx` — choose one canonical detail surface; exercise chat/policy success and failure; implement real export/completion workflows before restoring those controls.
5. `frontend/components/settings/TaskRoutesSection.tsx`, `N8NWebhooksSection.tsx`, `AICredentialsSection.tsx`, `SourceConnectorsSection.tsx`, and `PrivacySettings.tsx` — compact form wrapping, accessible icon controls, 44px touch targets, error and health states. `TaskRoutesSection.tsx` remains dense and was audited but not edited in the final tranche.
6. `frontend/components/onsit/DiscoveryForm.tsx`, `ProgressTracker.tsx`, `VendorDiscoverySection.tsx`, and `frontend/app/dashboard/onsit/page.tsx` — attach schema validation, remove unsupported platform/time claims, persist/resume jobs, bound polling failures, and require explicit outreach review.
7. `frontend/components/wizard/UrlAnalyzer.tsx`, `IdentityBuilder.tsx`, `ScopeSelector.tsx`, and `frontend/lib/stores/request-store.ts` — URL validation/abort, server-owned identity encryption, truthful draft/send state, draft persistence, and a complete phone/zoom flow.
8. `frontend/components/layout/NotificationsBell.tsx` and its data source — currently has no feed when mounted without props; wire a real profile-scoped feed or hide the affordance. Complete keyboard/touch review.
9. `frontend/components/dashboard/DataVolumeChart.tsx`, `RequestsTimeline.tsx`, `ReviewQueue.tsx`, and `ReviewDetailModal.tsx` — chart resize/no-data behavior, 320px/400%-zoom actions, keyboard flow, and persisted read state.
10. `frontend/app/dashboard/graph/page.tsx` and `PrivacyGraphControls.tsx` — verify the new below-`xl` inspector sheet by selecting a real node; verify resize and keyboard behavior.

Secondary inventory is already enumerated component-by-component in the tracker; resume from rows still marked `in-progress`, `backlog`, or `truthfulness-defect`.

## Open risks / questions

- ONSIT discovery is the real scan path but scan history/results are currently page-memory only.
- The New Request action returns delivered/draft/queued truthfully now, but the full wizard draft is not recoverable after reload.
- The internal-authority alignment was applied to the running containers. Recreating Compose without supplying the required signing/internal keys may reintroduce authentication failures.
- Historical R0 evidence remains historical; do not rewrite it as proof of this unfinished broad UX pass.

## Next recommended step

Start with `ZipImporter.tsx` as a bounded vertical slice: write a regression around completed upload results, replace stale state with returned persisted IDs, correct the evidence/projection wording, and verify one import end-to-end. Then complete the Settings compact forms and run the full 320/375/768/1024/1366/1920 plus 200%/400% browser matrix sequentially to avoid another CPU spike.
