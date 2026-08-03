# Independent R0 requirements audit

**Auditor:** independent requirements verifier (did not create the R0 ledger or browser/migration/CI baseline)  
**Audit date:** 2026-07-17  
**Scope:** Read-only verification of the R0 requirement ledger, issue registry and historical-status corrections against the original Task 1--6 plans (including Task 3A), the 15 July user audit, and a representative current-source sample. This audit does not make the R0 acceptance decision.

## Verdict

**Not yet sufficient to prove the R0 requirement-ledger definition of done.** The current baseline is a strong high-level reclassification and uses the exact status vocabulary, but it is not yet a *requirement-by-requirement* ledger for the granular requirements in Tasks 3--6/3A. It also omits two reported defects from the stable issue registry and has one status mismatch for the explicit 300 GB environment requirement. These are documentation/registry corrections within R0, not a request to implement later-plan product work.

## Method and evidence boundaries

- Read `NEW APP CONTEXT AND PLAN/post plan audit/01_R0_Truthful_Baseline_and_Acceptance_Reset.md`, `11_Issue_to_Plan_Traceability.md`, `audit 15.07.2026.md`, all original Task 1--6 plan files, `docs/remediation/ledgers/R0_REQUIREMENT_LEDGER.md`, `docs/remediation/issue-registry.json`, `docs/remediation/R0_BASELINE.md`, and the plan-document/static-scan evidence.
- Checked representative current-source references for each plan. Static code was treated as C evidence only; it was not treated as authenticated runtime proof.
- No files except this independent report were edited.

## Representative cross-plan verification

| Original plan sample | Current R0 classification / source check | Result |
|---|---|---|
| Task 1, §1 migration authority and §5 stable graph identity | Ledger records `IMPLEMENTED_NOT_INTEGRATED` and `BROKEN_REGRESSION`; `database/migrate.py` and migrations exist, while the reported graph `401` is contrary runtime evidence. | Reasonable high-level status; not operational. |
| Task 2, §2 no silent Google transfer | Ledger records `BROKEN_REGRESSION`; static scan identifies `frontend/lib/model-preferences.ts` active reads/defaults and the reported request-chat Google-key error corroborates it. | Supported. |
| Task 3, Wave 4 router/provider integration | Ledger records `BROKEN_REGRESSION`; Task 3 requires Task 2 router integration and current Google-default evidence contradicts it. | Supported. |
| Task 3A, §4 individual file-family packages | Ledger collapses all F1--F6 work into one `§4 family adapters` row. The source plan has distinct requirements for structured/text, Office/PDF, email/calendar/contacts, media/subtitles, geo/database/browser and archive formats. | **Deficiency: not requirement-by-requirement.** |
| Task 4, Wave 5 UI modules | Ledger collapses the global temporal control plus eight named modules (overview, atlas, search/AI, map, changes/eras, correlation, evidence inspector) into one row. | **Deficiency: not requirement-by-requirement.** |
| Task 5, Wave 1 connector runtime and Wave 7 controls | Ledger records `BROKEN_REGRESSION`; user audit's invalid-session/empty selector and `SourceConnectorsSection.tsx` API-only definition rendering support this. | Supported at wave level; granular requirements still collapsed. |
| Task 6, Wave 7 graph UI/API | Ledger records `BROKEN_REGRESSION`; reported graph `401` is contrary runtime evidence. | Supported at wave level; compare/profile/modes/styling/inspector/drift/panels are not independently classified. |

## Classification-model review

The ledger and `R0_BASELINE.md` use precisely the nine required enum values:

`OPERATIONAL`, `IMPLEMENTED_NOT_INTEGRATED`, `PARTIAL`, `UI_ONLY`, `TEST_ONLY`, `MISSING`, `DEFERRED_EXPLICITLY`, `BROKEN_REGRESSION`, `ENVIRONMENT_DEPENDENT`.

No non-enum status was found. The no-`OPERATIONAL` conclusion is appropriately conservative because the ledger records no current authenticated runtime evidence. However, exact enum spelling alone does not meet Wave 1: every individual row must carry evidence and blockers.

### Deficiency R0-REQ-001 — wave-level aggregation prevents per-requirement evidence

