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