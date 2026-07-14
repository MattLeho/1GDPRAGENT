---
title: Task 6 Implementation Ledger
date: 2026-07-13
tags:
  - gdpr-agent
  - task-6
  - implementation
status: active
---

# Task 6 Implementation Ledger

Shared-file owner: orchestrator. PostgreSQL is authoritative; Neo4j is a derived high-value projection. Model output may explain typed evidence bundles but may not promote epistemic or legal status.

| Wave | Requirement | Owner | Dependency | Canonical contract | Implementation path | Tests / gate | Status | Blocker |
|---:|---|---|---|---|---|---|---|---|
| 0 | Predecessor and Task 5 audit | orchestrator + audit agents | Tasks 1–5/3A | predecessor plans | [[Task 6 Predecessor Audit Ledger]] | baseline suite/static audit | complete with remediation gates | DB suite rerun pending |
| 0 | Canonical Task 6 contracts | orchestrator | evidence/temporal foundation | `privacy/contracts.py` + TS DTOs | migrations 027-028, privacy package | 5 contract tests; migrations applied | complete | none |
| 0 | Explicit graph epistemics | orchestrator | graph projection | `GraphEpistemicState` | projection, graph API, canvas | projection/type checks | complete | legacy property removed on reprojection |
| 1 | Versioned capability taxonomy/rules | delegated leaf after freeze | temporal aggregates/assertions | `CapabilityCandidate` | `privacy/capability.py` | deterministic rule fixtures | complete | none |
| 1 | Identifier statistics and EdgeRisk | delegated leaf after freeze | identifiers/events | `EdgeRisk` | `privacy/linkability.py` | metric reproducibility | complete | exact high-value graph only |
| 1 | Graph metrics/removal simulation | delegated leaf after freeze | graph snapshot | `IdentifierRemovalSimulation` | `privacy/linkability.py` | graph-cut fixtures | complete | exact high-value graph only |
| 2 | Policy SourceArtifact/version ingestion | delegated adapter; orchestrator integration | canonical ingestion/router | `PolicySourceVersion` | privacy policy service/API | 4 provenance/security tests | complete | authorised bytes supplied by caller |
| 2 | Grounded Claim extraction | delegated leaf after freeze | exact locators/router | `Claim` | `privacy/purpose.py`, `/extract/policy-claims` | locator/citation tests | complete | none |
| 2 | Purpose lineage/distance | delegated leaf after freeze | Claims/activities | `PurposeDistanceAssessment` | `privacy/purpose.py` | wording/distance tests | complete | none |
| 2 | Original/current/technical reach | orchestrator integration | purpose ontology | explicit edge types | projection/repository | semantic-separation tests | complete | none |
| 3 | Institutional Access | delegated leaf after freeze | Dataset/Authority | `InstitutionalAccessEdge` | `privacy/access.py` | no-access-from-overlap tests | complete | none |
| 4 | PrivacyHypothesis lifecycle | orchestrator | assertions/requests | `PrivacyHypothesis` | migration/repository/service | lifecycle audit tests | complete | none |
| 4 | Deterministic detectors/templates | delegated leaves | hypothesis contract | detector/template DTOs | `privacy/hypotheses.py` | synthetic detectors/DSAR | complete | none |
| 4 | Existing-request integration | orchestrator | request workflow | hypothesis-request link | API/workflow registry | no-second-request test | complete | none |
| 5 | DeletionSimulation/ExpectedRemoval | delegated calculations; orchestrator integration | Task 5 deletion model | simulation contracts | `privacy/deletion.py` | topology prediction tests | complete | none |
| 5 | Later-export verification | delegated leaf | export snapshots | `DeletionVerification` | `privacy/deletion.py` | uncertainty wording tests | complete | none |
| 6 | Typed PrivacyQueryService | orchestrator contract + delegated tools | all prior waves | allow-listed tools/citations | `privacy/query.py`, API | tool/citation/read-only tests | complete | none |
| 6 | Legacy query retirement | orchestrator | typed query API | no arbitrary Cypher | Python/Next routes | negative security tests | complete | legacy agents retained only for non-Task-6 background compatibility |
| 7 | Temporal/epistemic graph API | orchestrator contract + delegated leaf | projection/query | graph filter DTO | graph API | filter/compare tests | complete | none |
| 7 | Final product graph UI | delegated leaf modules after API freeze | graph DTOs | TS privacy DTOs | graph page/components | build/runtime smoke | complete | none |
| 7 | Evidence inspector/drift/profile layers | delegated leaf modules | evidence/query APIs | evidence trace DTO | UI components | separation/runtime tests | complete | none |
| 8 | Wording guardrails | delegated utility/tests | all presentation paths | guardrail vocabulary | backend/frontend utility | prohibited-language tests | complete | none |
| 8 | Synthetic end-to-end acceptance | delegated fixtures; orchestrator audit | all waves | acceptance pack | tests/fixtures | all required scenarios | complete | none |
| 9 | Final line-by-line audit and docs | orchestrator | all gates | Task 6 plan | final audit/README | full commands/runtime logs | complete | none |

## Frozen invariants

- Capability exposure uses only: `evidenced_from_export`, `documented`, `legally_authorised`, `technically_possible`, `speculative`, `human_confirmed`.
- Graph edges use only: `currently_observed`, `potentially_enabled`, `alleged_unverified`.
- Profile layers remain: `self_declared`, `observed_behaviour`, `controller_profile`, `system_hypotheses`.
- Purpose, LegalBasis, Claim, ProcessingActivity and Capability are distinct.
- Custody, access, legal gateway, sharing, technical linkability and identifier overlap are distinct.
- Hypotheses remain uncertainty objects until source evidence resolves them.
- Export absence can establish only removal from the observed export, never legal deletion.
- Privacy query tools are typed, allow-listed, read-only and citation-bearing.
