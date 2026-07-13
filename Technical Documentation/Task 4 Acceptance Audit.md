---
title: Task 4 Acceptance Audit
date: 2026-07-13
tags:
  - gdpr-agent
  - task-4
  - acceptance
status: accepted
---

# Task 4 Acceptance Audit

The remediation closes all implementation, automated-verification and authenticated-runtime gaps found by the first independent audit. Task 4 is accepted. The user's live profile contained no event partitions, so the evidence-drawer interaction was verified with an isolated local synthetic subject, `task4-browser-smoke`, rather than altering or seeding the user's profile.

Status meanings:

- **Proven** — current production code and proportionate test/runtime evidence cover the requirement.

## Re-audit of every former partial or missing item

| Former gap | Current status | Current evidence |
|---|---|---|
| Frozen typed API responses | Proven | Every Python endpoint now declares a Pydantic `response_model`; `test_personal_insights_openapi_has_typed_response_contracts` verifies schemas. |
| Accepted Assertions were not consumed | Proven | `InsightService._build_snapshot` reads accepted Assertions; `_augment_interest_sources` adds matching Assertion evidence; the database-backed service test verifies counts and indexed evidence. |
| TemporalStates/aggregates were not consumed | Proven | The snapshot reads both, augments interest/engagement evidence, and traces both kinds. Database-backed tests verify catalogue/index persistence. |
| Partition/run invalidation only rebuilt the whole snapshot | Proven | Cache identity includes current/baseline/history partition hashes and canonical dependency tokens. The integrated snapshot service reuses unaffected materialised buckets and selectively recomputes affected buckets; focused integration tests cover reuse and invalidation. |
| Payload compactness was unproven | Proven | `_compact_snapshot` bounds inline evidence to 100 refs while the immutable index retains all refs; the service test verifies 100 returned versus 120 indexed. |
| Full snapshot reproducibility | Proven | `generated_at` now uses the deterministic effective period boundary, nested feature values are JSON-normalised, and a database-backed independent rebuild equals the cached snapshot. |
| Search revisitation/related patterns | Proven | Recurring summaries now include revisit count and first/latest observation; dedicated recurrence and revisit tests pass. Related episode grouping remains deterministic and privacy-safe. |
| AI cross-session return/refinement chain | Proven | Recurrent topics retain session counts; `refinement_chains` records initial, technical, architecture, implementation and project stages. The ordered-chain test passes and the UI renders it. |
| Source-specific reliability | Proven | `ClassifiedSignal` carries reliability and rule provenance; reliable versus unreliable open evidence is distinguished and tested. |
| Project topic co-emergence | Proven | `ProjectEpisodeView.topic_co_emergence` is calculated and rendered separately from labels. |
| Human confirmation did not use accepted Assertions | Proven | The service resolves accepted human-confirmed relationship Assertions that reference the change and external event; the engine keeps confirmation distinct from pre-change exposure and never creates causation. |
| External event classes were untyped | Proven | Import now restricts event types to legislation, platform change, product release, public policy, user-added or other; response is typed. |
| Competing explanations/persistence were placeholders | Proven | Service calculates competing relevant events and supplies detector-derived behavioural persistence. Values remain visible in candidates/UI. |
| Exposure resolver did not include confirmation path | Proven | Local pre-change observations and accepted Assertion confirmations are separate inputs. Post-change/unrelated evidence is rejected by tests. |
| Context UI lacked change/event details | Proven | Candidate DTOs carry constrained local-change and external-event summaries; the UI displays both alongside exposure/status metrics. External-event evidence is indexed and traceable. |
| Media mode had no operational router path | Proven | `/api/insights/media-analysis` reads/writes `insight_settings`, keeps metadata-only at zero tasks, resolves provenance, calls the Task Router via `executeTask`, persists execution-linked specialist results, and selects follow-up work by mode/origin. Six direct source-contract tests cover metadata-only, selective/full routing and strict-local privacy behaviour; live metadata-only smoke passed. |
| Origin classifier omitted dimensions/geometry/download provenance | Proven | Deterministic features now include dimensions, common screen geometry and download/source hints; focused tests pass. |
| Selective semantic work was not limited to ambiguous candidates | Proven | Selective mode runs origin first, then OCR/caption only for screenshots, landmark only for unknown origin, and nothing further for confident camera origin. Helper and direct route source-contract tests verify the branches and privacy policy. |
| Sidecar and user-confirmed locations lacked integrated paths | Proven | Service consumes Takeout sidecars with their own artifact/locator and exposes a typed confirmation API/Next proxy. Database-backed media tests verify both. |
| Selective screenshot OCR/application/webpage/topics/entities was absent | Proven | `MediaContentCandidate` consumes completed origin/OCR/caption results, hides raw OCR, extracts reviewable application/interface/webpage/service/topic/entity candidates and retains image evidence. Database-backed content tracing and the direct media-route staging tests pass. |
| Activity-centre changes/travel/place-linked projects were empty | Proven | Presence-only algorithms now calculate all three, exclude screenshot candidates, avoid HOME inference and preserve non-causal wording; focused tests pass. |
| Download/media integration fixtures were helper-only | Proven | Database fixture now covers camera GPS, sidecar, screenshot, downloaded media, landmark, confirmation, routed OCR/caption and evidence tracing. |
| Interest Atlas omitted prior values and peak | Proven | DTO/service calculate prior dimensions/deltas, `peak_at` is rendered, and compare-mode tests verify values. |
| Search UI displayed only counts | Proven | UI now lists recurring patterns, clusters and refinement chains and exposes project transitions. Raw text remains hidden. |
| AI UI lacked refinement stages | Proven | UI renders refinement stage sequences plus existing session, topic, recurrence, service and project metrics. |
| Backend never emitted DECLINING | Proven | Compare mode emits a `DECLINING` change for a baseline topic absent from the current period; database test verifies it. |
| Every card/evidence action was not demonstrated | Proven | All derived items are catalogued independently, full evidence is indexed, and actions are shown for evidence-bearing items. Database tests iterate every evidence-bearing derived item in their fixture and media tests trace content candidates. In authenticated browser smoke, the isolated `task4-browser-smoke` subject exposed one visible “Why am I seeing this?” action; it opened the Evidence inspector and loaded the expected trace. |
| Evidence trace returned snapshot-level metadata | Proven | Migration 019 versions index keys by materialisation; migration 020 adds immutable per-card catalogue records. Tracer selects the exact nested DTO and materialisation, returns its detector/version/features/window/model explanation, and resolves events, Assertions, temporal inputs, context, artifacts and locators. Tests verify exact equality. |
| Stable project/era IDs could retain an old window | Proven by schema/query | The index primary key starts with `materialisation_id`, catalogue keys include materialisation and insight, and the tracer selects the newest matching immutable materialisation. Live database schema confirms the new key. |
| Returning topic required an earlier Task 4 query | Proven | Service scans a bounded two-year occurrence-time history; database test detects a nine-month return without a prior Task 4 snapshot. |
| Historical import proof bypassed Task 4 | Proven | Database-backed service test places a 2018 event in the 2018 API window and excludes it from the 2026 window. |
| Scenario 18 covered only one trace class | Proven | Evidence tests check every evidence-bearing derived item in their snapshot; the media database test adds a media-content trace. Generic catalogue/tracer logic covers the remaining DTOs, and authenticated synthetic-subject smoke confirms the rendered drawer path. |
| Python/TypeScript evidence-kind parity | Proven | Python, migration 019, tracer and `frontend/lib/insights/types.ts` all include `temporal_aggregate`; TypeScript compilation passes. |

