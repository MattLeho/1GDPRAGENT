# 1GDPRAGENT — R0 Completion Audit Brief

**Audit date:** 2026-08-14  
**Repository:** `MattLeho/1GDPRAGENT`  
**Current `main`:** `264433a0ba36892af3d3484c54f9e92c9665dcce` — `R2 Done`  
**Objective:** finish R0 as an evidence/test/CI baseline without pulling R3–R7 product implementation back into R0.

## Executive verdict

R0 is **not yet formally accepted**, but most of the original R0 infrastructure exists and several July blockers were subsequently repaired by R1/R2 or by later R0 edits. The remaining work should be a **focused R0 closure pass**, not another broad remediation implementation.

The latest GitHub Actions run (`R0 truthful baseline`, run `31718418746`, job `94508950115`) did not execute the R0 gates. It failed during `actions/setup-node@v4` because the workflow requests pnpm caching before pnpm is installed. The exact hosted-run error is:

```text
Unable to locate executable file: pnpm.
```

Every substantive gate after that point was skipped. Therefore the red check on the `R2 Done` commit is a **CI bootstrap failure**, not evidence that the R2 request/domain implementation failed.

The correct objective now is:

```text
repair R0 CI bootstrap
→ repair R0 harness drift introduced by R1/R2
→ close the known R0 audit-infrastructure gaps
→ execute all R0 gates on current main
→ classify remaining failures as R0 defects vs registered later-plan defects
→ perform fresh independent re-audits
→ update R0 acceptance decision with current evidence
```

R0 must not implement R3 model-routing remediation, R5 responsive redesign, R6 graph features or R7 security hardening merely to make the baseline look green.

---

# 1. R0 contract being audited

Source:

`NEW APP CONTEXT AND PLAN/post plan audit/01_R0_Truthful_Baseline_and_Acceptance_Reset.md`

R0's purpose is to establish a truthful, reproducible evidence baseline for original Tasks 1–6. Its required deliverables are:

1. requirement ledger;
2. stable issue registry;
3. clean/legacy migration fixtures;
4. authenticated Playwright regression evidence;
5. CI covering migrations, Python, TypeScript, lint, build and browser tests;
6. historical acceptance reports marked provisional when current evidence contradicts them.

Its definition of done does **not** require R3–R7 product defects to be fixed. It requires those defects to be truthfully detected, registered and assigned.

The programme protocol also says every later plan must rerun predecessor tests and repair blocking predecessor regressions. R3 should therefore not begin while R0's own evidence pipeline cannot execute.

---

# 2. Current R0 assets that already exist

## 2.1 Baseline documentation

Present:

- `docs/remediation/R0_BASELINE.md`
- `docs/remediation/R0_ACCEPTANCE_DECISION.md`
- `docs/remediation/ledgers/R0_REQUIREMENT_LEDGER.md`
- `docs/remediation/issue-registry.json`
- `docs/remediation/evidence/subagent-plan-doc-audit.md`
- independent requirements, migration, browser and security audits/re-audits.

The baseline is intentionally anchored to the pre-remediation commit `67e50b...`. Do not rewrite that historical snapshot. R0 completion should append/currently verify the baseline on `264433a...`, not erase the original baseline date.

## 2.2 R0 command entry points

Present:

- `scripts/r0-run-all.sh`
- `scripts/r0-compose-validate.sh`
- `scripts/r0-migration-fixtures.sh`
- `scripts/r0-python-suite.sh`
- `scripts/r0-static-invariants.sh`
- `scripts/r0-frontend.sh`
- `scripts/r0-browser.sh`

`r0-run-all.sh` intentionally executes all gates even if an earlier gate fails, then exits non-zero if any gate failed. This is a useful baseline property and should be preserved.

## 2.3 Migration fixtures

Current R0 fixture file:

`tests/migration_fixtures/test_r0_migration_baseline.py`

It now includes:

