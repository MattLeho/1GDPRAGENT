# Task 6 — Capability, purpose drift, linkability, active DSAR testing and the final privacy product UI

Continue work in `MattLeho/1GDPRAGENT`.

This task assumes Tasks 1–5 and Task 3A are implemented.

# Product philosophy

The application exists to return analytical power to the person being profiled.

It should help the user see:

- what personal data appears to exist;
- how records are linked;
- what has been declared;
- what has been observed;
- what has been derived;
- what a controller appears to have inferred or assigned;
- what capabilities are enabled by data/system combinations;
- who controls, processes, hosts, shares or may legally access relevant datasets;
- why processing/capability was originally justified;
- how documented purpose/scope changed;
- what remains unknown;
- what targeted access request could resolve uncertainty.

The system must not:

- present model speculation as truth;
- equate technical possibility with current use;
- imply capability proves abuse;
- turn heuristic purpose distance into a legal conclusion;
- call behavioural signals psychological truth.

# Primary objective

Build:

- Capability and CapabilityExposureState;
- deterministic Capability Candidate engine;
- Structural Linkability indicators;
- Purpose and possible Purpose Drift;
- original justification versus current scope/technical reach;
- Institutional Access graph;
- PrivacyHypothesis and active DSAR testing;
- DeletionSimulation and post-deletion verification;
- typed privacy query service;
- temporal/epistemic graph API;
- final graph/privacy product UI.

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

# Wave 0 — Orchestrator ontology and epistemic freeze

**Owner: orchestrator only**

Audit predecessor outputs.

Freeze canonical contracts for:

```text
Capability
CapabilityExposureState
CapabilityCandidate
EdgeRisk
LinkabilitySnapshot
IdentifierRemovalSimulation
Purpose
Claim
PurposeDistanceAssessment
Dataset
Authority
InstitutionalAccessEdge
PrivacyHypothesis
DeletionSimulation
ExpectedRemoval
DeletionVerification
PrivacyQueryCitation
```

Freeze status distinctions.

Capability exposure:

```text
evidenced_from_export
documented
legally_authorised
technically_possible
speculative
human_confirmed
```

Graph edge epistemics:

```text
currently_observed
potentially_enabled
alleged_unverified
```

Profile layers:

```text
self_declared
observed_behaviour
controller_profile
system_hypotheses
```

The orchestrator owns migrations and ontology changes.

No sub-agent may add `isInferred` as a replacement for explicit epistemic state.

# Wave 1 — Capability and Linkability engines

## Sub-agent 6.1A — Capability taxonomy and deterministic rules

**Recommended: Terra-Medium**

Implement versioned taxonomy concepts including:

- age classification;
- cross-service identity resolution;
- location reconstruction;
- social graph reconstruction;
- purchase profiling;
- behavioural personalisation;
- behavioural prediction;
- biometric matching;
- communications-content scanning;
- device correlation;
- interest inference;
- sensitive-interest inference;
- risk scoring;
- automated access restriction.

Implement reviewed trigger rules such as:

```text
stable identifier spans services
 → CROSS_SERVICE_IDENTITY_RESOLUTION candidate
```

```text
precise location + sufficient temporal density
 → LOCATION_RECONSTRUCTION candidate
```

```text
behavioural history + controller labels co-occur
 → INTEREST_PROFILING candidate
```

```text
directional interaction history
 → SOCIAL_GRAPH_RECONSTRUCTION candidate
```

Rules produce CapabilityCandidate with rule/version, supporting Assertions/aggregates and evidence status.

The model may explain. It may not promote evidence status beyond the evidence standard.

## Sub-agent 6.1B — Structural identifier statistics

**Recommended: Terra-Medium**

Calculate per identifier:

- controller count;
- service count;
- data-domain count;
- schema count;
- first/last seen;
- temporal persistence;
- occurrence count.

Build EdgeRisk vector:

```text
linkage type
directness
stability
cross-context reuse
uniqueness gain
legal accessibility
reversibility
confidence
```

Vector remains source truth.

## Sub-agent 6.1C — Graph metrics and identifier-removal simulation

**Recommended: Terra-Medium**

Over high-value topology calculate:

- degree;
- betweenness or scalable approximation;
- articulation points;
- connected-component impact.

Implement reproducible graph-snapshot simulation.

Example output must be calculated:

```text
Removing these 3 identifiers would disconnect 41% of currently observed cross-domain linkage paths.
```

Store analysis date, graph version, selected nodes and method.

