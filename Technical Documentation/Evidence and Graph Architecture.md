# Evidence and Graph Architecture

## Product and epistemic boundaries

The system exists to reverse information asymmetry: it helps a person inspect what an organisation appears to process, how a conclusion was observed or derived, what capabilities the data and systems may enable, and how documented purpose or scope changes over time.

It is not a psychological truth engine. Explicit declarations, observed activity, controller-assigned records, deterministic derivations, model suggestions, human confirmations, documented implementation, legal authorisation, technical possibility, and speculation remain distinct. Capability does not imply abuse; a relationship does not establish psychological truth; absence from an export does not prove deletion; and a purpose-drift indicator is not a legal judgement.

## Authority and flow

PostgreSQL is authoritative. Neo4j is a rebuildable projection of accepted assertions, not an independent truth store.

1. `AnalysisRun` records every pipeline execution and version.
2. `ExportSnapshot` records the controller export, DSAR response, Takeout, or manual import occurrence.
3. `ContentBlob` deduplicates immutable bytes by SHA-256.
4. `SourceArtifact` preserves each path/archive occurrence even when bytes are shared.
5. `EvidenceLocator` resolves a typed location against those immutable bytes and records the resolved hash and verification method.
6. `Assertion` records semantic content, epistemic basis, derivation, time, lifecycle state, and source assertions.
7. Only accepted, provenance-valid assertions can enter `GraphProjectionService`.

## Provenance invariants

- JSON Pointer, CSV row/cell, UTF-8 byte span, HTML DOM span, media time range, image region, and archive member locators have strict schemas.
- A verified locator is mechanically resolved; exact quotations additionally require `exact_quote_match`.
- Model hypotheses require exact, structured, or human-verified evidence before acceptance.
- Source-explicit and controller-assigned assertions require verified evidence.
- Deterministic derivations require verified evidence or linked source assertions.
- MAKGED returns a non-mutating interpretation verdict and never returns executable graph-write Cypher.
- Accepted assertion semantics cannot be updated. A changed conclusion is a new assertion that references and supersedes the previous accepted assertion atomically.
- Ledger rows and data artifact versions cannot be deleted through normal database operations.

## Ontology and identity

The canonical machine-readable ontology is `ontology/graph-ontology.json`, consumed by Python and TypeScript adapters.

Every graph node has `:GraphNode {node_id}` with a uniqueness constraint. `node_id` is a deterministic UUID derived from the ontology label and typed canonical key. Legacy nodes are backfilled without merging ambiguous occurrences.

`Subject`, `ControllerProfile`, and `Claim` never share identity. Manual merge operations require an accepted human-confirmed assertion and reject nodes whose ontology labels differ. Identifier keys include type and, where required, controller/service scope; raw value equality cannot merge unrelated identifiers.

ONSIT labels are explicitly listed separately. ONSIT bulk mutations still pass through the intelligence projection service and record a human-confirmed assertion.

## Compatibility

- `received_data.graph_ingested` remains as a display compatibility flag, but versioned `AnalysisRun` records are authoritative.
- Legacy upload routes submit model output to the evidence adapter. They do not mark candidates as graph truth.
- N8N response parsing remains supported. KG, identity, and MAKGED workflow templates now call canonical services and cannot execute graph writes.
- Existing graph reads and UX remain in Next.js, using stable UUIDs. Direct frontend graph writes are rejected.
- `data_artifacts` retains every version and exposes `current_data_artifacts` for the latest view.

## Migration operations

`database/migrate.py` discovers numbered SQL migrations, takes a PostgreSQL advisory lock, validates immutable SHA-256 checksums, and applies each file transactionally. Compose gates n8n, intelligence, and Next.js on successful completion of the one-shot `migrate` service.

The operational migration set is `000`, `000a`, and `001` through `009`. It reconciles legacy request, file, artifact, chat, webhook, and serial-profile variants without destructive startup behavior. The top-level schema files and root migration directory are compatibility references only.
