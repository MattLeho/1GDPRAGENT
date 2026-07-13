# Task 3 — Build the local-first ingestion and temporal analysis engine for very large personal-data corpora

Continue work in the local repository:

`MattLeho/1GDPRAGENT`

This task assumes Task 1 and Task 2 are implemented. Inspect the actual merged implementation before editing. The current repository is stronger evidence of implementation state than old documentation.

This task has one required companion specification:

`Task 3A- file type support and extraction workflows.md`

Read Task 3A before implementation. [[Task 3A file type support and extraction workflows]] Task 3A is part of Task 3 acceptance, not a later optional enhancement.

# Primary objective

Build a local-first, deterministic personal-data ingestion engine capable of processing very large heterogeneous exports, including a Google Takeout corpus exceeding 300 GB.

The model must see the smallest possible residue that deterministic code cannot classify reliably.

Do not implement:

```python
for file in export:
    for chunk in file:
        llm.analyse(chunk)
```

Target architecture:

```text
RAW EXPORT / CONNECTED SNAPSHOT
        ↓
SAFE INVENTORY
        ↓
CONTENT HASHING + SOURCE OCCURRENCE
        ↓
FILE-TYPE TRUTH
        ↓
FILE-FAMILY EXTRACTION ADAPTER
        ↓
STRUCTURE FINGERPRINT
        ↓
KNOWN SOURCE/SCHEMA?
   ├── YES → APPROVED DETERMINISTIC PARSER
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
NORMALISED ACTIVITY EVENT LAKE
        ↓
DETERMINISTIC PRIVACY FEATURES
        ↓
TEMPORAL AGGREGATES AND STATES
        ↓
AMBIGUOUS EVIDENCE BUNDLES ONLY
        ↓
SEMANTIC TASK ROUTER
        ↓
PROVENANCE VALIDATION
        ↓
ASSERTION LEDGER
        ↓
HIGH-VALUE NEO4J PROJECTION
```

Next.js owns run creation, enqueueing, progress/review UI, and result queries. Heavy ingestion belongs in the Python intelligence service and Celery. N8N must not run the bulk parsing pipeline.

## Delegation protocol for this task

The primary agent is the you, the **orchestrator and integrator**. Keep GPT-5.6 Sol on work that requires cross-cutting architectural judgement, security/privacy decisions, migration ownership, shared contracts, integration, or final acceptance.

Use **Terra-Medium** for bounded delegated subtasks where the input, output contract, file ownership, and tests can be stated precisely. If Terra-Medium is unavailable in the current environment, use the cheapest competent sub-agent available for the same bounded work. Do not silently push every leaf task back to the orchestrator unless delegation has failed.

### Work that stays with the orchestrator (you)

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

# Phase boundary

Do not implement Task 4 Personal Insights UI, Task 5 live connectors/retention, or Task 6 capability/purpose-drift product features.

Task 3 may create the deterministic event, state, aggregate and candidate foundations those later tasks consume.

# Wave 0 — Orchestrator audit, baseline and contract freeze

**Owner: orchestrator only. Do not delegate architecture yet.**

## 0.1 Audit Task 1 and Task 2 outputs

Verify in code:

- AnalysisRun, ExportSnapshot, ContentBlob, SourceArtifact, EvidenceLocator and Assertion contracts;
- assertion provenance enforcement;
- GraphProjectionService or equivalent canonical graph-write path;
- stable graph node identity;
- TaskDefinition, TaskRoute, engine registry and execution privacy mode;
- per-workflow execution registry;
- credential storage boundaries;
- built-in workflow/task adapters that Task 3 should reuse.

Record any missing predecessor assumption. Fix only blockers that are genuinely predecessor defects.

## 0.2 Establish baseline

Run and record:

- Docker/service bootstrap;
- database migrations;
- frontend build;
- frontend type check;
- lint;
- Python compile/type checks already used by the repository;
- current test suites;
- a minimal Celery task execution.

Do not begin feature work until the baseline is known.

