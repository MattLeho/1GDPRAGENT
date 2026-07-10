Prompt to Chatgpt:
Yooo 5.6 sol how u doing, ive been waiting long for you! So here we go, essentially ive been following the vote for chat control and I was speaking with 5.5 about it and it gave me several ideas on how we could add to and enhance my GDPR agent project. So, I've cloned the repo to this computer im working on but I need you to comb through the repo using the github connector, and have a look at my repo- [@MattLeho/1GDPRAGENT](https://github.com/MattLeho/1GDPRAGENT) Have a look at the current state, and think about my actual philosophy behind the project; People should be able to see and understand the same patterns in their own data that platforms, data brokers and advertisers use to profile them. At the moment, personal data is fragmented across browsing histories, accounts, purchases, locations, interactions and identifiers. Individually, those records may look meaningless. Once connected, they can reveal patterns about behaviour, interests, routines and relationships that the person generating the data may never be able to see themselves. The app tries to reverse that information asymmetry. GDPR access rights become the mechanism for retrieving the data. The system then parses it, links related information across sources and represents those connections in a private knowledge graph. AI is used as an interface for exploring that graph: helping the user ask questions, notice recurring patterns and understand relationships that would be impractical to inspect manually. The point is not to let AI declare hidden truths about someone's psychology. Its interpretations should be treated as prompts for reflection, backed by visible evidence and relationships in the user's own data. The wider idea is that data collection does not have to be primarily extractive or predatory. The same kinds of behavioural connections used to optimise engagement, advertising or influence could instead be made visible to the individual who produced the data. So the project is really about personal data autonomy, self-knowledge and returning analytical power to the person being profiled. I think the philosophy can be sharpened. At the moment its core idea is roughly: Take personal-data exports → parse them → preserve provenance → construct a knowledge graph → let the person inspect and interrogate what organisations know about them. I would expand that into: Map not only the data that exists, but the institutional capability created by the data, the edges that make it linkable, the purpose under which it was collected, and how far current use has drifted from the original justification. Anyway- so below are some extracted parts of the conversation I had and you need to create one or more plans for me to pass onto codex to make the changes. conceptual change to your GDPR project Your current question is: What do organisations know about me? Upgrade it to four questions: What do they know about me? How did they derive it? What can they do because the data and systems exist? Why was that capability created, and has its permitted purpose changed? Then I asked chatgpt a follow up- I have over 300gb of google takeout data to analyse do u think Gemma 4 is good enough? No quantisation and what other deterministic filters cld I include. I said Gemma 4 but there may be other specialised models and we dont necessarily need to run local we can run on a cloud with 0 data retention but it kinda defeats the point of local first. Here is what it responded to that: pasted text 2. Then, I asked one more follow up- it was long so its the 3rd paste. and the response is in the 4th paste.


## Response From ChatGPT




Yeah. I went through it properly.

My blunt read is: **your new philosophy is not a feature addition to the existing GDPR Agent. It is the architectural thesis the existing app has been missing.**

Right now the repository is still fundamentally:

```text
DSAR
 ↓
receive files
 ↓
AI reads files
 ↓
extract "data points"
 ↓
assign risk
 ↓
put them in Neo4j
 ↓
ask an AI what companies know about me
```

The README still explicitly describes an **“8 specialised AI agents”** system where Gemini powers analysis, classification and graph extraction. fileciteturn6file0L24-L51

Your actual philosophy has moved much further:

```text
EVIDENCE ACQUISITION
        ↓
WHAT WAS OBSERVED?
        ↓
HOW IS IT LINKABLE?
        ↓
WHAT WAS DERIVED OR INFERRED?
        ↓
WHAT CONTROLLER PROFILE IS EVIDENCED?
        ↓
WHAT CAPABILITIES DOES THE DATA TOPOLOGY ENABLE?
        ↓
WHY WAS THAT CAPABILITY CREATED?
        ↓
HOW HAS PURPOSE / ACCESS / CAPABILITY CHANGED?
        ↓
WHAT IS UNKNOWN?
        ↓
TARGETED DSAR
        ↓
NEW EVIDENCE
        ↓
GRAPH UPDATED
```

That is a **completely more serious product**.

## My diagnosis of the current repo

