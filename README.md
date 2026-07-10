# 1GDPRAGENT

1GDPRAGENT is a local-first system for:

> privacy-rights acquisition + provenance-preserving personal-data analysis + temporal evidence graph + human-controlled AI interpretation

It helps a person request data from organisations, preserve the returned source material, inspect what a controller appears to record or infer, and explore evidence-backed relationships without treating model output as psychological truth.

## Trusted evidence architecture

PostgreSQL is the canonical evidence ledger. Immutable content bytes, source occurrences, mechanically resolvable locators, versioned analysis runs, and lifecycle-controlled assertions are recorded before accepted conclusions can be projected to Neo4j.

```text
SourceArtifact
  -> extraction
  -> Assertion candidates
  -> locator/provenance verification
  -> deterministic, MAKGED, or human review
  -> accepted Assertions
  -> GraphProjectionService
  -> Neo4j
```

Model suggestions remain `candidate` assertions with `epistemic_basis=model_hypothesis`. Confidence does not promote them. MAKGED can assess an interpretation, but it cannot create missing evidence. The graph UI hides hypothesis relationships by default and uses stable UUID `node_id` values rather than Neo4j internal IDs.

The ontology keeps these layers distinct:

- the person (`Subject`);
- a controller's representation of the person (`ControllerProfile`);
- observed activity and controller-assigned attributes;
- deterministic derivations;
- model hypotheses and human-confirmed claims;
- ONSIT public-source findings, which use an explicitly separate label set.

## Services

- Next.js UI: <http://localhost:3001>
- Intelligence and canonical graph projection API: <http://localhost:8001>
- PostgreSQL: `localhost:15432`
- Neo4j Browser: <http://localhost:7474>
- n8n (optional workflow backend): <http://localhost:5678>
- Qdrant: <http://localhost:6333>
- Redis: `localhost:6379`

DSAR/request management, email workflows, built-in/N8N/hybrid selection, provider credentials, ONSIT, grounded extraction, MAKGED, and the existing graph experience remain available. N8N graph templates are compatibility adapters: they submit to the canonical evidence service and do not generate or execute graph-write Cypher.

## Start and migrate

1. Copy `.env.example` to an untracked `.env` and set the required local secrets.
2. Run `docker compose up -d` (or `start-app.bat` / `start-app.sh`).
3. Open <http://localhost:3001>.

The one-shot `migrate` service must complete before application services start. It applies the ordered, checksum-protected migrations in `database/migrations/` and records them in `gdpr_schema_migrations`. To run migrations explicitly, use `docker compose run --rm migrate` or the `init-db` helper. Normal startup never drops request or evidence data.

`02_DATABASE_SCHEMA.sql`, `docker/init/01_schema.sql`, root `migrations/`, and `App_Context_and_Plan_ORIGINAL/` are compatibility or historical references, not operational architecture.

## Verification

Task 1 is verified with disposable PostgreSQL migration tests, real Neo4j projection/backfill tests, locator and assertion invariant tests, TypeScript checking, linting, a production build, and live Compose health checks. See:

- [Evidence and graph architecture](Technical%20Documentation/Evidence%20and%20Graph%20Architecture.md)
- [Task 1 implementation ledger](Technical%20Documentation/Task%201%20Implementation%20Ledger.md)
- [Task 1 acceptance audit](Technical%20Documentation/Task%201%20Acceptance%20Audit.md)
