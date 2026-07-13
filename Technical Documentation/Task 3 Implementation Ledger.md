# Task 3 implementation ledger

This ledger is the canonical implementation record for Task 3 and mandatory Task 3A. It is updated at every wave gate.

| Requirement | Owner | Dependency | Implementation location | Status | Tests | Integration status | Migration/backfill note | Blocker |
|---|---|---|---|---|---|---|---|---|
| Wave 0 predecessor audit | Orchestrator | Task 1/2 | `frontend/lib/evidence.ts`, registries, Python ledger/projection | complete | Baseline suite | verified | none | none |
| Canonical Task 3 contracts | Orchestrator | Task 1 evidence ledger | `intelligence/ingestion/models.py` | complete | `tests/test_task3_contracts.py` (15 passed) | frozen for Wave 1 | additive only | none |
| Task 3A locator extension | Orchestrator | Task 1 locator enum | `intelligence/evidence`, migrations 011/012 | contract complete | contract tests passed | frozen for adapter work; resolvers pending | additive enum migration | none |
| Task 3 persistence catalogue | Orchestrator | PostgreSQL | migrations 011/012 | complete | migration idempotency passed | frozen for Wave 1 | no backfill required initially | none |
| Bulk ingestion foundation | Delegated + orchestrator integration | frozen contracts | `intelligence/ingestion/{storage,inventory,hashing,file_types,fingerprints,processor,catalogue}.py` | complete | Wave 1 suites | integrated | catalogue migration 012 | none |
| File-family adapters | F1/F2/F3/F4/F5/F6 delegates; orchestrator review | `FileFamilyAdapter` | `intelligence/ingestion/adapters` | P0 complete | adapter + cross-family fixtures | integrated | support registry sync | optional codecs reported |
| Schema/parser/event runtime | Orchestrator fallback after delegation limit | Wave 1 | `intelligence/ingestion/{schema_registry,parser_runtime,sampling,events,checkpoints}.py` | complete | `tests/test_task3_wave2.py` | integrated through Task 2 route | migrations 012/013 | none |
| Deterministic features | 3 Wave 3 delegates + orchestrator integration | Wave 2 | `intelligence/features` | complete | Wave 3 feature suites | integrated over event Parquet | local analytical output only | none |
| Task router integration and private benchmark | Orchestrator + `wave4_benchmark` | Task 2 `executeTask` | `frontend/lib/execution/task3.ts`, ingestion routes, `intelligence/benchmark` | complete | Wave 4 route/benchmark suites | audited Task 2 boundary | existing ExecutionRecord | none |
| Temporal engine | 3 Wave 5 delegates + orchestrator persistence | Wave 4 | `intelligence/temporal` | complete | synthetic + PostgreSQL bitemporal suites | integrated | migrations 012/014 | none |
| High-value graph projection | Orchestrator | GraphProjectionService | `intelligence/graph` | pending | end-to-end | not started | no raw-event backfill to Neo4j | Wave 5 gate |
| Final Task 3/3A acceptance audit | Orchestrator | all waves | Technical Documentation | pending | full suite + benchmarks | not started | risk report required | all waves |

## Wave 0 baseline

- Docker services: all eight configured services healthy.
- Celery: `intelligence.health_check` completed successfully.
- Python compilation: passed.
- Python tests: 38 passed with configured PostgreSQL and Neo4j; one pre-existing Pydantic configuration warning.
- Frontend type check: passed.
- Frontend production build: passed.
- Frontend lint: zero errors, 141 pre-existing warnings.
- Worktree: contains uncommitted Task 2/user changes; Task 3 preserves them.

## Predecessor findings

- Task/engine selection is canonically TypeScript-owned in `frontend/lib/execution/registry.ts` and `router.ts`.
- Workflow selection is canonically TypeScript-owned in `frontend/lib/workflows/registry.ts`.
- Privacy modes are exactly `strict_local`, `local_first`, and `controlled_cloud`.
- Source artefacts and assertions are canonically persisted by `EvidenceLedger`; graph writes are canonically performed by `GraphProjectionService`.
- The legacy Python `/ingest` endpoint remains graph-oriented and is not suitable for bulk event-lake ingestion.
- The source-artifact endpoint currently supplies invalid `manual_upload` instead of canonical `manual_import`; this is a predecessor integration defect to correct during Task 3 wiring.
- Direct Google file-processing code remains in legacy upload routes and must be removed or migrated during Task 3A integration.

