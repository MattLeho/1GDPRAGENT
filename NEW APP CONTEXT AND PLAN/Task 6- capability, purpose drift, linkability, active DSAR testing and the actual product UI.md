Continue work in the local repository:

`MattLeho/1GDPRAGENT`

This task assumes completion of:

1. the immutable evidence/assertion and canonical graph foundation;
    
2. the large-scale deterministic ingestion/event-lake pipeline;
    
3. the temporal personal/controller/system history model.
    

Inspect the actual merged repository before editing.

# Product philosophy

The application exists to return analytical power to the person being profiled.

It should help the user see:

- what personal data appears to exist;
    
- how records are linked;
    
- what has been explicitly declared;
    
- what has been observed;
    
- what has been derived;
    
- what a controller appears to have inferred or assigned;
    
- what capabilities are enabled by the combination of data and systems;
    
- who controls, processes, hosts, shares or may legally access relevant datasets;
    
- why processing or capability was originally justified;
    
- how documented purpose or scope changed;
    
- what remains unknown;
    
- what targeted access request could resolve the uncertainty.
    

The system must not present model speculation as truth.

The system must not equate technical possibility with current use.

The system must not imply that capability proves abuse.

The system must not use a heuristic purpose-distance result as a legal conclusion.

The system must not call observed behavioural signals psychological truth.

# Primary task

Build the Capability, Linkability, Purpose Drift, Institutional Access, Active Graph Testing and Deletion Verification layers.

Then redesign the graph and analysis interface around the application's three temporal histories:

1. personal behavioural history;
    
2. controller-profile/capability history;
    
3. system-understanding history.
    

# 1. Add Capability as a first-class ontology concept

Implement:

```text
Capability {
  node_id,
  name,
  description,
  capability_type,
  sensitivity,
  reversibility
}
```

Capability itself is a stable concept.

Evidence that a capability is visible or relevant through time belongs in:

```text
CapabilityExposureState {
  node_id,
  capability_id,
  first_evidenced_at,
  last_evidenced_at,
  evidence_basis,
  confidence,
  status
}
```

Supported capability-status values must distinguish:

- `evidenced_from_export`
    
- `documented`
    
- `legally_authorised`
    
- `technically_possible`
    
- `speculative`
    
- `human_confirmed`
    

Do not collapse them into one boolean `exists`.

Initial capability taxonomy may include:

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
    

Taxonomy entries are concepts.

The system still needs evidence before associating a capability with a controller/profile.

Relationships may include:

```text
(:Capability)-[:ENABLED_BY]->(:DataDomain)
(:Capability)-[:REQUIRES]->(:ProcessingActivity)
(:Organisation)-[:OPERATES]->(:Capability)
(:PolicyInstrument)-[:CREATES_OR_EXPANDS]->(:Capability)
(:Purpose)-[:JUSTIFIES]->(:Capability)
(:Capability)-[:LATER_USED_FOR]->(:Purpose)
(:CapabilityExposureState)-[:ABOUT]->(:Capability)
(:ControllerProfile)-[:HAS_CAPABILITY_EXPOSURE]->(:CapabilityExposureState)
```

All evidence-bearing relationships must reference Assertion IDs.

# 2. Build a deterministic Capability Candidate engine

Do not ask a model:

```text
What scary things could Google do?
```

Create reviewed deterministic trigger rules.

Examples:

```text
IF a stable identifier spans multiple services
THEN candidate = CROSS_SERVICE_IDENTITY_RESOLUTION
```

```text
IF precise location + sufficient temporal density
THEN candidate = LOCATION_RECONSTRUCTION
```

```text
IF behavioural history + controller category labels co-occur
THEN candidate = INTEREST_PROFILING
```

```text
IF repeated directional interaction data exists
THEN candidate = SOCIAL_GRAPH_RECONSTRUCTION
```

```text
IF device identifier + account identifier repeatedly co-occur
THEN candidate = DEVICE_ACCOUNT_RESOLUTION
```

```text
IF declared age evidence is absent
AND controller age-like classification is present
THEN candidate = AGE_INFERENCE
```

```text
IF content-consumption history and recommendation/profile records co-occur
THEN candidate = BEHAVIOURAL_PERSONALISATION
```

Rules produce:

```text
CapabilityCandidate
```

with:

- trigger rule ID;
    
- trigger version;
    
- supporting Assertions;
    
- supporting aggregates;
    
- confidence;
    
- evidence status.
    

The semantic model may explain the evidence bundle.

It must not promote the candidate to `evidenced_from_export` unless the evidence standard for that status is satisfied.

# 3. Build the Structural Linkability engine

