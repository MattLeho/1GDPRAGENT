Continue work in the local repository:

`MattLeho/1GDPRAGENT`

This task assumes the immutable SourceArtifact / EvidenceLocator / Assertion foundation and canonical graph ontology have already been implemented.

Inspect the actual merged implementation before editing.

# Primary task

Build a local-first, deterministic personal-data ingestion engine capable of processing very large heterogeneous exports, including a Google Takeout corpus exceeding 300 GB.

The model must see the smallest possible residue that deterministic code cannot classify reliably.

Do NOT implement:

```python
for file in takeout:
    for chunk in file:
        llm.analyse(chunk)
```

The target architecture is:

```text
RAW EXPORT
    ↓
SAFE INVENTORY
    ↓
CONTENT HASHING
    ↓
FILE-TYPE VERIFICATION
    ↓
STRUCTURAL FINGERPRINTING
    ↓
KNOWN SCHEMA?
    ├── YES → DETERMINISTIC PARSER
    └── NO  → REPRESENTATIVE SAMPLE
                    ↓
             SCHEMA INTERPRETATION
                    ↓
               HUMAN REVIEW
                    ↓
          DECLARATIVE PARSER SPEC
                    ↓
             DETERMINISTIC PARSER
    ↓
NORMALISED EVENT LAKE
    ↓
DETERMINISTIC PRIVACY FEATURES
    ↓
TEMPORAL AGGREGATES
    ↓
CAPABILITY / LINKABILITY CANDIDATES
    ↓
AMBIGUOUS EVIDENCE BUNDLES ONLY
    ↓
SEMANTIC MODEL
    ↓
PROVENANCE VALIDATION
    ↓
HUMAN REVIEW WHERE REQUIRED
    ↓
ASSERTION LEDGER
    ↓
HIGH-VALUE NEO4J PROJECTION
```

# Architectural boundary

Move heavy ingestion into the Python intelligence service and Celery.

Next.js should:

- create an AnalysisRun;
    
- enqueue the ingestion job;
    
- show progress;
    
- show review items;
    
- query results.
    

Next.js must not load a 300 GB corpus through application API memory.

N8N must not run the heavy parsing pipeline.

N8N remains useful for:

- DSAR orchestration;
    
- email workflows;
    
- scheduled request monitoring;
    
- external workflow automation.
    

Python/Celery owns:

- archive traversal;
    
- inventory;
    
- hashing;
    
- structure analysis;
    
- parser dispatch;
    
- Parquet writes;
    
- deterministic feature analysis;
    
- model adjudication.
    

# 1. Add the analytical storage layer

Add explicit Python dependencies suitable for high-volume local analysis.

Use:

- Polars;
    
- PyArrow / Parquet;
    
- DuckDB;
    
- a streaming JSON parser such as `ijson`;
    
- explicit NetworkX dependency rather than relying on an indirect dependency;
    
- a safe file-signature library or equivalent verified magic-byte implementation;
    
- `ruptures` or an equivalent tested change-point implementation if appropriate.
    

Keep dependencies version constrained sensibly.

Update the Docker image for any required system library.

Do not add Spark.

The personal-scale corpus is large, but this remains a local workstation/home-lab application.

Implement an event-lake root configurable by environment variable.

Suggested default local layout:

```text
data/
  blobs/
  event_lake/
  analysis/
  cache/
```

Do not commit these directories.

# 2. Build safe archive inventory before extraction

Create a new package, preferably:

```text
intelligence/personal_data/
```

Suggested modules:

```text
personal_data/
  models.py
  inventory.py
  archive_policy.py
  hashing.py
  file_typing.py
  fingerprints.py
  schema_registry.py
  normalisation.py
  event_lake.py
  parser_runtime.py

  parsers/
    base.py
    declarative.py
    google_takeout/

  features/
    data_classes.py
    identifiers.py
    opaque_tokens.py
    urls.py
    inference_language.py
    temporal.py
    geospatial.py
    interactions.py
    density.py
    cooccurrence.py

  temporal/
    aggregates.py
    interests.py
    bursts.py
    change_points.py
    recurrence.py
    routines.py
    interactions.py
    project_episodes.py
    eras.py

  model_roles/
    router.py
    policies.py
    benchmark.py
```

Inventory archives before recursively extracting them.

