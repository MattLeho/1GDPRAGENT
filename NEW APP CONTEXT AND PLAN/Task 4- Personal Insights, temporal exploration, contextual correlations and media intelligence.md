Continue work in:

`MattLeho/1GDPRAGENT`

This task assumes:

- immutable evidence and Assertion architecture exists;
    
- the event lake and temporal analysis engine exist;
    
- Task Execution Router exists;
    
- high-volume ActivityEvents are not stored individually in Neo4j.
    

Inspect the actual merged repository before editing.

# Primary task

Create a new user-facing page:

```text
/dashboard/insights
```

Display name:

```text
Personal Insights
```

This page is a longitudinal, evidence-backed projection of the person's own data.

It is not the Data Graph page.

The distinction is:

```text
Data Graph
How are my data, identifiers, controller profiles and capabilities connected?

Personal Insights
How did my observed activity, interests, routines, projects, places and engagement change through time?
```

The page must never present model-generated psychological interpretation as fact.

# 1. Add Personal Insights to dashboard navigation

Add:

```text
Personal Insights
/dashboard/insights
```

to the primary dashboard navigation.

Position it between operational request management and the structural Data Graph.

Suggested conceptual navigation:

```text
Home
View Requests
Personal Insights
Data Graph
ONSIT Discovery
New Request
Settings
```

Use a suitable existing Lucide icon.

Do not overload the Home dashboard with the full insights experience.

A small Personal Insights preview may later be added to Home.

# 2. Build the page around one global temporal control

At the top of the page create a persistent time control.

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

Example:

```text
JAN 2019 ─────── JUN 2021 ─────── MAY 2024 ─────── NOW
                            ▲
                         selected
```

Render a low-profile activity-density histogram behind or beneath the time slider.

This helps the user see sparse and dense periods.

The selected period is global page state.

All insight modules must use the same temporal selection unless a module explicitly enters local drill-down mode.

Support shareable query parameters:

```text
?from=
?to=
?compareFrom=
?compareTo=
```

# 3. Do not create a second source of truth

The Personal Insights page must query:

- ActivityEvent partitions;
    
- accepted Assertions;
    
- TemporalStates;
    
- ProjectEpisodeCandidates;
    
- PersonalEraCandidates;
    
- ControllerProfile states where explicitly compared.
    

Do not create generic editable fields such as:

```text
current_interest = AI
```

Materialised insight tables may exist for performance.

They are derived views linked to:

- analysis run;
    
- derivation method;
    
- derivation version.
    

# 4. Create InsightSnapshot API

Implement a typed PersonalInsightsService.

Suggested methods:

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

Build APIs such as:

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

Endpoints must accept temporal parameters.

Return machine-readable evidence references.

# 5. Model exposure separately from engagement

Create or formalise:

```text
TopicExposureState
ObservedInterestState
EngagementProfile
```

Do not derive interest from topic occurrence count alone.

Evidence classes must distinguish:

```text
AMBIENT_EXPOSURE
PASSIVE_CONSUMPTION
ACTIVE_INVESTIGATION
CREATION
IMPLEMENTATION
COMMUNICATION
```

Examples:

```text
newsletter received
    AMBIENT_EXPOSURE

newsletter opened
    PASSIVE_CONSUMPTION candidate

newsletter link followed
    ACTIVE_INVESTIGATION

search query
    ACTIVE_INVESTIGATION

user-authored AI prompt
    ACTIVE_INVESTIGATION or COMMUNICATION

assistant output
    AMBIENT_EXPOSURE

repeated AI follow-up
    sustained ACTIVE_INVESTIGATION

project file created
    CREATION

code / workflow implementation
    IMPLEMENTATION

email reply about topic
    COMMUNICATION
```

A received email must not increase ObservedInterestState by default.

A recommendation shown to the user must not increase ObservedInterestState by default.

# 6. Add source-specific signal semantics

## Browser/search

Model:

- query;
    
- visit;
    
- transition;
    
- revisitation;
    