**Severity:** high (blocks R0 definition of done)  
**Evidence:** `docs/remediation/ledgers/R0_REQUIREMENT_LEDGER.md` has 60 rows, but rows such as `T3 | Wave 1 storage/inventory/hashing`, `T4 | Wave 5 insights UI`, `T5 | Wave 4 other connectors`, and `T6 | Wave 7 graph UI/API` each cover many separately specified requirements. Original-plan examples include Task 3 §§277--403 (five named Wave 1 work packages), Task 3A §§383--691 (F1--F6), Task 4 §§602--750 (eight UI work packages), Task 5 §§479--555 (four connector packages), and Task 6 §§666--764 (eight graph/UI packages).

**Required R0 correction:** Expand the canonical ledger and its detailed evidence source so every named section/work package/acceptance requirement has its own stable row, exact source reference, C/M/T/R evidence paths or explicit absence, revised enum status, contradiction, and blocking owner. A parent/wave summary may remain, but cannot substitute for child rows.

### Deficiency R0-REQ-002 — the 300 GB scale requirement is classified inconsistently

**Severity:** medium  
**Evidence:** Original Task 3 Wave 6 explicitly requires a 300 GB scale/restart target (`Task 3...md`, §1032 onward). The detailed documentation-audit evidence calls that 300 GB environment `ENVIRONMENT_DEPENDENT`, but the canonical ledger's `T3 | Wave 6 scale/E2E` row is `TEST_ONLY` and does not split bounded-fixture proof from the 300 GB environment proof.

**Required R0 correction:** Split the bounded synthetic/restart acceptance from the 300 GB operational-scale requirement. Classify the latter `ENVIRONMENT_DEPENDENT` unless a suitable environment produces current evidence; retain `TEST_ONLY` only for the portions proven solely by tests.

### Deficiency R0-REQ-003 — ledger evidence is indirect and cannot be verified per row

**Severity:** medium  
**Evidence:** Most canonical ledger cells use only summary tokens such as `C/M/T; R absent`, with a single global link to `subagent-plan-doc-audit.md`. Because that document repeats the same grouped units, an auditor cannot locate exact paths and tests for the individual requirements omitted by R0-REQ-001.

**Required R0 correction:** Add a stable requirement ID/source locator and direct evidence references for each expanded row (or a per-row anchor into a detailed companion ledger). Preserve the current C/M/T/R separation.

## Issue-registry coverage review

The JSON registry is valid machine-readable JSON, has a stable schema/version and IDs, severity, root cause, affected paths, remediation plan and evidence. It covers the major traceability-table issues and static-scan themes, including the additional `R0-STATIC-NEO4J-DDL` finding.

### Deficiency R0-ISSUE-001 — reported privacy-policy scan failure has no registry issue

**Severity:** medium  
**Evidence:** `audit 15.07.2026.md` states: “the privacy policy scan is still failing”. No registry entry describes the functional policy-scan failure. `SEC-001` is only the SSRF/redirect-protection concern; it does not cover the observed unavailable/failing product journey.

**Required R0 correction:** Add a stable issue ID (for example `POLICY-001`) with the reported failure state, affected scan/API paths after investigation, evidence, severity and R6/R7 remediation assignment. It may remain unproven/diagnostic, but must be registered as a known issue.

### Deficiency R0-ISSUE-002 — missing graph credential-management UI is unregistered

**Severity:** medium  
**Evidence:** The same user audit says graph credentials should be configurable in Settings and that the setting is missing. `GRAPH-001` covers the 401 and `GRAPH-002` covers misleading infrastructure-login wording; neither records the missing configuration/control requirement.

**Required R0 correction:** Add a separate stable issue, affected Settings/graph configuration paths and an R6/R7 assignment. Do not implement the UI in R0.

## Historical acceptance-report review

**Pass.** `IMPLEMENTATION_TRACKER.md` now prominently labels historical completion marks provisional. All six implementation ledgers are marked provisional; Task 1/2/3A/4/6 acceptance reports are marked as required, and the existing Task 5 Final Self-Audit is also marked provisional. This preserves historical text rather than rewriting it. The documentation audit correctly records that a Task 5 final acceptance report does not exist.

## Acceptance implications

After the three ledger corrections and two registry additions above, re-run this audit against the expanded ledger. Until then, the evidence supports an honest baseline but not the R0 statement that **every original Plan 1--6 requirement has a revised evidence-backed status**.