For every archive/member track:

- compressed size;
    
- declared uncompressed size;
    
- expansion ratio;
    
- member count;
    
- nesting depth;
    
- relative path;
    
- duplicate member paths;
    
- symlink status;
    
- path traversal attempts.
    

Reject:

- `../` traversal;
    
- absolute archive paths;
    
- archive members escaping the configured workspace.
    

Set configurable limits for:

- archive recursion depth;
    
- expansion ratio;
    
- total expanded bytes;
    
- member count.
    

Prefer streaming member processing.

The input boundary must be safe for future third-party DSAR archives, not only trusted Google Takeout files.

# 3. Implement content and canonical deduplication

For raw bytes calculate:

```text
SHA-256
```

Store bytes once through ContentBlob.

Preserve every SourceArtifact occurrence.

Then implement format-aware canonical hashes.

JSON canonicalisation:

- parse using streaming methods where required;
    
- normalise Unicode;
    
- canonicalise timestamps only where parser semantics permit;
    
- sort object keys;
    
- ignore presentation whitespace;
    
- do not reorder arrays unless the schema explicitly defines them as unordered.
    

CSV:

- detect encoding and delimiter;
    
- normalise line endings;
    
- preserve row order by default;
    
- canonicalise header representation.
    

HTML/XML:

- preserve the raw ContentBlob;
    
- canonical hash may normalise presentation-only whitespace where safe;
    
- never destroy source provenance.
    

Store:

```text
raw_sha256
canonical_hash
```

as separate concepts.

# 4. Implement file-type truth

Do not trust file extension alone.

Collect:

- extension;
    
- declared MIME;
    
- magic-byte detection;
    
- parser probe result.
    

Produce:

```text
MATCH
MISMATCH
AMBIGUOUS
UNKNOWN
```

Store the evidence used for the classification.

Do not ask an LLM to identify malformed binary content that deterministic parser probes can reject.

# 5. Build StructureFingerprint as a first-class concept

This is a central feature.

For JSON produce a canonical structural description containing at minimum:

- top-level type;
    
- sorted key paths;
    
- nested key paths;
    
- array depth;
    
- value-type distribution;
    
- representative array/object shape;
    
- optional/variable field frequency where sampled.
    

Example:

```json
{
  "top_level_type": "array",
  "key_paths": [
    "$[].title",
    "$[].titleUrl",
    "$[].time",
    "$[].products[].name"
  ],
  "array_depth": 2,
  "value_types": {
    "string": 0.73,
    "timestamp_candidate": 0.09,
    "url": 0.09,
    "array": 0.09
  }
}
```

Hash the canonical structural representation.

Implement equivalent format-specific fingerprints for:

- CSV/tabular data;
    
- HTML;
    
- XML.
    

Do not interpret the same schema hundreds of thousands of times.

The schema registry must map:

```text
StructureFingerprint
    ↓
source service
data domain
parser ID
parser version
normalised event type
timestamp selector
subject selector
identifier selectors
object selectors
privacy feature hints
review status
```

Review statuses:

- `unknown`
    
- `proposed`
    
- `approved`
    
- `rejected`
    
- `deprecated`
    

# 6. Build a declarative parser system

For a previously unseen StructureFingerprint, produce representative samples.

Select deterministically:

- first valid record;
    
- median-sized record;
    
- record with maximum key coverage;
    
- record with maximum nested depth;
    
- a bounded number of structurally unusual records.
    

Do not send the entire file.

The schema interpretation model may propose a DeclarativeParserSpec.

The model must not generate arbitrary Python and have the application execute it.

Parser specification should be constrained and validated.

For JSON, support selectors such as:

- JSON Pointer;
    
- approved JSON-path-like selector subset.
    

Parser spec should declare:

- event type;
    
- data domain;
    
- timestamp selector;
    
- temporal precision rules;
    
- subject selector;
    
- object selectors;
    
- identifier selectors;
    
- location selectors;
    
- declared/observed/inferred hints;
    
- relationship field semantics.
    

Every extracted field must retain the exact source locator.

The flow is:

```text
unknown fingerprint
 ↓
representative sample
 ↓
model proposes parser spec
 ↓
schema validation
 ↓
human approval
 ↓
save approved parser version
 ↓
run deterministically against all matching records
```

