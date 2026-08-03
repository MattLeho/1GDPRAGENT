# R8 — Final Six-Plan Acceptance Audit

## Goal

Independently re-audit original Plans 1–6 and remediation Plans R0–R7 against the merged repository, clean installation, upgraded installation, restored installation and authenticated runtime.

This is an acceptance plan, not another broad implementation plan.


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

- R0–R7 merged into the candidate release branch.
- No required failing test is hidden or quarantined.

## Independence

Primary auditors must not be the agents that implemented the subsystem.

Material defects:

1. receive a stable ID;
2. are assigned to a separate remediation agent;
3. are fixed;
4. are re-audited by the original independent auditor.

## Lead-auditor ownership

The lead auditor owns the evidence standard, environments, acceptance matrix, release-blocking judgement, contradictions, known limitations and final plan statuses.

## Audit delegation

### 1 — Evidence/graph foundation

Original Plan 1 and projection invariants.

### 2 — Task router/models/workflows

Original Plan 2 and R3.

### 3 — Ingestion/file support

Plan 3/3A and current worker runtime.

### 4 — Personal Insights

Plan 4 and R6 integration.

### 5 — Connectors/retention

Plan 5 and R4.

### 6 — Capability/purpose/access/graph UI

Plan 6 and temporal graph.

### 7 — Authentication/request schema

R1 and R2.

### 8 — Responsive/accessibility

R5.

### 9 — Security/operations

R7.

### 10 — Clean-room release

Clean install, upgrades, production build and backup restore.

## Evidence standard

Acceptance may require:

```text
code
migration/schema
automated test
runtime evidence
authenticated browser evidence
documentation
```

Interactive requirements require interaction evidence. Source-string tests alone are insufficient.

## Required environments

### A — Clean

Empty volumes, generated secrets, migrations twice, production build and first account setup.

### B — Legacy upgrade

Representative profiles, requests, chat, uploads, workflows, model preferences, connectors, evidence and graph references.

### C — Representative temporal data

Synthetic or sanitised requests, connectors, assertions, temporal events and Insights.

### D — Restored

New volumes restored from R7 backup.

### E — Failure injection

Expired session, PostgreSQL/Neo4j/Redis/intelligence outages, missing model, provider rate limit, revoked OAuth, failed Celery, corrupted import, Qdrant unavailable and n8n disabled.

## Mandatory end-to-end scenarios

1. Profile username/email/avatar save and header update.
2. Expired session redirects before protected rendering.
3. Clean/upgraded Home has no SQL errors.
4. Ollama-only chat and policy analysis make zero Google calls.
5. Primary failure uses explicit fallback provider/model.
6. Missing ASR explains setup/private alternative.
7. Browser extension pairing, backfill and incremental sync.
8. Gmail least-privilege OAuth and incremental sync.
9. Outlook OAuth and delta sync.
10. Large mixed import stops/restarts/resumes without duplicate canonical records.
11. Personal Insights returns only active profile data.
12. Graph connects through app credentials without Neo4j browser login.
13. Point, period, compare and playback with evidence inspection.
14. Full responsive/zoom/theme matrix.
15. Every sensitive API rejects unauthorised/cross-profile access.
16. Policy SSRF attempts are blocked.
17. Clean-volume backup restore recovers requests/evidence/connectors/analytics.
18. No fabricated compliance, causation or deletion certainty.
19. UI distinguishes unconfigured, authentication-required, unavailable and failed.
20. Every model execution and evidence-bearing graph/Insight claim is traceable.

## Per-plan report

For every original/remediation plan:

```text
accepted
partial
failed
environment-dependent
deferred
regressions
evidence
follow-up
release-blocking status
```

## Release blockers

- unauthorised data access;
- cross-profile leakage;
- migration data loss;
- hidden provider route;
- SSRF;
- destructive action without review;
- unsupported evidence claim;
- broken clean install;
- failed restore;
- required browser scenario failure.

## Outputs

```text
docs/remediation/FINAL_ACCEPTANCE_REPORT.md
docs/remediation/FINAL_KNOWN_LIMITATIONS.md
docs/remediation/FINAL_TEST_MATRIX.md
docs/remediation/RELEASE_RUNBOOK.md
docs/remediation/evidence/<run-id>/
```

Update README/tracker only after acceptance.

## Definition of done

- Every original Plan 1–6 and R0–R7 requirement is independently classified.
- All mandatory scenarios pass.
- Clean, upgrade and restore environments pass.
- No release-blocking security/provenance defect remains.
- CI reproduces acceptance.
- Limitations are explicit and non-misleading.
- Final report distinguishes implemented, operational, partial and deferred.
- No auditor self-accepts its prior work without independent evidence.

## Paste-ready `/goal`

```text
Execute R8 — Final Six-Plan Acceptance Audit.

Do not assume any plan is complete. Audit original Plans 1–6 and R0–R7 against current code, migrations, CI, clean install, legacy upgrade, backup restore and authenticated browser runtime. Use independent domain auditors who did not implement the subsystem.

Run all mandatory end-to-end scenarios, failure injections, security gates, provider-isolation, temporal graph, responsive and evidence-trace tests. Record stable defects, assign material fixes to separate agents and re-audit them.

Do not treat source-string tests as proof of interactive behaviour. Do not update completion status until the final evidence matrix, limitations and release runbook exist. Release remains blocked by unauthorised access, data loss, hidden provider routes, SSRF, unsupported evidence claims, broken clean install or failed restore.
```