| Area | Actual state |
|---|---|
| DSAR request lifecycle | **Implemented / substantial** |
| Built-in, N8N and hybrid workflow selection | **Implemented** |
| Multi-provider model selection UI | **Implemented as configuration scaffolding** |
| Runtime model-provider abstraction | **Partial** |
| Local-first heavy data analysis | **Not implemented** |
| File catalogue | **Basic implementation** |
| Deterministic artefact detection | **Early implementation** |
| Grounded extraction with text offsets | **Partial and valuable** |
| End-to-end provenance enforcement | **Not implemented** |
| Knowledge graph | **Implemented, but ontologically inconsistent** |
| Temporal graph | **Not implemented** |
| Personal behavioural history | **Not implemented** |
| Separate controller profile | **Not implemented** |
| Capability model | **Not implemented** |
| Purpose drift | **Not implemented** |
| Institutional access graph | **Not implemented** |
| Identifier centrality / linkability | **Not implemented** |
| Active graph-testing DSAR loop | **Not implemented** |
| Graph-cut deletion analysis | **Not implemented** |
| `300 GB` event storage architecture | **Not implemented** |

The good news is that **you do not need to start over**.

Three existing pieces are particularly valuable.

First, `data_artifacts.ts` is the seed of the deterministic pre-model layer. It already produces JSON structure, tables, geographical points, timeline events and risk signals. fileciteturn11file0L116-L223 It is just currently extremely shallow: **“250”** rows, **“120,000”** characters and regex-based emails/IPs/dates/coordinates. fileciteturn11file0L40-L46

Second, your Python `GroundedExtractor` already understands the principle of schema-constrained extraction with source offsets. It explicitly tracks `start_offset` and `end_offset`, and the LangExtract path uses source intervals. fileciteturn36file0L237-L302 Your Pydantic schemas also already distinguish grounded entities and SPO triples and carry provenance-related fields. fileciteturn37file0L59-L99 fileciteturn37file0L158-L191

Third, you already have **PostgreSQL + Neo4j + Redis + Celery + a Python intelligence service**. fileciteturn17file0L3-L21 fileciteturn17file0L65-L107 fileciteturn17file0L115-L168 You have the correct broad stack.

The problem is that the **live upload path bypasses your best architecture**.

It currently sends complete file buffers to Google for extraction, summarises limited substrings, and then has a second generic graph extraction prompt. fileciteturn32file0L194-L253 fileciteturn32file0L273-L283 The direct graph path then does this:

```cypher
MERGE (e:Entity {value: $value})
```

and stores a basic evidence JSON containing file/company/source. fileciteturn33file0L3-L26

That is precisely the architecture you now philosophically disagree with.

Worse, your ontology has drifted.

The Python ingestor defines:

```text
User
Company
Account
Attribute
DataPoint
Persona
```

with a narrow relationship model. fileciteturn13file0L25-L47

The TypeScript graph schema additionally contains:

```text
Entity
Inference
Email
Phone
Username
Identifier
ONSIT entities
...
```

fileciteturn16file0L6-L37

Then graph chat queries relationships including:

```text
USES_EMAIL
HAS_PHONE
OWNS_ACCOUNT
REGISTERED_WITH
```

which are not the relationship model declared by the Python ingestor. fileciteturn15file0L23-L63

**Do not tell Codex to add Capability nodes to that.**

You will fossilise the schema drift.

There is also one current component I would actively demote: the existing relationship `InferenceEngine`. It defaults to LLM cross-community inference, transitive inference and lexical inference. fileciteturn40file0L123-L149 Its cross-community prompt literally asks what relationships **“might exist”**, then creates inferred triples with no source chunk or source text. fileciteturn40file0L331-L393

That is almost the exact anti-pattern your philosophy now rejects.

It can survive as a **hypothesis generator**.

It cannot be allowed to create ordinary graph truth.

The core principle from your pasted discussions is correct:

> **Never allow “what my behaviour suggests”, “what a controller explicitly classified”, and “what my system currently believes” to collapse into the same node or fact.** fileciteturn0file3

I would give Codex **three separate briefs, sequentially**. Do not feed it one enormous “redesign everything” prompt.

# Codex plan `1` — rebuild the evidence and graph foundation

Run this first. Do not start the `300 GB` Takeout work until this is merged.

:::writing{variant="document" id="81427"}
You are working in the local repository for:

`MattLeho/1GDPRAGENT`

Before editing, inspect the current repository recursively and use the CURRENT CODE as the strongest source of truth.

Read at minimum:

