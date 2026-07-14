---
title: Task 6 Predecessor Audit Ledger
date: 2026-07-13
tags:
  - gdpr-agent
  - task-6
  - audit
status: remediation-in-progress
---

# Task 6 Predecessor Audit Ledger

This ledger records current-code verification performed before Task 6. Historical completion notes were treated as leads, not proof.

## Runtime baseline

- Host suite: **338 passed, 2 skipped**. A further 39 database-backed tests failed at fixture setup only because `DATABASE_URL` was absent from the host process.
- Docker services were independently observed healthy for PostgreSQL, Redis, Neo4j, Qdrant, Intelligence, Celery, Next.js and N8N.
- The complete database-backed suite was started inside the Intelligence container but exceeded the 120-second command window; it is not recorded as passed and must be rerun after Task 6 integration.

## Task 1 — evidence and graph foundation

| Requirement | Current evidence | Status | Task 6 gate |
|---|---|---:|---|
| Immutable evidence ledger | Migrations 002, 005 and 008 enforce assertion/evidence immutability | verified | preserve |
| Exact EvidenceLocators | `intelligence/evidence/models.py` and resolver implementations cover Task 3A families | verified | preserve |
| Assertion lifecycle and accepted truth | Explicit candidate/accepted/rejected/superseded status; projection accepts only accepted assertions | verified | preserve |
| Epistemic basis | Explicit source/controller/deterministic/model/human bases | verified | map to, but do not replace, graph-edge epistemics |
| Subject versus ControllerProfile | Separate labels plus projection guard | verified | preserve through query/UI layers |
| Stable graph node IDs | Canonical UUID derivation and GraphNode constraint | verified | preserve |
| Canonical ontology/projection | JSON ontology and sole `GraphProjectionService` writer | partial | reconcile projection allowlist with ontology |
| Candidate versus accepted graph truth | Projection SQL enforces accepted and provenance-valid assertions | verified | preserve |
| Versioned derived artefacts | Existing materialisation/version tables | verified | reuse |

Defects requiring repair:

1. `GraphProjectionService` stores `r.inferred`, and graph APIs/UI consume `isInferred`. Task 6 requires `currently_observed`, `potentially_enabled`, and `alleged_unverified` as explicit states.
2. Projection omits temporal axes, assertion status, derivation/version and evidence references required for temporal/epistemic graph reads.
3. `Dataset` and `LegalBasis` exist in ontology but not the projection allowlist; `Authority` is absent.

## Task 2 — execution router and workflows

| Requirement | Current evidence | Status | Task 6 gate |
|---|---|---:|---|
| Task Execution Router | `frontend/lib/execution/router.ts` | verified | reuse |
| Engine/workflow registries | central registries and workflow preferences | verified | extend only |
| strict-local/local-first/controlled-cloud | explicit fail-closed routing checks | verified | preserve |
| External processing audit | execution records and blocked outcomes | verified | preserve |
| Encrypted credentials | encrypted credential store | verified | preserve |
| No silent fallback | router rejects unapproved combinations | verified | preserve |
| Existing request workflow | `request.drafting` and transport paths | verified | hypotheses must link here |

Defects requiring repair:

1. The registered grounded-extraction path can call Gemini directly and bypass the Task Execution Router.
2. The legacy Python `/query` endpoint and graph chat remain alternate uncited evidence-answer paths.

## Tasks 3 and 3A — ingestion and temporal engine

Event lake, parser registry, provenance-preserving normalization, resumable checkpoints, temporal states, three histories, NOW/AS OF/compare, export deltas, three drift categories, high-value-only graph projection and model-call reduction are present and reusable.

Defect requiring repair:

- Grounded extraction may persist truncated fallback text behind a `legacy-extracted-text://` URI that later locator resolution cannot reopen. Task 6 policy Claims must use canonical immutable ContentBlob/SourceArtifact bytes and resolvable exact locators.

## Task 4 — Personal Insights

Signal-versus-exposure semantics, AI turn-role separation, contextual non-causal wording, media/location evidence classes, temporal compare, versioned materialisation and evidence tracing are present.

Defect requiring repair:

- The evidence inspector does not yet expose the full Task 6 trace: semantic statement, epistemic/status/confidence, all time axes, derivation, resolved excerpt/record and review history.

## Task 5 — connectors and conservative retention/deletion

Focused current-runtime tests passed **31/31** for connector lifecycle/runtime/bridge, email semantics, retention leaf rules and deletion-safety leaf contracts. Docker services were healthy. The audit nevertheless found integration and authorization gaps that invalidate the historical Task 5 completion claim:

| Requirement | Current result | Status |
|---|---|---:|
| Registry/runtime/bridge and cursor-after-ingestion | Focused runtime tests pass | verified |
| Browser/IMAP/AI/photo/filesystem acquisition | Implemented with permission checks for reads | verified |
| Retention feature/policy leaf rules | Deterministic leaf tests pass | verified |
| Live retention evaluation | No production call path creates decisions from connector records | failed |
| Recurring incremental scheduling | `next_sync_at` is stored but no due-run dispatcher exists | failed |
| Source deletion permission | Capability exists without a separately displayed/enabled destructive permission | failed |
| Destructive authorization | Direct Intelligence routes and Next proxies lack authenticated authority | failed |
| Profile isolation | Overview/mutation paths are not consistently scoped to the authenticated profile | failed |
| Controller-erasure grace | Draft can be created before `eligible_for_delete` | failed |
| Local purge and reversible IMAP move | Safety checks exist | verified |

Task 5 remains the execution foundation for Task 6 deletion work after these repairs. `DeletionSimulation` will remain analytical and will not duplicate `DeletionPlan`, staging, source deletion, local purge or controller erasure.

## Mandatory remediation gates before later Task 6 waves

- [ ] Replace boolean inferred semantics with explicit edge epistemics end to end.
- [ ] Extend the sole graph projection/read contract with temporal, status, derivation and evidence metadata.
- [ ] Reconcile ontology/projection for Dataset, LegalBasis and Authority.
- [ ] Retire keyword/unrestricted evidence-bearing graph chat behind typed read-only tools.
- [ ] Route model-backed grounded extraction through the audited Task Execution Router.
- [ ] Persist policy sources as versioned canonical SourceArtifacts before Claim extraction.
- [ ] Require resolvable exact locators for grounded Claims.
- [ ] Extend evidence inspection with resolved evidence and review history.
- [ ] Add an explicit enabled destructive connector permission before source deletion.
- [ ] Add authenticated, profile-scoped connector and retention API authority.
- [ ] Wire connector-backed records through live retention evaluation.
- [ ] Dispatch due recurring connector runs without duplicate active syncs.
- [ ] Enforce staging/grace before controller-erasure candidate/draft creation.
- [ ] Rerun all predecessor database-backed tests against live services.

## Duplication prohibitions

Task 6 will reuse the existing evidence ledger, graph writer, temporal engine, request workflow, execution router and Task 5 deletion workflow. No second graph, request system, deletion execution model, query router or evidence model is permitted.
