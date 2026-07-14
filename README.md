# 1GDPRAGENT

1GDPRAGENT is a local-first system for:

> privacy-rights acquisition + provenance-preserving personal-data analysis + temporal evidence graph + human-controlled AI interpretation

In product terms, it is a local-first personal-data autonomy system that uses privacy access rights and user-authorised connectors to acquire evidence, reconstructs longitudinal behavioural and controller-profile histories, maps identifier linkability and institutional capability, and uses AI as an evidence-constrained interface for exploring a temporal privacy graph.

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

## Task execution and workflows

Processing is routed per concrete task rather than through one global model. Local deterministic, ASR, OCR, Ollama, and approved remote-generation adapters declare capabilities, health, discovery, and invocation behavior. `strict_local`, `local_first`, and `controlled_cloud` policies are enforced before invocation, and `ExecutionRecord` answers which external engine processed which source artefacts under which `AnalysisRun`.

Workflow execution is selected independently for drafting, email transport, inbox monitoring, parsing, ingestion, graph work, transcription, and the other shipped workflows. Built-in SMTP/IMAP operation no longer requires N8N. N8N remains an optional per-workflow adapter.

Email connector secrets require `CREDENTIALS_ENCRYPTION_KEY` in production and are encrypted server-side with authenticated AES-256-GCM. Legacy base64 passwords require re-entry.

## Personal Insights

Open <http://localhost:3001/dashboard/insights> to explore evidence-backed changes in activity, interests, investigations, projects, routines, places and engagement over time. One page-wide control selects a point in time, a period, or a comparison; every module uses that same selection and offers an evidence trace. Exposure is kept distinct from active interest, contextual matches are labelled as correlations rather than causes, and screenshot/downloaded-image content is never treated as proof of physical presence.

The browser uses the Next.js endpoints under `/api/insights`. Direct service entry points are available under <http://localhost:8001/insights>, including `overview`, `interests`, `search`, `ai-conversations`, `places`, `changes`, `context`, and `evidence/{id}`. Period endpoints accept `subject_id`, `mode`, `from`, `to`, `point`, `compareFrom`, `compareTo`, and `granularity` as applicable. Media analysis defaults to `metadata_only`; optional visual work still follows the configured Task Router privacy policy.

Task 4 is accepted. Authenticated verification covered every module and empty state, all three temporal modes, Quarter granularity, stable URL-backed controls, cohesive dark-theme surfaces, and the evidence-inspector interaction. The user's live profile stayed empty and unmodified; a dedicated local `task4-browser-smoke` subject supplied the synthetic temporal state used to open the drawer. That narrow fixture had no source artefacts or exact locators, while database-backed catalogue, trace and locator tests cover the broader evidence path. Exact results and fixture scope are recorded in the Task 4 acceptance audit below.

## Privacy capability and temporal graph

Open <http://localhost:3001/dashboard/graph> for eight evidence-preserving modes: Now, Through Time, Compare, Controller Profile, Capabilities, Linkability, Purpose, and Access. The page never collapses self-declared, observed behavioural, controller-assigned, and system-hypothesis layers into one truth. Observed edges are solid, technically possible edges are dashed, and alleged/unverified edges are dotted.

The model-facing `/query` surface contains exactly 19 typed, profile-scoped tools. Natural-language graph questions first select one of those tools; the validated result is read from PostgreSQL and may be explained only with resolvable Assertion, EvidenceLocator, and SourceArtifact citations. Arbitrary SQL/Cypher and the former keyword graph chat are not available through this surface.

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
- [Task execution and processing architecture](Technical%20Documentation/Task%20Execution%20and%20Processing%20Architecture.md)
- [Workflow architecture and inventory](Technical%20Documentation/Workflow%20Architecture%20and%20Inventory.md)
- [Settings architecture](Technical%20Documentation/Settings%20Architecture.md)
- [Task 2 implementation ledger](Technical%20Documentation/Task%202%20Implementation%20Ledger.md)
- [Task 2 acceptance audit](Technical%20Documentation/Task%202%20Acceptance%20Audit.md)
- [Personal Insights architecture](Technical%20Documentation/Personal%20Insights%20Architecture.md)
- [Task 4 implementation ledger](Technical%20Documentation/Task%204%20Implementation%20Ledger.md)
- [Task 4 acceptance audit](Technical%20Documentation/Task%204%20Acceptance%20Audit.md)
- [Task 6 privacy capability architecture](Technical%20Documentation/Task%206%20Privacy%20Capability%20Architecture.md)
- [Task 6 final acceptance audit](Technical%20Documentation/Task%206%20Final%20Acceptance%20Audit.md)