## 0.3 Freeze canonical Task 3 contracts

The orchestrator defines and commits the initial shared contracts before parallel implementation.

At minimum freeze:

```text
InventoryEntry
ArchiveMemberObservation
FileTypeEvidence
FileTypeTruth
StructureFingerprint
SchemaRegistryEntry
DeclarativeParserSpec
ParserExecutionResult
ActivityEvent
ActivityEventObservation
EventPartitionRecord
PipelineCheckpoint
TemporalState
TemporalAggregate
ModelAdjudicationBundle
```

Also freeze:

- content-addressed storage interface;
- event-lake writer interface;
- parser adapter interface;
- file-family extraction adapter interface from Task 3A;
- task-router invocation boundary;
- analysis-run/checkpoint identifiers;
- error and quarantine states.

The contracts must preserve unknown/ambiguous states.

## 0.4 Migration ownership

The orchestrator alone prepares or integrates PostgreSQL migrations for:

- structure fingerprints;
- schema registry and parser versions;
- event-partition catalogue;
- pipeline stages/checkpoints;
- event observation catalogue if required;
- temporal state/aggregate catalogue;
- review records required for parser approval.

Sub-agents may propose migration snippets in notes. They do not independently land competing migrations.

**Wave 0 gate:** contracts compile, migrations run idempotently, and Task 3A can be delegated against a stable adapter interface.

# Wave 1 — Bulk-ingestion foundation

Run bounded subtasks in parallel after Wave 0.

## Sub-agent 3.1A — Analytical storage and event-lake primitives

**Recommended: Terra-Medium**

**Owned area:** new event-lake/storage modules only.

Implement:

- constrained Python dependencies: Polars, PyArrow/Parquet, DuckDB, streaming JSON parser such as ijson, explicit NetworkX, safe file-signature dependency/equivalent, tested change-point dependency where selected;
- configurable roots for `data/blobs`, `data/event_lake`, `data/analysis`, `data/cache`;
- `.gitignore` and runtime directory creation;
- atomic Parquet partition writes;
- partition metadata calculation;
- DuckDB/Polars read helpers;
- no Spark.

Requirements:

- avoid millions of tiny Parquet files;
- expose row count, min/max time, schema version and file hash;
- do not create PostgreSQL or Neo4j truth from this module;
- unit tests for atomic write, read, partition metadata and interrupted temp-file cleanup.

## Sub-agent 3.1B — Safe inventory and archive policy

**Recommended: Terra-Medium**

**Owned area:** inventory/archive modules.

Implement streaming inventory and archive safety.

Track:

- compressed size;
- declared uncompressed size;
- expansion ratio;
- member count;
- nesting depth;
- relative path;
- duplicate member paths;
- symlink status;
- traversal attempts.

Reject or quarantine:

- `../` traversal;
- absolute archive paths;
- escape from configured workspace;
- excessive nesting;
- expansion-limit breaches;
- member-count breaches;
- total-expanded-byte breaches.

The inventory stage does not recursively extract everything to disk.

Provide synthetic malicious fixtures and tests.

Coordinate with Task 3A archive-family agent. Task 3.1B owns security policy; Task 3A owns format adapters.

## Sub-agent 3.1C — Hashing, canonicalisation and deduplication

**Recommended: Terra-Medium**

Implement:

- raw SHA-256;
- ContentBlob reuse without SourceArtifact provenance loss;
- canonical hash framework;
- JSON canonicalisation;
- CSV/TSV canonicalisation;
- HTML/XML safe canonical hash;
- explicit format-specific canonicaliser registration.

Rules:

- do not reorder arrays unless schema semantics say unordered;
- preserve raw bytes;
- raw hash and canonical hash remain separate;
- duplicate bytes at different paths create one blob and multiple source occurrences.

Tests:

- reordered JSON object keys;
- array-order preservation;
- line-ending changes;
- duplicate content at multiple paths;
- same bytes in separate export snapshots.

## Sub-agent 3.1D — File-type truth and structure fingerprints