- active duration where reliable;
    
- bookmark/save;
    
- referrer path;
    
- domain diversity.
    

A single search is weak evidence.

Repeated related searches, cross-source investigation and subsequent creation are stronger.

Do not infer enduring interest from one curiosity search.

## AI conversations

Separate:

```text
USER_AUTHORED_TURN
ASSISTANT_GENERATED_TURN
```

User-authored turns are behavioural evidence.

Assistant-generated turns are primarily exposure.

Calculate:

- topic;
    
- follow-up depth;
    
- session duration;
    
- repeated session count;
    
- topic recurrence;
    
- question refinement;
    
- cross-session return.
    

Detect investigation chains.

Example:

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

Create:

```text
InvestigationEpisodeCandidate
```

Do not classify the user psychologically.

## Email

Separate:

- received;
    
- opened where reliably known;
    
- clicked where evidence exists;
    
- replied;
    
- forwarded;
    
- archived;
    
- deleted;
    
- unsubscribed.
    

Bulk/newsletter arrival is exposure.

User replies are strong communication evidence.

Do not treat recurring newsletters as continuing interest merely because they continue arriving.

## Creation/project activity

Where connectors provide evidence, support:

- documents created;
    
- files modified;
    
- repositories changed;
    
- project episodes;
    
- repeated tool use.
    

Creation and implementation signals should remain separate from consumption.

# 7. Build Personal Insights page modules

## A. Period overview

Example:

```text
APRIL 2026

Most active topics
Planning
AI
Transport

3 emerging topic clusters
2 returning interests
1 major project episode

Observed activity:
Investigation 38%
Creation 27%
Implementation 19%
Communication 11%
Passive consumption 5%
```

Every percentage must be calculated.

## B. Interest Atlas

Display hierarchical topics.

Example:

```text
Artificial Intelligence

Intensity      ████████
Persistence    ██████
Recurrence     ███████
Breadth        █████████
Novelty        ██
Context spread ████████
```

The six-dimensional state is authoritative.

An optional composite display is secondary.

Allow topic expansion:

```text
AI
 ├── LLMs
 │    ├── Agents
 │    ├── RAG
 │    └── Local inference
 ├── Computer Vision
 └── AI Governance
```

Show:

- selected-period state;
    
- previous-period state;
    
- peak period;
    
- first observed;
    
- latest observed;
    
- active source domains.
    

## C. Search and investigation

Show:

- recurring searches;
    
- emerging question clusters;
    
- investigation episodes;
    
- query refinement chains;
    
- abandoned one-off searches;
    
- searches that later appear in project activity.
    

Do not display sensitive raw queries on the overview without appropriate user control.

Allow evidence drill-down.

## D. AI conversations

Show:

- user-originated topics;
    
- sustained conversation clusters;
    
- recurrent questions;
    
- assistants/services used;
    
- project-linked conversations;
    
- follow-up depth.
    

Do not use assistant-generated text as equal-strength evidence of the user's interests.

## E. Places and movement

Render an interactive map.

Support location evidence classes:

```text
DEVICE_LOCATION
EXIF_GPS
ADDRESS_EVENT
POSTCODE_EVENT
PLACE_EVENT
VISUAL_LOCATION_CANDIDATE
```

Display confidence and evidence type.

The user must be able to filter:

```text
Confirmed/strong observations
Candidates
All
```

Show:

- recurrent places;
    
- new places;
    
- changes in activity centres;
    
- travel periods;
    
- place-linked project episodes.
    

Do not automatically name a dominant overnight cluster `HOME`.

## F. Engagement profile

Display:

```text
CONSUMPTION
INVESTIGATION
CREATION
IMPLEMENTATION
COMMUNICATION
```

Compare with previous period.

Example:

```text
Implementation +41%
Passive consumption -18%
```

## G. Changes

Show:

```text
EMERGING
DECLINING
RETURNING
TEMPORARY BURST
REGIME SHIFT
ROUTINE CHANGE
```

Each card must explain the detector output.

