# GDPR Agent Remediation Programme

Generated: 17 July 2026

## Use these plans individually

Give each remediation plan to Codex as a separate `/goal`.

Do not give Codex the entire bundle as one goal. Each plan has its own dependency boundary, migrations, shared contracts, implementation scope, test gate and independent audit. Combining them would make it easier to blur completion criteria, edit conflicting files simultaneously and declare the programme complete before the signed-in product journey has been tested.

## Execution order

1. `R0` — establish the truthful baseline and CI.
2. `R1` — repair authentication, authority and profile ownership.
3. `R2` — reconcile the schema and request lifecycle.
4. `R3`, `R4` and `R5`:
   - safest: run sequentially in that order;
   - faster: use separate Git worktrees and the ownership rules in `10_Codex_Execution_Order_and_Subagent_Protocol.md`.
5. Merge and stabilise `R3`–`R5`.
6. `R6` — temporal graph and Personal Insights integration.
7. `R7` — security and production hardening.
8. `R8` — independent final acceptance audit.

## Mandatory method for every plan

### Before implementation

- inspect the repository recursively;
- read the plan completely;
- audit all predecessor plans against their own definitions of done;
- run predecessor tests;
- repair regressions that block the current plan;
- write an implementation ledger and delegation map.

### During implementation

- use bounded subagents with explicit path ownership;
- keep migrations, shared contracts, security-critical integration and final merge decisions under the lead agent;
- preserve existing data and provenance;
- do not add a second architecture beside the canonical one;
- do not claim a provider, connector or service is operational merely because code or a UI placeholder exists.

### Before completion

- audit the plan line by line;
- run static, unit, integration, migration, runtime and authenticated browser tests;
- test a clean installation and a representative upgrade;
- test failure and missing-configuration states;
- delegate the final audit to agents that did not implement the feature;
- document incomplete and environment-dependent items honestly;
- do not claim completion until every definition-of-done item has evidence.

## Generic Codex preamble

Paste this before the plan-specific goal when useful:

```text
Execute the attached remediation plan end to end.

Treat current code and runtime behaviour as stronger evidence than previous completion reports. Before implementation, audit predecessor plans and repair blocking regressions. Delegate bounded implementation tasks, but keep shared contracts, migrations, security-critical integration and the final acceptance decision under the lead agent.

Before claiming completion, re-audit every requirement, run clean-install and upgrade tests, run the production build and authenticated browser journeys, commission an independent audit, repair its findings and update the implementation ledger.
```

## Files

- `01_R0_Truthful_Baseline_and_Acceptance_Reset.md`
- `02_R1_Authentication_Profile_Ownership_and_API_Authority.md`
- `03_R2_Schema_Reconciliation_and_Request_Timing.md`
- `04_R3_Unified_Model_and_Execution_Control_Plane.md`
- `05_R4_Connector_Onboarding_and_Live_Synchronisation.md`
- `06_R5_Responsive_Shell_and_Settings_Redesign.md`
- `07_R6_Temporal_Graph_and_Personal_Insights_Integration.md`
- `08_R7_Security_Operational_Hardening_and_Semantic_Integrity.md`
- `09_R8_Final_Six_Plan_Acceptance_Audit.md`
- `10_Codex_Execution_Order_and_Subagent_Protocol.md`
- `11_Issue_to_Plan_Traceability.md`