- `README.md`
- `IMPLEMENTATION_TRACKER.md`
- `Audit.md`
- `fixes.md`
- `02_DATABASE_SCHEMA.sql`
- `docker/init/01_schema.sql`
- all current migration directories
- `frontend/lib/data-artifacts.ts`
- `frontend/lib/graph.ts`
- `frontend/lib/graph/schema.ts`
- all `frontend/app/api/graph/**`
- all `frontend/app/api/upload/**`
- `frontend/lib/model-preferences.ts`
- `frontend/lib/model-intents.ts`
- `intelligence/api/**`
- `intelligence/agents/kg_ingestor.py`
- `intelligence/extraction/**`
- `intelligence/validators/**`
- `intelligence/tasks.py`
- current N8N response-parser and KG workflows

Do not implement from old documentation blindly.

The repository currently contains schema drift and legacy assumptions. Preserve useful functionality, but the new architecture must establish one canonical evidence and ontology model.

# Project philosophy

The application exists to reverse information asymmetry.

People should be able to inspect and understand the same kinds of patterns in their own personal data that platforms, data brokers and advertisers may use to profile them.

The product is not a psychological truth engine.

AI-generated interpretations must remain evidence-backed prompts for reflection. They must never be presented as facts about the person's identity or psychology merely because a model inferred them.

The application must ultimately answer four distinct questions:

1. What does an organisation appear to know or process about me?
2. How was that information observed, derived or inferred?
3. What capabilities appear to be enabled by the combination of data and systems?
4. Why was that capability or processing created, and how has its documented purpose or scope changed?

The following concepts MUST remain epistemically separate:

- what the person explicitly declares;
- what the person's observed activity shows;
- what the controller explicitly assigns or records;
- what deterministic analysis derives;
- what a model suggests;
- what a human confirms;
- what is documented as implemented;
- what is legally authorised;
- what is merely technically possible;
- what is speculative.

Capability does not imply abuse.

A data relationship does not establish psychological truth.

Absence from an export does not prove deletion.

A purpose-drift indicator is not a legal judgement.

# Primary task

Refactor the repository around an immutable, provenance-preserving assertion model before adding new capability or temporal-analysis features.

This is an architectural migration, not a cosmetic graph-schema update.

## 1. Establish one migration source of truth

The repository currently contains schema definitions in multiple locations and route-level `CREATE TABLE` logic.

The top-level SQL schema also contains destructive `DROP TABLE IF EXISTS` statements.

Create a single canonical migration system.

Preferred architecture:

- canonical migrations in `database/migrations/`;
- numbered, ordered, idempotent migration files;
- a migration history table;
- a migration runner;
- a one-shot Docker migration service or equivalent startup migration stage;
- application services start after successful migration;
- route handlers do not create or alter database tables;
- `02_DATABASE_SCHEMA.sql` becomes a generated/reference snapshot or clearly marked compatibility artefact rather than the operational migration mechanism;
- never drop existing user evidence as part of normal startup or migration.

Preserve all current data.

Backfill legacy records where practical.

Add migration tests against a disposable PostgreSQL database.

## 2. Create the canonical evidence ledger

Implement PostgreSQL tables and typed Python/TypeScript models for the following concepts.

### AnalysisRun

A versioned execution of an ingestion, extraction or analytical pipeline.

Minimum fields:

- `id`
- `run_type`
- `profile_id`
- `request_id`
- `status`
- `pipeline_version`
- `configuration`
- `started_at`
- `completed_at`
- `error`
- `created_at`

Do not use one mutable `graph_ingested` boolean as the history of analysis.

Legacy flags may remain temporarily for backwards compatibility, but versioned analysis runs become authoritative.

### ExportSnapshot

Represents one controller export, Takeout export, DSAR response or manually imported dataset.

Minimum fields:

- `id`
- `profile_id`
- `request_id`
- `controller_key`
- `source_type`
- `exported_at`
- `ingested_at`
- `analysis_run_id`
- `metadata`

### ContentBlob

Represents unique immutable bytes.

Minimum fields:

- `id`
- `sha256`
- `byte_size`
- `storage_uri`
- `first_ingested_at`

`sha256` must be unique.

Deduplicating content MUST NOT delete provenance.

### SourceArtifact

Represents the actual file or archive-member occurrence seen in a source export.

Minimum fields:

- `id`
- `export_snapshot_id`
- `parent_artifact_id`
- `content_blob_id`
- `original_path`
- `archive_member_path`
- `file_name`
- `declared_mime`
- `detected_mime`
- `extension`
- `file_type_status`
- `canonical_hash`
- `structure_fingerprint_id`
- `source_organisation`
- `source_product`
- `source_service`
- `created_at`

Two SourceArtifacts may refer to the same ContentBlob.

This is how exact duplicate content is removed from repeated processing without losing the fact that the same content appeared in multiple exports or paths.

### EvidenceLocator

Implement a typed locator model.

Supported locator types must include:

- `json_pointer`
- `csv_row`
- `csv_cell`
- `text_span`
- `html_dom_span`
- `media_time_range`
- `image_region`
- `archive_member`

Minimum fields:

- `id`
- `artifact_id`
- `locator_type`
- `locator`
- `raw_hash`
- `created_at`

`locator` should be JSONB and use a strict schema per locator type.

Examples:

JSON:

```json
{
  "pointer": "/profile/ageSegment"
}
```

CSV:

```json
{
  "row": 1842,
  "column": "deviceId"
}
```

Text:

```json
{
  "byte_start": 4821,
  "byte_end": 4879,
  "line_start": 72,
  "line_end": 73
}
```

Media:

```json
{
  "start_ms": 18240,
  "end_ms": 23700
}
```

Add a locator resolver/verifier.

A source locator must be mechanically resolvable against the referenced artifact.

### Assertion

Every semantic conclusion becomes an immutable Assertion.

Minimum fields:

- `id`
- `subject_type`
- `subject_ref`
- `predicate`
- `object_type`
- `object_ref`
- `object_value`
- `assertion_type`
- `data_class`
- `status`
- `epistemic_basis`
- `confidence`
- `valid_from`
- `valid_to`
- `temporal_precision`
- `controller_observed_from`
- `controller_observed_to`
- `exported_at`
- `ingested_at`
- `system_asserted_at`
- `superseded_at`
- `supersedes_assertion_id`
- `derivation_method`
- `derivation_version`
- `analysis_run_id`

Use controlled enums.

`data_class`:

- `declared`
- `observed`
- `derived`
- `inferred`

`status`:

- `candidate`
- `accepted`
- `rejected`
- `superseded`

`epistemic_basis`:

- `source_explicit`
- `controller_assigned`
- `deterministic_derivation`
- `model_hypothesis`
- `human_confirmed`

Never mutate the semantic content of an accepted assertion in place.

A changed conclusion creates a new Assertion and supersedes the previous Assertion.

Create an `assertion_evidence` join table connecting assertions to one or more EvidenceLocators.

## 3. Enforce provenance as an invariant

The existing grounded extraction code is useful and should be retained.

However, provenance is currently not enforced end to end.

Implement these rules:

1. A `model_hypothesis` cannot become an accepted assertion without at least one verified EvidenceLocator.
2. A model supplying an estimated character offset is insufficient.
3. For exact-text extraction, the quoted source span must resolve against the original content.
4. If an exact source span cannot be located, create a review candidate or reject the extraction.
5. MAKGED may validate interpretation of evidence, but MAKGED cannot manufacture missing provenance.
6. Generic JSON such as `{fileId, companyName, source}` is metadata, not a source locator.
7. Every accepted assertion must record derivation method and derivation version.

Modify the Gemini fallback in `GroundedExtractor`.

It currently permits model-provided estimated offsets.

Do not silently accept an estimated offset when the exact extracted span cannot be found.

## 4. Replace the drifting graph ontology

Create one canonical graph ontology module shared conceptually between Python and TypeScript.

Do not maintain independent undocumented label and relationship sets.

Core Neo4j node types:

- `GraphNode`
- `Subject`
- `ControllerProfile`
- `Organisation`
- `Account`
- `Identifier`
- `DataDomain`
- `DataPoint`
- `Topic`
- `TemporalState`
- `ProjectEpisode`
- `ProcessingActivity`
- `Purpose`
- `LegalBasis`
- `Capability`
- `CapabilityExposureState`
- `PolicyInstrument`
- `Claim`
- `SourceArtifact`
- `Dataset`
- `Request`

ONSIT-specific graph types may remain, but they must be explicitly separate from the personal-data evidence ontology.

The key distinction is:

```text
Subject:Matt
```

is not:

```text
ControllerProfile:Google:Matt
```

and neither is:

```text
SystemHypothesis:Matt
```

Never merge these semantic layers.

