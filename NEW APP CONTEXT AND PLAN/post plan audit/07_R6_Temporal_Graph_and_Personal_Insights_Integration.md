# R6 — Temporal Graph and Personal Insights Integration

## Goal

Deliver the profile-scoped temporal graph experience: point-in-time selection, period selection, comparison and playback, integrated with authenticated Personal Insights and evidence tracing.


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

- R0–R5 accepted and merged.
- Authority, schema, router, connectors and responsive shell are stable.

## Lead-agent ownership

The lead agent owns temporal semantics, point/range contracts, graph snapshot/playback rules, profile-to-subject mapping, Graph/Insights consistency, evidence requirements, Neo4j diagnostics and final epistemic/performance review.

## Subagent delegation

### A — Profile-to-subject integration

Remove first-user defaults and implement canonical authority mapping.

### B — Temporal APIs

Build extent, density, point snapshot, period and comparison endpoints.

### C — PostgreSQL/Neo4j indexes

Optimise as-of and range queries without changing projection authority.

### D — Sliders/playback

Implement point slider, dual-handle range, comparison selection, URL persistence and playback controls.

### E — Graph renderer

Animate deterministic snapshot differences while preserving stable layout.

### F — Personal Insights integration

Use the same authority and temporal-selection contract across Insights modules.

### G — Neo4j diagnostics

Add protected connection, projection and queue diagnostics.

### H — Browser/performance/evidence tests

Own signed-in temporal fixtures, trace tests and scale tests.

## Temporal control contract

### Point

Single handle from earliest observation to `Now`.

Output:

```text
asOf
```

### Period

Dual handles.

Output:

```text
from
to
```

### Compare

Two explicit periods or current plus baseline:

```text
currentFrom
currentTo
baselineFrom
baselineTo
```

### Playback

```text
play
pause
step backward
step forward
speed
granularity
loop
```

Playback uses queryable graph snapshots, not a pre-rendered video as the canonical implementation.

## Extent API

Return:

```text
earliest_observation
latest_observation
now
available_granularities
event_density_buckets
important_boundaries
timezone
```

Return a truthful empty state when there is no data.

## Snapshot semantics

At a selected date:

- include nodes linked by active accepted assertions;
- optionally expose hypotheses as a distinct layer;
- distinguish active, dormant and retired;
- preserve provenance and isolated active nodes;
- never imply that visual retirement means evidence deletion.

## Prominence

Node size/opacity must derive from a named deterministic metric, such as:

- active accepted relationship count;
- bounded evidence-weight score;
- temporal interest strength;
- controller assignment count.

Expose the metric and window in the inspector. No arbitrary “AI importance”.

## Compare semantics

Mark:

```text
added
retired/no-longer-active
changed
unchanged
```

Retired is not erased.

## Playback algorithm

1. Fetch extent/density.
2. Select buckets by granularity.
3. Prefetch bounded adjacent snapshots.
4. Diff stable node/edge IDs.
5. Animate enter/update/retire.
6. Preserve positions where possible.
7. support reduced motion.
8. Pause on query/fetch error.

## Personal Insights authority

Every request must:

- use the authenticated canonical profile;
- send internal authority;
- share point/period/compare selection;
- reject arbitrary subject IDs as authority.

Integrate Interest Atlas, search patterns, AI conversation stages, projects, places, changes, context candidates, media settings and evidence trace.

## Evidence interaction

Graph:

```text
node/edge/change
→ assertion
→ EvidenceLocator
→ SourceArtifact
→ AnalysisRun
→ derivation method/version
```

Insights:

```text
Why am I seeing this?
→ exact derived item
→ detector/version
→ input events/states/assertions
→ artefacts and locators
```

## Neo4j infrastructure settings

Protected diagnostics:

```text
connection source
redacted URI
username
database
credential status
test connection
driver version
last successful query
projection health
projection queue
active nodes/relationships
last projection run
```

A separate Neo4j browser login must never be required for app operation.

## Required tests

### Authority

- missing/expired session rejected;
- Profile A cannot query B;
- Python rejects missing internal authority;
- no first-user fallback.

### Temporal

- earliest point;
- Now;
- dual-handle range;
- empty period;
- open-ended valid state;
- retired assertion;
- late-ingested old event;
- added/retired/unchanged compare;
- timezone boundary;
- URL restoration.

### Playback

- stable IDs preserve layout;
- controls work;
- no duplicate edges;
- pause on error;
- reduced motion;
- no fabricated snapshots.

### Evidence

- evidence-bearing changes resolve to assertions/locators;
- unknown remains explicit;
- hypothesis layer is visually and structurally distinct.

### Browser

- sliders work by mouse and keyboard;
- labels remain visible;
- playback works at narrow/wide widths;
- inspector opens during playback;
- Insights follows the same period;
- Neo4j connection test works without browser login.

### Performance

Use multi-year fixtures with thousands of nodes/edges and both dense/sparse periods. Set latency/memory budgets after measuring baseline.

## Definition of done

- Graph and Insights use the active profile.
- Point, period, compare and playback are operational.
- Sliders replace date-input-only interaction.
- Animation derives from deterministic snapshots.
- Retirement is not confused with deletion.
- Evidence-bearing changes are traceable.
- Neo4j diagnostics exist.
- Empty/error states are truthful.
- Independent temporal, epistemic, browser and performance audits pass.

## Paste-ready `/goal`

```text
Execute R6 — Temporal Graph and Personal Insights Integration.

Audit R0–R5 first. Remove first-user defaults and make Graph and Personal Insights use the authenticated canonical profile and signed internal authority. Implement temporal extent, a single-handle point slider, dual-handle period selector, comparison periods and snapshot-based graph playback with deterministic node/edge transitions.

Integrate Graph and Insights evidence tracing, preserve active/dormant/retired and hypothesis distinctions, and add protected Neo4j connection/projection diagnostics. Do not use a pre-rendered video as the canonical time engine and do not imply that visually retired data was deleted.

Delegate profile mapping, APIs/indexes, sliders, renderer, Insights, diagnostics and performance/browser tests to bounded subagents. Keep temporal semantics, evidence contracts, Graph/Insights consistency and final epistemic judgement under the lead agent.

Before completion, run authority, temporal edge-case, playback, evidence, responsive browser and scale tests. Commission independent temporal and signed-in browser auditors.
```