Do not call the output a universal privacy score.

Use the product language:

```text
STRUCTURAL LINKABILITY INDICATORS
```

Create an EdgeRisk vector containing:

- linkage type;
    
- directness;
    
- stability;
    
- cross-context reuse;
    
- uniqueness gain;
    
- legal accessibility;
    
- reversibility;
    
- confidence.
    

Keep the vector as the source of truth.

An optional configurable indicator summary may exist.

Implement deterministic identifier statistics:

- distinct controller count;
    
- distinct service count;
    
- distinct data-domain count;
    
- schema count;
    
- first seen;
    
- last seen;
    
- temporal persistence;
    
- occurrence count.
    

Calculate graph metrics over the high-value identifier topology.

At minimum:

- degree;
    
- betweenness centrality or a scalable approximation;
    
- articulation points where applicable;
    
- connected component impact.
    

Surface conclusions in evidence-based language such as:

```text
This email address is observed across 14 data domains.
```

```text
This telephone number appears across 7 controller datasets.
```

```text
This device identifier connects browsing, advertising and application activity.
```

Implement identifier-removal simulation.

Example:

```text
Removing these 3 high-centrality identifiers would disconnect 41% of currently observed cross-domain linkage paths.
```

The percentage must be calculated against a clearly defined graph snapshot.

Store:

- analysis date;
    
- graph version;
    
- selected node set;
    
- calculation method.
    

Do not imply that deleting the identifier from one platform automatically removes all linked data.

# 4. Build Purpose and Purpose Drift

Purpose is separate from LegalBasis.

Implement:

```text
Purpose {
  node_id,
  description,
  effective_from,
  effective_to
}
```

Implement relationships including:

```text
(:DataPoint)-[:COLLECTED_FOR]->(:Purpose)
(:ProcessingActivity)-[:ORIGINALLY_JUSTIFIED_BY]->(:Purpose)
(:ProcessingActivity)-[:CURRENTLY_USED_FOR]->(:Purpose)
(:Purpose)-[:EXPANDED_TO]->(:Purpose)
```

Every purpose association requires evidence.

Persist privacy policy and policy-document versions as SourceArtifacts.

The current Policy Analyzer must no longer save only a decontextualised LLM summary as authoritative evidence.

Persist the fetched policy source.

Create grounded Claims linked to source locators.

Implement:

```text
Claim {
  node_id,
  claim_type,
  text,
  valid_from,
  valid_to
}
```

Relationships:

```text
(:Capability)-[:ORIGINALLY_JUSTIFIED_BY]->(:Claim)
(:Claim)-[:SUPPORTED_BY]->(:SourceArtifact)
```

Where source text supports it:

```text
(:Capability)-[:CURRENT_SCOPE]->(:ProcessingActivity)
```

Technical reach must be separately represented:

```text
(:Capability)-[:TECHNICALLY_COULD_ENABLE]->(:ProcessingActivity)
```

That relationship must never be styled or queried as observed implementation.

## Purpose distance

Implement a configurable heuristic:

```text
same purpose                  0
closely compatible purpose    1
adjacent purpose              2
materially different purpose  3
unrelated purpose             4
```

The taxonomy/rule version must be stored.

Output:

```text
Possible purpose drift
```

Never:

```text
GDPR violation detected
```

The evidence view should show:

```text
ORIGINAL PURPOSE
Fraud prevention

        ↓

ADDITIONAL PURPOSE
Account security

        ↓

ADDITIONAL PURPOSE
Personalisation

        ↓

CURRENT ASSOCIATED PROCESSING
Advertising optimisation
```

Where dates are known, show them.

Where dates are unknown, explicitly show `UNKNOWN`.

# 5. Add original justification versus current capability

Original justification is not LegalBasis.

Model:

```text
Capability
    ↓ ORIGINALLY_JUSTIFIED_BY
Claim
    ↓ SUPPORTED_BY
SourceArtifact
```

Then separately:

```text
Capability
    ↓ CURRENT_SCOPE
ProcessingActivity
```

and:

```text
Capability
    ↓ TECHNICALLY_COULD_ENABLE
ProcessingActivity
```

The graph UI must visually distinguish:

```text
CURRENTLY OBSERVED
─────────────── solid

POTENTIALLY ENABLED
- - - - - - - dashed

ALLEGED / UNVERIFIED
·············· dotted
```

Do not reuse the same edge styling for all inferred concepts.

The current `isInferred` boolean is insufficient.

Introduce explicit epistemic and capability status metadata in the graph API.

# 6. Build the Institutional Access graph

Model data custody separately from access or linkability.