A parser proposal is not an approved parser.

Add fixtures generated from representative synthetic examples.

# 7. Create the normalised event lake

Do not put millions of search/watch/activity events in Neo4j.

Store normalised high-volume events in partitioned Parquet.

Create a canonical ActivityEvent schema.

Minimum fields:

- `event_id`
    
- `record_signature`
    
- `subject_id`
    
- `export_snapshot_id`
    
- `artifact_id`
    
- `service`
    
- `product`
    
- `data_domain`
    
- `event_type`
    
- `action_class`
    
- `occurred_at`
    
- `temporal_precision`
    
- `timezone`
    
- `timezone_assumption`
    
- `object_type`
    
- `object_id`
    
- `object_value`
    
- `parser_id`
    
- `parser_version`
    
- `source_locator_id`
    

Action classes should include:

- `CONSUMED`
    
- `SEARCHED`
    
- `CREATED`
    
- `EDITED`
    
- `PUBLISHED`
    
- `CODED`
    
- `COMMUNICATED`
    
- `PURCHASED`
    
- `VISITED`
    
- `AUTHENTICATED`
    
- `OTHER`
    

Generate `record_signature` deterministically from schema-appropriate canonical fields.

Typical components:

```text
service
event_type
subject identifier
normalised timestamp
normalised object
```

The same logical event appearing in multiple export snapshots should normally become:

```text
ONE EVENT
+
MULTIPLE OBSERVATIONS
```

Do not destroy export-to-export provenance.

Create a PostgreSQL catalogue of Parquet partitions with:

- partition URI;
    
- export snapshot;
    
- service;
    
- event type;
    
- row count;
    
- minimum time;
    
- maximum time;
    
- schema version;
    
- file hash.
    

Partition sensibly by high-level source/service/event type/time.

Avoid millions of tiny Parquet files.

# 8. Implement deterministic semantic prefilters

Implement the following as explicit engines.

## Service/path classifier

Original path is evidence.

Extract candidate:

- organisation;
    
- product;
    
- service;
    
- probable data domain.
    

Model only receives `UNKNOWN`, `AMBIGUOUS` or `MULTI_DOMAIN` cases.

## Schema-key dictionary

Maintain versioned registries for:

- timestamp keys;
    
- identifiers;
    
- locations;
    
- relationships;
    
- inference/classification language.
    

A key match creates a candidate.

It does not establish semantic truth.

## Data-class detector

Support multiple classes:

- `DIRECT_IDENTIFIER`
    
- `QUASI_IDENTIFIER`
    
- `CONTACT`
    
- `LOCATION`
    
- `COMMUNICATION`
    
- `SOCIAL_INTERACTION`
    
- `BEHAVIOURAL_EVENT`
    
- `SEARCH_HISTORY`
    
- `CONTENT_CONSUMPTION`
    
- `PURCHASE`
    
- `PAYMENT`
    
- `DEVICE`
    
- `AUTHENTICATION`
    
- `SECURITY_EVENT`
    
- `ADVERTISEMENT`
    
- `INFERRED_ATTRIBUTE`
    
- `DECLARED_ATTRIBUTE`
    
- `BIOMETRIC_CANDIDATE`
    
- `MEDIA`
    
- `DOCUMENT`
    
- `UNKNOWN`
    

## Stable identifier detector

Detect candidates including:

- email;
    
- telephone number;
    
- username;
    
- account ID;
    
- device ID;
    
- advertising ID;
    
- cookie ID;
    
- profile ID;
    
- payment/customer ID;
    
- IP address;
    
- MAC address;
    
- URL-carried identifier;
    
- opaque recurring token.
    

For every identifier candidate calculate:

- occurrence count;
    
- source count;
    
- service count;
    
- data-domain count;
    
- first seen;
    
- last seen;
    
- value stability.
    

Do not discard an opaque token because its human-readable meaning is unknown.

## High-entropy opaque value detector

Calculate bounded candidate features including:

- length;
    
- character distribution;
    
- entropy;
    
- recurrence;
    
- cross-schema occurrence;
    
- cross-domain occurrence.
    

Suppress obvious known hashes, UUIDs and cryptographic material where safely identifiable.

Create:

```text
OpaqueIdentifierCandidate
```

not an asserted identifier meaning.

## URL decomposition

