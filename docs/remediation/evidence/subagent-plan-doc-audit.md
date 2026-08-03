# Original-plan documentation audit (subagent evidence)

Audit date: 2026-07-17. Scope is read-only: original Task 1–6 plans (Task 3A is an explicit Task 3 dependency), historical ledgers/audits, tracker, migrations, source-tree and test inventory. `R0` status vocabulary is used exactly. A prior *accepted* report is a claim, not runtime proof.

## Evidence key and limits

- **Claim**: historical documents call every completed task area implemented/accepted: `Technical Documentation/Task {1..6}*`, and `[IMPLEMENTATION_TRACKER.md](../../../IMPLEMENTATION_TRACKER.md)` records checked items. Task 4/6 plans themselves contain acceptance claims (Task 4: 849–851).
- **C** = code exists by static search; **M** = a matching migration exists; **T** = matching focused Python/static test file exists; **R** = authenticated browser/runtime proof available to this audit.
- `R=none` is not evidence of failure by itself, but it prevents `OPERATIONAL`. This audit found no checked-in authenticated Playwright suite at audit time. User-reported authenticated failures in `post plan audit/audit 15.07.2026.md` are contrary runtime evidence for the marked rows.
- Candidate remediation assignments use R1–R8 from `post plan audit/11_Issue_to_Plan_Traceability.md`; R0 supplies only baseline/CI proof.

## Repository-wide contradictions found while reading

1. The tracker says **Task 2 accepted** yet its own “Audit Follow-Ups” says no frontend route test runner/test script and lists auth/upload/chat/graph/workflow API coverage as outstanding. This makes route claims `TEST_ONLY`, `PARTIAL`, or `IMPLEMENTED_NOT_INTEGRATED`, not operational.
2. The tracker says `Task 5`/`Task 6` are complete in their respective records, but the user reports invalid-session connector loading, Graph `401`, and profile/header divergence. These are cross-plan authority integration failures (AUTH-001/002, PROFILE-001, CONN-001, GRAPH-001).
3. `frontend/components/layout/DashboardLayout.tsx:241` renders literal **System Online**, contrary to the health claim (OPS-001).
4. `frontend/components/settings/SourceConnectorsSection.tsx:20` renders definitions only from API data; an auth failure therefore leaves the source selector empty, matching the reported defect.
5. `frontend/components/graph/GraphCanvas.tsx:228` turns a non-OK response into `Graph API returned <status>`; this is compatible with the reported 401 but not a diagnosis of it.
6. `frontend/lib/connectors/email.ts:37` retains an unscoped `ORDER BY ... LIMIT 1` settings query. This is contrary to the general profile-authority premise and needs R1 review.

## Requirement-level inventory

Each row is a plan requirement/acceptance unit, not a mere code file. “Claim” is `accepted` unless qualified above; it is sourced from that Task’s historical ledger/audit.

### Task 1 — evidence and graph foundation

