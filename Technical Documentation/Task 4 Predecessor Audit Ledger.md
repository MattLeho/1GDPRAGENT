---
title: Task 4 Predecessor Audit Ledger
date: 2026-07-11
tags:
  - gdpr-agent
  - task-4
  - predecessor-audit
status: complete
---

# Task 4 Predecessor Audit Ledger

> [!success] Phase 0 gate
> Tasks 1, 2, 3 and 3A were audited against current code and focused tests before Task 4 implementation. Two defects that would have made Task 4 incorrect or architecturally duplicative were repaired in the canonical predecessor systems. Task 5 was not started.

## Baseline

| Check | Exact result |
|---|---|
| Full Python suite without host database environment | 235 passed, 2 optional skips, 11 setup errors caused only by missing `DATABASE_URL`, 4 warnings |
| Database-backed rerun with repository environment and local PostgreSQL/Neo4j | 19 passed, 1 Pydantic deprecation warning |
| Unique combined Python result | 246 passed, 2 optional skips; no failing assertion |
| Frontend TypeScript | passed |
| Frontend lint | 0 errors, 133 pre-existing warnings |
| Frontend production build | passed; 57 pages generated |
| Migrations | runner completed twice successfully and idempotently through migration 015 before repairs |
| Services | PostgreSQL, Neo4j, Redis, Qdrant, intelligence, Celery, Next.js and N8N running; application services reported healthy |

## Task 1 — evidence and graph foundation

| Predecessor requirement | Expected implementation | Actual implementation location | Status | Tests run / result | Remediation required |
|---|---|---|---|---|---|
| Canonical non-destructive migrations | Ordered checksum migrations; no route DDL | `database/migrate.py`, `database/migrations`, Compose migration gate | complete | migration/database tests passed; runner passed twice | none |
| AnalysisRun and ExportSnapshot | Versioned execution and source snapshot authority | migrations 002+, `intelligence/evidence/models.py`, `ledger.py`, TypeScript evidence client | complete | database integration passed | none |
| ContentBlob and source occurrence deduplication | One byte blob, multiple provenance occurrences | evidence migration/ledger | complete | duplicate-blob database test passed | none |
| Exact EvidenceLocator resolution | Strict typed locators that mechanically resolve | `intelligence/evidence/models.py`, `locators.py`, migrations 002/006/011/012 | complete | locator tests passed | none |
| Immutable Assertions and supersession | Accepted content immutable; provenance and derivation mandatory | evidence ledger plus migrations 002/005/006/008 | complete | assertion lifecycle database test passed | none |
| Grounded model extraction | Estimated offsets never replace exact evidence | `intelligence/extraction/grounded_extractor.py` | complete | grounded/locator tests passed | none |
| Canonical ontology and stable identity | Shared ontology; Subject distinct from ControllerProfile; UUID `node_id` | `ontology/graph-ontology.json`, Python/TypeScript ontology modules, graph projection | complete for Task 4 dependencies | ontology and Neo4j integration passed | none for Task 4 |
| Full ontology projection parity | Every declared canonical label accepted by projection | `GraphProjectionService.HIGH_VALUE_LABELS` | partial | Task 4 labels are covered; no exhaustive parity test | `LegalBasis`, `Dataset` and `Request` remain a non-Task-4 follow-up; broad repair deferred |
| Hypothesis isolation | Model hypotheses remain candidates and accepted queries exclude them | inference engine/storage/KG adapter | complete | inference tests passed | preserve in Task 4 |
| Versioned data artefacts | Append versions linked to AnalysisRun | migration 003/005, `frontend/lib/data-artifacts.ts` | complete | database test passed | none |
| Single graph writer | Accepted assertions project through canonical Python service | `intelligence/graph/projection.py`, evidence APIs | complete for inspected personal-data paths | graph idempotency/identity tests passed | Task 4 must not add a graph writer |

## Task 2 — router, workflows and settings

| Predecessor requirement | Expected implementation | Actual implementation location | Status | Tests run / result | Remediation required |
|---|---|---|---|---|---|
| TaskDefinition, TaskRoute and engine registry | Canonical validated task/engine definitions and persisted routes | `frontend/lib/execution/registry.ts`, `router.ts`, migration 010 | complete | Task 2 architecture 9 passed; DB extension test passed | none |
| Privacy execution modes | Strict-local fail closed; explicit local-first fallback; controlled-cloud allowlist; audit | canonical router and processing settings | complete for Task 4 boundary | Task 3 route/privacy tests passed | all Task 4 specialist calls must use this router |
| Non-Google isolation | Selected engine cannot silently invoke Google | provider equality and explicit adapter dispatch | complete | static and route tests passed | none |
| ExecutionRecord provenance | Record run, task, engine, provider, source artefacts and outcome | migration 010 and router | complete | database test passed | Task 4 calls must supply run/artifact IDs |
| Local ASR | Parakeet/Whisper adapters with timestamped output | Python execution adapters | partial operationally | health: both unavailable because optional runtimes are absent | non-blocking; Task 4 tolerates missing transcripts |
| Workflow parity | Per-workflow preference and real built-in handlers | workflow registry/settings and concrete callers | partial | registry/static tests pass; no universal dispatcher | non-blocking; Task 4 uses Task Router directly |
| Concurrency/output schema enforcement | Persisted limits and validated task output | route fields and declared schemas | partial | no runtime enforcement test | record as limitation; Task 4 validates its own frozen DTOs at API boundary |
| Media-origin route | Honest camera/screenshot/download/edit/generation classifier | previously misrouted to OCR | regressed → repaired | `test_image_origin_route_is_honest_and_executable` passed | repaired with `deterministic_image_origin`; no presence claim |
| Selective caption/landmark route | Image-capable local route or explicit unavailable state | previously text-only generation default | regressed → repaired | registry/adapter regression passed | repaired with `local_visual`; local Ollama image adapter reports unavailable unless reachable, never falls back externally |
| Secure email credentials/settings | Server encryption and redesigned settings | migration 010, connector/actions/settings | complete for Task 4 | focused tests passed | none |