**Recommended: Terra-Medium**

Implement file-type evidence collection:

```text
extension
declared MIME
magic/signature
parser probe
```

Produce:

```text
MATCH
MISMATCH
AMBIGUOUS
UNKNOWN
```

Implement structure fingerprint providers for the core structured families defined in Task 3A.

JSON fingerprint minimum:

- top-level type;
- sorted key paths;
- nested key paths;
- array depth;
- value-type distribution;
- representative object/array shape;
- sampled optional-field frequencies.

Equivalent family-specific structural signatures are required for tabular, HTML/XML and other structurally inspectable formats.

Do not infer semantic meaning.

## Sub-agent 3.1E — Task 3A file-family adapters, wave one

**Recommended: multiple Terra-Medium sub-agents**

Execute Task 3A only after the orchestrator freezes `FileFamilyAdapter`.

Parallelise by file family, not random extensions.

Initial agent grouping:

```text
F1 structured + text
F2 PDF + Office + OpenDocument
F3 email + calendar + contacts
F4 image + audio + video + subtitles
F5 geospatial + databases + browser/storage artefacts
F6 archive/container adapters
```

Each agent must remain inside Task 3A's contract and fixtures.

**Wave 1 gate:** the system can safely inventory a heterogeneous directory/archive, identify content, deduplicate bytes, select a file-family adapter, emit extraction units/metadata with locators, fingerprint supported structured content, and write no semantic graph truth.

# Wave 2 — Schema registry, declarative parsers and normalised events

## 2.1 Schema-registry architecture

**Owner: orchestrator**

Freeze the registry mapping:

```text
StructureFingerprint
    ↓
source service
data domain
file-family adapter
parser ID
parser version
normalised event type
timestamp selector
subject selector
identifier selectors
object selectors
location selectors
privacy feature hints
review status
```

Review status:

```text
unknown
proposed
approved
rejected
deprecated
```

An approved parser is versioned and immutable.

## Sub-agent 3.2A — Declarative parser runtime

**Recommended: Terra-Medium**

Implement a constrained parser-spec runtime.

Support safe selector subsets appropriate to each family. For JSON this may include JSON Pointer and an approved restricted JSON-path-like selector set.

A parser spec declares:

- event type;
- data domain;
- timestamp selector;
- temporal precision rules;
- subject selector;
- object selectors;
- identifier selectors;
- location selectors;
- declared/observed/inferred hints;
- relationship-field semantics.

Every extracted field must retain an exact source locator.

Never execute model-generated Python.

Tests must show malformed or over-broad specs are rejected.

## Sub-agent 3.2B — Representative sampling and schema proposal preparation

**Recommended: Terra-Medium**

Implement deterministic representative sampling:

- first valid record;
- median-sized record;
- maximum key coverage;
- maximum nested depth;
- bounded structurally unusual records.

The output is a minimal `SchemaInterpretationBundle`.

Do not send the whole file.

The sub-agent implements sampling and bundle creation, not model prompting policy.

## 2.2 Schema interpretation task route

**Owner: orchestrator**

Wire `schema.interpretation` through Task 2's Task Execution Router.

The semantic engine may propose a constrained DeclarativeParserSpec.

Flow:

```text
unknown fingerprint
 ↓
representative sample
 ↓
schema.interpretation TaskRoute
 ↓
proposed parser spec
 ↓
schema validation
 ↓
human review
 ↓
approved parser version
 ↓
deterministic execution for all matching records
```

The orchestrator enforces:

- privacy execution mode;
- minimal evidence bundle;
- ExecutionRecord audit;
- no silent Google fallback;
- proposal != approval.

## Sub-agent 3.2C — ActivityEvent writer and logical deduplication

**Recommended: Terra-Medium**

Implement canonical ActivityEvent persistence to Parquet.

Minimum fields:

```text
event_id
record_signature
subject_id
export_snapshot_id
artifact_id
service
product
data_domain
event_type
action_class
occurred_at
temporal_precision
timezone
timezone_assumption
object_type
object_id
object_value
parser_id
parser_version
source_locator_id
```