| Source requirement | C/M/T/R | Candidate status | Contradiction / remediation |
|---|---|---|---|
| T1 §1 single operational migration authority and non-destructive legacy reconciliation | C `database/migrate.py`; M `000..009`; T `tests/test_task1_database_integration.py`; R none | IMPLEMENTED_NOT_INTEGRATED | historical claim has only old local/fixture result; R0 migration fixtures/CI must re-prove clean and upgrade paths. |
| T1 §2 AnalysisRun, ExportSnapshot, ContentBlob, SourceArtifact, typed EvidenceLocator, Assertion | C `intelligence/evidence/*`, `frontend/lib/evidence.ts`; M `002`; T locator/database tests; R none | IMPLEMENTED_NOT_INTEGRATED | require current DB proof including representative upgrade. |
| T1 §3 provenance invariant/exact-span acceptance | C `intelligence/evidence`, `grounded_extractor`; M `005,006,008`; T `tests/test_evidence_locators.py`; R none | TEST_ONLY | acceptance is static/synthetic; exercise an authenticated ingestion path later. |
| T1 §4 separated canonical ontology | C `ontology/graph-ontology.json`, `intelligence/graph/*`; M `002`; T `tests/test_ontology_and_inference.py`; R none | TEST_ONLY | no populated authenticated graph evidence. |
| T1 §5 stable UUID API identity, no Neo4j numeric IDs | C projection/API; M `002`; T Task1 integration/static; R contrary: graph 401 | BROKEN_REGRESSION | GRAPH-001 prevents validating graph API; R1/R6. |
| T1 §6 typed, scoped entity keys rather than value-only MERGE | C projection/evidence; M `002`; T ontology tests; R none | TEST_ONLY | current mutation-path scan needed in R0. |
| T1 §7 inference only produces hypotheses | C `intelligence/agents/kg_ingestor.py`; M `002`; T ontology tests; R none | TEST_ONLY | validate all live writers with R0 invariant scan. |
| T1 §8 versioned data_artifacts | C `frontend/lib/data-artifacts.ts`; M `003`; T Task1 database test; R none | IMPLEMENTED_NOT_INTEGRATED | re-run historical upgrade with representative artifacts. |
| T1 §9 sole GraphProjectionService writer | C `intelligence/graph/projection.py`; M n/a; T `tests/test_audit_static.py`; R graph 401 | TEST_ONLY | static guard must run in CI; authenticated graph unavailable. |
| T1 §10 retain DSAR/email/provider/graph useful functions | C broad legacy source; M n/a; T build-only claims; R contrary errors | PARTIAL | DB-001, AUTH-002 and MODEL-001 show retained journeys are not operational. |
| T1 §11 synthetic migration/provenance/graph acceptance | T listed focused tests; R none | TEST_ONLY | execute complete current suite and record artifacts in R0. |
| T1 §12 README/architecture/tracker documentation | C docs exist; M n/a; T none; R n/a | PARTIAL | completion language contradicts present runtime evidence; R0 must mark reports provisional. |

### Task 2 — execution control plane and settings

| Source requirement | C/M/T/R | Candidate status | Contradiction / remediation |
|---|---|---|---|
| T2 §1 TaskDefinition/TaskRoute with typed task characteristics | C `frontend/lib/execution/{registry,router}.ts`; M `010`; T `tests/test_task2_architecture.py`; R none | TEST_ONLY | trace all product call sites/R0 provider-call invariant. |
| T2 §2 Engine Registry: deterministic/local/remote engines, discovery, no silent Google transfer | C `frontend/lib/execution/*`; M `010`; T Task2 architecture; R contrary request chat Google key | BROKEN_REGRESSION | MODEL-001: R3 must remove hidden Google default and prove non-Google run. |
| T2 §3 split transcription from semantic interpretation | C execution adapters; M `010`; T Task2 architecture; R none | TEST_ONLY | needs route-level invocation proof. |
| T2 §4 strict_local/local_first/controlled_cloud policy | C router; M `010`; T Task2 architecture; R none | TEST_ONLY | provider egress/invocation audit belongs R0/R3. |
| T2 §5–6 WorkflowDefinition and inventory/parity for built-in/N8N paths | C `frontend/lib/workflows/registry.ts`; M `010`; T Task2 architecture; R none | IMPLEMENTED_NOT_INTEGRATED | no authenticated workflow execution proof; N8N deployment remains environment-dependent. |
| T2 §7 N8N not required for email operation | C connector/email code; M `010`; T Task2 architecture; R none | ENVIRONMENT_DEPENDENT | SMTP/IMAP external environment and credential proof required. |
| T2 §8 encrypted email credential storage/rotation/deletion | C `frontend/lib/connectors/email.ts`; M `010`; T Task5 email tests; R none | PARTIAL | duplicate/legacy secret stores require SEC scan (SEC-002, CONN-005). |
| T2 §9 settings IA: identity/connectors/routes/workflows/retention/security/advanced | C settings components; M `010`; T Task2 static; R contrary profile, connector, narrow UI failures | BROKEN_REGRESSION | PROFILE-001, CONN-001, UI-001; R1/R4/R5. |
| T2 §10 execution audit answering who/what/where/policy/outcome | C router ExecutionRecord types; M `010`; T Task2 architecture; R none | TEST_ONLY | force every model invocation through it (R0 invariant; R3 remediation). |
| T2 §11 Task2 tests | T only `test_task2_architecture.py`; R none | TEST_ONLY | historical “38 tests” is not a current authenticated/API acceptance pack. |
| T2 §12 processing/workflow/settings documentation | C tracker/docs; T none; R n/a | PARTIAL | must be labelled provisional. |

