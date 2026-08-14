# R0 completion hosted evidence — 2026-08-14

**Workflow:** `R0 truthful baseline`
**Run:** [31833659810](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810)
**Job:** [94874981330](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833659810/job/94874981330)
**Audited commit:** `4e7e62448e8fd8e837113279dc668bc3528cadcf`
**Conclusion:** success

## Hosted execution

- Job start: `2026-08-14T19:31:50Z`
- Clean bootstrap completed through Chromium installation: `2026-08-14T19:34:17Z`
- Nine-gate aggregate: `2026-08-14T19:34:17Z` to `2026-08-14T19:38:49Z` (4m32s)
- Artifact upload completed: `2026-08-14T19:38:52Z`
- Job completed after service/post-action cleanup: `2026-08-14T19:39:07Z`

Every bootstrap step passed: service initialization, checkout, Python setup, pnpm setup, Node setup, declared Python dependencies, frozen frontend dependencies and Chromium.

## Downloaded gate manifest

`test-results/r0-gates.json` names the audited commit and records nine complete zero statuses:

| Command | Exit status |
|---|---:|
| `bash scripts/r0-compose-validate.sh` | 0 |
| `bash scripts/r0-migration-fixtures.sh` | 0 |
| `bash scripts/r0-python-suite.sh` | 0 |
| `bash scripts/r0-static-invariants.sh` | 0 |
| `bash scripts/r0-frontend.sh typecheck` | 0 |
| `bash scripts/r0-frontend.sh lint` | 0 |
| `bash scripts/r0-frontend.sh unit` | 0 |
| `bash scripts/r0-frontend.sh build` | 0 |
| `bash scripts/r0-browser.sh` | 0 |

The combined log reports:

- migration fixtures: 11 passed in 18.46s;
- Python: 553 passed, 2 skipped, 8 warnings in 98.87s;
- static/security: 70 passed, 5 warnings in 6.61s;
- lint: 0 errors and 119 warnings;
- frontend unit: 130 passed, 1 skipped;
- production build: pass, 62 routes;
- browser: 8 passed and 4 guarded later tests skipped in 31.9s.

## Uploaded browser evidence

Artifact `r0-baseline-artefacts`:

- artifact ID: `9231834999`;
- size: 68,484,922 bytes;
- digest: `sha256:0a5e5d0011d701a22ea0a5110e0de643efa7de81d6bd10fd2586d4acebb7d073`;
- expiry reported by GitHub: `2026-11-12T19:31:46Z`.

The downloaded artifact was inspected rather than inferred from the workflow badge:

- all eight required R0 journey directories have `trace.zip`;
- all eight have an automatic completion screenshot;
- all eight have named `journey.png`;
- all eight have parseable `console-and-network.json`;
- the HTML report contains 56 files;
- JUnit is present at `test-results/playwright-junit.xml` and is 9,847 bytes;
- the runner combined log and complete JSON manifest are present.

Four R1 browser cases are intentionally guarded/skipped in this R0 execution. Their directories also retain automatic trace/screenshot output, but they are not counted as required R0 journey evidence.

## Diagnostic runs and repairs

- Run [31828846743](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31828846743) was cancelled at the 45-minute job timeout. Its partial manifest exposed one CI-only unit isolation failure and a browser preflight/cleanup hang. The graph test now disables the R0 test double only for the assertion that must exercise Neo4j parameters; browser cleanup has an explicit process-group leader and bounded TERM/KILL path.
- Run [31833009439](https://github.com/MattLeho/1GDPRAGENT/actions/runs/31833009439) finished in 5m48s and proved the first eight gates green. The browser preflight failed because pnpm 11 rejects `scripts.test:browser` as a property path containing `:`. The preflight now reads the script directly from `package.json` through Node, and an executable Linux regression forbids delegating that check to `pnpm pkg get`.
- Run 31833659810 proves both repairs and the complete R0 wrapper on hosted Ubuntu.

## Evidence boundary

This is disposable CI evidence with `R0_TEST_MODE=1`, purpose-distinct sentinel keys, PostgreSQL and Neo4j service containers, and no live provider credentials. The graph/connector/no-provider doubles prove harness authority and wiring, not live provider or service operation. `MODEL-008` and `OPS-001` remain registered later-plan defects.