Examples:

```text
(:Subject)-[:HAS_OBSERVED_SIGNAL]->(:TemporalState)
```

```text
(:ControllerProfile)-[:ASSIGNED_ATTRIBUTE]->(:DataPoint)
```

```text
(:Organisation)-[:MAINTAINS_PROFILE]->(:ControllerProfile)
```

A controller-assigned interest must not become a property of the Subject node.

A behavioural interest signal must not become a controller-assigned category.

## 5. Stop using Neo4j internal numeric IDs as API identity

The current graph API exposes Neo4j internal `id(n)` values.

Introduce a stable UUID `node_id`.

All ontology nodes should carry:

```text
:GraphNode {
  node_id
}
```

Add appropriate uniqueness constraints.

Backfill existing nodes with UUIDs.

Graph API responses and write APIs must use `node_id`.

Temporarily support legacy numeric IDs only where needed for migration compatibility.

Remove that compatibility after dependent code is migrated.

## 6. Replace `MERGE (e:Entity {value: $value})`

Do not resolve entities by raw value alone.

Implement typed canonical entity keys.

Examples:

```text
Email:
type + normalised address

Phone:
type + normalised E.164-style value where safely parseable

OpaqueIdentifier:
identifier_type + normalised value + relevant controller/service scope

Organisation:
canonical organisation key

Account:
controller/service + account identifier
```

Never merge:

```text
"123"
```

from unrelated schemas merely because the raw string is identical.

Create a deterministic resolver API.

Model suggestions may propose equivalence.

They may not directly merge nodes.

Human-approved or deterministic resolution performs the merge.

## 7. Demote the existing inference engine to hypothesis generation

Review:

`intelligence/extraction/inference_engine.py`

Its LLM cross-community inference and generic transitive inference must not generate ordinary accepted privacy relationships by default.

Change defaults so:

- LLM relationship inference is OFF for accepted evidence;
- generic transitive relationships do not write normal graph edges;
- lexical similarity does not establish entity identity;
- inferred relationships are emitted as Assertion candidates with `epistemic_basis=model_hypothesis`;
- source assertions used to generate a candidate are explicitly linked;
- no candidate is promoted merely because a model assigned high confidence.

The UI may display hypotheses.

They must have a visually and structurally different status.

## 8. Version `data_artifacts`

Current `replaceArtifactsForFile` deletes all existing data artifacts for a file and recreates them.

That destroys analytical history.

Replace delete-and-reinsert semantics with versioned outputs linked to AnalysisRun.

Add:

- `analysis_run_id`
- `artifact_version`
- `supersedes_artifact_id`
- `derivation_method`
- `derivation_version`

Old generated artifacts remain queryable.

The current view may select the latest accepted version.

## 9. Route graph writes through one service

There are currently multiple graph-ingestion paths:

- Python KG ingestor;
- direct Next.js upload scanning;
- legacy N8N ingestion;
- manual graph APIs.

Create one canonical graph-projection service in the Python intelligence layer.

The graph is a projection of accepted evidence/assertions.

Preferred flow:

```text
SourceArtifact
    ↓
Extraction
    ↓
Assertion candidates
    ↓
Provenance validation
    ↓
Deterministic / MAKGED / human review
    ↓
Accepted assertions
    ↓
GraphProjectionService
    ↓
Neo4j
```

Next.js upload routes must not independently invent another graph ontology.

N8N must not independently invent another graph ontology.

Manual graph edits should create human-confirmed Assertions and then use GraphProjectionService.

## 10. Preserve existing useful functionality

Do not unnecessarily remove:

- DSAR request management;
- email/request workflows;
- built-in / N8N / hybrid workflow selection;
- ONSIT functionality;
- provider credential UI;
- current graph visualisation;
- MAKGED;
- grounded extraction;
- existing request records.

Add compatibility adapters where necessary.

## 11. Tests and acceptance criteria

Add real tests, not only static source-text checks.

Required tests:

- migrations are idempotent;
- migrations do not destroy existing request/file data;
- duplicate ContentBlob bytes produce one blob and multiple SourceArtifacts;
- evidence locators resolve against fixture artefacts;
- invalid JSON Pointer is rejected;
- incorrect exact-text span is rejected;
- model assertion without verified evidence cannot become accepted;
- assertion semantic content is immutable;
- supersession creates a new assertion;
- Subject and ControllerProfile cannot be accidentally merged;
- raw value equality alone does not merge different identifier types;
- stable Neo4j `node_id` survives graph reloads;
- legacy graph data can be backfilled;
- speculative inference is not returned in current accepted-profile queries by default;
- graph projection is idempotent.

