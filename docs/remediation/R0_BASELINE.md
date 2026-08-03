# R0 truthful baseline

**Audited branch / commit:** `main` / `67e50b85daa923366d3bec80db6582edcc3ba134`  
**Audit date:** 2026-07-17  
**Scope:** R0 evidence and regression infrastructure only. No R1--R8 product remediation is claimed here.

## Evidence hierarchy and classification

The canonical R0 statuses are exactly: `OPERATIONAL`, `IMPLEMENTED_NOT_INTEGRATED`, `PARTIAL`, `UI_ONLY`, `TEST_ONLY`, `MISSING`, `DEFERRED_EXPLICITLY`, `BROKEN_REGRESSION`, and `ENVIRONMENT_DEPENDENT`.

Code (C), migration (M), automated tests (T), and authenticated runtime/browser evidence (R) are independent classes. A historical acceptance statement is a claim, not evidence. `OPERATIONAL` requires current C, M where relevant, T, and R evidence. A failing signed-in journey takes precedence over a historical acceptance report.

## Evidence index

- Original-plan requirement ledger: [R0_REQUIREMENT_LEDGER.md](ledgers/R0_REQUIREMENT_LEDGER.md).
- Stable registry: [issue-registry.json](issue-registry.json).
- Documentation audit: [subagent-plan-doc-audit.md](evidence/subagent-plan-doc-audit.md).
- Static/security findings: [subagent-static-security-scan.json](evidence/subagent-static-security-scan.json).
- Migration, browser, CI and independent-audit evidence are indexed here as they are produced.

## Initial observed contradictions

- Historic acceptance reports claim completion without a checked-in authenticated browser suite.
- Current user-reported signed-in failures contradict the profile, connector, graph, request-chat and responsive UI claims.
- The static baseline finds broad authority gaps, a legacy Google model-preferences path, direct provider calls, and a hard-coded green health indicator.

These are tracked as R0 evidence; their feature repairs are assigned to the later remediation plans in the registry.