### Task 3 and Task 3A — local-first ingestion, temporal engine, file catalogue

| Source requirement | C/M/T/R | Candidate status | Contradiction / remediation |
|---|---|---|---|
| T3 Wave0 predecessor audit, baseline, frozen contracts/migration ownership | C contracts/modules; M `011–016`; T Task3 contracts; R none | IMPLEMENTED_NOT_INTEGRATED | predecessor assumptions are now contradicted; re-baseline under R0. |
| T3 Wave1 analytical event-lake/storage, safe inventory, hashing/dedup, file truth | C `intelligence/ingestion/*`; M `012,015`; T storage/inventory/catalogue tests; R none | TEST_ONLY | clean/upgrade plus corpus restart proof required. |
| T3A §§1–3 FileFamilyAdapter, explicit supported/unsupported/quarantined status, P0/P1/P2 matrix | C adapters/catalogue; M `011,012`; T adapter tests; R none | TEST_ONLY | tests do not establish installed optional dependencies or production source behavior. |
| T3A §4 family adapters (structured/text, office/PDF, mail/calendar/contacts, media/subtitles, geo/DB/browser, archives) | C `intelligence/ingestion/adapters/*`; M `011`; T `test_task3_adapter_*`; R none | TEST_ONLY | verify fixtures/status for every listed family; optional RAR/browser formats may be DEFERRED_EXPLICITLY only when catalogue says so. |
| T3 Wave2 registry/declarative parser, sampling/proposal, task route, ActivityEvent writer, resumable progress | C `intelligence/ingestion/*`; M `012–016`; T wave2/processor/registry tests; R none | IMPLEMENTED_NOT_INTEGRATED | live ingestion and resumption unproven. |
| T3 Wave3 deterministic service/schema/identifier/URL/time/geo/co-occurrence features | C `intelligence/features/*`; M `012`; T feature test files; R none | TEST_ONLY | requires synthetic and live profile-scoped execution. |
| T3 Wave4 Task2 router integration, provider adapters and private benchmark | C benchmark/execution adapters; M `015`; T benchmark tests; R contrary MODEL-001 | BROKEN_REGRESSION | router default failure blocks non-Google guarantee; R3. |
| T3 Wave5 temporal aggregates, interest state, bursts, routines, eras, as-of/export delta | C `intelligence/temporal/*`; M `014`; T temporal tests; R none | TEST_ONLY | no authenticated populated-data proof. |
| T3 Wave6 projection, 300GB scale/restart and model-call benchmark, E2E acceptance | C projection/corpus; M `015,016`; T corpus/performance tests; R none | TEST_ONLY | current performance/scale result not recorded; run in CI only at bounded fixture scale and document 300GB as ENVIRONMENT_DEPENDENT. |
| T3A §§5–9 specialist routes/fallback order, locator rules, nesting, workflow registry, migration from uploads | C registry/adapters; M `011–016`; T cross-family/static tests; R none | IMPLEMENTED_NOT_INTEGRATED | request/upload routes must be checked for bypass/direct prompt logic. |
| T3A §§10–11 complete family test matrix and acceptance report | T adapter suite exists; R none | TEST_ONLY | acceptance report missing as a standalone Task3A doc; historical Task3/3A audit must become provisional. |