Do not imply deletion on one platform removes linked data elsewhere.

**Wave 1 gate:** capability and linkability outputs are deterministic candidates/indicators with evidence references and defined graph snapshot.

# Wave 2 — Purpose, policy claims and purpose drift

## 2.1 Purpose semantics

**Owner: orchestrator**

Purpose remains separate from LegalBasis.

Relationships may include:

```text
DataPoint COLLECTED_FOR Purpose
ProcessingActivity ORIGINALLY_JUSTIFIED_BY Purpose
ProcessingActivity CURRENTLY_USED_FOR Purpose
Purpose EXPANDED_TO Purpose
```

Every association requires evidence.

## Sub-agent 6.2A — Policy SourceArtifact/version ingestion

**Recommended: Terra-Medium**

Refactor current policy analysis so fetched policy source/version is preserved as SourceArtifact.

Track version/effective dates where available.

Do not keep only a decontextualised LLM summary as authoritative evidence.

## Sub-agent 6.2B — Grounded Claim extraction

**Recommended: Terra-Medium**

Use existing grounded extraction and Task Execution Router.

Create Claims linked to exact EvidenceLocators.

Claim includes type, text and validity window.

A claim without resolvable support remains candidate/review.

## Sub-agent 6.2C — Purpose lineage and distance heuristic

**Recommended: Terra-Medium**

Implement configurable/versioned heuristic:

```text
same purpose                  0
closely compatible            1
adjacent                      2
materially different          3
unrelated                     4
```

Output:

```text
Possible purpose drift
```

Never:

```text
GDPR violation detected
```

Preserve unknown dates.

## Sub-agent 6.2D — Original justification/current scope/technical reach

**Recommended: Terra-Medium**

Represent separately:

```text
Capability
  ORIGINALLY_JUSTIFIED_BY → Claim
  CURRENT_SCOPE           → ProcessingActivity
  TECHNICALLY_COULD_ENABLE→ ProcessingActivity
```

Technical reach is never queried/styled as observed implementation.

**Wave 2 gate:** policy/purpose claims are source-backed and the drift detector cannot produce legal conclusions.

# Wave 3 — Institutional Access graph

## Sub-agent 6.3A — Dataset and organisation/access ontology projection

**Recommended: Terra-Medium**

Implement supported relationships:

```text
Organisation CONTROLS Dataset
Organisation PROCESSES Dataset
Organisation HOSTS Dataset
Organisation CAN_REQUEST Dataset
Authority HAS_LEGAL_GATEWAY_TO Dataset
Organisation SHARES_WITH Organisation
Organisation USES_SUBPROCESSOR Organisation
```

Add Authority where required.

Access edges may carry:

- access type;
- jurisdiction;
- legal instrument;
- warrant/notice/consent requirements;
- reporting/transparency;
- assertion ID.

## Sub-agent 6.3B — Custody/access/linkability classifier

**Recommended: Terra-Medium**

Distinguish:

```text
CENTRALLY STORED
FEDERATED BUT MUTUALLY ACCESSIBLE
INDEPENDENTLY STORED BUT LINKABLE VIA COMMON IDENTIFIER
```

Do not infer access merely because identifiers match.

Linkability and access are separate.

## Sub-agent 6.3C — Institutional access evidence fixtures

**Recommended: Terra-Medium**

Build synthetic policy/export examples proving the distinctions.

**Wave 3 gate:** shared identifiers do not automatically create access edges.

# Wave 4 — Active graph testing and targeted DSARs

## 4.1 PrivacyHypothesis rules

**Owner: orchestrator**

Statuses:

```text
open
request_drafted
request_sent
confirmed
rejected
unresolved
superseded
```

A hypothesis is an uncertainty object, not graph truth.

## Sub-agent 6.4A — Deterministic hypothesis detectors

**Recommended: Terra-Medium**

Examples:

- stable identifier appears in multiple datasets but linkage mechanism is unknown;
- controller-assigned category exists but derivation evidence is absent;
- export references an internal profile/segment ID with no definition;
- capability candidate lacks evidence of current implementation;
- deletion response conflicts with later observed export evidence.

Produce PrivacyHypothesis with supporting evidence and exact unresolved question.

## Sub-agent 6.4B — Targeted DSAR question templates

**Recommended: Terra-Medium**

Implement evidence-driven templates.

Questions should request specific missing information such as:

- meaning of identifier;
- derivation/source of assigned category;
- recipients/processors;
- retention;
- automated decision logic where applicable;
- linkage across services;
- purpose associated with specific processing.