Action classes include:

```text
CONSUMED
SEARCHED
CREATED
EDITED
PUBLISHED
CODED
COMMUNICATED
PURCHASED
VISITED
AUTHENTICATED
OTHER
```

Generate `record_signature` deterministically from schema-appropriate canonical fields.

The same logical event in two exports becomes one logical event with multiple observations/provenance occurrences.

Add PostgreSQL partition-catalogue integration through the orchestrator-owned contract.

## Sub-agent 3.2D — Progress and resumability primitives

**Recommended: Terra-Medium**

Implement stage checkpoints for:

```text
inventory
hashing
file_typing
family_extraction
fingerprinting
parsing
normalisation
feature_extraction
temporal_aggregation
assertion_generation
graph_projection
```

Requirements:

- crash does not restart full corpus;
- deterministic run/stage keys;
- parser version and content hash participate in idempotency;
- failed/quarantined items remain visible;
- progress can be queried by AnalysisRun.

**Wave 2 gate:** known schemas bypass semantic interpretation, unknown fingerprints create one bounded proposal workflow, approved specs parse deterministically, logical events deduplicate while preserving export observations, and a killed/restarted run resumes from checkpoints.

# Wave 3 — Deterministic privacy features

Freeze a common `FeatureCandidate` contract before parallel work.

Feature output must contain:

- feature type;
- detector ID/version;
- source event/artefact references;
- calculated values;
- confidence or rule result where appropriate;
- candidate status;
- no unsupported semantic promotion.

## Sub-agent 3.3A — Service/path, schema-key and data-class detectors

**Recommended: Terra-Medium**

Implement:

- service/path classifier;
- versioned timestamp/identifier/location/relationship/inference-language key dictionaries;
- multi-label data-class candidates.

Data classes at minimum:

```text
DIRECT_IDENTIFIER
QUASI_IDENTIFIER
CONTACT
LOCATION
COMMUNICATION
SOCIAL_INTERACTION
BEHAVIOURAL_EVENT
SEARCH_HISTORY
CONTENT_CONSUMPTION
PURCHASE
PAYMENT
DEVICE
AUTHENTICATION
SECURITY_EVENT
ADVERTISEMENT
INFERRED_ATTRIBUTE
DECLARED_ATTRIBUTE
BIOMETRIC_CANDIDATE
MEDIA
DOCUMENT
UNKNOWN
```

Unknown/ambiguous cases only may be routed to semantic adjudication.

## Sub-agent 3.3B — Identifier and opaque-token analysis

**Recommended: Terra-Medium**

Detect candidate:

- email;
- phone;
- username;
- account ID;
- device ID;
- advertising ID;
- cookie ID;
- profile ID;
- payment/customer ID;
- IP;
- MAC;
- URL-carried identifier;
- opaque recurring token.

For every candidate calculate occurrence, source/service/domain counts, first/last seen and stability.

Implement entropy/recurrence/cross-schema/cross-domain features for `OpaqueIdentifierCandidate`.

Do not assign meaning to unknown tokens.

## Sub-agent 3.3C — URL, inference-language and temporal normalisation

**Recommended: Terra-Medium**

Implement:

- local URL decomposition without fetching URLs;
- inference-language candidate detector;
- temporal normalisation preserving original value, timezone evidence/assumption, precision and parser version.

Precision:

```text
SECOND
MINUTE
HOUR
DAY
MONTH
YEAR
RANGE
UNKNOWN
```

A date-only value must not silently become precise midnight UTC.

## Sub-agent 3.3D — Geospatial and interaction features

**Recommended: Terra-Medium**

Geospatial precision:

```text
EXACT_COORDINATE
COARSE_COORDINATE
ADDRESS
POSTCODE
PLACE
CITY
REGION
COUNTRY
```

Preserve reported accuracy.

A dominant overnight cluster must not be automatically called HOME.

Extract source-explicit interaction actions:

```text
SENT_TO
RECEIVED_FROM
FOLLOWED
SUBSCRIBED_TO
MEMBER_OF
APPEARS_IN_CONTACTS
```

Do not replace these with FRIEND/PARTNER/COLLEAGUE without explicit evidence or human confirmation.

## Sub-agent 3.3E — Density and co-occurrence aggregates

**Recommended: Terra-Medium**

Aggregate:

- event type;
- events/day and events/hour;
- unique objects;
- burstiness;
- periodicity;
- first/last seen;
- identifier/data-class cross-domain co-occurrence.

No raw-record Neo4j edges.

**Wave 3 gate:** deterministic feature extraction can run over fixture partitions with model invocation count far below event count.

# Wave 4 — Model-role runtime and private benchmark

## 4.1 Integrate Task 2's router

**Owner: orchestrator**

Map Task 3 semantic residue to Task 2 task keys. Do not create a second model-selection system.

Required roles/tasks include:

```text
schema.interpretation
semantic.adjudication
semantic.topic_labelling
media multimodal tasks from Task 3A/Task 4 boundary
narrative explanation where later consumed
```

Preserve existing aliases only for backwards compatibility.

Enforce:

```text
strict_local
local_first
controlled_cloud
```

No selected non-Google/local route may silently send personal content to Google.

## Sub-agent 3.4A — Python provider/runtime adapters not completed in Task 2

**Recommended: one Terra-Medium agent per adapter**

Only delegate adapters after the orchestrator defines a common invocation contract.

Possible adapter subtasks:

- Ollama;
- Google;
- OpenAI;
- OpenRouter;
- Hugging Face;
- NVIDIA.

Each adapter implements health, capability declaration, structured invocation and structured error handling.

Do not add cloud fallbacks that are absent from the TaskRoute.

## Sub-agent 3.4B — Benchmark harness and labelled fixtures

**Recommended: Terra-Medium**

Build a private benchmark harness using synthetic or user-approved samples.

Measure:

- classification accuracy;
- schema interpretation accuracy;
- locator validity;
- abstention quality;
- structured-output validity;
- latency;
- peak memory where measurable;
- local/external execution;
- configured cost metadata.

Do not select a model because generic public benchmarks rank it highest.

Produce per-task benchmark reports.

**Wave 4 gate:** semantic routes are auditable and benchmarkable, strict-local is mechanically enforced, and the model sees bounded bundles rather than corpus-sized content.

# Wave 5 — Temporal personal-analysis engine

The orchestrator first freezes the three-history model:

```text
PERSONAL BEHAVIOURAL HISTORY
CONTROLLER PROFILE HISTORY
SYSTEM UNDERSTANDING HISTORY
```

Time axes must remain distinct:

```text
occurred_at
valid_from / valid_to
controller_observed_from / controller_observed_to
exported_at / ingested_at
system_asserted_at / superseded_at
```

Unknown is valid.

## Sub-agent 3.5A — Temporal aggregates and six-dimensional interest state

**Recommended: Terra-Medium**

For every topic/window calculate:

- intensity;
- persistence;
- recurrence;
- breadth;
- novelty;
- context dispersion.

The six-dimensional state is authoritative.

An optional weighted view may exist but must be clearly derived/configurable.

Support hierarchical topics and evidence-linked topic assignment.

## Sub-agent 3.5B — Burst, recurrence and change-point detectors

**Recommended: Terra-Medium**

Implement:

- robust rolling baseline;
- median/MAD burst detection;
- recurrence metrics;
- continuous/recurrent/one-off classification;
- change-point detection using the selected tested deterministic algorithm, such as PELT where appropriate;
- signal decay without deleting historical evidence.

Create candidates:

```text
ProjectEpisodeCandidate
TopicClusterEpisodeCandidate
```

A model may label an already-detected cluster; it may not perform the statistical detection.

## Sub-agent 3.5C — Engagement, routines and interactions

**Recommended: Terra-Medium**

Implement deterministic `EngagementProfile` dimensions:

```text
consumption
investigation
creation
implementation
communication
```

Implement routine distributions by hour/day/service/event/topic and routine drift.

Implement InteractionState metrics where evidence permits:

- inbound;
- outbound;
- reciprocity ratio;
- response interval;
- active days;
- service count;
- burstiness.

Do not automatically label relationships or personality.

## Sub-agent 3.5D — Personal era candidates

**Recommended: Terra-Medium**

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
optional evidence-constrained machine label
 ↓
separate human label
```

Machine and human labels remain separate.

## Sub-agent 3.5E — Current/as-of views and export delta

**Recommended: Terra-Medium**

Implement materialised/query views for:

```text
NOW
AS OF <date>
```

Current profile is a temporal view, not source truth.

Compare ExportSnapshots at assertion/schema/event-observation level:

```text
NEW
REMOVED_FROM_EXPORT
UNCHANGED
MODIFIED
```

Produce separate:

```text
PERSONAL DRIFT
CONTROLLER DRIFT
UNDERSTANDING DRIFT
```

Do not say “newly collected by controller” when the evidence only means “newly observed by this system”.

**Wave 5 gate:** synthetic historical imports demonstrate the three histories and bitemporal distinction correctly.

# Wave 6 — High-value projection, scale tests and acceptance

## 6.1 Neo4j projection rules

**Owner: orchestrator**

Neo4j contains high-value privacy topology only.

Project suitable:

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
- Capability concepts where already defined by Task 1 ontology;
- policy/claim/source provenance references.

Do not project every ActivityEvent.

All graph writes use the canonical GraphProjectionService.

## Sub-agent 3.6A — Synthetic corpus and restart tests

**Recommended: Terra-Medium**

Build fixtures for:

- repeated Takeout snapshots;
- duplicate raw files at different paths;
- reordered JSON keys;
- logical events across two exports;
- malformed JSON;
- MIME/extension mismatch;
- traversal archive;
- expansion breach;
- unknown schema;
- approved parser;
- opaque token across services;
- date-only timestamps;
- exact coordinate versus city label;
- interactions;
- controller-assigned interest;
- project burst;
- recurrent topic;
- regime shift.

Add restart checkpoints and forced-interruption tests.

## Sub-agent 3.6B — Model-call reduction and performance benchmark

**Recommended: Terra-Medium**

Measure on synthetic/approved fixtures:

- records/files processed;
- bytes inventoried;
- semantic calls;
- model-call-to-record ratio;
- throughput by stage;
- peak memory where measurable;
- Parquet partition counts/sizes;
- restart recovery time.

The benchmark should prove the architecture materially reduces model calls.

## 6.2 End-to-end acceptance audit

**Owner: orchestrator only**

Required assertions:

- unknown schema sampled once per fingerprint/version;
- approved schema bypasses model interpretation;
- duplicate content preserves multiple provenance occurrences;
- event signatures deduplicate logical events while preserving observations;
- raw events go to Parquet, not Neo4j;
- model invocation count is dramatically lower than record count;
- strict-local never invokes external provider;
- non-Google/local selection never silently routes personal data to Google;
- controller-assigned profile does not alter Subject behavioural profile;
- bitemporal queries distinguish occurrence from system discovery;
- a killed run resumes without restarting the entire import;
- every supported file family from Task 3A has locator-preserving fixtures;
- unsupported/encrypted/corrupt files remain visible with explicit status.

Run full builds/tests and audit every requirement in Task 3 and Task 3A line by line.

At completion report:

1. final pipeline;
2. sub-agent delegation map and integrated branches/worktrees;
3. new dependencies;
4. storage layout;
5. file-family support matrix from Task 3A;
6. schema/parser registry;
7. model execution policy;
8. temporal-state architecture;
9. exact tests and benchmark results;
10. unsupported schemas/file families;
11. measured model-call reduction;
12. restart/resumability evidence;
13. data-loss or migration risks;
14. every incomplete requirement.

Do not begin Task 4.
