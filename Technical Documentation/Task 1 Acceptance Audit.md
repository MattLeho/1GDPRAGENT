# Task 1 Acceptance Audit

Audit date: 2026-07-10

Scope: `NEW APP CONTEXT AND PLAN/Task 1- rebuild the evidence and graph foundation.md` only. The finished code was checked against every section of that document after migrations, tests, type checking, linting, production build, and live Compose verification. Task 2 and the 300 GB Takeout pipeline were not started.

## Result

All Task 1 requirements are implemented. No acceptance criterion is knowingly omitted. The graph is now a rebuildable projection of accepted, provenance-valid assertions in PostgreSQL; model output cannot silently become graph truth.

## 1. One migration source of truth — implemented

- `database/migrations/` is the only operational migration directory. It contains ordered migrations `000`, `000a`, and `001` through `009`.
- `database/migrate.py` records immutable SHA-256 checksums in `gdpr_schema_migrations`, takes an advisory lock, and applies each migration transactionally.
- The one-shot Compose `migrate` service gates n8n, intelligence, and Next.js startup on successful completion.
- `02_DATABASE_SCHEMA.sql`, `docker/init/01_schema.sql`, and root `migrations/` are explicitly compatibility/reference artefacts, not startup schema mechanisms.
- Application code contains no route-level or library-level `CREATE TABLE`, `ALTER TABLE`, or `DROP TABLE` operations.
- Existing request, file, artifact, chat, webhook, and serial-ID profile variants are reconciled or backfilled without dropping user data. Historical source tables/IDs remain available for mapping.
- Migrations ran successfully twice in the live environment; the second run was a no-op. The live history contains 11 applied versions.
- Disposable PostgreSQL integration tests prove idempotency and preservation of synthetic legacy request/file rows.

## 2. Canonical evidence ledger — implemented

- `AnalysisRun`, `ExportSnapshot`, `ContentBlob`, `SourceArtifact`, `EvidenceLocator`, `Assertion`, `assertion_evidence`, and `assertion_derivations` exist in PostgreSQL and in typed Python models. TypeScript evidence types mirror the application-facing ledger contract.
- Every minimum field and controlled enum in Task 1 is represented. `AnalysisRun` is authoritative analytical history; `received_data.graph_ingested` is display compatibility only.
- `ContentBlob.sha256` is unique. Identical bytes produce one blob while each export/path remains a distinct `SourceArtifact`.
- Locator types include JSON Pointer, CSV row, CSV cell, UTF-8 byte text span, HTML DOM span, media time range, image region, and archive member. Each has a strict locator shape and a mechanical resolver/verifier against the source bytes.
- Accepted assertion semantic fields are immutable. A changed conclusion is created as a replacement assertion and atomically supersedes the prior assertion.
- Assertion-to-evidence and assertion-to-source-assertion joins are immutable provenance records.

## 3. Provenance invariant — implemented

The seven required rules are enforced in the ledger and extraction adapters:

1. A `model_hypothesis` cannot be accepted without verified exact, structured, or human-verified evidence.
2. A model-estimated offset is not a verified locator.
3. Exact-text evidence is accepted only when the quotation resolves against the immutable original bytes.
4. Missing exact spans remain candidates or are rejected; they are not silently accepted.
5. MAKGED can return an interpretation verdict, but cannot manufacture a locator or return graph-write Cypher.
6. File/company/source metadata is not treated as a locator.
7. Every accepted assertion requires both derivation method and derivation version.

Additional enforcement requires verified evidence for `source_explicit` and `controller_assigned` assertions. A deterministic derivation requires verified evidence or immutable links to source assertions. Database triggers prevent accepted-semantic mutation, destructive ledger deletion, and deletion or mutation of provenance joins.

`GroundedExtractor` and the extraction API reject Gemini/model quotations that cannot be found exactly; model-provided estimated offsets no longer substitute for source evidence.

## 4. Canonical graph ontology — implemented