### Task 4 — Personal Insights and temporal/correlation/media UI

| Source requirement | C/M/T/R | Candidate status | Contradiction / remediation |
|---|---|---|---|
| T4 Wave0 epistemic/contract freeze | C insights contracts; M `017–020`; T Task4 contracts; R none | IMPLEMENTED_NOT_INTEGRATED | must inherit reclassified T1–T3 assumptions. |
| T4 Wave1 InsightSnapshot period aggregation/materialisation/API | C `intelligence/insights/{models,service}.py`; M `017–020`; T service/materialization/API; R none | TEST_ONLY | no signed-in populated response evidence. |
| T4 Wave2 search, AI-conversation, exposure/engagement, episodes/eras | C insights modules; M `017`; T signals tests; R none | TEST_ONLY | direct model routing must be statically checked. |
| T4 Wave3 contextual correlation storage/candidates/exposure resolver | C insight context modules; M `017`; T context tests; R none | TEST_ONLY | correlation wording must be run against current UI/API. |
| T4 Wave4 media origin, metadata/location, selective vision, place aggregates | C media modules/routes; M `017`; T media tests; R none | ENVIRONMENT_DEPENDENT | external/local vision/model configuration remains unproven. |
| T4 Wave5 all Personal Insights UI modules, global time/compare, evidence inspector | C `frontend/lib/insights`, dashboard UI; M n/a; T frontend runtime contract; R none | UI_ONLY | browser report is limited to historical claim; R0 needs authenticated browser evidence. |
| T4 Wave6 scenario fixtures, cold/warm/performance and final acceptance | T Task4 acceptance/perf suite; R none | TEST_ONLY | historical Task4 acceptance calls it complete; mark provisional. |

### Task 5 — live connectors and retention/deletion

| Source requirement | C/M/T/R | Candidate status | Contradiction / remediation |
|---|---|---|---|
| T5 Wave0 connector/deletion authority and safety contracts | C `intelligence/connectors`, retention; M `021`; T Task5 contracts; R none | IMPLEMENTED_NOT_INTEGRATED | active profile/authority contradicts invalid session; R1. |
| T5 Wave1 registry, sync runtime/raw bridge, schedule/pause/health | C `intelligence/connectors/{registry,runtime,bridge}.py`; M `021,026`; T connector runtime/lifecycle/bridge; R contrary empty selector | BROKEN_REGRESSION | CONN-001: auth/API integration prevents use. |
| T5 Wave2 browser extension/local bridge/page-content policy | C `browser-extension/**`, `022`; T browser bridge; R none | ENVIRONMENT_DEPENDENT | extension installation/native bridge cannot be treated operational without paired-browser run. |
| T5 Wave3 IMAP source, encrypted credential boundary, transport/events/newsletters/engagement | C connector/email modules; M `023`; T IMAP/SMTP/semantics tests; R none | ENVIRONMENT_DEPENDENT | needs real (or isolated SMTP/IMAP) auth/credential runtime; OAuth Gmail/Outlook are not a Task5 requirement and are R4 work. |
| T5 Wave4 AI conversation/photo/filesystem connectors and parser fixtures | C connectors; M `021`; T ai/filesystem tests; R none | TEST_ONLY | no signed-in connector onboarding proof. |
| T5 Wave5 deterministic retention features/adjudication/evaluator | C `intelligence/retention/*`; M `024`; T retention engine tests; R none | TEST_ONLY | needs profile-scoped database integration. |
| T5 Wave6 deletion plan/quarantine/source execution/local purge/erasure candidates | C retention modules; M `025`; T deletion safety tests; R none | TEST_ONLY | dangerous operational actions intentionally require isolated synthetic proof; production execution remains environment-dependent. |
| T5 Wave7 connector, permissions, retention, deletion-review settings UI | C settings components; M n/a; T static/contracts; R contrary connectors invalid session | BROKEN_REGRESSION | CONN-001/AUTH-001. |
| T5 Wave8 synthetic connector and deletion suites/final audit | T Task5 test files; R none | TEST_ONLY | no Task5 Final Acceptance Audit found; tracker/ledger claims must be provisional. |

