---
title: Task 4 Implementation Ledger
date: 2026-07-13
tags:
  - gdpr-agent
  - task-4
  - implementation-ledger
status: provisional-r0-revalidation-required
---

# Task 4 Implementation Ledger

> **PROVISIONAL — superseded by R0 evidence pending revalidation (2026-07-17).** Historical evidence is retained below but does not prove current integrated or authenticated runtime behaviour.

Task 4 implementation, automated verification and authenticated `/dashboard/insights` verification are delivered and accepted. Because the user's live profile had zero event partitions, the evidence-drawer interaction was verified with the isolated local `task4-browser-smoke` subject instead of changing the user's profile. The orchestrator retained ownership of shared contracts, migrations, evidence semantics, temporal selection, privacy, integration and acceptance; delegates implemented bounded modules against the frozen contracts in `intelligence/insights/models.py`, `frontend/lib/insights/types.ts` and migrations 017, 019 and 020.

## Frozen invariants

- Personal Insights is a derived temporal projection, never a mutable interest truth store.
- All insights derive from ActivityEvents, accepted Assertions, versioned TemporalStates/aggregates, episodes/eras and explicit controller-profile comparisons.
- Signal order is `AMBIENT_EXPOSURE → PASSIVE_CONSUMPTION → ACTIVE_INVESTIGATION → CREATION → IMPLEMENTATION → COMMUNICATION` with disengagement and unknown retained separately.
- Received email and assistant-authored text are exposure by default.
- User-authored AI turns are behavioural evidence; one search is weak and cannot establish enduring interest.
- Correlation candidates start from detected personal change and never emit automatic causation.
- Screenshot/download/generated media cannot establish physical presence; visual landmarks remain candidates until review.
- Model explanations are displayed separately and are not evidence.
- All specialist/model work uses the Task 2 router under the configured privacy mode.
- Raw ActivityEvents remain in Parquet and are not projected individually to Neo4j.

## Contract freeze

| Contract | Owner | Location | Status | Gate |
|---|---|---|---|---|
| InsightPeriod / comparison and shared temporal modes | orchestrator | Python/TypeScript Task 4 models | frozen | model validation and TypeScript compile |
| InsightEvidenceRef and InsightTrace | orchestrator | Python/TypeScript Task 4 models; migrations 019/020 evidence index and catalogue | frozen | every derived DTO exposes typed evidence, including `temporal_aggregate` parity |
| Exposure, conversation-role, correlation and media/location enums | orchestrator | Python models and migration 017 checks | frozen | invalid epistemic promotions rejected mechanically |
| InsightSnapshot and module DTOs | orchestrator | Python/TypeScript Task 4 models | frozen | UI delegates consume without inventing analytics |
| Versioned materialisation storage | orchestrator | migrations 017, 019 and 020 | frozen | immutable materialisation-scoped evidence/catalogue; no mutable `current_interest` column/table |
| API query contract | orchestrator | `subject_id`, `mode`, `from`, `to`, `point`, `compareFrom`, `compareTo`, `granularity` | frozen | all page modules use one selection |

## Implementation waves