## Frozen Wave 1 contracts

- `FileFamilyAdapter`, `ExtractionContext`, `ExtractionResult`, `ExtractionUnit`, `EmbeddedMember`, and `FormatSupportRecord` in `intelligence/ingestion/models.py`.
- `InventoryEntry`, `ArchiveMemberObservation`, `FileTypeEvidence`, `FileTypeTruth`, and `StructureFingerprint` in the same module.
- Content-addressed storage writes raw immutable bytes under a configurable local root; PostgreSQL catalogue registration remains outside the storage leaf module.
- Event-lake writes are atomic Parquet partitions and return metadata compatible with `EventPartitionRecord`; leaf storage code does not create database or graph truth.
- Error visibility uses `CheckpointStatus`, `QuarantineStatus`, `file_ingestion_records`, and `pipeline_checkpoints`; unknown and ambiguous are never coerced to supported.
- Task-router calls remain in the TypeScript `executeTask` boundary. Python ingestion modules may prepare bounded bundles but may not invoke providers directly.

## Wave 1 gate

- Focused Task 3 suite: 108 passed, 2 optional/platform skips.
- Python compilation: passed.
- Frontend type check: passed.
- Storage review found and fixed a Windows-only fsync defect after the delegated Linux run.
- Adapter review normalised JSON, CSV, XML, HTML, text, geospatial, database, and document locators against the frozen schema; locator construction now validates mechanically.
- Cross-family fixtures prove ZIP member lineage into JSON/image/email, MBOX attachment resolution, duplicate embedded bytes with distinct occurrences, XLSX cell resolution, GPX/SQLite resolution, and explicit corrupt/unsupported visibility.
- Raw content is content-addressed; event-lake Parquet writes are atomic and queryable through Polars/DuckDB.
- No Wave 1 module writes semantic graph truth or invokes a model/provider.

### Delegation map

| Package | Delegate ownership | Integrated files | Result |
|---|---|---|---|
| 3.1A storage | `wave1_storage` | `storage.py`, storage tests | integrated after Windows durability fix |
| 3.1B archive policy | `wave1_inventory` | `inventory.py`, inventory tests | integrated |
| 3.1C/3.1D classification | `wave1_classification` | hashing, file typing, fingerprints | integrated and catalogue-expanded |
| F1 structured/text | `wave1_f1_structured` | structured adapter/tests | integrated after canonical locator correction |
| F2 documents | `wave1_f2_documents` | document adapter/tests | integrated; OCR remains routed residue |
| F3 email/calendar | `wave1_f3_email` | email adapter/tests | integrated; MIME/ICS resolver corrected |
| F4 media/subtitles | `wave1_f4_media` | media adapter/tests | integrated; extension-only fallback removed |
| F5 geo/SQLite | `wave1_f5_geo_db` | geospatial/database adapter/tests | integrated after locator correction |
| F6 archives | `wave1_f6_archives` | archive adapter/tests | integrated; duplicate/nested resolver added |
| Cross-family fixtures | `wave1_cross_fixtures` | cross-family tests | integrated; GPX resolver gap fixed |

### Wave 1 optional limitations

- HEIF requires an optional platform/Pillow codec.
- Video stream metadata requires `ffprobe`; the real multi-stream fixture is skipped when unavailable.
- Filesystem-symlink fixture is skipped where the host cannot create symlinks; archive symlink policy is still tested.
- P1 7z/RAR/legacy Office/MSG/PST and the catalogued P2 formats remain outside P0 execution.

## Wave 2 gate

