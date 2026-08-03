# R0 — Truthful Baseline and Acceptance Reset

## Goal

Replace the existing blanket completion claims with a reproducible baseline showing what is operational, implemented but unintegrated, partial, represented only in tests, missing, broken or deliberately deferred.

This plan establishes the evidence and test infrastructure for every later plan. It should not expand into broad feature implementation.


## Programme rules

- Current code and runtime behaviour outrank previous completion reports.
- Preserve user data, provenance and migration history.
- PostgreSQL remains canonical; Neo4j remains a rebuildable projection.
- Model output cannot silently become graph truth.
- Every model call must use the canonical Task Router and create an execution record.
- Every protected operation must be scoped to the authenticated canonical profile.
- Distinguish unknown, unconfigured, unavailable, blocked and failed.
- Do not introduce hardcoded Google execution, synthetic graph data or invented compliance metrics.
- Implementation agents cannot be the sole final auditors of their own work.


## Dependencies

None.

## Deliverables

1. Requirement ledger for original Plans 1–6.
2. Stable issue registry with IDs, severity, root cause, affected paths and remediation assignment.
3. Clean-install and legacy-upgrade database fixtures.
4. Authenticated Playwright tests reproducing the user-reported failures.
5. CI covering migrations, Python, TypeScript, lint, build and browser tests.
6. Historical acceptance reports marked provisional where current integration evidence contradicts them.

## Lead-agent ownership

The lead agent owns the classification standard, final ledger, shared fixtures, CI contract, acceptance-status changes and prioritisation. Do not delegate the final determination of whether a requirement is operational.

## Subagent delegation

### A — Plan/document auditor

Read original plans, implementation ledgers, acceptance audits, architecture documents, README, workflow inventory and implementation tracker.

For every requirement return:

- exact source;
- claimed status;
- code evidence;
- migration evidence;
- automated-test evidence;
- authenticated-runtime evidence;
- revised status;
- contradiction;
- remediation plan.

No code changes.

### B — Static architecture scanner

Audit for:

- unauthenticated API routes;
- direct model-provider calls;
- active `model_preferences` reads;
- direct Neo4j mutation paths;
- runtime DDL;
- profile queries using `LIMIT 1`;
- personal-data queries without profile scope;
- hardcoded health indicators;
- routes calling Python without internal authority;
- duplicate secret stores and encryption schemes.

Deliver structured findings and candidate regression tests.

### C — Migration baseline

Create disposable fixtures for:

- clean schema;
- pre-Task-1 legacy schema;
- integer-profile legacy schema;
- current schema with representative requests, chat, connector, evidence and graph references.

Run migrations twice. Capture schema diff, migration history, preserved rows and current query failures.

### D — Browser/session baseline

Create Playwright cases for:

- missing cookie;
- valid session;
- expired session;
- malformed cookie;
- valid signature with missing user/profile binding;
- profile save;
- connectors loading;
- graph loading;
- request chat;
- narrow-width settings and Home.

Capture screenshots, network responses and console errors.

### E — CI/test infrastructure

Add explicit commands for:

- frontend unit/component tests;
- Playwright;
- API integration;
- migration fixtures;
- Python suite;
- TypeScript;
- lint;
- production build;
- Docker Compose validation;
- repository invariants.

## Implementation waves

### Wave 0 — Evidence structure

Create:

```text
docs/remediation/
docs/remediation/evidence/
docs/remediation/ledgers/
tests/browser/
tests/integration/
tests/migration_fixtures/
```

Record audited branch and commit SHA.

### Wave 1 — Classification model

Use exactly:

```text
OPERATIONAL
IMPLEMENTED_NOT_INTEGRATED
PARTIAL
UI_ONLY
TEST_ONLY
MISSING
DEFERRED_EXPLICITLY
BROKEN_REGRESSION
ENVIRONMENT_DEPENDENT
```

Each row must include evidence and blocking dependencies.

### Wave 2 — Stable issue registry

Use IDs such as:

```text
AUTH-001
DB-001
MODEL-001
CONN-001
UI-001
GRAPH-001
SEC-001
OPS-001
SEM-001
```

Store the registry as JSON or YAML as well as a readable ledger.

### Wave 3 — Reproduction tests

At minimum reproduce:

- stale session permits shell but protected APIs return `401`;
- profile save does not refresh header;
- connectors selector has no definitions after auth failure;
- graph returns `401`;
- dashboard references missing `updated_at`;
- request chat defaults to Google;
- settings controls overlap at narrow container width;
- “System Online” remains green during failures.

Tests may initially fail. That is valid baseline evidence.

### Wave 4 — Correct historical status

Add a prominent provisional status to unsupported acceptance reports. Do not delete or rewrite historical evidence.

### Wave 5 — CI

CI must run clean install, legacy upgrade, Python, TypeScript, lint, frontend tests, production build, authenticated browser smoke and static architecture invariants.

## Required acceptance tests

- Every migration fixture applies twice.
- Representative data survives.
- Browser tests fail on unhandled console errors in required journeys.
- CI detects a sensitive route lacking the authority guard.
- CI detects direct provider calls outside approved adapters.
- CI detects a Neo4j writer outside the projection service.
- CI stores browser and test artefacts.

## Definition of done

- Every original Plan 1–6 requirement has a revised evidence-backed status.
- Every known issue has a stable ID and assigned remediation plan.
- Clean and legacy fixtures run locally and in CI.
- Playwright reproduces the current failures.
- Unsupported completion reports are marked provisional.
- No broad later-plan feature is smuggled into R0.
- Independent auditors validate a sample of the ledger, migrations, browser tests and invariants.

## Independent audit

Use four agents that did not create the baseline:

- requirements verifier;
- migration verifier;
- browser-test verifier;
- security-invariant verifier.

## Paste-ready `/goal`

```text
Execute R0 — Truthful Baseline and Acceptance Reset.

Audit the repository recursively before changing code. Reclassify every original Plan 1–6 requirement using code, migrations, tests and authenticated runtime as separate evidence. Build the issue registry, clean-install and legacy-upgrade fixtures, Playwright regression suite and CI pipeline. Mark unsupported completion reports provisional without deleting history.

Delegate documentation, static scanning, migration fixtures, browser baselines and CI to bounded subagents. Keep the status model, shared fixtures, final evidence interpretation and acceptance decision under the lead agent.

Do not implement later remediation features beyond the test and audit infrastructure required here. Before completion, run the complete R0 definition of done and commission independent auditors who did not build the ledger.
```
