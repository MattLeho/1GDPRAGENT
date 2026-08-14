# `/goal` — Finish R0 Truthful Baseline on Current Main, Then Stop Before R3

Work in repository:

```text
C:\Users\Jean-Marc\Documents\GDPR Agent\1GDPRAGENT
```

Repository upstream: `MattLeho/1GDPRAGENT`.

Current expected main when this goal was written:

```text
264433a0ba36892af3d3484c54f9e92c9665dcce  R2 Done
```

## Objective

Finish **R0 — Truthful Baseline and Acceptance Reset** end to end on the current post-R2 repository, using the smallest coherent set of changes required to make R0's evidence/test/CI infrastructure genuinely reproducible and independently acceptable.

This is a **focused R0 closure goal**. Do not start R3 implementation and do not pull R3–R7 product fixes into R0 merely to make tests green.

Current code/runtime evidence outranks old completion reports.

R1 and R2 have already been implemented and independently accepted in their ledgers. Preserve them. Treat any regression of R1/R2 as a blocker and repair it, but do not redesign their architecture.

## Read first — no broad rediscovery unless a finding contradicts current code

Read these files before editing:

```text
NEW APP CONTEXT AND PLAN/post plan audit/00_READ_ME_FIRST.md
NEW APP CONTEXT AND PLAN/post plan audit/01_R0_Truthful_Baseline_and_Acceptance_Reset.md
NEW APP CONTEXT AND PLAN/post plan audit/10_Codex_Execution_Order_and_Subagent_Protocol.md

docs/remediation/R0_BASELINE.md
docs/remediation/R0_ACCEPTANCE_DECISION.md
docs/remediation/issue-registry.json
docs/remediation/ledgers/R0_REQUIREMENT_LEDGER.md
docs/remediation/ledgers/R1_IMPLEMENTATION_LEDGER.md
docs/remediation/ledgers/R1_ROUTE_AUTHORITY_INVENTORY.md
docs/remediation/ledgers/R2_IMPLEMENTATION_LEDGER.md

docs/remediation/evidence/independent-requirements-audit.md
docs/remediation/evidence/independent-migration-audit.md
docs/remediation/evidence/independent-browser-final-reaudit.md
docs/remediation/evidence/independent-security-final-reaudit.md

.github/workflows/r0-baseline.yml
scripts/r0-run-all.sh
scripts/r0-migration-fixtures.sh
scripts/r0-python-suite.sh
scripts/r0-static-invariants.sh
scripts/r0-frontend.sh
scripts/r0-browser.sh

tests/integration/test_r0_ci_contract.py
tests/integration/test_r0_architecture_invariants.py
tests/migration_fixtures/test_r0_migration_baseline.py
tests/browser/r0-global-setup.ts
tests/browser/r0-authenticated-baseline.spec.ts
frontend/playwright.config.ts
frontend/tests/r1-route-authority.test.ts
tests/integration/r1_route_coverage_test.py
tests/integration/r1_internal_authority_security_test.py

database/migrations/030_r1_profile_ownership.sql
```

Create a short R0 completion ledger before edits:

```text
finding
severity
current evidence
owner (R0 / R1-R2 regression / later plan)
change required
verification
status
```

Do not spend tokens recreating the entire July audit. Use the existing independent reports plus current source, then verify the concrete findings below.

# Mandatory Wave 1 — repair the hosted CI bootstrap first

The latest GitHub Actions run for `R2 Done` is:

```text
workflow: R0 truthful baseline
run:      31718418746
job:      94508950115
```

It failed before any R0 gate executed. The hosted error was:

```text
Unable to locate executable file: pnpm.
```

Root cause in `.github/workflows/r0-baseline.yml`:

```yaml
actions/setup-node@v4
  cache: pnpm
```

runs **before**:

```yaml
pnpm/action-setup@v4
```

### Required fix

Install/configure pnpm before `actions/setup-node` attempts pnpm cache discovery. Preserve Node `20` for this focused fix unless actual repository compatibility tests require a different project runtime. Do not waste this goal on the separate GitHub Actions Node-runtime deprecation warning.

### Required regression test

Extend `tests/integration/test_r0_ci_contract.py` so it proves the workflow ordering, not merely the presence of both actions. This exact invalid ordering must fail the contract test.

Also use distinct CI sentinel values for session signing, internal authority, legacy credential key if still required, and `CREDENTIALS_ENCRYPTION_KEY`; do not use identical dummy values that can mask cross-purpose key fallback.

# Mandatory Wave 2 — repair R0 browser fixture drift caused by R1

`database/migrations/030_r1_profile_ownership.sql` makes `requests.profile_id` `NOT NULL`.

Current `tests/browser/r0-global-setup.ts` registers a disposable account but inserts its request without `profile_id`.

