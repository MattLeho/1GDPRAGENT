# Task 4 — Personal Insights, temporal exploration, contextual correlations and media intelligence

Continue work in `MattLeho/1GDPRAGENT`.

This task assumes:

- Task 1 immutable evidence/assertion architecture exists;
- Task 2 Task Execution Router exists;
- Task 3 and Task 3A event lake, temporal states, file adapters and specialist task routes exist;
- high-volume ActivityEvents are not stored individually in Neo4j.

Inspect the actual merged implementation before editing.

# Primary objective

Create:

```text
/dashboard/insights
```

Display name:

```text
Personal Insights
```

The page is a longitudinal, evidence-backed projection of the person's own data.

```text
DATA GRAPH
How are data, identifiers, controller profiles and capabilities connected?

PERSONAL INSIGHTS
How did observed activity, interests, routines, projects, places and engagement change through time?
```

Never present model-generated psychological interpretation as fact.

## Delegation protocol for this task

The primary agent is the **orchestrator and integrator**. Keep GPT-5.6 Sol on work that requires cross-cutting architectural judgement, security/privacy decisions, migration ownership, shared contracts, integration, or final acceptance.

Use **Terra-Medium** for bounded delegated subtasks where the input, output contract, file ownership, and tests can be stated precisely. If Terra-Medium is unavailable in the current environment, use the cheapest competent sub-agent available for the same bounded work. Do not silently push every leaf task back to the orchestrator unless delegation has failed.

### Work that stays with the orchestrator

The orchestrator owns:

- reading the full task and all predecessor plans;
- auditing the actual merged repository before edits;
- freezing shared interfaces and invariants;
- PostgreSQL migration ownership and migration ordering;
- canonical Pydantic/TypeScript contracts that multiple modules consume;
- provenance and epistemic rules;
- processing-mode and external-data-transfer rules;
- concurrency/resumability architecture;
- any destructive operation or deletion semantics;
- merge/integration decisions;
- end-to-end tests;
- final line-by-line acceptance audit.

### Work suitable for Terra-Medium sub-agents

Prefer delegation for:

- repository inventories and implementation maps;
- isolated adapters behind a frozen interface;
- deterministic extractors or classifiers with explicit fixtures;
- source/file-family parser implementations;
- test fixture generation;
- unit-test expansion;
- leaf React components consuming already-defined API contracts;
- documentation updates after implementation is stable;
- performance micro-benchmarks;
- compatibility shims and narrow migrations prepared for orchestrator review.

### Delegation rules

1. **Freeze the contract before parallel work.** Do not delegate five agents to invent five versions of the same interface.
2. **One owner per shared file.** The orchestrator should pre-assign file/directory ownership. Avoid parallel edits to migrations, canonical models, registries, or central routers.
3. **Use isolated worktrees/branches where supported.** Each sub-agent should make a coherent, reviewable change set.
4. **No semantic scope expansion.** A sub-agent may not redesign the ontology, weaken provenance, add an external fallback, or introduce a new source of truth because it makes its leaf task easier.
5. **No unreviewed merge.** The orchestrator reviews diffs, runs focused tests, then integrates.
6. **Failed sub-agent work is not a blocker to reasoning.** Re-scope, re-delegate, or implement the critical part centrally.
7. **Do not count generated files as implementation.** A delegated task is complete only when the contract is satisfied and tests pass.

### Required sub-agent handoff

Every delegated task must return:

```text
SUBTASK
Scope completed:

FILES CHANGED
- ...

CONTRACT USED
- ...

TESTS RUN
- command
- result

ASSUMPTIONS
- ...

KNOWN LIMITATIONS
- ...

INTEGRATION NOTES
- ...

BLOCKERS
- none / ...
```

The orchestrator maintains one implementation ledger for the whole task:

```text
requirement
owner
dependency
implementation location
status
tests
integration status
migration/backfill note
blocker
```

### Wave gates

Do not begin a later wave merely because one sub-agent finished early.

At the end of every wave the orchestrator must:

