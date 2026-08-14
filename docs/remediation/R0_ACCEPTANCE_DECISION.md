# R0 acceptance decision — accepted on evidenced environments

**Decision date:** 2026-08-14
**Decision owner:** lead agent
**Audited implementation commit:** `4e7e62448e8fd8e837113279dc668bc3528cadcf`
**Hosted acceptance run:** [R0 truthful baseline / 31833659810](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810)
**Hosted job:** [r0-baseline / 94874981330](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810/job/94874981330)

## Decision

R0 accepted as truthful baseline/test/CI infrastructure on the environments evidenced below. Later-plan product defects remain open and are not represented as fixed.

This decision accepts reproducible R0 evidence infrastructure. It does not claim production readiness, live provider/connector/Neo4j operation, or completion of R3--R8.

## Definition-of-done matrix

| R0 requirement | Evidence | Verdict |
|---|---|---|
| pnpm/setup-node hosted bootstrap defect fixed and order-regression protected | Hosted setup steps 5--8 passed; `test_r0_ci_contract.py` verifies pnpm precedes cached Node setup and clean frozen install | Proven |
| Browser fixture obeys R1 profile-owned request schema | Global setup resolves the registered user's exact `default_profile_id`; hosted authenticated browser gate passed | Proven |
| Missing, valid, expired, malformed, and deleted-binding sessions are evidenced | R0 unit gate executes the R1 adversarial session suite; hosted frontend gate reported 130 passed, 1 skipped | Proven |
| Unexpected browser console errors fail required journeys | Eight hosted R0 journeys passed with per-journey console/network JSON; only the exact deliberate 401 resource message is scoped | Proven |
| Narrow Home and Settings controls are usable at 390x844 | Hosted narrow-layout journey passed and retained trace plus screenshots | Proven for the tested R0 controls |
| Migration audit residue is closed without weakening R1/R2 | Eleven disposable migration fixtures passed; every successful history family compares complete schema objects over two passes and preserves representative rows | Proven |
| Strong R1 authority inventory is part of R0 static evidence | Hosted static/security gate reported 70 passed; exact global middleware/public paths and R1 internal-authority suites are included | Proven |
| Provider and Neo4j scanners fail on omitted roots/styles | Adversarial alias/computed-URL, annotated-variable, derived-transaction, extension and runtime-root controls passed; expected finding registry linkage passed | Proven |
| Later-plan findings remain visible | `MODEL-008` remains an exact expected R3 provider finding; `OPS-001` remains a strict expected R5/R7 browser failure | Proven |
| Runner continues, records, and uploads every gate | Downloaded `r0-gates.json` contains the audited SHA and nine zero statuses; combined log and browser artifacts were uploaded | Proven |
| Full R0 gate executes on current code | Hosted aggregate completed successfully in 4m32s; job completed successfully in 7m17s | Proven |
| R1/R2 regressions found during closure are repaired | Full hosted Python, migration, frontend and browser gates passed; Linux-only unit isolation defect was reproduced and repaired | Proven |
| Four bounded independent re-audits completed | Fresh requirements, migration, browser/CI and static/security audit reports exist; every valid R0 finding was repaired and retested | Proven |
| Current registry, ledger and acceptance record match evidence | `issue-registry.json`, `R0_COMPLETION_LEDGER.md`, this decision and hosted evidence are reconciled to run 31833659810 | Proven |

## Hosted gate results

The uploaded manifest is bound to `4e7e62448e8fd8e837113279dc668bc3528cadcf` and contains all nine required gates:

| Gate | Result |
|---|---|
| Compose configuration | 0 / pass |
| Migration fixtures | 0 / 11 passed |
| Complete Python suite | 0 / 553 passed, 2 skipped, 8 warnings |
| Static/security suite | 0 / 70 passed, 5 warnings |
| Frontend typecheck | 0 / pass |
| Frontend lint | 0 / 0 errors, 119 warnings |
| Frontend unit/component | 0 / 130 passed, 1 skipped |
| Frontend production build | 0 / pass, 62 routes generated |
| Authenticated browser | 0 / 8 required R0 journeys passed, 4 later guarded journeys skipped |