- clean schema/idempotency;
- pre-Task-1 legacy upgrade;
- integer-profile legacy upgrade;
- current representative state;
- current dashboard/request lifecycle schema compatibility.

This is materially stronger than the version reviewed by the July independent migration audit.

## 2.4 Browser harness

Present:

- `tests/browser/r0-global-setup.ts`
- `tests/browser/r0-authenticated-baseline.spec.ts`
- `frontend/playwright.config.ts`
- CI-only managed server startup in `scripts/r0-browser.sh`;
- R0 deterministic graph/connector/no-provider test paths.

The managed browser script now correctly requires `R0_TEST_MODE=1`, fixing one of the July browser-audit findings.

## 2.5 Authority tests added by R1

R1 subsequently added stronger authority infrastructure that R0 should reuse rather than reinvent:

- `frontend/tests/r1-route-authority.test.ts`
- `tests/integration/r1_route_coverage_test.py`
- `tests/integration/r1_internal_authority_security_test.py`
- `docs/remediation/ledgers/R1_ROUTE_AUTHORITY_INVENTORY.md`

The TypeScript route test inventories every Next API route/method and uses the TypeScript AST to require the canonical guard before protected parsing/database/network work. This is stronger than the original R0 regex-only Next-route scanner.

## 2.6 R2 migration/request evidence

R2's implementation ledger records accepted migration/query/deadline work on the current repository. R0 should reuse those executed fixtures and tests where they satisfy an R0 requirement rather than duplicating equivalent work solely for documentation.

---

# 3. Current R0 blockers and defects

## P0 — CI bootstrap ordering is broken

**Files:**

- `.github/workflows/r0-baseline.yml`
- `tests/integration/test_r0_ci_contract.py`

Current workflow order:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: pnpm
    cache-dependency-path: frontend/pnpm-lock.yaml

- uses: pnpm/action-setup@v4
  with:
    version: 11.9.0
```

This is backwards for the current Actions runner. `setup-node` attempts pnpm-cache resolution before the `pnpm` executable exists.

**Required fix:** install pnpm first, then run cached `actions/setup-node`.

Minimal shape:

```yaml
- uses: pnpm/action-setup@v4
  with:
    version: 11.9.0

- uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: pnpm
    cache-dependency-path: frontend/pnpm-lock.yaml