Parse locally:

- scheme;
    
- domain;
    
- subdomain;
    
- path;
    
- query keys;
    
- fragment.
    

Inspect query values for identifier candidates.

Never automatically fetch URLs found in personal-data exports.

## Inference-language detector

Detect terms including:

- predicted;
    
- inferred;
    
- estimated;
    
- likely;
    
- probability;
    
- confidence;
    
- segment;
    
- audience;
    
- interest;
    
- affinity;
    
- classification;
    
- propensity;
    
- score;
    
- risk;
    
- profile;
    
- recommendation;
    
- personalisation;
    
- lookalike.
    

Create:

```text
InferenceCandidate
```

The local context may later be sent to semantic adjudication.

Do not immediately assert that the controller inferred the value.

## Temporal normalisation

Store:

- original value;
    
- parsed value;
    
- timezone if known;
    
- timezone assumption;
    
- temporal precision;
    
- parser version.
    

Precision:

- `SECOND`
    
- `MINUTE`
    
- `HOUR`
    
- `DAY`
    
- `MONTH`
    
- `YEAR`
    
- `RANGE`
    
- `UNKNOWN`
    

Do not silently convert a date-only value into precise midnight UTC.

## Geospatial precision

Distinguish:

- `EXACT_COORDINATE`
    
- `COARSE_COORDINATE`
    
- `ADDRESS`
    
- `POSTCODE`
    
- `PLACE`
    
- `CITY`
    
- `REGION`
    
- `COUNTRY`
    

Store reported accuracy where present.

A dominant overnight geographical cluster may be detected deterministically.

It must not automatically be labelled `HOME`.

## Interaction edges

Extract source-explicit directional actions:

- `SENT_TO`
    
- `RECEIVED_FROM`
    
- `FOLLOWED`
    
- `SUBSCRIBED_TO`
    
- `MEMBER_OF`
    
- `APPEARS_IN_CONTACTS`
    

Do not replace them with:

- `FRIEND`
    
- `PARTNER`
    
- `COLLEAGUE`
    

unless the source explicitly states the relationship or the human confirms it.

## Behavioural density

Aggregate:

- event type;
    
- events per day;
    
- events per hour;
    
- unique objects;
    
- burstiness;
    
- periodicity;
    
- first seen;
    
- last seen.
    

The semantic model should receive change points and unusual transitions rather than millions of ordinary events.

## Cross-domain co-occurrence

Aggregate identifier/data-class co-occurrence before graph projection.

Do not create a Neo4j relationship for every raw record.

# 9. Create a model-role and privacy-execution policy

The current model-purpose system is too generic.

Extend model roles to support at minimum:

- `schema_interpretation`
    
- `semantic_adjudication`
    
- `multimodal_extraction`
    
- `topic_labelling`
    
- `narrative_explanation`
    
- `request_drafting`
    

Preserve existing model-purpose aliases where required for backwards compatibility.

Implement real runtime provider adapters in the Python intelligence service.

Do not let a selected non-Google provider silently fall back to Google for raw personal-data processing.

Implement execution policies:

## `strict_local`

- external model providers blocked for personal-data content;
    
- local models only.
    

## `local_first`

- local deterministic and model processing first;
    
- external model invocation only for explicitly permitted task roles;
    
- only the minimal evidence bundle required for the task;
    
- record that external processing occurred;
    
- never upload the full archive as a convenience fallback.
    

## `controlled_cloud`

- configured external providers allowed for approved roles;
    
- external transfer is explicit in the analysis audit;
    
- provider/model/task recorded.
    

Do not generically promise “zero data retention”.

Provider policy or contractual claims should be recorded as configurable/documented metadata with a verification date.

The application must distinguish:

```text
configured provider policy claim
```

from:

```text
technical guarantee made by this application
```

Gemma-family models may be benchmarked as local semantic workers.

They must remain implementations of model roles rather than architectural dependencies.

# 10. Add a private benchmark harness

Build a benchmark harness using labelled synthetic or user-approved samples.

The architecture must permit comparing models for each role.

Measure:

- classification accuracy;
    
- schema interpretation accuracy;
    
- locator validity;
    
- abstention quality;
    
- structured-output validity;
    
- latency;
    
- peak memory where measurable;
    
- external/local execution;
    
- cost metadata where configured.
    

