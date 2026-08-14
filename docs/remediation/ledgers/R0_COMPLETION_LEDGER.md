# R0 completion ledger

**Live audit start:** 2026-08-14
**Starting branch / commit:** `main` / `0ae187bff5e313ab528b758efc528ebf636c5088`
**Scope:** R0 evidence, test and CI closure on the post-R2 checkout. R3--R7 product defects remain assigned to their owning plans.

| Finding | Severity | Current evidence | Owner | Change required | Verification | Status |
|---|---|---|---|---|---|---|
| CI installs cached Node/pnpm support before pnpm exists | P0 | pnpm setup now precedes cached `setup-node`; order regression passes | R0 | Prove the corrected order on GitHub-hosted Ubuntu | `test_r0_ci_contract.py`; hosted run | AWAITING_HOSTED |
| CI credential sentinels overlap | P2 | four purpose-distinct CI-only values; contract passes | R0 | None locally | CI/architecture contract 18 passed | LOCALLY_VERIFIED |
| Browser request fixture violates R1 profile ownership | P0 | setup resolves the registered account's exact `default_profile_id` and inserts the request with it | R0 / R1 regression | None locally | production Playwright 8 suite passes | LOCALLY_VERIFIED |
| Required journeys do not fail on unexpected console errors | P1 | every R0 journey captures evidence and fails on unexpected `console.error`; exact deliberate 401 only is scoped | R0 | None locally | production Playwright 8 suite passes | LOCALLY_VERIFIED |
| Session evidence matrix is not explicitly linked into R0 | P1 | R0 unit gate explicitly executes the R1 adversarial session suite | R0 | None | Vitest 130 passed, including 18 session cases | LOCALLY_VERIFIED |
| Narrow-layout proof under-asserts selector/options/Home | P2 | trigger, option and action are visible/enabled and bounded at 390x844; narrow Home content/overflow also asserted | R0 evidence / R5 product | None for observed baseline | production Playwright 8 suite passes | LOCALLY_VERIFIED |
| Migration fixture schema stability and representative survival are under-asserted | P1 | every successful history family compares complete schema objects across both passes; representative minimal/R2/connector/assertion rows survive | R0 | None | migration fixtures 11/11 | LOCALLY_VERIFIED |
| Static gate duplicates weaker authority policy | P1 | stronger R1 route/internal/sensitive inventories are explicit R0 gate inputs; global middleware and public paths are AST-verified | R0 | None | static/security 70/70 | LOCALLY_VERIFIED |
| Provider scanner omits roots/styles and hides active legacy bypasses | P1 | reviewed runtime-root policy plus alias/HTTP controls and exact expected finding manifest | R0 evidence / R3 product | `MODEL-008` remains open in R3 | architecture suite and static gate green | LOCALLY_VERIFIED |
| Neo4j scanner misses variable, annotated, transaction and alias calls | P1 | structural scanner and variable/f-string/annotated/derived-transaction/alias fixtures are executed across declared roots/extensions | R0 evidence / R7 product | None in current active roots | architecture suite and static gate green | LOCALLY_VERIFIED |
| R0 runner has no durable machine-readable gate summary | P1 | runner writes combined log and JSON gate/command/status manifest while continuing all gates | R0 | Prove exact complete wrapper on hosted Linux | Linux `[1,0]` continuation regression | AWAITING_HOSTED |
| Registry and acceptance record lag current repairs | P1 | historical commit retained; post-R1/R2 statuses, stable findings, resolvable evidence and later-plan defects reconciled | R0 | Final hosted SHA and acceptance decision | JSON parse; fresh requirements audit | LOCALLY_VERIFIED |
| Full suite lacks declared Neo4j and portable Node prerequisites | P0 | Neo4j hosted service declared; tests resolve Node from `PATH`; clean disposable environment passed focused and full runs | R0 | Prove GitHub service health | Python 553 passed, 1 skipped | LOCALLY_VERIFIED |
| Clean pnpm bootstrap rejects lifecycle packages / pnpm 11 runtime | P1 | explicit allow/deny policy for six lifecycle packages; hosted runtime aligned to Node 22 | R0 | Prove hosted frozen install | disposable clean install passed with 1,054 packages | AWAITING_HOSTED |
| Green browser journeys do not retain direct evidence | P1 | each required journey emits trace, automatic and named screenshots, named console/network JSON and HTML/JUnit entries | R0 | Confirm hosted upload contents | 8/8 local artifact directories complete | AWAITING_HOSTED |
| Hosted substantive gate execution absent | P0 | prior cited run stopped in tool bootstrap | R0 / environment | Push one coherent closure and inspect the workflow on that SHA | GitHub Actions evidence | OPEN |

Status is updated only from executed evidence. Later-plan findings are not closed merely because the R0 detector recognises them.