Example:

```text
Urban transport returned after 11 months of low activity.

Evidence:
4 active periods
3 prior dormant periods
mean dormancy: 8.2 months
```

## H. Project episodes

Show burst-derived episodes.

Example:

```text
HEALTHY STREETS WORKFLOW EPISODE
6–19 June 2026

Observed signals:
transport planning
Healthy Streets
workflow automation
data sources
presentation activity

Peak investigation:
11 June

Shift towards implementation:
6 July
```

Do not invent a project name unless:

- source evidence names it;
    
- the user confirms it;
    
- or the label is visibly marked machine-generated.
    

## I. Personal eras

Display contiguous behavioural-regime candidates.

Machine label and human label are separate.

Example:

```text
Machine candidate:
"Planning + transport implementation period"

Your label:
"PJA placement"
```

# 8. Build Contextual Correlation Engine

Purpose:

Surface possible relationships between detected behavioural changes and external events.

The engine must detect the behavioural change FIRST.

Do not scan world events and search the user's history for arbitrary coincidences.

Pipeline:

```text
behavioural time series
 ↓
change point / burst / regime shift
 ↓
detected local event
 ↓
retrieve relevant external-context events around window
 ↓
calculate contextual relation vector
 ↓
TemporalCorrelationCandidate
```

Create:

```text
TemporalCorrelationCandidate
```

Fields:

- `id`
    
- `local_change_id`
    
- `external_event_id`
    
- `temporal_proximity`
    
- `semantic_relevance`
    
- `user_exposure_evidence`
    
- `direct_user_statement`
    
- `preceding_related_activity`
    
- `behavioural_persistence`
    
- `competing_explanations_count`
    
- `status`
    
- `analysis_run_id`
    

Statuses:

```text
coincidence_candidate
possible_relation
evidence_supported_relation
user_confirmed
rejected
```

Never use `caused_by` as a machine-generated relationship.

A direct user statement may create a human-confirmed causal claim.

## Exposure evidence

Before strengthening an external-event relationship, search for evidence that the user encountered the subject.

Examples:

- relevant search;
    
- article visit;
    
- user-authored AI discussion;
    
- email engagement;
    
- message authored by user;
    
- user confirmation.
    

Example output:

```text
Instagram use fell from a 20-minute daily median to zero on 14 March.

A relevant regulatory event occurred on the same date.

No evidence currently shows you encountered the event before the behavioural change.

Classification:
Temporal coincidence candidate.
```

Stronger example:

```text
Instagram use ceased after a concentrated 52-minute period of searches and AI discussion about the same regulatory issue.

Related activity occurred before the final Instagram session.

Classification:
Possible relation.

This does not establish cause.
```

# 9. Build external context event storage

Create ExternalContextEvent.

Fields:

- `id`
    
- `title`
    
- `event_type`
    
- `occurred_at`
    
- `ended_at`
    
- `topics`
    
- `jurisdiction`
    
- `source_uri`
    
- `source_artifact_id`
    
- `ingested_at`
    

Sources may later include:

- legislation/regulation feeds;
    
- public policy events;
    
- major platform changes;
    
- software/product releases;
    
- cultural events;
    
- user-added events.
    

External event ingestion must remain separate from personal-data ingestion.

Do not send personal behavioural data to public event sources.

# 10. Add optional Media Intelligence pipeline

Media processing is opt-in and tiered.

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

## Stage 1: deterministic metadata

For every image:

- content hash;
    
- perceptual hash where appropriate;
    
- format;
    
- dimensions;
    
- EXIF;
    
- capture timestamp;
    
- timezone metadata;
    
- GPS;
    
- camera/device metadata;
    
- editing software metadata where available.
    

Preserve raw metadata as evidence.

## Stage 2: media-origin classification

Classify:

```text
camera_origin
screenshot
downloaded_media
edited_media
generated_media
unknown
```

Use deterministic metadata/path/dimension heuristics first.

Semantic model only receives ambiguous candidates.