- Three prescribed Wave 2 delegate assignments (`wave2_parser_runtime`, `wave2_sampling`, and `wave2_events`) were created, but each failed before producing edits because the shared agent account reached its delegation usage limit. The orchestrator therefore used the specification's central fallback and owns the resulting code and review.
- `SchemaRegistry.resolve` checks for an approved fingerprint/parser binding first. Known schemas return the immutable approved spec without creating interpretation work; unknown fingerprints create one idempotent, bounded interpretation request per interpretation version.
- The frontend schema-interpretation endpoint invokes the existing Task 2 `executeTask` route. It rechecks the byte budget, supplies source artefact IDs for `ExecutionRecord` auditing, inherits the canonical privacy policy, and returns only `review_status: proposed`; it never approves or executes model output.
- Parser specs accept JSON Pointer and a restricted non-wildcard JSON-path subset only. Recursive descent, wildcards, filters, slices, executable expressions, malformed pointers, unsupported families, and overlong selectors are rejected. No generated code is evaluated.
- Deterministic parser execution retains an exact locator ID for every selected field. Missing field provenance rejects the record rather than emitting a partially grounded event.
- Representative sampling covers first valid, median size, maximum key coverage, maximum depth, and bounded structural rarity. The complete sample array is enforced against a hard byte budget; whole files are never placed in an interpretation bundle.
- Canonical ActivityEvents are written atomically to Parquet. Logical identity is derived from schema-appropriate canonical fields; repeated exports produce one event and multiple append-only PostgreSQL observation occurrences. Raw event rows are not written to Neo4j.
- Approved parser versions and approved registry bindings are immutable (with status-only deprecation allowed). Event signatures and provenance catalogues are append-only.
- Checkpoint idempotency includes stage, item key, content hash, and parser version. A forced-failure integration test resumes at attempt two and a completed replay stays completed instead of reprocessing.
- Wave 2 focused gate: 8 tests passed against real PyArrow and a freshly migrated PostgreSQL database. Python compilation and frontend type checking passed.

## Wave 3 gate

- The orchestrator froze `FeatureCandidate`, `FeatureCandidateStatus`, `PrivacyDataClass`, and `OpaqueIdentifierCandidate` before delegating detector work. Every candidate requires detector identity/version, exact event or artefact grounding, calculated values, and a rule result or confidence.
- `wave3_classifiers_identifiers` implemented conservative versioned key dictionaries, service/path candidates, all required multi-label privacy data classes, strong/contextual identifier types, URL-carried identifiers, and opaque-token recurrence/entropy/cross-schema/cross-domain features. Opaque tokens retain `assigned_meaning=None` and are never exposed raw in their aggregate candidate.
- `wave3_url_temporal` implemented offline-only URL decomposition, bounded inference-language candidates, and precision-aware temporal normalisation. No URL path performs DNS or HTTP. Natural-language/ambiguous times remain `UNKNOWN`.
- `wave3_geo_density` implemented all required geospatial precision levels, preservation of reported accuracy, the exact six source-explicit interaction actions, event/day/hour density, object diversity, burstiness, periodicity, first/last seen, and hashed cross-domain co-occurrence. It contains no HOME or social-role inference and no graph writer.
- Orchestrator integration corrected the canonical parser boundary so date-only values no longer become midnight UTC. `ActivityEvent` now retains `occurred_at_original` and `timezone_evidence`; only timezone-aware instants populate `occurred_at`.
- The feature pipeline validates detector identity and event grounding, runs against canonical event Parquet, and batches only ambiguous/adjudication residue under a hard byte limit. A 1,000-event fixture with two ambiguous candidates creates one bundle; an all-deterministic fixture creates zero model work.
- Wave 3 focused integration: 41 passed (one database-only test deselected for the focused run). Full Task 3 regression with PostgreSQL: 150 passed, 2 optional/platform skips. Python feature/ingestion compilation passed.

### Wave 3 delegation map

| Package | Delegate ownership | Integrated files | Result |
|---|---|---|---|
| 3.3A/3.3B classification and identifiers | `wave3_classifiers_identifiers` | dictionaries, classification, identifiers, tests | integrated; conservative English v1 dictionaries |
| 3.3C URL/inference/temporal | `wave3_url_temporal` | URL, inference-language, temporal, tests | integrated; parser date-only boundary corrected centrally |
| 3.3D/3.3E geo/interactions/density | `wave3_geo_density` | geospatial, density, tests | integrated; no semantic place/social promotion |
| Feature orchestration | Orchestrator | pipeline, Parquet fixture tests, package exports | integrated; bounded residue only |

## Wave 4 gate