Repair the fixture by resolving the newly registered user's canonical profile binding and creating the fixture request owned by **that exact profile**. Prefer the canonical application/repository creation path if it can be used cleanly; otherwise use an explicit disposable SQL insert with the resolved `default_profile_id`.

Forbidden:

- removing/weakening `requests.profile_id NOT NULL`;
- first-profile/`LIMIT 1` fallback;
- using a real account/request;
- hardcoding an existing profile ID.

Add a focused regression assertion for fixture ownership if practical.

# Mandatory Wave 3 — close the remaining browser-harness contract gaps

Audit `tests/browser/r0-authenticated-baseline.spec.ts` against the R0 plan.

## 3A. Console errors

R0 requires required browser journeys to fail on unhandled console errors. Current code captures them but does not generally fail.

Add a narrow fail-closed assertion for unexpected browser console errors. Any allowlist must be tiny, issue-ID-linked and specific. Do not ignore all errors or warnings.

## 3B. Session cases

Ensure current executed evidence covers:

```text
missing session
valid session
expired session
malformed session
validly signed token whose user/profile binding no longer exists
```

Reuse R1 session/test helpers or R1 adversarial suites where possible. Do not create a second session implementation just for R0. If equivalent R1 tests are used rather than Playwright duplication, make the R0 evidence matrix explicitly point to those executed tests instead of falsely claiming a Playwright case exists.

## 3C. Narrow-layout evidence

Strengthen the existing `390×844` case just enough to check that the source selector/trigger/options being exercised are visible, enabled and inside the viewport, not only the `Add source` button.

Do **not** implement R5 responsive redesign. If the current product fails the desired UI contract, record it against `UI-001`/R5 as baseline evidence.

## 3D. Preserve test doubles' epistemic boundary

R0 graph/connector/no-provider doubles prove harness authority/wiring only. Do not relabel them as proof that live Neo4j, Intelligence or external providers are operational.

# Mandatory Wave 4 — close migration-fixture audit residue

Audit current `tests/migration_fixtures/test_r0_migration_baseline.py` before changing it. Several July findings are already partially repaired.

Complete only the missing low-cost evidence:

1. prove schema signature stability across the first/second migration pass for each fixture family, not only clean install;
2. in the representative fixture explicitly assert the seeded `source_connector_definitions` row survives;
3. explicitly assert the seeded accepted graph-reference `assertions` row survives, not only `assertion_evidence`;
4. keep the current R2 request-lifecycle/query compatibility assertion;
5. preserve disposable `r0_*` database isolation and cleanup.

Do not invent new migration/product requirements.

# Mandatory Wave 5 — finish R0 static-verifier infrastructure without implementing R3/R7

The old R0 static scanner was independently judged partial. Since then R1 added stronger route/internal-authority tests. Reuse them.

## 5A. Authority

Make the R0 static gate include/recognise the complete R1 authority inventory and R1 internal-authority tests. Do not maintain a weaker selected-path policy as the only R0 proof.

## 5B. Provider bypass detector

Strengthen the detector/fixtures so it cannot silently miss obvious SDK aliases/direct HTTP completion paths and so active runtime roots are explicit.

Important current fact to investigate: a direct `genai.Client` exists under:

```text
agents/python/gdpr_agent.py
```

Do not automatically delete or rewrite it. Determine whether that root is runtime-active. Either:

- include active runtime code in the forbidden-provider inventory; or
- classify the root as legacy/inactive with concrete loader/registry evidence.

Do not hide it merely because the current scanner only walks `frontend` and `intelligence`.

Narrow approved adapters to actual canonical execution adapters. A later-plan direct provider defect may remain an expected baseline finding assigned to R3.

## 5C. Neo4j mutation detector

Add synthetic negative controls for variable/f-string Cypher, transaction/alias calls and a writer outside `GraphProjectionService` using the same abstraction style as production code.

Do not remove R7-owned runtime DDL merely to satisfy R0. R0's job is to detect/register it truthfully.

## 5D. Expected later-plan defects

Never turn registered defects into invisible allowlist entries simply to make R0 green. If you introduce an expected-findings manifest, it must be stable, issue-ID-linked and fail on:

- a new unregistered offender;
- changed offender scope;
- scanner weakness/negative-control failure.

# Mandatory Wave 6 — preserve machine-readable R0 execution evidence

`r0-run-all.sh` already continues through all gates. Preserve that behaviour.

Add a small durable result file under `test-results/`, for example:

```text
test-results/r0-gates.json
```

containing at least:

```text
commit SHA
gate name
command
exit status
```

Duration/timestamps are useful but not mandatory if they complicate the change.

Preserve a combined text log if easy.

Ensure `.github/workflows/r0-baseline.yml` uploads this evidence together with Playwright traces/screenshots/report.

Do not build a bespoke CI dashboard.

# Mandatory Wave 7 — reconcile R0 documentation/registry without rewriting history