The 68,484,922-byte uploaded artifact has digest `sha256:0a5e5d0011d701a22ea0a5110e0de643efa7de81d6bd10fd2586d4acebb7d073`. Each of the eight required R0 journey directories contains a trace, automatic screenshot, named `journey.png`, and parseable `console-and-network.json`. The upload also contains the 56-file HTML report and 9,847-byte JUnit report.

## Local gate results

The final staggered local verification recorded:

- migration fixtures: 11 passed;
- complete Python suite: 553 passed, 1 skipped;
- static/security: 70 passed;
- frontend: typecheck passed, lint 0 errors, 130 passed and 1 skipped, production build passed;
- production browser: eight R0 suite passes, with `OPS-001` retained as a strict expected failure and four guarded later tests skipped;
- eight complete R0 browser evidence directories;
- clean Node 22 / pnpm 11.9 frozen install in a disposable container;
- executable Linux runner continuation statuses `[1,0]` with a parseable manifest.

Exact local commands, timings, prerequisites, browser facts and CPU staggering evidence are retained in `docs/remediation/evidence/r0-completion-local-evidence-2026-08-14.md`.

## Hosted diagnostic history

Two hosted runs were intentionally not hidden from the record:

1. [31828846743](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31828846743) reached the substantive wrapper but timed out. Its uploaded partial manifest exposed a CI-only graph-test isolation failure and a browser preflight/cleanup hang. Both were repaired with regressions.
2. [31833009439](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833009439) completed in under six minutes. Its manifest proved the first eight gates green and isolated pnpm 11's rejection of the colon-bearing property path used by the browser preflight. The preflight now reads `package.json` directly through Node and has a Linux executable regression.
3. [31833659810](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810) is the acceptance run: all nine gates, artifact upload and post-job cleanup passed.

## Historical R0 findings repaired

- `R0-REQ-001`: granular requirement coverage and current post-R1/R2 dispositions are reconciled without rewriting the historical audit commit.
- `R0-BROWSER-001` and `R0-BROWSER-002`: authoritative profile-owned fixture, valid authenticated chat surface, hermetic graph/connector/provider behaviour, fail-closed console handling and retained green-journey evidence are hosted-verified.
- `R0-STATIC-001`: the stronger authority, provider, Neo4j and runtime-root controls are hosted-verified.
- `R0-MIG-AUDIT-001` and `R0-MIG-AUDIT-002`: full schema-object stability and representative connector/assertion/request preservation are hosted-verified.
- `R0-CI-001`: clean bootstrap, complete durable wrapper, Linux cleanup, manifest and artifact upload are hosted-verified.

## Independent audit verdicts

- Requirements/registry: stale classifications, later-plan scope drift, status drift and unresolved evidence labels were repaired.
- Migration fixtures: the overclaim, incomplete schema signature and weak partial-history preservation were repaired; 11 fixtures passed locally and hosted.
- Browser/CI: runner continuation, clean bootstrap, green evidence retention, credential-alias hermeticity and narrow Home coverage were repaired; the final hosted browser/CI run passed.
- Static/security: provider, Neo4j, authority-evidence, runtime-root and registry-linkage false negatives were repaired; 70 checks passed locally and hosted.

The detailed reports are `docs/remediation/evidence/fresh-r0-*-audit-2026-08-14.md`.

## Explicit later-plan and environment boundaries

- `MODEL-008` remains open for R3: `intelligence/llm/gemini.py` directly calls Gemini outside the approved frontend adapter.
- `OPS-001` remains open for R5/R7: the UI still renders literal `System Online`; the browser suite records it as a strict expected failure.
- Other R3--R7 issues remain in `docs/remediation/issue-registry.json`; R0 acceptance does not change their ownership or status.
- R0 browser mode deliberately rejects provider credentials and uses deterministic graph, graph-stats, connector and no-provider doubles. These prove authority and wiring only, not live services.
- Hosted evidence uses disposable PostgreSQL and Neo4j services and CI sentinel keys. Local evidence uses isolated Docker services and disposable `r0_*` databases.
- No production deployment, external provider call, live connector, live intelligence service, production data migration, scale target or R8 production-readiness decision is evidenced here.