| Requirement | Wave | Owner | Dependencies | Expected files/modules | Tests | Integration gate | Status | Blocker |
|---|---:|---|---|---|---|---|---|---|
| Period/event-lake reader and materialisation repository | 1 | orchestrator | Task 3 partitions, migration 017 | `insights/repository.py`, `materialization.py` | period filtering, cache/recompute, reproducibility | real snapshot from Parquet | delivered | none |
| Period overview and density | 1 | delegated backend | frozen DTOs/repository | `insights/service.py` | period/compare/density | evidence on every output | delivered | none |
| Day/week/month/quarter/year buckets | 1 | delegated materialisation | migration 017 | materialisation module | cold/warm benchmark, selective bucket reuse/recompute | no per-card full scan | delivered | none |
| Typed API endpoints | 1 | orchestrator | frozen DTOs/services | Python API + Next.js proxies | query validation/API integration | compact real payloads | delivered | none |
| Deterministic exposure/engagement classifier | 2 | delegated signals | ActivityEvent semantics | `insights/signals.py` | newsletter/open/click/reply/unsubscribe, assistant/user turns | hierarchy acceptance | delivered | none |
| Interest Atlas | 2 | orchestrator integration | Task 3 six dimensions + filtered signals | service/materialisation | one-off vs recurrent/returning | no exposure-only interest | delivered | none |
| Search/investigation analysis | 2 | delegated search | frozen episode DTO | `insights/search.py` | refinement, recurrence, one-off, project transition | scenario gate | delivered | none |
| AI conversation analysis | 2 | delegated AI analysis | turn-role enum | `insights/ai_conversations.py` | authored-role weighting and follow-up depth | scenario gate | delivered | none |
| Project episode/era presentation | 2 | orchestrator integration | Task 3 candidates/labels | service DTO mapping | labels remain separate | scenario gate | delivered | none |
| ExternalContextEvent import/storage | 3 | delegated context | migration 017 | `insights/context.py`, API | deterministic fixture import | no personal data sent externally | delivered | none |
| Correlation candidate engine | 3 | delegated context | detected changes, external events | `insights/context.py` | unrelated/proximity/exposure/confirmation | never caused_by | delivered | none |
| Exposure-evidence resolver | 3 | orchestrator integration | local events/assertions | context/service | pre-change evidence only | status strengthening rules | delivered | none |
| Media-origin classifier integration | 4 | delegated media | repaired Task 2 route | `insights/media.py` | camera/screenshot/download/edit/generated | presence guard | delivered | none |
| MediaLocationCandidate processing | 4 | delegated media | EXIF/sidecar/landmark/user confirmation | media/repository/API | GPS, landmark, screenshot/download | evidence-class gate | delivered | none |
| Selective visual routing | 4 | orchestrator integration | Task Router/privacy/media mode | media API/task requests | six direct route/privacy tests; live metadata-only smoke | default metadata-only and strict-local enforcement | delivered | optional local visual model is an enhancement, not a blocker |
| Place aggregates | 4 | delegated media | candidates | media/service | recurrent/new/travel | candidate/confirmed distinct | delivered | none |
| Global temporal control/query params | 5 | delegated UI | frozen TS DTO/API | insights page/components | URL round trip, mode tests and authenticated interaction | one coherent selection; stable memoized URL defaults | delivered | none |
| Period Overview/Engagement | 5 | delegated UI | overview API | UI modules | values from API; authenticated dark-mode style verification | no placeholder data; theme-token surfaces | delivered | none |
| Interest Atlas | 5 | delegated UI | interests API | UI module | six dimensions and compare | no generic score dominance | delivered | none |
| Search and AI modules | 5 | delegated UI | separate APIs | UI modules | sensitive raw text hidden | separate semantics | delivered | none |
| Places/movement | 5 | delegated UI | places API | map/list module | evidence filter distinction | presence-safe | delivered | none |
| Changes/projects/eras | 5 | delegated UI | changes API | UI module | detector explanations | label separation | delivered | none |
| Contextual correlation UI | 5 | delegated UI | context API | UI module | constrained wording | no causal language | delivered | none |
| Evidence inspector | 5 | delegated UI | trace API | drawer/component | complete locator resolution in database fixtures plus authenticated synthetic-subject drawer smoke | every evidence-bearing card exposes trace | delivered | none |
| Synthetic scenario suite | 6 | delegated fixtures/tests | all modules | Task 4 tests/fixtures | all 18 required scenarios | acceptance assertions | delivered | none |
| End-to-end/runtime/performance verification | 6 | orchestrator | integrated app | full stack/docs | migrations/build/type/lint/tests/smoke/benchmark | final audit | complete | none |

## Current verification record

- Task 4 Python: 77 passed, 1 warning.
- Full Python: 323 passed, 2 skipped, 4 warnings.
- Direct media route/privacy source-contract suite: 6 passed.
- TypeScript, focused insights ESLint and Next.js production build passed; the build generated 61 pages.
- Live period API and media metadata-only smoke passed.
- Migrations 019 and 020 are present and exercised.
- The 500-event materialisation benchmark recorded `0.255215 s` cold, `0.0000967 s` warm and one Parquet scan.
- Authenticated `/dashboard/insights` rendered every named module and empty state. Point-in-time, period and compare modes and Quarter granularity changed the URL coherently and controls remained usable.
- The isolated local `task4-browser-smoke` subject supplied one visible “Why am I seeing this?” action. Authenticated interaction opened the Evidence inspector and loaded detector `task4.signal-hierarchy v2.0.0`, one temporal state and source counts without exposing raw user content.
- The authenticated run exposed an infinite-refresh loop caused by unstable default timestamps. URL-derived selection is now memoized and a frontend runtime contract test guards the fix.
- In the real dark session, the temporal selector and activity-density surfaces computed to background `rgb(2, 8, 23)`, border `rgb(30, 41, 59)`, and text `rgb(248, 250, 252)`; page header and empty/error/loading states use the same theme-token system.
- Browser-console review found only pre-existing global dashboard messages and no new Task 4 request failures. This is not a claim that the global console was error-free.
- Browser-fixture scope: the user's live profile stayed empty and unmodified. The dedicated synthetic subject proves the card-to-drawer interaction, but its single temporal-state trace contained zero source artefacts and zero exact locators. Broader database fixtures remain authoritative for catalogue/index selection and exact source/locator resolution.

## API freeze

All module endpoints use the same query selection and return calculated data with evidence references:

- `GET /api/insights/overview`
- `GET /api/insights/interests`
- `GET /api/insights/search`
- `GET /api/insights/ai-conversations`
- `GET /api/insights/places`
- `GET /api/insights/changes`
- `GET /api/insights/context`
- `GET /api/insights/evidence/:id`

Required query names are `subject_id`, `mode`, `from`, `to`, `point`, `compareFrom`, `compareTo`, and `granularity`. The UI owns one global selection and forwards the same serialized query to every module.

## Delegation record

Delegated handoffs must contain scope, files changed, frozen contract used, exact tests/results, assumptions, limitations, integration notes and blockers. No delegated change is accepted until reviewed and retested by the orchestrator.

Related: [[Task 4 Predecessor Audit Ledger]], [[Task 4 Personal Insights, temporal extraction, contextual correlations and media intelligence- delegated]].