Core relationships:

```text
(:Organisation)-[:CONTROLS]->(:Dataset)
(:Organisation)-[:PROCESSES]->(:Dataset)
(:Organisation)-[:HOSTS]->(:Dataset)
(:Organisation)-[:CAN_REQUEST]->(:Dataset)
(:Authority)-[:HAS_LEGAL_GATEWAY_TO]->(:Dataset)
(:Organisation)-[:SHARES_WITH]->(:Organisation)
(:Organisation)-[:USES_SUBPROCESSOR]->(:Organisation)
```

Add `Authority` as an ontology type where required.

Access-related relationships may carry:

- access type;
    
- jurisdiction;
    
- legal instrument;
    
- requires warrant;
    
- requires notice;
    
- requires consent;
    
- reported to subject;
    
- transparency available;
    
- evidence assertion ID.
    

Distinguish:

```text
CENTRALLY STORED
```

from:

```text
FEDERATED BUT MUTUALLY ACCESSIBLE
```

from:

```text
INDEPENDENTLY STORED BUT LINKABLE VIA COMMON IDENTIFIER
```

Do not infer controller access merely because two datasets share an identifier.

Linkability and access are separate concepts.

# 7. Turn DSAR into active graph testing

The current DSAR workflow should remain.

Add a deterministic uncertainty/hypothesis layer.

Create a PrivacyHypothesis model.

Minimum fields:

- `id`
    
- `profile_id`
    
- `hypothesis_type`
    
- `subject_ref`
    
- `unknown_predicate`
    
- `object_ref`
    
- `uncertainty_reason`
    
- `detector_id`
    
- `detector_version`
    
- `supporting_assertion_ids`
    
- `status`
    
- `created_at`
    
- `resolved_at`
    

Statuses:

- `open`
    
- `request_drafted`
    
- `request_sent`
    
- `confirmed`
    
- `rejected`
    
- `unresolved`
    
- `superseded`
    

Detectors should generate hypotheses from structural uncertainty.

Examples:

### Inferred age with unclear derivation

Evidence:

```text
age range = 18–24
data class = inferred/controller assigned
source lineage unclear
```

Create hypothesis:

```text
Controller processing inferred age or age-range data with unknown derivation lineage.
```

### High-centrality telephone identifier

Evidence:

```text
telephone identifier links 6 data domains
```

Create hypothesis:

```text
Unclear whether telephone number is used as a matching or cross-product linkage key.
```

### Suspected external enrichment

Evidence:

```text
profile attribute lacks self-origin evidence
+
controller/source lineage unknown
```

Create hypothesis:

```text
Possible personal data obtained from a third-party source.
```

The uncertainty detector is deterministic.

The model may draft or improve the natural-language request.

The model does not decide that the hypothesis is true.

The loop becomes:

```text
GRAPH / ASSERTION LEDGER
 ↓
UNKNOWN EDGE OR LINEAGE
 ↓
PRIVACY HYPOTHESIS
 ↓
TARGETED DSAR QUESTION
 ↓
HUMAN REVIEW
 ↓
REQUEST
 ↓
RESPONSE / EXPORT
 ↓
INGEST
 ↓
ASSERTION DELTA
 ↓
CONFIRM / REJECT / UNRESOLVED
 ↓
UPDATED GRAPH
```

Integrate this with the existing request workflow.

Do not create a separate disconnected request system.

# 8. Build targeted DSAR templates

Create deterministic request-question templates.

Examples:

## Inferred attribute lineage

```text
Please confirm whether you process inferred age or age-range data relating to me. Please provide the source data used to make the inference, the categories of logic or methodology involved, the date of inference, recipients of the inferred attribute, and the purposes for which it is processed.
```

## Identifier linkage

```text
Please identify each processing activity in which my telephone number is used as an identifier, matching key or linkage attribute, including any use to correlate records across products, services or datasets.
```

## Third-party source

```text
Please identify personal data concerning me obtained from sources other than myself, including the source, categories of personal data obtained, date obtained and purposes of subsequent processing.
```

These are template semantics.

The drafting model may adapt wording to the controller/request context.

Preserve the generated hypothesis IDs and target unknown edges in request metadata.

When a response is ingested, automatically compare new Assertions with open hypotheses.

# 9. Treat deletion as a graph-cut and verification problem

Do not model deletion only as:

```text
DELETE ACCOUNT
```

Implement DeletionSimulation.

Inputs:

- graph snapshot/version;
    
- selected controller/account/dataset;
    
- expected deletion scope;
    
- requested date.
    

Calculate predicted topology effects.

Example:

```text
BEFORE

143 high-value nodes
279 relationships
```

```text
PREDICTED AFTER SUCCESSFUL REQUEST

112 nodes
201 relationships
```

List potentially surviving identifiers and profiles.

Do not assert that they will survive.

Label them:

```text
POTENTIALLY SURVIVING BASED ON CURRENT LINKAGE
```

Create expected-removal records.

After a post-deletion export or response is ingested compare:

- `EXPECTED_REMOVED`
    
- `CONFIRMED_REMOVED_FROM OBSERVED EXPORT`
    
- `STILL_OBSERVED`
    
- `UNVERIFIABLE`
    

Do not call an absent export item “confirmed deleted” unless there is additional evidence establishing deletion.

Use precise UI language.

Store before/after graph snapshot versions and Assertion IDs.

# 10. Redesign the graph API around temporal and epistemic queries

Extend the graph API.

Support parameters such as:

- `asOf`
    
- `compareTo`
    
- `profileLayer`
    
- `epistemicBasis`
    
- `assertionStatus`
    
- `capabilityStatus`
    
- `purpose`
    
- `sourceArtifact`
    
- `controller`
    
- `dataDomain`
    

Profile layers:

- `self_declared`
    
- `observed_behaviour`
    
- `controller_profile`
    
- `system_hypotheses`
    

Default graph view must not mix all four without explicit visual distinction.

Replace Neo4j internal ID use with stable `node_id`.

Graph responses should expose:

- assertion IDs;
    
- evidence counts;
    
- confidence;
    
- valid time;
    
- controller-observed time;
    
- system assertion time;
    
- derivation method;
    
- epistemic basis;
    
- capability status where applicable.
    

# 11. Replace keyword-based graph chat with evidence tools

The current graph chat uses keyword checks such as `email`, `company`, `phone` and manually chooses Cypher.

Replace this with a typed PrivacyQueryService.

Expose deterministic tools/functions such as:

- `get_current_profile`
    
- `get_profile_at`
    
- `compare_profile_periods`
    
- `trace_assertion`
    
- `get_assertion_evidence`
    
- `find_identifier_links`
    
- `get_identifier_centrality`
    
- `simulate_identifier_removal`
    
- `list_controller_assignments`
    
- `compare_behavioural_and_controller_profile`
    
- `list_capability_exposure`
    
- `trace_capability_evidence`
    
- `list_purpose_drift_candidates`
    
- `trace_purpose_lineage`
    
- `list_open_privacy_hypotheses`
    
- `compare_export_snapshots`
    
- `get_personal_drift`
    
- `get_controller_drift`
    
- `get_understanding_drift`
    

The model may select tools and explain returned evidence.

Do not give the model unrestricted write access.

Do not let the model invent Cypher and directly mutate the graph.

Answers must return machine-readable citations to Assertion IDs and EvidenceLocators.

The frontend should allow the user to open the cited evidence.

# 12. Redesign the Data Graph page

Retain the existing force-graph infrastructure where useful.

Do not rebuild the entire visualisation library without reason.

Add primary graph modes:

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

## Time mode

Add a time slider.

Example:

```text
2019 ─ 2020 ─ 2021 ─ 2022 ─ 2023 ─ 2024 ─ 2025 ─ NOW
```

The graph query is an `AS OF` slice through temporal states/assertions.

The current profile is a temporal projection.

## Compare mode

Allow date A and date B.

Show:

- newly visible nodes;
    
- no-longer-current nodes;
    
- changed temporal states;
    
- changed controller assignments;
    
- changed capability exposure;
    
- changed identifier linkability.
    

Do not imply old evidence was deleted merely because a state is no longer current.

## Profile-layer selector

Allow:

```text
WHO I SAY I AM
WHAT MY ACTIVITY EVIDENCES
WHAT THE CONTROLLER ASSIGNS
WHAT THE SYSTEM HYPOTHESISES
```

Support overlay mode, but every layer must remain visually distinguishable.

## Evidence inspector

When selecting a node, relationship, temporal state or capability exposure, show:

- semantic statement;
    
- epistemic basis;
    
- status;
    
- confidence;
    
- valid time;
    
- controller-observed time;
    
- system assertion time;
    
- derivation method/version;
    
- supporting Assertions;
    
- source artefacts;
    
- exact source locator;
    
- resolved excerpt/record;
    
- review history.
    

The user should be able to answer:

```text
Why is this in my graph?
```

without trusting the AI explanation.

# 13. Build the longitudinal analysis views

Create separate views.

## Personal drift

Answer:

```text
What changed in my observed activity?
```

Show:

