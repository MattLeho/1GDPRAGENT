# Task 1 Implementation Ledger

| Requirement | Implementation location | Status | Tests | Migration/backfill notes | Blockers |
|---|---|---|---|---|---|
| One migration source of truth | `database/migrate.py`, `database/migrations/`, `docker-compose.yml` | Implemented | disposable DB idempotency and preservation tests | Existing schemas reconciled non-destructively; history/checksums recorded | None |
| Remove destructive/runtime DDL | `02_DATABASE_SCHEMA.sql`, `docker/init/01_schema.sql`, frontend routes/libs | Implemented | runtime-DDL static guard | Old SQL locations explicitly compatibility-only | None |
| AnalysisRun and ExportSnapshot | migration 002, Python/TS models | Implemented | integration fixtures create both | Legacy KG scan uses AnalysisRun instead of mutable flag authority | None |
| ContentBlob and SourceArtifact | migration 002, `evidence/ledger.py` | Implemented | one blob/two artifacts integration test | SHA-256 dedup retains source occurrences | None |
| Typed EvidenceLocator and verifier | migration 002/006, `evidence/locators.py`, `frontend/lib/evidence.ts` | Implemented | JSON/CSV/text/HTML/archive/media/image tests | Exact quote and structured verification methods recorded | None |
| Assertion lifecycle and provenance | migrations 002/005/006, `evidence/ledger.py` | Implemented | missing evidence, immutability, acceptance, supersession tests | Accepted legacy semantic rows are not fabricated | None |
| Grounded extraction exact spans | `grounded_extractor.py` | Implemented | estimated-offset rejection test | Unresolvable quotations remain absent/review candidates | None |
| Canonical separated ontology | `ontology/graph-ontology.json`, Python/TS adapters | Implemented | separation and typed-key tests | Legacy labels are compatibility inputs only | None |
| Stable graph UUIDs | `graph/ontology.py`, `graph/projection.py`, graph APIs | Implemented | live Neo4j idempotency/backfill tests | Ambiguous legacy duplicates receive distinct stable IDs | None |
| Typed entity resolver | `canonical_entity_key`, `/evidence/entity-key` | Implemented | same raw value/different type and scope test | LLM/root-word identity rewriting disabled | None |
| Hypothesis-only inference | inference defaults, extraction storage, KG adapter | Implemented | default-off and projection rejection tests | Existing model outputs become candidates | None |
| Version data artifacts | migration 003/005, `data-artifacts.ts` | Implemented | version retention/latest view/delete rejection tests | Existing artifact rows receive legacy AnalysisRuns | None |
| Consolidated projection path | `GraphProjectionService`, evidence API, Next/N8N adapters | Implemented | projection idempotency and mutation guards | ONSIT handled as explicit separate labels through same service | None |
| Preserve useful application functions | compatibility routes and N8N adapters | Implemented | build/typecheck/lint plus runtime health | DSAR/email/provider/ONSIT/graph UI kept | None |
| Documentation and audit | README, implementation tracker, architecture guide, ledger, acceptance audit | Implemented | line-by-line acceptance audit; final repository/runtime verification | Updated alongside implementation; operational risks recorded separately | None |

## Final verification record

- Canonical migrations: 11 versions applied; a second live run was a successful no-op.
- Automated tests: final rerun `26 passed, 1 warning in 11.46s`.
- Python compilation, TypeScript type checking, full frontend lint, production build, and Compose configuration all passed.
- Full Compose rebuild/start passed. PostgreSQL, Neo4j, Redis, Qdrant, intelligence, Celery, n8n, and Next.js were healthy; migration exited 0.
- Runtime checks returned HTTP 200 for intelligence health, frontend login, Neo4j HTTP, and n8n readiness.
- Graph backfill endpoint ran successfully; the current empty evidence ledger required zero projections.

## Recorded risks, not blockers

- The live local database is empty, so populated legacy upgrade paths are exercised with synthetic disposable PostgreSQL fixtures.
- Previously imported workflow copies in separately deployed n8n instances require operator re-import or disablement.
- Ambiguous legacy Neo4j identities are preserved as separate stable nodes pending deterministic or human-confirmed resolution.