## Stage 3: route by origin class

### camera_origin

Potentially extract:

- scene category;
    
- objects;
    
- landmark candidate;
    
- visual location candidate.
    

GPS + original capture timestamp may create a strong location observation.

No GPS + visual landmark produces a location candidate.

Require evidence and confidence.

### screenshot

Extract:

- OCR;
    
- application/interface candidate;
    
- webpage/service candidate;
    
- visible topics;
    
- visible entities.
    

A screenshot showing a place must not establish physical presence.

### downloaded_media

May contribute content exposure.

It does not establish physical presence.

### unknown

Review or selected visual analysis.

## Stage 4: location evidence

Create MediaLocationCandidate.

Minimum fields:

- `artifact_id`
    
- `occurred_at`
    
- `temporal_precision`
    
- `location_type`
    
- `lat`
    
- `lon`
    
- `place_label`
    
- `basis`
    
- `confidence`
    
- `evidence_locator_id`
    

Basis:

```text
exif_gps
takeout_sidecar
visual_landmark
user_confirmed
```

Do not merge visual landmark candidates into confirmed location observations automatically.

# 11. Evidence inspector

Every insight card requires:

```text
Why am I seeing this?
```

The evidence drawer should display:

- detector;
    
- detector version;
    
- analysis run;
    
- time window;
    
- calculated features;
    
- source counts;
    
- supporting ActivityEvents;
    
- supporting Assertions;
    
- source artefacts;
    
- evidence locators;
    
- model explanation where used.
    

The model explanation is not the evidence.

# 12. Performance

Do not query millions of Parquet records separately for every React card.

Create period-level materialised aggregates.

Suggested levels:

```text
day
week
month
quarter
year
```

Invalidate/recompute aggregates by analysis run and affected partition.

Use DuckDB/Polars for bulk calculations.

The frontend consumes compact insight payloads.

# 13. Tests

Required synthetic scenarios:

1. newsletter received weekly for 3 years but never engaged with;
    
2. newsletter received and clicked repeatedly;
    
3. AI answer mentions robotics but user never follows up;
    
4. user asks repeated robotics questions across 6 sessions;
    
5. search burst followed by project creation;
    
6. one curiosity search does not become enduring interest;
    
7. topic disappears and returns after 9 months;
    
8. camera photo with GPS and capture time;
    
9. UCL landmark photo without GPS;
    
10. screenshot of UCL website;
    
11. downloaded photo of Paris;
    
12. behavioural usage collapse aligned with unrelated external event;
    
13. behavioural change aligned with event but no user exposure evidence;
    
14. behavioural change preceded by relevant searches and user-authored AI discussion;
    
15. contextual candidate never becomes causal fact automatically;
    
16. user confirms a relationship;
    
17. historical data imported in 2026 appears at historical occurred_at time while system discovery remains 2026;
    
18. all insight evidence links resolve to source evidence.
    

Required assertions:

- ambient email exposure does not increase ObservedInterestState by default;
    
- assistant output is not weighted as a user-authored interest signal;
    
- screenshots cannot establish physical presence;
    
- downloaded images cannot establish physical presence;
    
- visual landmark result is a candidate until reviewed;
    
- external-event search begins from detected personal change points;
    
- temporal proximity alone cannot produce evidence-supported relation;
    
- insight materialisation is reproducible from source events.
    

# 14. Documentation

Document:

- Personal Insights philosophy;
    
- signal versus exposure;
    
- time-slider architecture;
    
- AI conversation semantics;
    
- contextual correlation guardrails;
    
- media evidence hierarchy;
    
- location inference guardrails.
    

At completion report:

1. page architecture;
    
2. APIs;
    
3. insight modules;
    
4. interest evidence semantics;
    
5. AI conversation semantics;
    
6. Contextual Correlation Engine;
    
7. Media Intelligence pipeline;
    
8. map/location evidence hierarchy;
    
9. performance strategy;
    
10. tests and exact results.
    

Do not implement automatic data deletion in this task.