```

Do not fold a Node-major-version migration into this fix unless actual project tests require it. The hosted-run Node deprecation warnings are separate from the pnpm failure.

### Missing regression test

`tests/integration/test_r0_ci_contract.py` checks only that both R0 runner and artifact upload exist. It does **not** assert that pnpm setup precedes pnpm cache setup. This allowed the checked-in workflow contract test to pass despite a workflow that could never reach the test gates.

Add an ordering assertion so this exact regression cannot recur.

---

## P0 — browser fixture drifted behind R1 ownership migration

**Files:**

- `tests/browser/r0-global-setup.ts`
- `database/migrations/030_r1_profile_ownership.sql`

R1 migration `030_r1_profile_ownership.sql` makes `requests.profile_id` `NOT NULL`.

Current R0 global setup registers a disposable account and then executes:

```sql
INSERT INTO requests(company_name, status)
VALUES('R0 browser fixture controller', 'draft')
RETURNING id
```

It does not supply `profile_id`.

On a current fully migrated database, that insert is no longer valid. This would become the next managed-browser blocker after the pnpm workflow issue is repaired.

**Required fix:** after registration, resolve the disposable user's canonical `default_profile_id` (or otherwise use the canonical application/repository creation path) and create the fixture request with that exact profile ownership. Do not weaken the R1 `NOT NULL` constraint and do not invent a first-profile fallback.

The fixture must remain disposable and must never use a real user/profile.

---

## P0 — R0 has never completed its hosted managed run on current main

`docs/remediation/R0_ACCEPTANCE_DECISION.md` still says `not accepted` and identifies a complete managed CI/browser execution as a blocker.

The August `R2 Done` run was the required opportunity, but all R0 gates were skipped after the pnpm bootstrap failure.

R0 cannot be marked accepted until the repaired workflow actually reaches:

- migration fixtures;
- full Python run;
- static invariants;
- TypeScript;
- lint;
- frontend tests;
- production build;
- authenticated Playwright.

A rerun that dies in tool setup is not acceptance evidence.

---

## P1 — R0 browser suite does not enforce the plan's general console-error rule

R0 requires browser tests to fail on **unhandled console errors in required journeys**.

`r0-authenticated-baseline.spec.ts` currently records console messages into an evidence object and attaches them when a test fails. It does not generally assert that unexpected `console.error` output makes an otherwise passing journey fail.

There is a narrow database-error check for the Home test, but no cross-journey rule.

**Required fix:** add an after-each or helper-level assertion that fails on unexpected console errors, with a very small explicit allowlist only where a stable registered baseline issue genuinely requires it. Do not create a broad regex that hides application errors.

---

## P1 — required session cases are incomplete in the Playwright matrix

The R0 plan calls for browser/session cases for:

- missing cookie;
- valid session;
- expired session;
- malformed cookie;
- valid signature with missing user/profile binding;
- profile save;
- connectors;
- graph;
- request chat;
- narrow-width settings/Home.

Current browser coverage handles missing/malformed/stale cookies and uses a normal valid login in `beforeEach`, but does not explicitly prove:

1. an **expired but correctly shaped/signed session** fails closed; and
2. a **cryptographically valid session whose user/profile binding no longer exists** fails closed in the managed browser/API harness.

R1 has strong adversarial session tests, so do not duplicate heavy machinery. Either add minimal managed cases using existing R1 test/session helpers, or document and mechanically include the executed R1 adversarial tests in the R0 acceptance matrix if they satisfy the exact requirement. The final R0 ledger must not silently claim the Playwright cases exist if they do not.

---

## P1 — R0 static-security verifier remains only partial

**Files:**

- `tests/integration/test_r0_architecture_invariants.py`
- `scripts/r0-static-invariants.sh`
- R1 authority suites listed above.

The final independent R0 security re-audit found the parameterised scanner materially improved but still incomplete. The current source still has these design limitations:

### Next authority

The old R0 scanner only classifies selected path segments. R1 now has a complete explicit route inventory and stronger AST assertions. R0 should **reuse R1's complete inventory/test** as the authority component of the current baseline instead of maintaining a weaker duplicate policy.

### Internal Intelligence authority

R0 should include the R1 internal-authority security suite and verify authenticated Next→Python proxies carry the canonical profile-bound internal authority where required.

### Provider bypass detection

The R0 provider regex remains incomplete and its allowlist includes legacy surfaces such as `intelligence/llm/gemini.py`. It also scans only `frontend` and `intelligence`, while a direct `genai.Client` still exists under `agents/python/gdpr_agent.py`.

R0 does not need to remove every legacy provider call—that is R3's job—but it must not silently omit executable/legacy roots. Establish a small machine-readable runtime-root/exclusion policy:

```text
active runtime root
legacy/inactive root with evidence
approved provider adapter
forbidden direct provider surface
```

Then make the detector report unapproved provider usage truthfully.

### Neo4j mutation detection

The current regex catches only a limited set of literal quoted Cypher calls. It can miss variable/f-string Cypher, `tx.run`, aliases and other transaction styles.

Add synthetic negative controls using the same abstraction style as real graph code. The purpose is to prove the detector works, not to move R7's runtime-DDL/product hardening into R0.

### Required semantics

Do **not** make R0 green by broadening allowlists until defects disappear. A known later-plan defect may remain a registered baseline finding. R0 acceptance is about the truthfulness and reproducibility of the detector.

---

## P1 — migration independent-audit findings are only partially closed

The July migration audit identified:

- missing deterministic schema-diff proof;
- missing current-query compatibility evidence;
- under-asserted representative connector/evidence survival.

Current code has already repaired much of this:

- clean fixture captures a schema signature and verifies repeat migration leaves it unchanged;
- a request-lifecycle compatibility test now proves the R2 columns exist;
- current representative fixture now asserts `export_snapshots`, `source_artifacts` and `evidence_locators` survive.

Remaining low-cost closure work:

1. apply schema-signature equality before/after the second migration to **all four fixture families**, not only the clean fixture;
2. explicitly assert the seeded `source_connector_definitions` row survives;
3. explicitly assert the seeded accepted graph-reference `assertions` row survives, not merely its `assertion_evidence` edge;
4. register/update the old migration-audit findings as repaired or current rather than leaving them only in an independent report;
5. commission a fresh read-only migration re-audit after execution.

Do not add unrelated migration scope.

---

## P1 — CI does not preserve a useful machine-readable summary of every R0 gate

`r0-run-all.sh` prints every gate and correctly continues after failures, but the workflow's uploaded paths contain browser artifacts and `.pytest_cache`; there is no durable R0 gate-status manifest.

For a baseline programme, preserve at least:

```text
gate
command
exit status
start/end or duration
current commit
```

as `test-results/r0-gates.json` or a simple TSV/JSON equivalent. Also preserve the combined runner log if practical.

This makes a failing baseline reproducible without requiring an auditor to reconstruct which gates were skipped/failed from a long Actions log.

Keep implementation tiny; do not build a new CI reporting framework.

---

## P1 — current issue/acceptance records are stale relative to repairs

`docs/remediation/issue-registry.json` is still anchored to the original R0 audit commit and contains R0 infrastructure issues such as:

- `R0-REQ-001` — ledger aggregation;
- `R0-BROWSER-001` / `002` — browser harness false-pass/hermeticity;
- `R0-STATIC-001` — static verifier weakness.

The requirement ledger now has a granular annex, browser test mode is stricter, and migration fixtures have evolved, but the registry/acceptance decision has not been reconciled with those repairs.

Do not rewrite the historical evidence. Update issue statuses/evidence links and produce a **current R0 completion/acceptance record** that clearly distinguishes:

```text
historical baseline finding
R0 infrastructure repair status
later-plan product defect status
current execution evidence
```

Also add stable IDs for material R0 migration/CI infrastructure findings if they are not already represented. Avoid duplicate issue IDs when an existing R0 issue can be updated cleanly.

---

## P2 — responsive browser proof remains slightly weak

The browser re-audit noted that the narrow-width evidence originally proved the `Add source` button but not the selector/options themselves.

Current `R0-AUTH-002` now checks a source selector bounding box and a visible option, which is an improvement. The `R0-UI-001` narrow test can be closed cheaply by also verifying the relevant selector trigger/options are enabled and their bounding boxes remain inside the `390 px` viewport.

Do not implement the R5 responsive redesign here. If the current UI actually fails those desired-contract assertions, record the failure against `UI-001`/R5.

---

## P2 — CI test secrets should be distinct sentinels

The workflow currently uses the same dummy string for `CREDENTIAL_KEY` and `CREDENTIALS_ENCRYPTION_KEY`.

R1's architecture explicitly separates session signing, internal authority and credential encryption. CI should use distinct test sentinel values so an accidental cross-purpose fallback cannot pass because two values happen to match.

Use separate non-secret CI-only strings. Do not do a production secret migration in R0.

---

# 4. Findings that are NOT R0 closure work

Do not spend the remaining Codex budget implementing these while closing R0:

- `MODEL-*` TaskRouter/model-route problems → R3;
- Gmail/Outlook/browser live onboarding → R4;
- responsive shell redesign and real aggregate health → R5;
- temporal graph/playback and graph infrastructure UX → R6;
- SSRF, runtime Neo4j DDL removal, final secret consolidation, production hardening → R7;
- all final whole-product acceptance → R8.

R0 may strengthen detectors for those defects and must keep them visible. It must not absorb their substantive implementation.

---

# 5. Recommended low-usage execution order

Use one Codex goal and make it work in this order so expensive work is not repeated unnecessarily.

## Wave A — deterministic cheap repairs

1. Fix pnpm/setup-node order.
2. Add the CI-order regression assertion.
3. Fix R0 browser fixture `profile_id` ownership.
4. Make CI test secret sentinels distinct.
5. Add the R0 gate result manifest/log.
6. Run only focused CI-contract + migration/browser setup static tests.

## Wave B — close documented R0 audit gaps

1. Migration fixture assertions/schema signatures.
2. Browser console-error invariant and missing session coverage.
3. Reuse R1 route/internal-authority coverage in R0 static gate.
4. Strengthen provider/Neo4j negative controls just enough to meet the independent audit standard.
5. Update R0 issue statuses/evidence metadata.

Run focused tests after each area; do not run the entire repository after every small edit.

## Wave C — one complete local acceptance run

Run:

```bash
bash scripts/r0-run-all.sh
```

Classify each failure:

```text
R0 infrastructure defect
R1/R2 regression
registered later-plan product defect
environment-dependent
```

Repair the first two categories only. Do not repair R3–R7 product scope inside R0.

## Wave D — independent read-only re-audit

Use fresh subagents that did not implement the fixes:

- requirement/registry verifier;
- migration verifier;
- browser verifier;
- static/security verifier.

They should audit the **current diff and executed evidence**, not redo the whole repository implementation.

Repair only valid R0 findings.

## Wave E — hosted run and acceptance decision

Commit/push once the local gate is coherent. Watch the GitHub Actions run. If the hosted run exposes Linux/CI-only problems, repair them within the same goal and rerun.

Only then update:

- `docs/remediation/R0_ACCEPTANCE_DECISION.md`;
- current R0 evidence/ledger links;
- issue statuses.

R0 may be accepted with later-plan product defects still open **if** the baseline infrastructure detects and records them truthfully and the R0 definition of done is evidenced.

Do not claim R3–R8 are complete or production-ready.

---

# 6. R0 completion acceptance matrix

Codex should not mark R0 accepted until this matrix is evidenced.

| Area | Required closure evidence |
|---|---|
| CI bootstrap | pnpm available before pnpm cache setup; regression test exists |
| Hosted execution | all substantive R0 gates actually start/run; no tool-bootstrap skip |
| Requirements | every named Task 1–6/3A unit has stable row/anchor or verified granular annex |
| Registry | known R0 issues have stable IDs/status/evidence; later defects remain assigned |
| Migrations | clean + legacy fixtures; twice-run; schema stability; representative evidence preservation |
| Python | full current suite result recorded; environmental failures separated truthfully |
| Static | complete authority inventory reused; provider/graph verifier negative controls pass; known offenders recorded |
| Frontend | typecheck, lint, tests, production build executed |
| Browser fixture | canonical profile-owned test request on current schema |
| Browser authority | missing/malformed/expired/deleted-binding semantics evidenced |
| Browser journeys | profile/header, connectors, graph, request chat, Home/request DB, narrow UI and status cases execute |
| Console handling | unhandled browser console errors fail required journeys |
| Evidence | gate status manifest + Playwright traces/screenshots/report uploaded |
| Independence | fresh read-only requirements/migration/browser/security verdicts |
| Final record | R0 acceptance decision updated from current evidence, without rewriting historical baseline |

---

# 7. Key conclusion for the next plan

R3 should start only after this R0 closure pass has made the baseline executable and the lead has recorded a defensible R0 acceptance decision. R1 and R2 should be treated as already implemented predecessors and regression-checked, not reimplemented inside R0.