- `ontology/graph-ontology.json` is the machine-readable ontology. Python and TypeScript adapters load the same definitions rather than maintaining independent undocumented lists.
- All required core types are present: `GraphNode`, `Subject`, `ControllerProfile`, `Organisation`, `Account`, `Identifier`, `DataDomain`, `DataPoint`, `Topic`, `TemporalState`, `ProjectEpisode`, `ProcessingActivity`, `Purpose`, `LegalBasis`, `Capability`, `CapabilityExposureState`, `PolicyInstrument`, `Claim`, `SourceArtifact`, `Dataset`, and `Request`.
- ONSIT labels are listed in an explicitly separate ontology set.
- `Subject`, `ControllerProfile`, and `Claim` have different typed identities. A controller-assigned attribute is projected from `ControllerProfile`, not onto `Subject`; a model hypothesis remains an assertion candidate and is not a subject property.
- The documented epistemic boundaries preserve declared, observed, controller-assigned, deterministic, model-suggested, human-confirmed, implemented, authorised, technically possible, and speculative states as distinct concepts.

## 5. Stable Neo4j node identity — implemented

- Every projected ontology node carries `:GraphNode {node_id}` and Neo4j has a uniqueness constraint for `GraphNode.node_id`.
- New node IDs are stable UUIDs derived from ontology label plus typed canonical key.
- Existing Neo4j nodes are backfilled. Ambiguous legacy duplicates receive distinct stable UUIDs rather than being guessed into one identity.
- Graph read/write APIs and the graph UI use `node_id`; no `id(n)` or numeric-ID conversion remains in application graph APIs.
- Live Neo4j tests prove stable IDs survive projection reloads and legacy backfill reruns.

## 6. Typed canonical entity keys — implemented

- `canonical_entity_key` handles email, phone, opaque identifier with controller/service scope, organisation, account, and the remaining ontology node types deterministically.
- The resolver is exposed through `/evidence/entity-key` and shared with graph projection.
- Raw string equality cannot merge identifiers: the value `"123"` produces different identities by identifier type and scope.
- Lexical similarity and root-word rewriting are disabled for identity establishment. Model equivalence suggestions remain candidates; deterministic or human-confirmed resolution is required before a merge.
- Manual merge rejects different ontology labels and records an accepted human-confirmed assertion before projection.

## 7. Inference is hypothesis generation — implemented

- LLM relationship inference, generic transitive inference, and lexical identity inference default to off.
- Inference output is an `Assertion` candidate with `epistemic_basis=model_hypothesis`, never an ordinary accepted graph edge.
- Candidate derivations link the source assertion IDs used to produce them.
- Confidence alone cannot promote a candidate.
- The KG ingestion compatibility adapter stores candidates through the ledger and does not write Neo4j or mark candidate output as authoritative graph ingestion.
- Hypothesis relationships have an explicit inferred/status marker. Accepted-profile graph queries and the UI exclude them by default; users may deliberately reveal them as a structurally distinct layer.

## 8. Versioned data artifacts — implemented

- `data_artifacts` includes `analysis_run_id`, `artifact_version`, `supersedes_artifact_id`, `derivation_method`, and `derivation_version`.
- Replacement now appends a version under an advisory lock and links it to the previous version. It does not delete and recreate historical rows.
- `current_data_artifacts` selects the latest version while older versions remain queryable.
- Synthetic legacy artifact rows are linked to backfilled legacy `AnalysisRun` records. Database enforcement rejects destructive deletion and mutation of historical versions.

## 9. One graph projection path — implemented

- `intelligence/graph/projection.py` contains the sole Neo4j write service.
- The enforced flow is SourceArtifact → extraction → candidates → provenance validation/review → accepted assertions → `GraphProjectionService` → Neo4j.
- Python KG ingestion creates candidates; Next.js upload routes submit evidence work; n8n KG/identity/MAKGED templates call canonical APIs; none invents a second graph ontology or executes graph writes.
- The generic Next.js Cypher helper rejects mutation statements.
- Manual node, merge, identity, and ONSIT mutations create accepted human-confirmed assertions and then call the projection service. ONSIT removal is a soft retirement, preserving history.
- A repository-wide write-path search found Neo4j mutation statements only in `intelligence/graph/projection.py`.
- Live `/evidence/backfill-graph` execution completed successfully and returned zero updates for the currently empty ledger.