## Wave status after remediation

| Wave | Status | Gate evidence |
|---:|---|---|
| 0 — contracts and evidence semantics | Proven | Python, TypeScript, schema and tracer evidence kinds are aligned, and the frozen semantics are covered. |
| 1 — service, materialisation and APIs | Proven | Canonical sources, deterministic snapshots, compact payloads, typed APIs and selective affected-bucket reuse/recomputation are proven. |
| 2 — signal-specific analytics | Proven | Search, AI, exposure/engagement and project/era requirements have implementation and focused tests. |
| 3 — contextual correlation | Proven | Change-first bounded search, exposure/Assertion confirmation, competing explanations, constrained DTOs and UI are present and non-causal. |
| 4 — media/location | Proven | Interpretation, sidecars, confirmation and place analytics are proven. Six direct media route/privacy source-contract tests and live metadata-only smoke cover the operational route. |
| 5 — UI | Proven | In an authenticated dark-mode session all named modules and their empty states rendered. Point-in-time, period and compare modes and Quarter granularity changed the URL coherently and left controls usable. The temporal selector, density panel/chart and page states were visually and computationally verified against dark theme tokens. A dedicated local synthetic subject supplied the evidence-bearing card used to open and verify the drawer. |
| 6 — acceptance/integration | Accepted | All 77 current Task 4 tests and the full 323-test suite pass. Authenticated browser verification passed for rendering, temporal interaction, dark-theme cohesion and the evidence-inspector interaction. |