- Task 3 roles map to existing Task 2 keys for schema interpretation, semantic adjudication, topic labelling, media-boundary work, and narrative explanation. Legacy aliases are mapping-only; no second task, engine, provider, credential, or fallback registry was created.
- `executeTask3Bundle` mechanically caps model-facing residue at 256 samples / 256 KiB, 1,024 source artefacts, and a 2,048-character purpose. Python `ModelAdjudicationBundle` independently verifies its actual serialised sample size.
- Structured Task 3 responses are parsed as JSON. Invalid output remains explicitly `structured_output_valid: false`; schema proposals remain `proposed` and semantic results remain candidates/abstentions rather than accepted facts.
- Privacy hardening removed the legacy unknown-provider-to-Google normalisation. Unsupported provider IDs now fail closed. `controlled_cloud` now requires explicit membership in `approved_external_engines` (an empty list allows none), and denied local-first external candidates create auditable privacy-block records rather than disappearing as a no-route result.
- Task 2 already implemented Ollama, Google, OpenAI, OpenRouter, Hugging Face, and NVIDIA generation adapters with health and structured errors. No Wave 4 Python cloud adapter was delegated because that would duplicate the verified canonical provider runtime; Python retains local specialist service adapters only.
- `wave4_benchmark` delivered an injected-executor harness and four bounded synthetic cases. Reports cover exact classification/schema accuracy, locator validity, abstention, structured-output validity, latency, supplied peak memory, audited local/external execution, and configured cost metadata. The report contract mechanically fixes `selection_recommendation=None` and performs no public ranking lookup.
- `Task2RouterBenchmarkExecutor` calls the audited benchmark route; every real invocation resolves its engine/provider/model/location from the corresponding `ExecutionRecord`. The harness itself has no provider or network knowledge and writes per-task reports atomically.
- Wave 4 focused integration: 20 passed; frontend type checking and Python benchmark compilation passed.

### Wave 4 delegation map

| Package | Delegate ownership | Integrated files | Result |
|---|---|---|---|
| 3.4A provider adapters | Orchestrator audit | existing Task 2 TypeScript provider runtime | no missing cloud adapter; duplicate implementation intentionally not created |
| 3.4B private benchmark | `wave4_benchmark` | harness, labelled synthetic fixtures, tests | integrated with Task 2 router executor and API metadata boundary |

## Wave 5 gate

- The frozen history types are `personal_behavioural`, `controller_profile`, and `system_understanding`. `TemporalState` and PostgreSQL retain occurrence, valid, controller-observation, export, ingest, system-assertion, and supersession axes separately; every axis permits unknown.
- `wave5_interest_episodes` implemented evidence-linked hierarchical topic rollups and the authoritative six dimensions: intensity, persistence, recurrence, breadth, novelty, and context dispersion. Optional weighted output is explicitly derived/configured and cannot replace the six source dimensions.
- Robust temporal detection uses past-only rolling median/MAD, recurrence classes, deterministic univariate/multivariate PELT, non-destructive exponential decay, and evidence-grounded project/topic-cluster episode candidates. Models may label detected candidates later but do not perform detection.
- `wave5_engagement_routines` implemented transparent action-count engagement across consumption, investigation, creation, implementation, and communication; hour/day/service/event/topic distributions and total-variation drift; and hashed-counterpart interaction metrics. Only explicit inbound/outbound evidence is consumed and relationship/personality labels remain mechanically absent.
- `wave5_eras_views` implemented monthly multivariate vectors, deterministic/missing-month boundaries, contiguous era candidates, stable IDs, evidence-constrained machine labels with `ExecutionRecord`, and separately proven human labels. Neither label type falls back to the other.
- Pure and database-backed NOW/AS-OF views keep valid time and system-discovery time distinct. Export comparison covers assertion, schema, and event-observation levels with all four statuses and separate personal/controller/understanding drift. Wording states “newly observed by this system” and never equates absence/presence with controller deletion/collection.
- Migration 014 adds missing temporal axes, history-aware aggregates, append-only topic/episode/era/label/delta catalogues, current view, and a two-axis `temporal_states_as_of` function. Only one-time supersession can mutate a state; all other history is append-only.
- A freshly migrated PostgreSQL integration proves all three histories coexist and that the same valid-time query returns different state versions at different system times. Focused Wave 5 gate: 24 passed; temporal compilation passed.

### Wave 5 delegation map

| Package | Delegate ownership | Integrated files | Result |
|---|---|---|---|
| 3.5A/3.5B interest and episodes | `wave5_interest_episodes` | interest, episodes, synthetic tests | integrated; statistical detection only |
| 3.5C engagement/routines/interactions | `wave5_engagement_routines` | engagement, routines, interactions, tests | integrated; no relationship/personality inference |
| 3.5D/3.5E eras/views/deltas | `wave5_eras_views` | eras, views, tests | integrated; machine/human provenance separate |
| Temporal persistence/as-of | Orchestrator | repository, migration 014, PostgreSQL test | integrated; append-only bitemporal histories |

## Wave 6 gate