## 10. Useful legacy functionality — preserved

- DSAR/request management, existing request records, email/request workflows, built-in/n8n/hybrid selection, provider credentials, graph visualisation, ONSIT, grounded extraction, and MAKGED remain in place.
- Compatibility routes reconcile legacy request, log, credential, webhook, artifact, and profile schema variants.
- All 15 shipped n8n workflow JSON files parse successfully. Response parsing remains supported; KG, identity, integrity/MAKGED, and query templates are canonical/read-only adapters.
- The current local n8n database has no active legacy graph-writing workflow to disable.
- Startup helpers now advertise the actual default ports: Next.js `3001` and PostgreSQL `15432`.

## 11. Tests and acceptance criteria — passed

All required acceptance tests use synthetic data:

- migration idempotency and preservation of legacy request/file records;
- one content blob with multiple source occurrences;
- valid locators for all required locator families;
- invalid JSON Pointer rejection;
- incorrect exact-text span rejection;
- estimated model offset rejection;
- model acceptance without verified evidence rejection;
- accepted assertion semantic immutability;
- atomic assertion supersession;
- `Subject`/`ControllerProfile` merge rejection;
- typed/scope-aware identity separation despite equal raw values;
- stable Neo4j node identity across reloads;
- legacy graph backfill stability;
- speculative inference excluded by default;
- idempotent graph projection;
- retained artifact history and latest-version view;
- static guards against runtime DDL, destructive artifact replacement, schema drift, and stale ports.

Exact result: `26 passed, 1 warning in 17.96s`. The warning is the existing Pydantic class-based configuration deprecation and is not a test failure.

Additional verification:

- Python compilation: passed.
- TypeScript `tsc --noEmit`: passed.
- Full frontend lint: passed with 0 errors and 139 pre-existing warnings.
- Next.js production build: passed; 48 routes/pages generated.
- `docker compose config --quiet`: passed.
- Full Compose rebuild/start: passed.
- PostgreSQL, Neo4j, Redis, Qdrant, intelligence, Celery, n8n, and Next.js were all healthy; the migration service exited successfully with code 0.
- Intelligence health, frontend login, Neo4j HTTP, and n8n readiness endpoints returned HTTP 200.

## 12. Documentation — implemented

- `README.md` now presents the product as privacy-rights acquisition + provenance-preserving personal-data analysis + temporal evidence graph + human-controlled AI interpretation.
- `IMPLEMENTATION_TRACKER.md` records Task 1 completion and removes the stale migration assessment.
- `Technical Documentation/Evidence and Graph Architecture.md` documents authority, flow, epistemic boundaries, provenance, ontology, identity, compatibility, and migration operations.
- `Technical Documentation/Task 1 Implementation Ledger.md` maps requirements to implementation, tests, migration notes, and blockers.
- This document records the final line-by-line acceptance audit and operational risks.

## Explicitly not implemented

No Task 1 requirement is knowingly unimplemented.

The following work is intentionally outside Task 1 and was not started:

- the 300 GB Takeout ingestion pipeline;
- Task 2 or later capability, temporal-analysis, inference, and UI backlog;
- unrelated lint-warning reduction and unrelated API-route coverage already present in the project backlog.

## Incomplete migration and operational risks

- The current live local PostgreSQL database contains no request, file, or assertion rows. Populated legacy upgrades are therefore proven with disposable PostgreSQL fixtures, including request/file/artifact/chat/webhook and serial-profile variants, rather than with personal production data.
- Workflow JSON in this repository is migrated, and the current local n8n runtime has no active legacy graph writer. Separately deployed n8n instances may contain previously imported copies; operators must re-import the migrated templates or disable those old copies before connecting them to this ledger.
- Legacy Neo4j nodes without sufficient identity context are intentionally assigned distinct stable IDs. They require later deterministic or human-confirmed resolution; the migration does not guess equivalence.
- Legacy compatibility columns and adapters remain where useful. They are non-authoritative and may be removed only after dependent deployments are confirmed migrated.

These are deployment/backfill risks, not missing Task 1 architecture. Unknown, unresolved, and candidate states remain valid outputs; no source evidence or graph truth is fabricated to eliminate them.