The historical R0 baseline stays anchored to its original audit commit. Do not rewrite that history as though R1/R2 existed at the time.

Update current status/evidence for R0 infrastructure issues including, as applicable:

```text
R0-REQ-001
R0-BROWSER-001
R0-BROWSER-002
R0-STATIC-001
migration-audit infrastructure findings
CI bootstrap/order regression
```

Reuse existing stable IDs where sensible; create new R0 IDs only when the issue is materially distinct.

The current requirement ledger already has a granular annex. Verify it against the original plan and the old `R0-REQ-001` finding rather than blindly expanding it again.

Do not remove later-plan issues from the registry just because R0 is being accepted.

# Verification strategy — conserve usage

Do **focused tests first**. Do not run the full repository after every edit.

Suggested focused progression:

```bash
python -m pytest -q tests/integration/test_r0_ci_contract.py
python -m pytest -q tests/migration_fixtures/test_r0_migration_baseline.py
python -m pytest -q tests/integration/test_r0_architecture_invariants.py tests/integration/r1_route_coverage_test.py tests/integration/r1_internal_authority_security_test.py

cd frontend
pnpm run typecheck
pnpm exec vitest run tests/r1-route-authority.test.ts
cd ..
```

Run browser-focused verification once its fixture is fixed.

Then run the complete R0 gate **once**:

```bash
bash scripts/r0-run-all.sh
```

Do not stop at the first failing product assertion. Classify every failure as:

```text
A. R0 infrastructure defect            → fix now
B. R1/R2 regression                     → fix now
C. registered R3–R7 product defect      → record; do not implement here
D. environment-dependent                → document exact missing dependency/evidence
```

R0 is an evidence baseline. Category C is not permission to smuggle later implementation into R0.

# Independent acceptance audit

After the implementation diff is stable, delegate four **read-only, bounded** re-audits to agents that did not implement the corresponding fix:

1. requirements/registry;
2. migration fixtures;
3. managed browser harness;
4. static/security verifier.

Give each auditor only the R0 plan, relevant old audit, current diff and executed evidence. They do not need to recursively redesign the app.

Repair valid R0 findings, then rerun only affected focused tests plus the final complete gate.

# Hosted GitHub Actions verification

If `gh` is authenticated, commit and push the coherent R0 closure once, then inspect/watch `R0 truthful baseline` on the pushed SHA.

Do not claim R0 accepted from local tests alone if the hosted workflow still fails before executing its gates.

If the hosted runner exposes a Linux/Actions-only defect, repair it in this same goal and rerun.

Do not treat a hosted failure from a registered downstream product defect as an R0 infrastructure failure without examining the evidence. Conversely, do not mark a tool/bootstrap/harness failure as an expected product defect.

# Final acceptance decision

Only after the current hosted/local evidence and independent re-audits exist, update:

```text
docs/remediation/R0_ACCEPTANCE_DECISION.md
```

The final decision must explicitly state:

- audited current commit;
- each R0 definition-of-done requirement and evidence;
- all executed gate results;
- which historical R0 findings are repaired;
- which remaining failures belong to R3–R7;
- environment-dependent limitations;
- independent audit verdicts.

Permitted conclusion only if supported:

```text
R0 accepted as truthful baseline/test/CI infrastructure on the environments evidenced below. Later-plan product defects remain open and are not represented as fixed.
```

Do not say:

```text
production ready
everything passes
all plans complete
```

unless that is separately proven at R8.

# Definition of done for this goal

Do not stop until all of the following are true or a concrete external blocker is documented:

- pnpm/setup-node hosted bootstrap defect fixed;
- CI contract prevents the ordering regression;
- R0 browser fixture works with current profile-owned request schema;
- required session semantics are evidenced;
- unexpected browser console errors fail required journeys;
- migration fixture audit residue closed;
- R0 authority/static verifier uses the stronger R1 coverage and has adequate negative controls;
- provider/Neo4j scanners do not silently omit active roots/styles;
- R0 gate result manifest is retained/uploaded;
- full R0 gate executed on current code;
- R1/R2 regressions, if found, repaired;
- later-plan defects remain registered rather than silently fixed/hidden;
- four bounded independent re-audits completed;
- hosted Actions run reaches the substantive gates;
- R0 acceptance decision and issue statuses updated from evidence.

## Token/usage discipline

You have limited remaining usage. Optimise accordingly:

- lead agent owns integration, acceptance semantics and final changes;
- use cheaper/bounded subagents only for read-only audits or narrow fixture/test edits;
- do not re-audit unrelated product features;
- do not rewrite working R1/R2 code unless a reproducible regression requires it;
- do not repeatedly run full test suites;
- batch independent audits after the implementation is stable;
- prefer adapting/reusing existing R1/R2 tests over creating duplicate frameworks;
- make one coherent commit/push before hosted verification where possible.