## Synthetic scenarios

All 18 required scenario assertions now have implementation evidence:

1. long-running unengaged newsletters remain exposure;
2. repeated clicks contribute active interest;
3. assistant-only robotics remains exposure;
4. user-authored robotics across sessions recurs;
5. search refinement links to project creation;
6. one curiosity search remains a one-off;
7. a nine-month return is detected from source history without a prior Task 4 query;
8. credible camera GPS/time is a strong observation;
9. a no-GPS landmark stays a candidate;
10. UCL screenshot content cannot establish presence and can produce content-only OCR candidates;
11. downloaded Paris media remains a candidate in the database-backed pipeline;
12. an unrelated coincident event remains coincidence;
13. relevance without exposure remains coincidence;
14. pre-change search/AI evidence can support a relation, never cause;
15. candidates never become causal automatically;
16. human confirmation is attributable and distinct;
17. late import is selected by occurrence time through the Task 4 service;
18. evidence-bearing derived items resolve through the immutable catalogue/index to source evidence.

## Verification record

Independent re-audit results on the current worktree:

- Task 4 Python suite: **77 passed, 1 warning**.
- Full Python suite: **323 passed, 2 skipped, 4 warnings**.
- Direct media route/privacy source-contract suite: **6 passed**.
- Focused frontend TypeScript: passed (`tsc --noEmit`).
- Focused insights ESLint: passed.
- Next.js production build: passed, **61 pages** generated.
- Authenticated `/dashboard/insights`: every named module and empty state rendered; point-in-time, period and compare modes and Quarter granularity updated the URL coherently and controls remained unlocked.
- Authenticated evidence inspector: the isolated local `task4-browser-smoke` subject exposed one visible “Why am I seeing this?” action. It opened the Evidence inspector and loaded detector `task4.signal-hierarchy v2.0.0`, one temporal state and source counts without exposing raw user content.
- A repeated-refresh defect caused by unstable default timestamps was found during the authenticated run, fixed by memoizing the URL-derived selection, and covered by a frontend runtime contract regression test.
- Dark-mode visual verification passed for the temporal selector, activity-density panel/chart, page header, and empty/error/loading states. Computed styles in the real dark session were background `rgb(2, 8, 23)`, border `rgb(30, 41, 59)`, and text `rgb(248, 250, 252)` for the temporal and density surfaces.
- Live database: `insight_catalogue` exists and the evidence-index primary key is `materialisation_id, insight_id, evidence_kind, evidence_ref_id, role`.
- Migrations 019 and 020 are present, exercised by database-backed tests and present in the live schema.
- Live period API and media metadata-only smoke passed.
- The 500-event benchmark completed in `0.255215 s` cold and `0.0000967 s` warm with one Parquet scan.

Browser-fixture scope:

- The user's live profile had zero event partitions and correctly rendered empty states. Drawer verification therefore used the dedicated local `task4-browser-smoke` subject and one synthetic temporal state; it did not modify the user's profile.
- That narrow browser fixture contained zero source artefacts and zero exact evidence locators. It proves the authenticated card-to-drawer interaction, detector/version display, temporal-state display and safe absence of raw user content. Broader database-backed catalogue/index/tracer/locator tests remain authoritative for exact source artefact and locator resolution.
- The browser console contained pre-existing global dashboard messages. No new Task 4 request failure was observed, but this is not a claim that the browser console was globally error-free.

## Acceptance conclusion

The prior architectural, functional, contract, performance and route/privacy gaps are remediated. The authenticated Personal Insights page passed module, empty-state, temporal-control, dark-theme and evidence-inspector verification, while the automated suite proves the broader catalogue/index/tracer/locator paths. Task 4 is accepted. This conclusion does not claim that the isolated browser fixture contained source artefacts or exact locators, or that unrelated global dashboard console messages were resolved. No Task 5 or automatic-deletion work is included.

Related: [[Personal Insights Architecture]], [[Task 4 Implementation Ledger]].