- `wave6_synthetic_corpus` supplied repeated snapshots, duplicate/reordered inputs, malformed content, file-truth mismatch, and restart fixtures. `wave6_performance` supplied an instrumented local benchmark and restart boundary.
- The orchestrator replaced both legacy upload processing routes with thin clients for `/bulk-ingestion/process`. Specialist work is returned as explicit Task 2 requests and results are persisted with engine/model/derivation/confidence provenance.
- Migration 015 adds extraction units, specialist requests, replay-safe reconciliation, and explicit `unverified_legacy` status for predecessor model summaries. Raw events remain append-only Parquet; PostgreSQL stores catalogues and observations, not a duplicate event lake.
- The workflow registry now points `file.ingestion` at `/bulk-ingestion/process`. Durable container storage is mounted at `/data`; imports are constrained to `/source-uploads`.
- `GraphProjectionService.HIGH_VALUE_LABELS` restricts Task 3 projection to privacy topology. `ActivityEvent` is absent, and a controller-profile-to-Subject guard preserves the three-history separation.
- Exact performance evidence: 3 files / 254,674 bytes / 3,000 records / 2,000 events / 1 semantic call. The call-to-record ratio was 0.000333 (99.9667% fewer calls than per-record processing); provider/network calls were zero. Two Parquet partitions contained 4,000 rows / 347,014 bytes. Peak traced memory was 75,127,597 bytes. Restart skipped three completed items and replayed none in 0.109 ms.
- The SQLite scale fixture now contains exactly 1,000,000 rows while sampling and counting remain bounded.
- Final verification: Python compile passed; full repository tests 246 passed / 2 optional skips; frontend lint, TypeScript, and production build passed; Docker compose validation and migrations 011–015 passed; intelligence and Celery were recreated healthy with the durable data volume.

### Wave 6 delegation map

| Package | Delegate ownership | Integrated files | Result |
|---|---|---|---|
| 3.6A synthetic corpus/restart | `wave6_synthetic_corpus` | corpus fixtures and restart tests | integrated; 11 focused tests passed |
| 3.6B performance | `wave6_performance` | performance benchmark/tests | integrated; exact measurements recorded above |
| Interest/episode completion | `wave5_interest_episodes` | temporal interest/episode implementation | integrated in Wave 5 |
| Bulk orchestration, graph policy, acceptance | Orchestrator | API, frontend client, migration 015, graph policy, final audit | integrated and repository-tested |

### Explicit Stage 5 follow-up audits

- `wave5_asof_export_audit` independently re-audited Stage 5 lines 973–999 after the final integration. It confirmed NOW and AS-OF derived views, independent valid/system time, immutable inputs, assertion/schema/event-observation comparisons, all four delta statuses, separate personal/controller/understanding drift, and conservative non-deletion/non-collection wording. Focused result: 6 passed; no fix required. Delta logic is intentionally co-located in `temporal/views.py`.
- `wave5_interest_episodes` independently re-audited the package and found three concrete completeness gaps. It added prefix-only recurrence histories with active/dormant/return metrics, made deterministic PELT use robust L1 by default for uni/multivariate histories, added an evidence-preserving decay result, and enforced a default two-event minimum for project episodes. Appending future periods cannot alter earlier recurrence states; isolated outliers do not create change points; isolated one-evidence bursts do not become projects. Focused temporal/view/corpus result: 29 passed; temporal compilation passed.

### Graph projector completion evidence

- Task 3 does not introduce a second graph writer. It extends the canonical Task 1 `GraphProjectionService`, whose real PostgreSQL/Neo4j integration test proves accepted-only, provenance-valid and idempotent projection.
- Task 3 adds an explicit `HIGH_VALUE_LABELS` privacy-topology allowlist. It includes Subject, ControllerProfile, Organisation, Account, Identifier, DataDomain, Topic, high-value DataPoint, TemporalState, ProjectEpisode, ProcessingActivity, Purpose, Capability/exposure, policy/claim, and SourceArtifact concepts; it excludes `ActivityEvent`.
- ControllerProfile→Subject mutation is rejected, preserving controller-assigned and personal-behavioural histories. The bulk ingestion module is statically proven to have no Neo4j or `GraphProjectionService` dependency.
- Graph tests cover stable identity, idempotent accepted assertion projection, rejection of candidates, cross-ontology merge rejection, the Task 3 allowlist, raw-event exclusion, and semantic separation.