1. inspect every delegated diff;
2. reconcile duplicate concepts;
3. run the wave's focused tests;
4. run type checking/compile checks for touched services;
5. update the implementation ledger;
6. explicitly mark the shared contracts that are now frozen for the next wave.

# Wave 0 — Contract and evidence-semantics freeze

**Owner: orchestrator**

Audit Task 3 outputs and freeze:

```text
InsightPeriod
InsightComparisonPeriod
InsightEvidenceRef
InsightSnapshot
TopicExposureState
ObservedInterestState
EngagementProfile
InvestigationEpisodeCandidate
TemporalCorrelationCandidate
ExternalContextEvent
MediaLocationCandidate
```

Freeze the distinction:

```text
AMBIENT_EXPOSURE
PASSIVE_CONSUMPTION
ACTIVE_INVESTIGATION
CREATION
IMPLEMENTATION
COMMUNICATION
```

Rules:

- received newsletter = exposure by default;
- assistant-generated AI output = exposure by default;
- user-authored AI prompt = behavioural evidence;
- one curiosity search is weak evidence;
- repeated investigation across sources is stronger;
- creation and implementation remain distinct from consumption;
- correlation is not causation;
- screenshot/downloaded image does not establish physical presence;
- visual landmark is a candidate until reviewed.

The orchestrator defines API contracts before leaf UI work.

# Wave 1 — Insight service and materialisation backend

## Sub-agent 4.1A — Period aggregates and InsightSnapshot service

**Recommended: Terra-Medium**

Implement typed service methods:

```text
get_period_overview
get_interest_states
get_search_insights
get_ai_conversation_insights
get_place_insights
get_engagement_profile
get_project_episodes
get_routine_changes
get_personal_drift
get_contextual_correlations
trace_insight
```

Use ActivityEvent partitions, accepted Assertions and versioned TemporalStates.

Do not create `current_interest` truth fields.

Materialised tables/views are derived and store:

- analysis run;
- derivation method;
- derivation version;
- affected partition/window.

## Sub-agent 4.1B — Period materialisation and performance

**Recommended: Terra-Medium**

Create day/week/month/quarter/year aggregate materialisation.

Use DuckDB/Polars.

Requirements:

- no per-card scan of millions of Parquet rows;
- invalidation/recompute by affected analysis run/partition;
- compact API payloads;
- benchmark cold/warm period queries;
- cache key includes temporal selection and derivation version.

## 1.3 API integration

**Owner: orchestrator**

Expose typed APIs such as:

```text
GET /api/insights/overview
GET /api/insights/interests
GET /api/insights/search
GET /api/insights/ai-conversations
GET /api/insights/places
GET /api/insights/changes
GET /api/insights/context
GET /api/insights/evidence/:id
```

Every endpoint accepts period/compare parameters and returns evidence references.

**Wave 1 gate:** one synthetic period snapshot is reproducible from source events and every surfaced insight is traceable.

# Wave 2 — Signal-specific analytical modules

## Sub-agent 4.2A — Search and investigation semantics

**Recommended: Terra-Medium**

Calculate:

- query recurrence;
- related-query clusters;
- revisitation;
- domain diversity;
- refinement chains;
- abandoned one-offs;
- search-to-project transitions.

Create evidence-backed InvestigationEpisodeCandidates.

Do not treat a single search as enduring interest.

## Sub-agent 4.2B — AI conversation semantics

**Recommended: Terra-Medium**

Preserve:

```text
USER_AUTHORED_TURN
ASSISTANT_GENERATED_TURN
SYSTEM_TURN
TOOL_TURN
UNKNOWN
```

Calculate:

- user-originated topic;
- follow-up depth;
- session duration;
- repeated-session count;
- recurrence;
- question refinement;
- cross-session return;
- project-linked activity where evidence exists.

Detect:

```text
initial question
 ↓
technical follow-up
 ↓
architecture follow-up
 ↓
implementation follow-up
 ↓
related project activity
```

Assistant text is not equal-strength evidence of user interest.

## Sub-agent 4.2C — Exposure and engagement classifier

**Recommended: Terra-Medium**

Implement deterministic mapping from source event semantics to:

```text
AMBIENT_EXPOSURE
PASSIVE_CONSUMPTION
ACTIVE_INVESTIGATION
CREATION
IMPLEMENTATION
COMMUNICATION
```

Add source-specific confidence/reliability.

For email:

- received = exposure;
- reliable open evidence = weak passive;
- click = active;
- reply = communication;
- unsubscribe = disengagement action.

Repeated bulk delivery without engagement must not sustain ObservedInterestState.

## Sub-agent 4.2D — Project episode and era presentation models

**Recommended: Terra-Medium**

Consume Task 3 candidates.

Build presentation DTOs for:

- project episodes;
- topic co-emergence;
- personal eras;
- human label versus machine label;
- peak investigation;
- transition toward creation/implementation.

Do not invent project names unless source/human evidence exists or the label is explicitly marked machine-generated.

**Wave 2 gate:** synthetic newsletter, AI-conversation and curiosity-search scenarios enforce the signal hierarchy.

# Wave 3 — Contextual Correlation Engine

## 3.1 Correlation epistemic rules

**Owner: orchestrator**

Freeze status:

```text
coincidence_candidate
possible_relation
evidence_supported_relation
user_confirmed
rejected
```

Never emit `caused_by` automatically.

A direct user-confirmed statement may create a human-confirmed causal claim through the normal Assertion path.

## Sub-agent 4.3A — ExternalContextEvent storage and import interface

**Recommended: Terra-Medium**

Implement:

```text
id
title
event_type
occurred_at
ended_at
topics
jurisdiction
source_uri
source_artifact_id
ingested_at
```

External event acquisition stays separate from personal-data ingestion.

Do not send personal behavioural data to external event sources.

Build fixture/import interfaces for legislation, platform changes, product releases, public-policy events and user-added events.

Live external feeds are not required unless already available.

## Sub-agent 4.3B — Correlation candidate engine

**Recommended: Terra-Medium**

Pipeline:

```text
detected personal change
 ↓
bounded temporal window
 ↓
relevant external context retrieval
 ↓
relation feature vector
 ↓
TemporalCorrelationCandidate
```

Fields:

```text
local_change_id
external_event_id
temporal_proximity
semantic_relevance
user_exposure_evidence
direct_user_statement
preceding_related_activity
behavioural_persistence
competing_explanations_count
status
analysis_run_id
```

The search starts from a detected personal change. Do not trawl world events and hunt for arbitrary coincidences.

## Sub-agent 4.3C — Exposure-evidence resolver

**Recommended: Terra-Medium**

Before strengthening a relation, search local evidence for:

- related search;
- article visit;
- user-authored AI discussion;
- email engagement;
- authored message;
- user confirmation.

Temporal proximity alone cannot produce evidence-supported relation.

Output language is evidence-constrained.

**Wave 3 gate:** unrelated coincident events remain coincidence candidates; relevant pre-change exposure may produce possible relation but never automatic cause.

# Wave 4 — Media intelligence and location evidence

Task 3A provides file-family media adapters. Task 4 adds interpretation.

## 4.1 Media policy

**Owner: orchestrator**

Modes:

```text
metadata_only
selective_visual
full_visual
```

Default:

```text
metadata_only
```

All model calls go through Task Execution Router and processing privacy mode.

## Sub-agent 4.4A — Media-origin classifier

**Recommended: Terra-Medium**

Create deterministic features from:

- EXIF;
- path;
- dimensions;
- device/camera metadata;
- editing software;
- screenshot-like geometry/metadata;
- download/source hints.

Classify candidate:

```text
camera_origin
screenshot
downloaded_media
edited_media
generated_media
unknown
```

Semantic task receives ambiguous candidates only.

## Sub-agent 4.4B — Image metadata and MediaLocationCandidate

**Recommended: Terra-Medium**

Build location candidate creation from:

```text
exif_gps
takeout_sidecar
visual_landmark
user_confirmed
```

Fields:

```text
artifact_id
occurred_at
temporal_precision
location_type
lat
lon
place_label
basis
confidence
evidence_locator_id
```

Rules:

- GPS + credible original capture time may support strong location observation;
- no-GPS landmark result is candidate;
- screenshot of a place does not establish physical presence;
- downloaded media does not establish physical presence;
- never auto-label overnight cluster HOME.

## Sub-agent 4.4C — Selective screenshot/visual workflow

**Recommended: Terra-Medium**

Use TaskRoutes:

```text
image.ocr
image.caption
image.landmark_candidate
image.origin_classification
```

For screenshots extract candidate:

- OCR;
- application/interface;
- webpage/service;
- visible topics;
- visible entities.

Preserve image-region locators.

Do not treat visible place content as presence evidence.

## Sub-agent 4.4D — Place aggregate backend

**Recommended: Terra-Medium**

Aggregate location observations/candidates into:

- recurrent places;
- new places;
- activity-centre changes;
- travel periods;
- place-linked project episodes.

Preserve evidence class and confidence.

**Wave 4 gate:** media fixtures enforce presence versus content-exposure distinctions.

# Wave 5 — Personal Insights UI

The orchestrator freezes `InsightSnapshot` and module API DTOs before UI delegation.

## Sub-agent 4.5A — Global temporal control

**Recommended: Terra-Medium**

Build a persistent page time control.

Modes:

```text
POINT IN TIME
PERIOD
COMPARE
```

Granularity:

```text
month
quarter
year
custom
```

Add low-profile activity-density histogram.

Support query parameters:

```text
?from=
?to=
?compareFrom=
?compareTo=
```

Global selection drives every module unless a drill-down explicitly overrides locally.

## Sub-agent 4.5B — Period Overview and Engagement Profile

**Recommended: Terra-Medium**

Render calculated:

- active topics;
- emerging/returning topics;
- project episode count;
- engagement distribution.

Percentages must come from API values.

Compare engagement dimensions with prior period.

## Sub-agent 4.5C — Interest Atlas

**Recommended: Terra-Medium**

Display hierarchical topics and six dimensions:

```text
intensity
persistence
recurrence
breadth
novelty
context dispersion
```

Show selected period, previous period, peak, first/latest observed and active source domains.

Optional composite is secondary.

## Sub-agent 4.5D — Search and AI conversation modules

**Recommended: Terra-Medium**

Build two separate modules consuming backend DTOs.

Search:

- recurring searches;
- emerging question clusters;
- investigation episodes;
- refinement chains;
- abandoned one-offs;
- project-linked searches.

AI:

- user-originated topics;
- sustained clusters;
- recurrent questions;
- services/assistants;
- project-linked conversations;
- follow-up depth.

Sensitive raw queries are hidden from overview by default and available in evidence drill-down.

## Sub-agent 4.5E — Places and movement map

**Recommended: Terra-Medium**

Render interactive map with filters:

```text
Confirmed/strong observations
Candidates
All
```

Show evidence class and confidence.

Do not merge candidate and confirmed markers visually without distinction.

## Sub-agent 4.5F — Changes, Project Episodes and Personal Eras

**Recommended: Terra-Medium**

Render:

```text
EMERGING
DECLINING
RETURNING
TEMPORARY BURST
REGIME SHIFT
ROUTINE CHANGE
```

Each card explains calculated detector values.

Render project episodes and eras with separate machine/human labels.

## Sub-agent 4.5G — Contextual correlation module

**Recommended: Terra-Medium**

Display local change, context event, exposure evidence and classification.

Use wording such as:

```text
Temporal coincidence candidate
Possible relation
Evidence-supported relation
User confirmed
```

Never imply cause from timing alone.

## Sub-agent 4.5H — Evidence inspector

**Recommended: Terra-Medium**

Every insight card exposes:

```text
Why am I seeing this?
```

Drawer displays:

- detector/version;
- analysis run;
- time window;
- calculated features;
- source counts;
- supporting ActivityEvents;
- Assertions;
- SourceArtifacts;
- EvidenceLocators;
- model explanation where used.

The model explanation is not the evidence.

**Wave 5 gate:** all UI modules use the same temporal state, every card traces to evidence, and no component invents its own analytics.

# Wave 6 — Synthetic acceptance and integration

## Sub-agent 4.6A — Insight scenario fixtures

