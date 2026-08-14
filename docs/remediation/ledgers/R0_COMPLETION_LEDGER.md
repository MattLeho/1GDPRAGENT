# R0 completion ledger

**Live audit start:** 2026-08-14
**Starting branch / commit:** `main` / `0ae187bff5e313ab528b758efc528ebf636c5088`
**Accepted implementation commit:** `4e7e62448e8fd8e837113279dc668bc3528cadcf`
**Hosted acceptance run:** [31833659810](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810)
**Scope:** R0 evidence, test and CI closure on the post-R2 checkout. R3--R7 product defects remain assigned to their owning plans.

| Finding | Severity | Current evidence | Owner | Change required | Verification | Status |
|---|---|---|---|---|---|---|
| CI installs cached Node/pnpm support before pnpm exists | P0 | pnpm setup precedes cached `setup-node`; clean frozen install passes | R0 | None | CI contract; hosted bootstrap steps 5--8 | HOSTED_VERIFIED |
| CI credential sentinels overlap | P2 | Four purpose-distinct CI-only values | R0 | None | CI contract and hosted workflow | HOSTED_VERIFIED |
| Browser request fixture violates R1 profile ownership | P0 | Setup resolves the registered account's exact `default_profile_id` and inserts the owned request | R0 / R1 regression | None | Hosted authenticated browser gate | HOSTED_VERIFIED |
| Required journeys do not fail on unexpected console errors | P1 | Every R0 journey captures evidence and fails on unexpected `console.error`; only the exact deliberate 401 is scoped | R0 | None | Eight hosted R0 passes and parsed JSON | HOSTED_VERIFIED |
| Session evidence matrix is not explicitly linked into R0 | P1 | R0 unit gate executes the R1 adversarial session suite | R0 | None | Hosted Vitest 130 passed, including 18 session cases | HOSTED_VERIFIED |
| Narrow-layout proof under-asserts selector/options/Home | P2 | Trigger, option and action are visible/enabled/bounded at 390x844; narrow Home overflow/content asserted | R0 evidence / R5 product | None for observed baseline | Hosted browser trace/screenshots | HOSTED_VERIFIED |
| Migration fixture schema stability and representative survival are under-asserted | P1 | Every successful history family compares complete schema objects across both passes; representative minimal/R2/connector/assertion rows survive | R0 | None | Hosted migration fixtures 11/11 | HOSTED_VERIFIED |
| Static gate duplicates weaker authority policy | P1 | Stronger R1 route/internal/sensitive inventories are gate inputs; global middleware and public paths are AST-verified | R0 | None | Hosted static/security 70/70 | HOSTED_VERIFIED |
| Provider scanner omits roots/styles and hides active legacy bypasses | P1 | Reviewed runtime roots plus alias/computed-HTTP controls and exact expected finding manifest | R0 evidence / R3 product | `MODEL-008` remains open in R3 | Hosted architecture/static gate | HOSTED_VERIFIED |
| Neo4j scanner misses variable, annotated, transaction and alias calls | P1 | Structural scanner and adversarial variable/f-string/annotated/derived-transaction/alias fixtures cover declared roots/extensions | R0 evidence / R7 product | None in current active roots | Hosted architecture/static gate | HOSTED_VERIFIED |
| R0 runner has no durable machine-readable gate summary | P1 | Runner continues, writes combined log and complete JSON gate/command/status manifest | R0 | None | Downloaded hosted manifest has nine zero statuses | HOSTED_VERIFIED |
| Registry and acceptance record lag current repairs | P1 | Historical commit retained; current statuses, resolvable evidence and later-plan boundaries reconciled | R0 | None | Fresh requirements audit; registry/document contract | VERIFIED |
| Full suite lacks declared Neo4j and portable Node prerequisites | P0 | Neo4j hosted service declared; tests resolve Node from `PATH` | R0 | None | Hosted Python 553 passed, 2 skipped | HOSTED_VERIFIED |
| Clean pnpm bootstrap rejects lifecycle packages / pnpm 11 runtime | P1 | Explicit decisions for six lifecycle packages; hosted runtime Node 22 | R0 | None | Hosted frozen install passed | HOSTED_VERIFIED |
| Green browser journeys do not retain direct evidence | P1 | Each required journey emits trace, automatic/named screenshots, named console/network JSON and HTML/JUnit entries | R0 | None | Downloaded artifact: 8/8 complete | HOSTED_VERIFIED |
| Hosted substantive gate execution absent | P0 | Final run reaches and passes all nine gates, artifact upload and cleanup | R0 / environment | None | Run 31833659810 | HOSTED_VERIFIED |
| CI global R0 test mode bypasses a graph isolation assertion | P1 | Graph test disables the double only for the parameter-authority assertion and restores the environment afterward | R1 regression exposed by R0 | None | Hosted frontend unit gate 130 passed | HOSTED_VERIFIED |
| Browser preflight/cleanup can hang or reject a valid colon-bearing script | P0 | Script reads `package.json` through Node; server is explicit process-group leader with bounded TERM/KILL cleanup | R0 | None | Linux regression; hosted browser gate and job cleanup passed | HOSTED_VERIFIED |

Status is updated only from executed evidence. Later-plan findings are not closed merely because the R0 detector recognises them.
