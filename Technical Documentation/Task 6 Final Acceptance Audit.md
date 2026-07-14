---
title: Task 6 Final Acceptance Audit
date: 2026-07-13
tags: [gdpr-agent, task-6, acceptance]
status: accepted
---

# Task 6 Final Acceptance Audit

## Delegation map

The orchestrator owned contracts, migrations, integration, query/API security, UI freeze, and final audit. Delegated audits covered Task 5 readiness, cross-plan invariants, and Task 6 inventory. Bounded implementation leaves covered deletion authority, scheduler, retention evaluation, auth checks, linkability, policy-source preservation, purpose, and access; stalled leaves were interrupted and completed centrally.

## Accepted product areas

1. Capability architecture: fourteen versioned deterministic rules and six non-collapsed exposure states.
2. Linkability engine: reproducible snapshot hash, vector risk, centrality/articulation/context metrics, and exact identifier removal simulation.
3. Purpose/policy lineage: canonical policy bytes, exact locators, grounded Claims, separate purpose/legal-basis/technical-reach semantics, and non-legal distance wording.
4. Institutional access: custody, linkability, access, sharing, and legal gateway separation.
5. PrivacyHypothesis and active DSAR: deterministic gaps, targeted questions, existing-request integration, evidence-only resolution, audited transitions.
6. Deletion: expected graph effects and observation-limited verification.
7. PrivacyQueryService: exactly 19 typed tools, profile scope, citation validator, audit hashes, and constrained model tool selection/explanation.
8. Graph API: all ten filters, as-of/compare semantics, explicit profile layers, and profile-scoped projected edges.
9. Final UI: eight modes, time/compare controls, solid/dashed/dotted epistemics, three drift panels, four-layer comparison, cited query output, and evidence inspection.
10. Wording: shared Python/TypeScript guardrails reject unsupported certainty, illegality, abuse, and deletion-survival claims.

## Verification evidence

- Task 6 wording/acceptance/deletion/hypothesis focus: 29 passed.
- Task 6 frontend/query architecture focus: 22 passed across the latest focused runs.
- Broad non-database suite: 361 passed, 2 skipped. Celery is absent from the bundled host Python, so the application-container scheduler suite was run separately and passed 5/5.
- Database-backed set: 95 passed in the host dependency runtime. Three host Neo4j hostname failures were rerun in the Compose network, where the complete Task 1 integration file passed 8/8. The container-only Node path mismatches were covered by the host run.
- Final production `next build --webpack`: compiled, TypeScript checked, and generated 61/61 pages after the constrained natural-language tool selector was added.
- Live typed query: authenticated call 200; unauthorised call 401.
- Live grounded extraction health: Task-Router-candidates-only, direct model execution false, canonical source and exact locator required.
- Browser smoke: `/dashboard/graph` redirected an unauthenticated session to `/login`; no console warnings/errors.

## Acceptance scenarios

Synthetic tests cover stable identifiers across services, location and identity-resolution capability candidates, documented versus technically possible exposure, controller versus behavioural separation, purpose distance wording, overlap without access, evidenced legal gateway, open and divergent hypothesis outcomes, targeted questions, deletion simulation, later presence, later export absence without legal-deletion claims, layer separation, time/compare contracts, and mandatory citations.

## Incomplete requirements

None in Task 6. Live signed-in graph content was not mutated to manufacture a browser fixture; authenticated behaviour is covered by route/runtime tests, static contract tests, production build, and the protected-route browser smoke.