- emerging topics;
    
- declining topics;
    
- recurrence;
    
- project episodes;
    
- routine shifts;
    
- engagement-profile changes;
    
- era candidates.
    

## Controller drift

Answer:

```text
What changed in controller-provided profile evidence?
```

Show:

- new assigned categories;
    
- removed-from-export categories;
    
- new identifiers;
    
- new cross-service linkage evidence;
    
- new inferred attributes;
    
- new capability exposure evidence.
    

## Understanding drift

Answer:

```text
What did this import newly teach the system?
```

Example:

```text
4.2 years of previously unobserved historical activity discovered.

3 previously unidentified stable identifier candidates.

2 controller-assigned categories newly evidenced.

No evidence establishes that these were newly collected in 2026.
They were newly observed by this system in the July 2026 export.
```

All figures must come from calculated data.

# 14. Build profile comparison

Create a three-layer comparison:

```text
SELF-DECLARED
```

```text
OBSERVED BEHAVIOURAL SIGNAL
```

```text
CONTROLLER-ASSIGNED
```

Example table structure:

```text
TOPIC | SELF | BEHAVIOURAL SIGNAL | CONTROLLER ASSIGNED
```

Never automatically reconcile disagreement into a single truth.

Generate evidence-based discrepancy candidates such as:

```text
Potential controller over-weighting
```

```text
Potential controller blind spot
```

```text
Ecosystem visibility gap
```

These are analytical prompts.

The model may suggest possible explanations.

Possible explanations must remain explicitly labelled as hypotheses.

# 15. UI language and legal/epistemic guardrails

Create shared wording helpers.

Prefer:

```text
The available export evidence indicates...
```

```text
This appears to have been controller-assigned...
```

```text
Observed activity shows...
```

```text
This combination of data could technically support...
```

```text
Possible purpose drift...
```

```text
No source evidence currently establishes...
```

Avoid:

```text
You are...
```

```text
Google knows for certain...
```

```text
This is illegal...
```

```text
The organisation is abusing...
```

```text
This identifier will survive deletion...
```

unless direct evidence actually establishes the proposition and the legal wording has been separately reviewed.

# 16. Acceptance tests

Create synthetic end-to-end scenarios.

Required scenarios:

1. Behaviour suggests AI interest but controller profile has no AI category.
    
2. Controller assigns `Technology` but behavioural evidence is weak.
    
3. Temporary activity burst is detected as ProjectEpisodeCandidate rather than enduring interest.
    
4. Same device ID spans multiple services and generates a cross-service capability candidate.
    
5. Capability candidate is visible as potentially enabled but not observed implementation.
    
6. Policy version A states fraud prevention; policy version B introduces personalisation; purpose-distance engine flags possible drift.
    
7. Two independent datasets share an identifier but no access relationship exists; system shows linkability without claiming mutual access.
    
8. Unknown inferred age lineage creates a PrivacyHypothesis and targeted DSAR candidate.
    
9. New DSAR response provides lineage evidence and resolves the hypothesis.
    
10. Deletion simulation predicts surviving linkages.
    
11. Post-deletion export still contains one expected identifier; state becomes STILL_OBSERVED.
    
12. Item absent from export becomes REMOVED_FROM_OBSERVED_EXPORT, not legally confirmed deleted.
    
13. Time slider shows historical state without overwriting current state.
    
14. Controller-profile and Subject graph remain separate.
    
15. System hypothesis never appears in accepted current profile by default.
    
16. Every evidence link in the UI resolves to the correct source locator.
    

# 17. Documentation

Rewrite architecture documentation around the actual product philosophy.

The product should no longer be described primarily as:

```text
an AI system automating GDPR requests
```

A more accurate architectural description is:

```text
A local-first personal-data autonomy system that uses privacy access rights to acquire evidence, reconstructs longitudinal behavioural and controller-profile histories, maps identifier linkability and institutional capability, and uses AI as an evidence-constrained interface for exploring the resulting temporal privacy graph.
```

Keep clear distinctions between:

- implemented;
    
- partial;
    
- experimental;
    
- planned.
    

At completion provide:

1. files changed;
    
2. graph ontology changes;
    
3. Capability engine rules;
    
4. Linkability calculations;
    
5. Purpose Drift rules;
    
6. institutional access model;
    
7. active DSAR hypothesis workflow;
    
8. deletion simulation/verification design;
    
9. temporal UI changes;
    
10. privacy-query tools;
    
11. exact tests and results;
    
12. remaining epistemic or legal risks.
    

Do not weaken provenance requirements to make the UI appear more complete.

Unknown must remain a valid and visible state.