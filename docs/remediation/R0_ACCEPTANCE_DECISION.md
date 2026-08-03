# R0 acceptance decision — not accepted

**Decision date:** 2026-07-17  
**Decision owner:** lead agent

R0 is **not accepted** yet. This is an evidence-based decision, not a statement that later remediation features should be implemented in R0.

The final independent re-audits confirm that the browser harness has removed its former false-pass paths, while the static harness is improved but still partial. Neither finding changes this decision.

## Evidence completed

- Repository baseline recorded at `main` / `67e50b85daa923366d3bec80db6582edcc3ba134`.
- Original-plan ledger, stable JSON issue registry, and provisional historical-report corrections are present.
- Disposable migration fixtures ran locally: **4 passed, 1 strict expected failure**. The expected failure captures DB-001 (`requests.updated_at`).
- TypeScript check passed; frontend unit test passed (2 tests); lint passed with 131 existing warnings.
- The browser harness has a CI-only managed stack, deterministic connector/graph doubles, and a fail-closed no-provider chat adapter. It has not yet produced a fresh managed-stack run. Earlier local runs reproduced stale-session and empty-selector failures with trace/video/screenshot artifacts; those historical artifacts are not evidence for the repaired harness.
- A fresh local managed-stack attempt was rerun using the configured Webpack server against a disposable migrated database. This resolves the prior direct-Turbopack-only ontology error: unauthenticated graph requests returned 401 and authenticated test-mode graph requests returned 200. The later browser timeouts are the intentionally captured product regressions, not an ontology blocker.
- The parameterised static-invariant suite has executable synthetic negative controls (**2 passed**). Against the real repository it is intentionally red on four baseline classes: missing Next authority guards, missing Python internal authority, direct providers, and runtime Neo4j DDL. These failures are assigned to R1/R3/R7 and must remain visible.
- Production build passed on the current worktree. Focused migration/CI-contract coverage recorded **9 passed, 1 strict expected failure**, plus the four expected static-baseline failures.
- Four independent audits were commissioned. Their reports are in `docs/remediation/evidence/independent-*.md`.

## Acceptance blockers

1. **Managed browser CI still needs one full workflow execution.** The re-audit repairs removed the false 404 chat pass and made connector/graph services deterministic, but the complete matrix has not been run through this managed path.
2. **The complete Python suite did not finish inside the bounded local execution window.** Collection and focused coverage are not a substitute for a complete result.
3. **The static invariant suite is intentionally red on current defects.** This is valid baseline evidence, but the final R0 report needs a reproducible CI artifact containing those results and browser artifacts.

## Explicitly unproven

- clean CI app bootstrap plus disposable authenticated browser journey;
- live managed-harness artifacts for profile-header, connector selector, graph 401, request chat, and narrow UI;
- complete Python-suite result on the current worktree;
- any claim that a Plan 1--6 requirement is operational.

The next R0 work must repair only this test/fixture/CI evidence infrastructure, then rerun the four independent audits. Do not treat this document as authorisation to implement R1--R8 product repairs.