Use synthetic fixtures only.

Do not put Matt's real personal data into tests.

## 12. Documentation

Update:

- `README.md`
- `IMPLEMENTATION_TRACKER.md`
- relevant architecture documentation

The README should no longer describe the product primarily as “8 Gemini agents”.

Describe the architecture as:

```text
privacy-rights acquisition
+
provenance-preserving personal-data analysis
+
temporal evidence graph
+
human-controlled AI interpretation
```

At completion, report:

1. files changed;
2. migrations added;
3. legacy behaviour retained;
4. legacy behaviour deprecated;
5. new ontology;
6. provenance invariants;
7. tests run and exact results;
8. any incomplete migration risks.

Do not start the 300 GB Takeout pipeline in this task.

This task establishes the trusted foundation it requires.
:::

# Codex plan `2` — build the `300 GB` local-first ingestion and temporal analysis engine

This is where the project genuinely changes category.

Your previous discussion was right that the model must see **the smallest residue deterministic code cannot classify**. fileciteturn0file1

Do not make “Gemma 4” itself the architecture.

Your current model settings already have multiple provider choices, but the heavy upload code falls back to Google even when the selected workflow provider is not Google. fileciteturn34file0L67-L75 The Python LangExtract endpoint also currently hardcodes `gemini-2.5-flash`. fileciteturn39file0L222-L233

So Gemma should be a **candidate implementation of a model role**. Benchmark it. Do not wire your ontology to it.

:::writing{variant="document" id="39061"}
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
:::

# Codex plan `3` — capability, purpose drift, linkability, active DSAR testing and the actual product UI

This is the layer that turns your project from **“look at my GDPR data”** into **“show me the profiling and institutional machinery that becomes visible when my data is connected”**.

It directly implements the Capability, Edge Risk, Purpose Drift, access graph, graph-testing and deletion ideas from your earlier discussion. fileciteturn0file0

It also preserves the longitudinal personal-analysis side rather than replacing it. Your system therefore becomes:

```text
WHO I SAY I AM
        │
WHAT MY ACTIVITY EVIDENCES
        │
WHAT CONTROLLERS APPEAR TO CLASSIFY
        │
WHAT THE SYSTEM CURRENTLY HYPOTHESISES
        │
WHAT THE DATA TOPOLOGY ENABLES
        │
HOW ALL FIVE CHANGED THROUGH TIME
```

That is the core product.

:::writing{variant="document" id="62743"}
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
:::

## My actual view on the project now

Your original app was basically a **DSAR operating system with a knowledge graph**.

The repo still reflects that. The `received_data` table stores extracted text, AI summaries, extracted entities and a `graph_ingested` boolean. fileciteturn10file0L59-L90 The old AgentDescriptions describe a Response Parser that asks Gemini to classify personal data and assign `LOW/MEDIUM/HIGH` risk, followed by a KG agent that turns those outputs into triples. fileciteturn22file0L260-L307 fileciteturn22file0L338-L397

The thing you are describing now is different.

I would define the system as:

> **A personal-data autonomy system that reconstructs the machine-observable version of a person's life, preserves how that reconstruction changes through time, compares it with controller-assigned profiles, and exposes the data relationships, institutional access paths and technical capabilities that become visible when fragmented personal data is connected.**

The GDPR bit is still essential.

But **GDPR is the acquisition mechanism**.

The knowledge graph is not the product either.

The graph is the **explanatory structure**.

AI is not the analyst of record.

AI is the **interface and semantic adjudicator for material deterministic code cannot resolve**.

And the personal longitudinal side is not a distraction from the privacy project. The fact that you can reconstruct project sprints, interests, routines and changing centres of activity from records you generated almost incidentally is the demonstration of the privacy thesis itself. Your own pasted temporal design already recognised that raw evidence, observed events, temporal states and current profile must be separate layers. fileciteturn0file2

The strongest question the finished app could ask is no longer merely:

> **“What does Google know about me?”**

It is:

> **“How did the digitally observable version of me evolve, how closely did organisations' machine-readable profiles track that evolution, which links allowed fragmented observations to become a profile, and what capabilities became possible because those links existed?”**

That is the project. Run the three Codex briefs in order.