Use existing request workflow and drafting TaskRoute.

Do not create a parallel DSAR subsystem.

## Sub-agent 6.4C — Hypothesis resolution service

**Recommended: Terra-Medium**

On new response/export:

```text
ingest evidence
 ↓
compare against open hypothesis
 ↓
assertion delta
 ↓
confirmed / rejected / unresolved / superseded
```

Never resolve based solely on model opinion.

**Wave 4 gate:** an uncertainty can generate a targeted request, new evidence can resolve it, and all state changes remain auditable.

# Wave 5 — Deletion simulation and verification

## 5.1 Deletion semantics

**Owner: orchestrator**

Deletion analysis is graph-cut simulation and post-action verification.

Absence from a later export is not proof of legal deletion.

## Sub-agent 6.5A — DeletionSimulation engine

**Recommended: Terra-Medium**

Before deletion/erasure action calculate predicted effects on:

- identifiers;
- account/controller links;
- data-domain paths;
- capability candidates;
- linkability indicators.

Store graph snapshot and method.

Create ExpectedRemoval records.

## Sub-agent 6.5B — Post-deletion observation comparison

**Recommended: Terra-Medium**

Classify:

```text
EXPECTED_REMOVED
CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT
STILL_OBSERVED
UNVERIFIABLE
```

Wording must preserve the distinction between export absence and legal deletion.

## Sub-agent 6.5C — Deletion verification presentation DTOs

**Recommended: Terra-Medium**

Build evidence-backed comparison outputs for UI.

**Wave 5 gate:** no code path equates absence from export with confirmed legal deletion.

# Wave 6 — Typed PrivacyQueryService

## 6.1 Query architecture

**Owner: orchestrator**

Replace keyword graph chat and unrestricted narrative graph interpretation with typed tools.

The model selects tools and explains outputs.

It does not perform arbitrary Cypher writes.

Required tools:

```text
get_current_profile
get_profile_at
compare_profile_periods
trace_assertion
get_assertion_evidence
find_identifier_links
get_identifier_centrality
simulate_identifier_removal
list_controller_assignments
compare_behavioural_and_controller_profile
list_capability_exposure
trace_capability_evidence
list_purpose_drift_candidates
trace_purpose_lineage
list_open_privacy_hypotheses
compare_export_snapshots
get_personal_drift
get_controller_drift
get_understanding_drift
```

Answers cite Assertion IDs/EvidenceLocators.

## Sub-agent 6.6A — Temporal/profile query tools

**Recommended: Terra-Medium**

Implement current/as-of/compare/profile-layer tools.

## Sub-agent 6.6B — Linkability/capability query tools

**Recommended: Terra-Medium**

Implement identifier/linkability/capability tools.

## Sub-agent 6.6C — Purpose/hypothesis/delta query tools

**Recommended: Terra-Medium**

Implement purpose, hypothesis and drift/delta tools.

## Sub-agent 6.6D — Query citation validator

**Recommended: Terra-Medium**

Reject or flag narrative claims that cite no resolvable Assertion/EvidenceLocator for evidence-bearing statements.

**Wave 6 gate:** model chat can answer complex privacy questions without arbitrary graph writes and with evidence citations.

# Wave 7 — Graph API and final product UI

The orchestrator freezes API/filter contracts before UI delegation.

Graph API filters:

```text
asOf
compareTo
profileLayer
epistemicBasis
assertionStatus
capabilityStatus
purpose
sourceArtifact
controller
dataDomain
```

## Sub-agent 6.7A — Temporal and compare graph API

**Recommended: Terra-Medium**

Implement time/compare semantics against accepted temporal states and graph snapshots.

## Sub-agent 6.7B — Profile-layer graph API

**Recommended: Terra-Medium**

Layers:

```text
WHO I SAY I AM
WHAT MY ACTIVITY EVIDENCES
WHAT THE CONTROLLER ASSIGNS
WHAT THE SYSTEM HYPOTHESISES
```

Never reconcile them into one “truth”.

## Sub-agent 6.7C — Graph page modes/navigation

**Recommended: Terra-Medium**

Build modes:

```text
NOW
THROUGH TIME
COMPARE
CONTROLLER PROFILE
CAPABILITIES
LINKABILITY
PURPOSE
ACCESS
```

Add time slider and compare mode.

## Sub-agent 6.7D — Epistemic graph styling

**Recommended: Terra-Medium**

Visually distinguish:

```text
CURRENTLY OBSERVED    solid
POTENTIALLY ENABLED   dashed
ALLEGED / UNVERIFIED  dotted
```

Do not use one `isInferred` boolean.

## Sub-agent 6.7E — Evidence inspector

**Recommended: Terra-Medium**

Display:

- semantic statement;
- basis;
- status;
- confidence;
- all time axes;
- derivation;
- Assertion IDs;
- SourceArtifacts;
- exact EvidenceLocator;
- resolved excerpt/record;
- review history.

## Sub-agent 6.7F — Longitudinal drift views

**Recommended: Terra-Medium**

Render:

```text
PERSONAL DRIFT
CONTROLLER DRIFT
UNDERSTANDING DRIFT
```

## Sub-agent 6.7G — Three-layer profile comparison

**Recommended: Terra-Medium**

Display separately:

```text
SELF-DECLARED
OBSERVED BEHAVIOURAL SIGNAL
CONTROLLER-ASSIGNED
```

System hypotheses remain an explicit fourth analytical layer where shown.

## Sub-agent 6.7H — Capability, linkability, purpose and access panels

**Recommended: Terra-Medium**

Build leaf modules from frozen DTOs.

No component recalculates its own capability/purpose score.

**Wave 7 gate:** final UI exposes uncertainty, time and epistemic layers rather than flattening them.

# Wave 8 — Product wording guardrails and acceptance scenarios

## Sub-agent 6.8A — Shared wording guardrail utility/tests

**Recommended: Terra-Medium**

Preferred language:

```text
available export evidence indicates
appears controller-assigned
observed activity shows
the combination could technically support
possible purpose drift
no source evidence currently establishes
```

Avoid unsupported:

```text
You are ...
knows for certain
illegal
abusing
will survive deletion
```

unless direct evidence establishes the statement and the assertion basis permits it.

Implement tests for generated/presented status wording where practical.

## Sub-agent 6.8B — End-to-end synthetic acceptance pack

**Recommended: Terra-Medium**

Create scenarios covering:

- stable ID across multiple services;
- location reconstruction candidate;
- controller-assigned interest distinct from behavioural interest;
- capability documented versus technically possible;
- policy purpose expansion;
- unrelated purpose-distance candidate;
- shared identifier without access evidence;
- legal gateway evidence;
- open PrivacyHypothesis;
- targeted DSAR;
- response confirms one hypothesis and leaves another unresolved;
- deletion simulation;
- later export still observes data;
- later export lacks data but legal deletion remains unverifiable;
- self-declared/behaviour/controller layers disagree;
- as-of and compare views;
- every narrative answer cites evidence.

# Wave 9 — Orchestrator final audit

**Owner: orchestrator only**

Required acceptance:

- CapabilityExposureState distinguishes evidenced/documented/authorised/possible/speculative;
- deterministic capability candidate engine precedes model explanation;
- Structural Linkability uses vector/metrics, not universal privacy score;
- identifier-removal percentages are reproducible from named graph snapshots;
- Purpose and LegalBasis remain distinct;
- possible purpose drift never becomes automatic legal conclusion;
- policy Claims are grounded to source artefacts/locators;
- technical reach is distinct from current observed scope;
- custody/access/linkability are distinct;
- shared identifier alone does not create access;
- PrivacyHypothesis is not graph truth;
- active DSAR testing uses existing request workflow;
- deletion verification does not equate export absence with legal deletion;
- PrivacyQueryService is typed and read-only with evidence citations;
- graph API supports time, compare and profile layers;
- UI keeps self-declared, behavioural, controller and hypothesis layers distinct;
- Unknown/unresolved remains visible.

Run full application/runtime tests.

Update README and architecture docs to describe the finished product as:

> A local-first personal-data autonomy system that uses privacy access rights and user-authorised connectors to acquire evidence, reconstructs longitudinal behavioural and controller-profile histories, maps identifier linkability and institutional capability, and uses AI as an evidence-constrained interface for exploring a temporal privacy graph.

At completion report:

1. delegation map;
2. capability architecture;
3. linkability engine;
4. purpose/policy lineage;
5. institutional access;
6. PrivacyHypothesis and active DSAR testing;
7. deletion simulation/verification;
8. PrivacyQueryService;
9. graph API;
10. final product UI;
11. exact end-to-end tests/results;
12. wording/epistemic guardrails;
13. every incomplete requirement.

Do not weaken provenance, temporal history or epistemic distinctions to make the UI look complete.