Use the application's own ontology and Takeout schema samples.

Do not choose the largest model merely because generic benchmarks rank it higher.

Model routing should be evidence-based against this application's tasks.

# 11. Build the temporal personal-analysis layer

The application must model three histories:

1. how the person actually behaved;
    
2. what a controller appeared to know or infer;
    
3. how this system's understanding changed as new evidence was imported.
    

These timelines must remain separate.

Support:

```text
occurred_at

valid_from
valid_to

controller_observed_from
controller_observed_to

exported_at
ingested_at

system_asserted_at
superseded_at
```

Unknown is a valid temporal state.

Do not invent precision.

## Personal behavioural states

Implement temporal states for:

- observed interest signal;
    
- activity pattern;
    
- location pattern;
    
- interaction state;
    
- device state;
    
- routine state;
    
- project episode;
    
- personal era candidate.
    

## Controller profile states

Represent controller-assigned or explicitly controller-recorded profile attributes separately.

Examples:

```text
ControllerProfile:Google:Matt
    ASSIGNED_INTEREST → Technology
```

This must not produce:

```text
Subject:Matt
    INTERESTED_IN → Technology
```

## System-understanding history

Track when the GDPR system first discovered evidence.

Example:

An export imported in July 2026 may reveal retained activity from 2019.

The UI and API must be capable of saying:

```text
The activity is historical.

The system's discovery of that retained activity is new.
```

# 12. Implement longitudinal deterministic detectors

## Interest dimensions

Do not use one interest score as the source of truth.

For every topic/time window maintain:

- intensity;
    
- persistence;
    
- recurrence;
    
- breadth;
    
- novelty;
    
- context dispersion.
    

A weighted “Observed interest signal” may exist as an optional configurable view.

The six-dimensional state is authoritative.

## Topic ontology

Support hierarchical topics.

Example:

```text
Technology
 └── Artificial Intelligence
      ├── LLMs
      │    ├── Agents
      │    ├── RAG
      │    └── Local inference
      ├── Computer Vision
      └── AI Governance
```

Topic assignment must preserve evidence and derivation.

The model may propose human-readable cluster labels.

It must not rewrite underlying event classifications.

## Temporal burst detector

Use a robust rolling baseline.

Prefer median and median absolute deviation for bursty behavioural data.

Create:

```text
ProjectEpisodeCandidate
```

when threshold and minimum evidence conditions are met.

## Change-point detection

Detect behavioural regime shifts using a tested deterministic algorithm such as PELT where appropriate.

The model interprets the already-detected change.

The model does not perform the statistical detection.

## Recurrence

Calculate:

- active period count;
    
- dormant period count;
    
- mean dormancy;
    
- return count;
    
- return intensity.
    

Distinguish:

- continuous;
    
- recurrent;
    
- one-off episode.
    

## Decay

A decayed current signal may be calculated for display.

Never delete historical evidence.

Maintain:

- historical peak;
    
- current signal;
    
- decay rate.
    

## Topic co-emergence

Detect topics whose temporal signals rise together.

Create:

```text
TopicClusterEpisodeCandidate
```

The model may propose a descriptive cluster label.

Human labels must be stored separately from machine labels.

## Service divergence

Calculate topic distribution by service.

This can help distinguish structurally different modes of engagement.

Do not let the model infer engagement mode from raw activity without the calculated distribution.

## Consumption versus production

Build an EngagementProfile with dimensions such as:

- consumption;
    
- investigation;
    
- creation;
    
- implementation;
    
- communication.
    

Use deterministic action-class distributions.

## Routine detection

Aggregate by:

- hour;
    
- day of week;
    
- service;
    
- event type;
    
- topic.
    

Describe observed distributions.

Do not assign personality labels such as `nocturnal`.

## Routine drift

Compare period-by-time matrices and identify changes.

## InteractionState

Per observed person/account/time window calculate where data permits:

- inbound count;
    
- outbound count;
    
- reciprocity ratio;
    
- response interval;
    
- active days;
    
- service count;
    
- burstiness.
    

Call the output `InteractionState`.

Do not automatically call it a friendship or personal relationship.

## Personal eras

Pipeline:

```text
monthly feature vectors
 ↓
change-point detection
 ↓
cluster contiguous periods
 ↓
PersonalEraCandidate
 ↓
model summarises evidence-based differences
 ↓
human names or confirms era
```