### Task 6 — privacy capability and final graph product UI

| Source requirement | C/M/T/R | Candidate status | Contradiction / remediation |
|---|---|---|---|
| T6 Wave0 ontology/epistemic contracts | C `intelligence/privacy/contracts.py`; M `028,029`; T contracts; R none | IMPLEMENTED_NOT_INTEGRATED | depends on T1 graph and R1 authority. |
| T6 Wave1 capability taxonomy, identifier statistics, graph metrics/removal simulation | C `privacy/{capability,linkability}.py`; M `028`; T capability/linkability; R none | TEST_ONLY | no populated graph response proof. |
| T6 Wave2 policy source/grounded claims/purpose lineage/technical reach | C `privacy/purpose.py`; M `028`; T purpose/policy source; R none | TEST_ONLY | policy URL acquisition security remains SEC-001 (R7). |
| T6 Wave3 institutional-access graph semantics | C `privacy/access.py`; M `028`; T access; R none | TEST_ONLY | requires evidence-backed live graph. |
| T6 Wave4 hypotheses, targeted DSAR, resolution | C `privacy/hypotheses.py`; M `028`; T hypotheses; R none | IMPLEMENTED_NOT_INTEGRATED | existing request lifecycle is broken by DB-001; R2. |
| T6 Wave5 deletion simulation/later-export verification presentation | C `privacy/deletion.py`; M `028`; T deletion; R none | TEST_ONLY | no live export comparison proof. |
| T6 Wave6 typed, read-only cited PrivacyQueryService | C `privacy/query.py`, API; M `028`; T query/frontend contract; R none | TEST_ONLY | needs authenticated allowed/denied API proofs. |
| T6 Wave7 graph API filters/compare, modes, styling, inspector, drift/profile panels | C graph components/API; M `028`; T frontend contracts; R contrary graph 401 and date-input report | BROKEN_REGRESSION | GRAPH-001; GRAPH-003/004; R1/R6. |
| T6 Wave8 wording guardrails and E2E scenarios | C guardrail modules; T wording/acceptance pack; R none | TEST_ONLY | source-string/static tests do not replace browser acceptance. |
| T6 Wave9 line-by-line audit/docs | C final audit; T historical commands only; R one historical unauthenticated route smoke | PARTIAL | report explicitly says signed-in content was not tested; its “None incomplete” claim is unsupported. |

## Direct historical-report changes requested of lead

Mark the following reports prominently **PROVISIONAL — superseded by R0 evidence pending revalidation**, preserving their text and date: `Technical Documentation/Task 1 Acceptance Audit.md`, `Task 2 Acceptance Audit.md`, `Task 3 and 3A Acceptance Audit.md`, `Task 4 Acceptance Audit.md`, `Task 6 Final Acceptance Audit.md`, all six implementation ledgers, and relevant checked claims in `IMPLEMENTATION_TRACKER.md`. No Task5 final acceptance file exists; record that absence.

## Handoff: priority proof matrix

1. **R0 baseline**: create authenticated browser/API proof, current migration fixture evidence, CI and static invariant reports for every `TEST_ONLY`/`IMPLEMENTED_NOT_INTEGRATED` item.
2. **R1**: repair and prove shell/API authority, active-profile scope and header invalidation (AUTH-001–004, PROFILE-001, CONN-001, GRAPH-001).
3. **R2**: reconcile `requests.updated_at`, request repository/lifecycle and stop fabricated metrics (DB-001–003, SEM-001).
4. **R3–R7**: do not relabel a feature operational until a corresponding signed-in, configured runtime case is recorded; preserve `ENVIRONMENT_DEPENDENT` where external credentials/hardware/installations are genuinely required.