**Recommended: Terra-Medium**

Implement all scenarios:

1. weekly newsletter for 3 years, never engaged;
2. newsletter clicked repeatedly;
3. assistant mentions robotics with no user follow-up;
4. user asks robotics questions across 6 sessions;
5. search burst followed by project creation;
6. one curiosity search;
7. topic returns after 9 months;
8. camera photo with GPS/time;
9. UCL landmark without GPS;
10. screenshot of UCL website;
11. downloaded Paris photo;
12. usage collapse aligned with unrelated event;
13. behavioural change/event with no exposure evidence;
14. change preceded by relevant searches and user-authored AI discussion;
15. contextual candidate never becomes causal automatically;
16. user confirms relationship;
17. historical activity imported in 2026;
18. every evidence link resolves.

## 6.2 Orchestrator acceptance audit

Required assertions:

- ambient email exposure does not increase ObservedInterestState by default;
- assistant output is not weighted as user-authored interest;
- screenshots cannot establish physical presence;
- downloaded images cannot establish physical presence;
- visual landmark remains candidate until reviewed;
- external-event search begins from detected change points;
- temporal proximity alone cannot create evidence-supported relation;
- materialised insights are reproducible;
- all cards expose resolvable evidence;
- compare mode uses one coherent global temporal selection;
- no generic editable `current_interest` truth store exists.

Run builds, type checks, lint, relevant Python checks/tests and full synthetic acceptance.

Update documentation for:

- Personal Insights philosophy;
- signal versus exposure;
- time control;
- AI conversation semantics;
- contextual-correlation guardrails;
- media evidence hierarchy;
- location inference.

At completion report:

1. sub-agent delegation map;
2. page architecture;
3. APIs and materialisation;
4. insight modules;
5. interest evidence semantics;
6. AI conversation semantics;
7. contextual-correlation engine;
8. media intelligence;
9. location evidence hierarchy;
10. performance benchmarks;
11. exact tests/results;
12. every incomplete requirement.

Do not begin Task 5 and do not implement automatic deletion.

## Completion record — 2026-07-13

Task 4 is complete and accepted. The complete delegation map, frozen contracts, implementation locations, migration notes and per-wave integration record are in `Technical Documentation/Task 4 Implementation Ledger.md`; the requirement-by-requirement decision is in `Technical Documentation/Task 4 Acceptance Audit.md`; the resulting system design is in `Technical Documentation/Personal Insights Architecture.md`.

Final evidence:

- all 18 synthetic acceptance scenarios pass;
- the Task 4 suite reports **77 passed, 1 warning**;
- the full Python suite reports **323 passed, 2 skipped, 4 warnings**;
- focused TypeScript and insights ESLint checks pass;
- the Next.js production build passes with **61 pages**;
- the live period API, metadata-only zero-task media path and 500-event one-scan benchmark pass (`0.255215 s` cold, `0.0000967 s` warm);
- authenticated `/dashboard/insights` renders every named module and empty state;
- point-in-time, period and compare selections and Quarter granularity update the shared URL coherently and controls remain unlocked;
- the isolated local `task4-browser-smoke` subject exposes one visible evidence action; it opens the Evidence inspector and loads detector `task4.signal-hierarchy v2.0.0`, one temporal state and source counts without exposing raw user content;
- an infinite-refresh loop caused by unstable default timestamps was corrected with memoized URL-derived selection and a regression contract test;
- dark-mode temporal controls, activity-density surfaces, page header and empty/error/loading states use theme tokens; the real dark session measured background `rgb(2, 8, 23)`, border `rgb(30, 41, 59)`, and text `rgb(248, 250, 252)` on the temporal and density surfaces.

The user's authenticated profile contained zero event partitions and remained unmodified. Drawer smoke therefore used the dedicated synthetic subject and temporal state described above. Its trace contained zero source artefacts and zero exact locators, so broader database-backed fixtures remain authoritative for catalogue/index selection and exact source/locator resolution. Browser-console review found pre-existing global dashboard messages and no new Task 4 request failure; this is not a claim that the global console was error-free.

No Task 5 or automatic-deletion work was started.