The human label must remain separate from the machine candidate.

# 13. Materialise the current profile from history

The current profile is a view.

It is not the source of truth.

Calculate current states from temporal Assertions and TemporalStates where the validity window contains the selected date.

Support:

```text
NOW
```

and:

```text
AS OF <date>
```

Do not overwrite historical InterestState, RoutineState, InteractionState or controller-profile states.

# 14. Export-to-export delta engine

Compare ExportSnapshots.

At assertion, schema and event-observation level classify:

- `NEW`
    
- `REMOVED_FROM_EXPORT`
    
- `UNCHANGED`
    
- `MODIFIED`
    

The UI language must distinguish:

```text
newly observed by this system
```

from:

```text
newly collected by the controller
```

unless evidence establishes collection time.

Produce three separate delta summaries:

```text
PERSONAL DRIFT
What changed in observed activity?

CONTROLLER DRIFT
What changed in controller-provided profile evidence?

UNDERSTANDING DRIFT
What did this import newly teach the system?
```

# 15. Neo4j projection rules

Neo4j contains high-value privacy topology.

Neo4j does NOT contain every raw ActivityEvent.

Project:

- Subject;
    
- ControllerProfile;
    
- Organisation;
    
- Account;
    
- Identifier;
    
- DataDomain;
    
- Topic;
    
- high-value DataPoint;
    
- TemporalState;
    
- ProjectEpisode;
    
- ProcessingActivity;
    
- Purpose;
    
- Capability;
    
- CapabilityExposureState;
    
- PolicyInstrument;
    
- Claim;
    
- high-value source provenance references.
    

Parquet contains mass behavioural events.

PostgreSQL contains:

- artefact catalogue;
    
- export snapshots;
    
- schema registry;
    
- analysis runs;
    
- parser versions;
    
- assertion ledger;
    
- evidence locators;
    
- review state;
    
- event partition catalogue.
    

DuckDB/Polars perform bulk analysis.

# 16. Progress and resumability

A 300 GB import must be resumable.

Implement explicit pipeline stages and checkpoints.

Examples:

- inventory;
    
- hashing;
    
- fingerprinting;
    
- parsing;
    
- normalisation;
    
- feature extraction;
    
- temporal aggregation;
    
- assertion generation;
    
- graph projection.
    

A crash must not require restarting the full import.

Use deterministic run IDs, parser versions and content hashes for idempotency.

Expose progress through AnalysisRun APIs.

# 17. Tests and benchmark fixtures

Create synthetic fixtures representing:

- repeated Takeout snapshots;
    
- duplicate raw files at different paths;
    
- reordered JSON keys;
    
- similar logical events in two exports;
    
- malformed JSON;
    
- MIME/extension mismatch;
    
- archive traversal attack;
    
- archive expansion-limit breach;
    
- unknown schema;
    
- approved declarative parser;
    
- opaque recurring token across services;
    
- date-only value;
    
- exact coordinate versus city label;
    
- interaction events;
    
- controller-assigned interest;
    
- project burst;
    
- recurrent topic;
    
- behavioural regime shift.
    

Required assertions:

- unknown schema is sampled once per fingerprint/version;
    
- approved schema bypasses model interpretation;
    
- duplicate content retains multiple provenance occurrences;
    
- event signatures deduplicate logical events while preserving observations;
    
- raw events are written to Parquet, not Neo4j;
    
- model invocation count is dramatically lower than record count;
    
- strict-local mode never invokes an external provider;
    
- selected non-Google/local provider does not silently route raw content to Google;
    
- controller-assigned profile does not alter the Subject behavioural profile;
    
- bitemporal queries distinguish event occurrence from system discovery.
    

At completion report:

1. final pipeline;
    
2. new dependencies;
    
3. storage layout;
    
4. schemas and parser registry;
    
5. model execution policy;
    
6. temporal-state architecture;
    
7. exact tests and benchmark results;
    
8. known unsupported Takeout schemas;
    
9. measured model-call reduction on fixtures;
    
10. any data-loss or migration risks.
    

Do not implement capability/purpose-drift UI or DSAR hypothesis generation in this task.

This task creates the evidence reduction and longitudinal analysis engine those features require.