## Task 3 and 3A — ingestion, temporal and file families

| Predecessor requirement | Expected implementation | Actual implementation location | Status | Tests run / result | Remediation required |
|---|---|---|---|---|---|
| File type truth, archive safety and hashing | Deterministic evidence, bounded archive handling, raw/canonical hash separation | `intelligence/ingestion` inventory/hash/file-type modules | complete | focused storage/inventory/adapters/registry/locator tests passed | none |
| Content/provenance deduplication | Logical events deduplicate while observations remain append-only | events/catalogue plus migrations 012/013 | complete | event/database tests passed | none |
| File-family adapters and exact locators | P0 adapters emit generic units and family locators | `intelligence/ingestion/adapters`, locator resolver | complete at family level | adapter/cross-family/locator tests passed | none for Task 4 |
| Per-format fixture/support claims | Every advertised format mapped to measured fixture/locator coverage | support registry | partial | family tests pass; fixture IDs and maximum sizes are not exhaustively machine-verified per format | non-blocking for Task 4 fixtures; do not broaden support claims |
| Schema registry and declarative parser | Approved immutable specs; unknown fingerprint sampled once | schema/parser modules plus migrations 012/013 | complete | Wave 2 and DB tests passed | none |
| ActivityEvent lake and observation catalogue | Raw events in Parquet; PostgreSQL holds partition/observation catalogues | event/storage modules plus migration 012 | complete | storage, wave and DB tests passed | none |
| Resumability/checkpoints | Deterministic stages resume without full replay | checkpoint store and bulk pipeline | complete through parsing; repaired through temporal stages | restart tests passed; repaired bulk regression 13 passed | none |
| Deterministic features and temporal algorithms | Six-dimensional interests, engagement, routines, episodes, eras and three histories | `intelligence/features`, `intelligence/temporal`, migrations 012/014 | complete algorithmically | focused feature/temporal tests passed | none |
| Production feature/temporal materialisation | Canonical import invokes feature and temporal stages and persists versioned outputs | previously no production caller | missing → repaired | `test_ingestion_materializes_features_and_temporal_outputs_idempotently` passed; bulk regressions 13 passed | migration 016 and `ingestion/materialization.py` added; FEATURE_EXTRACTION and TEMPORAL_AGGREGATION checkpoints now execute |
| Three histories and NOW/AS OF | Separate personal/controller/system histories and valid/system time | temporal models/views/repository, migration 014 | complete | bitemporal PostgreSQL test passed | Task 4 reuses these distinctions |
| Media metadata boundary | EXIF/time/GPS/device/software without presence promotion | media adapter | complete | media/cross-family tests passed | none |
| Image origin specialist support | Image formats permit routed origin classification | previously absent from executable format routes | missing → repaired | media registry regression passed | Task 3 registry now advertises the canonical route |
| Strict local and reduced model calls | Bounded residue only; no whole-file cloud loop | Task 2 router boundary and Task 3 bundles/benchmark | complete | privacy/benchmark tests passed | none |
| No raw events in Neo4j | High-value topology only | graph projection allowlist; bulk has no Neo4j dependency | complete | graph policy tests passed | none |

## Predecessor repairs

1. Migration 016 adds an idempotent, versioned Task 3 materialisation-run catalogue and deterministic feature candidates, linking derived aggregates/states/episodes/eras to their materialisation run.
2. The bulk parser now executes `FEATURE_EXTRACTION` and `TEMPORAL_AGGREGATION` checkpoints through the canonical Task 3 modules.
3. Image-origin classification now uses deterministic Pillow/EXIF/path rules and always returns a candidate with `physical_presence_supported=false`.
4. Selective visual caption/landmark work now has an honest local image-capable adapter. If no local Ollama visual model is reachable it reports unavailable; it never silently uses an external provider.
5. Task 3A image-format routes now include `image.origin_classification`.

Focused repair verification: 2 predecessor-repair tests passed; combined bulk/wave/temporal/repair regression: 13 passed; Python compilation passed.

## Deferred non-blocking predecessor limitations

- Optional ASR runtimes are not installed.
- Task 2 workflow parity is partly declarative and has no universal dispatcher.
- Task-route concurrency and schema declarations are not fully enforced by the generic router.
- Three canonical ontology labels unrelated to Personal Insights are not in the high-value projection allowlist.
- Task 3A per-format fixture metadata is less exhaustive than the family-level adapter tests.

These items do not make Task 4 incorrect, unsafe, untestable or duplicative. They remain disclosed and are not broadened into Task 5 work.

Related plans: [[Task 1- rebuild the evidence and graph foundation]], [[Task 2- Task Execution Router, built-in workflow parity and settings rebuild]], [[Task 3- local-first ingestion and temporal engine - delegated]], [[Task 3A file type support and extraction workflows]], [[Task 4 Personal Insights, temporal extraction, contextual correlations and media intelligence- delegated]].
