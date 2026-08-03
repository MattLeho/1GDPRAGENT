# R0 requirement-by-requirement implementation ledger

This is the lead-owned classification ledger for all original Task 1--6 requirement units (including Task 3A). Evidence classes are independent: C=code, M=migration, T=automated test, R=authenticated runtime. The detailed exact-source, path-level C/M/T/R evidence and historical claim for every row is retained in [the documentation-audit evidence](../evidence/subagent-plan-doc-audit.md); this ledger records the final R0 baseline classification and blocking dependency for each requirement unit.

| Plan | Requirement unit (exact plan section) | C/M/T/R evidence | R0 status | Blocking dependency / owner |
|---|---|---|---|---|
| T1 | §1 migration source of truth | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | clean/upgrade fixture evidence (R0) |
| T1 | §2 canonical evidence ledger | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | representative upgrade (R0) |
| T1 | §3 provenance invariant | C/M/T; R absent | TEST_ONLY | authenticated ingestion (R1/R3) |
| T1 | §4 ontology separation | C/M/T; R absent | TEST_ONLY | populated graph runtime (R6) |
| T1 | §5 stable graph IDs | C/M/T; R graph 401 | BROKEN_REGRESSION | GRAPH-001 (R1/R6) |
| T1 | §6 scoped entity keys | C/M/T; R absent | TEST_ONLY | writer invariant (R0/R1) |
| T1 | §7 hypotheses only | C/M/T; R absent | TEST_ONLY | live-writer invariant (R0/R1) |
| T1 | §8 versioned data artifacts | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | upgrade fixture (R0) |
| T1 | §9 one graph projection writer | C/T; R graph 401 | TEST_ONLY | invariant/runtime graph (R0/R1) |
| T1 | §10 preserve useful functions | C/T; R failures | PARTIAL | AUTH/DB/MODEL repairs |
| T1 | §11 acceptance scenarios | T; R absent | TEST_ONLY | current full suite/R0 |
| T1 | §12 documentation | C; reports contradicted | PARTIAL | provisional status (R0) |
| T2 | §1 TaskDefinition/TaskRoute | C/M/T; R absent | TEST_ONLY | product call-site proof (R3) |
| T2 | §2 Engine Registry/no Google fallback | C/M/T; R Google error | BROKEN_REGRESSION | MODEL-001 (R3) |
| T2 | §3 transcription split | C/M/T; R absent | TEST_ONLY | route invocation proof (R3) |
| T2 | §4 execution privacy policy | C/M/T; R absent | TEST_ONLY | egress proof (R3) |
| T2 | §§5-6 workflow registry/parity | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | authenticated execution (R3) |
| T2 | §7 built-in email without N8N | C/T; R absent | ENVIRONMENT_DEPENDENT | SMTP/IMAP runtime (R4) |
| T2 | §8 secret storage | C/T; conflicting stores | PARTIAL | SEC-002 (R3/R7) |
| T2 | §9 settings IA | C/T; R failures | BROKEN_REGRESSION | R1/R4/R5 |
| T2 | §10 execution audit | C/M/T; R absent | TEST_ONLY | forced router invariant (R3) |
| T2 | §11 Task 2 acceptance tests | T only | TEST_ONLY | API/browser suite (R0) |
| T2 | §12 docs | C; reports contradicted | PARTIAL | provisional status (R0) |
| T3 | Wave 0 predecessor/contracts | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | R0 rebaseline |
| T3 | Wave 1 storage/inventory/hashing | C/M/T; R absent | TEST_ONLY | restart fixture/runtime |
| T3A | §§1-3 adapter/status/matrix | C/M/T; R absent | TEST_ONLY | installed dependency proof |
| T3A | §4 family adapters | C/M/T; R absent | TEST_ONLY | per-family runtime |
| T3 | Wave 2 parser/event/resume | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | live ingestion |
| T3 | Wave 3 deterministic features | C/M/T; R absent | TEST_ONLY | profile-scoped execution |
| T3 | Wave 4 router/providers/benchmark | C/M/T; R Google error | BROKEN_REGRESSION | MODEL-001 (R3) |
| T3 | Wave 5 temporal engine | C/M/T; R absent | TEST_ONLY | populated runtime |
| T3 | Wave 6 scale/E2E | C/T; R absent | TEST_ONLY | bounded CI / 300GB env |
| T3A | §§5-9 routes/locators/workflows | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | upload route authority |
| T3A | §§10-11 test matrix/report | T; report absent | TEST_ONLY | acceptance report/R0 |
| T4 | Wave 0 contracts | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | predecessor reset |
| T4 | Wave 1 snapshots/API | C/M/T; R absent | TEST_ONLY | signed-in populated API |
| T4 | Wave 2 search/AI signals | C/M/T; R absent | TEST_ONLY | model route invariant |
| T4 | Wave 3 correlations | C/M/T; R absent | TEST_ONLY | current UI/API execution |
| T4 | Wave 4 media/location | C/M/T; R absent | ENVIRONMENT_DEPENDENT | model/media environment |
| T4 | Wave 5 insights UI | C/T; R absent | UI_ONLY | authenticated browser |
| T4 | Wave 6 scenario/perf acceptance | T; R absent | TEST_ONLY | rerun + runtime |
| T5 | Wave 0 safety contracts | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | R1 authority |
| T5 | Wave 1 registry/runtime/scheduler | C/M/T; R empty selector | BROKEN_REGRESSION | CONN-001 (R1/R4) |
| T5 | Wave 2 browser extension/bridge | C/M/T; R absent | ENVIRONMENT_DEPENDENT | paired browser |
| T5 | Wave 3 IMAP/transport/events | C/M/T; R absent | ENVIRONMENT_DEPENDENT | credential runtime |
| T5 | Wave 4 other connectors | C/M/T; R absent | TEST_ONLY | onboarding runtime |
| T5 | Wave 5 retention engine | C/M/T; R absent | TEST_ONLY | profile DB integration |
| T5 | Wave 6 deletion safety | C/M/T; R absent | TEST_ONLY | isolated execution evidence |
| T5 | Wave 7 settings controls | C/T; R connector failure | BROKEN_REGRESSION | R1/R4 |
| T5 | Wave 8 acceptance | T; R absent | TEST_ONLY | browser/API evidence |
| T6 | Wave 0 contracts | C/M/T; R absent | IMPLEMENTED_NOT_INTEGRATED | graph authority |
| T6 | Wave 1 capability/linkability | C/M/T; R absent | TEST_ONLY | populated graph |
| T6 | Wave 2 policy/purpose | C/M/T; R absent | TEST_ONLY | SEC-001/R7 |
| T6 | Wave 3 institutional access | C/M/T; R absent | TEST_ONLY | evidence-backed graph |
| T6 | Wave 4 hypotheses/DSAR | C/M/T; R DB failure | IMPLEMENTED_NOT_INTEGRATED | DB-001/R2 |
| T6 | Wave 5 deletion verification | C/M/T; R absent | TEST_ONLY | live export evidence |
| T6 | Wave 6 cited query service | C/M/T; R absent | TEST_ONLY | allowed/denied API proof |
| T6 | Wave 7 graph UI/API | C/M/T; R graph 401 | BROKEN_REGRESSION | GRAPH-001/R1/R6 |
| T6 | Wave 8 wording/acceptance | C/T; R absent | TEST_ONLY | browser acceptance |
| T6 | Wave 9 audit/docs | C/T; signed-in gap | PARTIAL | provisional reports/R0 |

No row is classified `OPERATIONAL` in this R0 baseline: none has current authenticated runtime evidence sufficient to meet the stated standard. No requirement is marked `MISSING` or `DEFERRED_EXPLICITLY` unless the original plan or runtime evidence explicitly establishes that status; missing later-plan features are tracked as issues rather than silently reclassifying an unrelated completed-code claim.

## Granular work-package annex (Tasks 3--6)

These child rows expand the original plans' named work packages. Exact source, code/migration/test paths are in the corresponding child section of [the detailed evidence audit](../evidence/subagent-plan-doc-audit.md); `R=none` means no current authenticated-runtime proof.

| ID / exact source | C/M/T/R | R0 status | Blocker |
|---|---|---|---|
| T3-1A analytical storage/event lake | C/M/T/R-none | TEST_ONLY | bounded restart runtime |
| T3-1B archive inventory/policy | C/M/T/R-none | TEST_ONLY | production corpus |
| T3-1C hashing/canonical/dedup | C/M/T/R-none | TEST_ONLY | representative import |
| T3-1D file truth/fingerprints | C/M/T/R-none | TEST_ONLY | real corpus |
| T3-1E Task3A wave-one adapters | C/M/T/R-none | TEST_ONLY | family runtime |
| T3-2A declarative parser runtime | C/M/T/R-none | TEST_ONLY | live ingestion |
| T3-2B sampling/schema proposal | C/M/T/R-none | TEST_ONLY | reviewed import |
| T3-2C ActivityEvent writer | C/M/T/R-none | IMPLEMENTED_NOT_INTEGRATED | profile runtime |
| T3-2D progress/resumability | C/M/T/R-none | TEST_ONLY | crash/restart runtime |
| T3-3A service/schema/data-class features | C/M/T/R-none | TEST_ONLY | profile execution |
| T3-3B identifier/token analysis | C/M/T/R-none | TEST_ONLY | profile execution |
| T3-3C URL/language/time features | C/M/T/R-none | TEST_ONLY | profile execution |
| T3-3D geo/interaction features | C/M/T/R-none | TEST_ONLY | profile execution |
| T3-3E density/co-occurrence aggregates | C/M/T/R-none | TEST_ONLY | profile execution |
| T3-4A provider/runtime adapters | C/M/T/R-Google error | BROKEN_REGRESSION | MODEL-001/R3 |
| T3-4B private benchmark | C/T/R-none | TEST_ONLY | configured models |
| T3-5A temporal observations/aggregates | C/M/T/R-none | TEST_ONLY | populated profile |
| T3-5B interest/burst/routine/era views | C/M/T/R-none | TEST_ONLY | populated profile |
| T3-6A bounded synthetic/restart acceptance | C/T/R-none | TEST_ONLY | current E2E run |
| T3-6B 300GB scale/restart requirement | C/T/R-none | ENVIRONMENT_DEPENDENT | 300GB hardware/storage environment |
| T3A-F1 structured/text family | C/M/T/R-none | TEST_ONLY | installed format runtime |
| T3A-F2 Office/PDF family | C/M/T/R-none | TEST_ONLY | optional dependencies/runtime |
| T3A-F3 mail/calendar/contact family | C/M/T/R-none | TEST_ONLY | connector runtime |
| T3A-F4 media/subtitle family | C/M/T/R-none | TEST_ONLY | media dependencies/runtime |
| T3A-F5 geo/database/browser family | C/M/T/R-none | TEST_ONLY | paired browser/database runtime |
| T3A-F6 archive family | C/M/T/R-none | TEST_ONLY | optional archive runtime |
| T4-1A signal hierarchy/contracts | C/M/T/R-none | TEST_ONLY | populated profile |
| T4-1B snapshot/materialisation/API | C/M/T/R-none | TEST_ONLY | signed-in API |
| T4-2A search signals | C/M/T/R-none | TEST_ONLY | live data |
| T4-2B AI conversation signals | C/M/T/R-none | TEST_ONLY | routed model runtime |
| T4-2C exposure/engagement semantics | C/M/T/R-none | TEST_ONLY | live data |
| T4-2D episodes/eras | C/M/T/R-none | TEST_ONLY | live data |
| T4-3A correlation storage/candidates | C/M/T/R-none | TEST_ONLY | live data |
| T4-3B exposure resolver | C/M/T/R-none | TEST_ONLY | live data |
| T4-4A media origin | C/M/T/R-none | ENVIRONMENT_DEPENDENT | media runtime |
| T4-4B metadata/location candidate | C/M/T/R-none | ENVIRONMENT_DEPENDENT | media runtime |
| T4-4C selective vision | C/M/T/R-none | ENVIRONMENT_DEPENDENT | configured vision model |
| T4-4D place aggregates | C/M/T/R-none | TEST_ONLY | populated profile |
| T4-5A global temporal control | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5B overview/engagement module | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5C interest atlas | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5D search/AI module | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5E places/movement map | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5F changes/eras module | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5G correlation module | C/T/R-none | UI_ONLY | authenticated browser |
| T4-5H evidence inspector | C/T/R-none | UI_ONLY | authenticated browser |
| T5-1A registry/sync runtime | C/M/T/R-empty selector | BROKEN_REGRESSION | CONN-001 |
| T5-1B raw-record bridge | C/M/T/R-none | TEST_ONLY | signed-in sync |
| T5-1C scheduler/pause/health | C/M/T/R-none | TEST_ONLY | worker runtime |
| T5-2A Chromium extension | C/T/R-none | ENVIRONMENT_DEPENDENT | paired browser |
| T5-2B native/local bridge | C/M/T/R-none | ENVIRONMENT_DEPENDENT | paired host |
| T5-3A IMAP source | C/M/T/R-none | ENVIRONMENT_DEPENDENT | IMAP credential runtime |
| T5-3B transport | C/T/R-none | ENVIRONMENT_DEPENDENT | SMTP runtime |
| T5-3C email semantics | C/T/R-none | TEST_ONLY | live mailbox |
| T5-3D bulk/newsletter detector | C/T/R-none | TEST_ONLY | live mailbox |
| T5-3E engagement semantics | C/T/R-none | TEST_ONLY | live mailbox |
| T5-4A AI snapshot connectors | C/T/R-none | TEST_ONLY | onboarding runtime |
| T5-4B photo connector | C/T/R-none | TEST_ONLY | filesystem runtime |
| T5-4C filesystem connector | C/T/R-none | TEST_ONLY | filesystem runtime |
| T5-5A deterministic retention | C/M/T/R-none | TEST_ONLY | profile DB integration |
| T5-5B adjudication bundles | C/M/T/R-none | TEST_ONLY | profile DB integration |
| T5-5C policy evaluator | C/M/T/R-none | TEST_ONLY | profile DB integration |
| T5-6A deletion-plan builder | C/M/T/R-none | TEST_ONLY | isolated destructive runtime |
| T5-6B quarantine/grace | C/M/T/R-none | TEST_ONLY | isolated destructive runtime |
| T5-6C controller-erasure integration | C/M/T/R-none | TEST_ONLY | request lifecycle/DB-001 |
| T5-7A connector settings | C/T/R-empty selector | BROKEN_REGRESSION | CONN-001 |
| T5-7B permission inspector | C/T/R-none | UI_ONLY | authenticated browser |
| T5-7C retention settings | C/T/R-none | UI_ONLY | authenticated browser |
| T5-7D deletion review UI | C/T/R-none | UI_ONLY | authenticated browser |
| T6-1A capability taxonomy | C/M/T/R-none | TEST_ONLY | populated graph |
| T6-1B identifier statistics | C/M/T/R-none | TEST_ONLY | populated graph |
| T6-1C graph metrics/simulation | C/M/T/R-none | TEST_ONLY | populated graph |
| T6-2A policy source ingestion | C/M/T/R-none | TEST_ONLY | policy runtime |
| T6-2B grounded claims | C/M/T/R-none | TEST_ONLY | policy runtime |
| T6-2C purpose lineage/distance | C/M/T/R-none | TEST_ONLY | policy runtime |
| T6-2D justification/scope/reach | C/M/T/R-none | TEST_ONLY | policy runtime |
| T6-3A access ontology projection | C/M/T/R-none | TEST_ONLY | populated graph |
| T6-3B custody/access classifier | C/M/T/R-none | TEST_ONLY | populated graph |
| T6-3C access fixtures | T/R-none | TEST_ONLY | runtime |
| T6-4A hypothesis detectors | C/M/T/R-none | IMPLEMENTED_NOT_INTEGRATED | DB-001/R2 |
| T6-4B DSAR templates | C/T/R-none | IMPLEMENTED_NOT_INTEGRATED | DB-001/R2 |
| T6-4C resolution service | C/M/T/R-none | IMPLEMENTED_NOT_INTEGRATED | DB-001/R2 |
| T6-5A deletion simulation | C/M/T/R-none | TEST_ONLY | live export |
| T6-5B later-export comparison | C/M/T/R-none | TEST_ONLY | live export |
| T6-5C verification DTOs | C/T/R-none | TEST_ONLY | live export |
| T6-6A temporal/profile tools | C/M/T/R-none | TEST_ONLY | signed-in API |
| T6-6B linkability/capability tools | C/M/T/R-none | TEST_ONLY | signed-in API |
| T6-6C purpose/hypothesis/delta tools | C/M/T/R-none | TEST_ONLY | signed-in API |
| T6-6D citation validator | C/T/R-none | TEST_ONLY | signed-in API |
| T6-7A temporal/compare graph API | C/M/T/R-401 | BROKEN_REGRESSION | GRAPH-001 |
| T6-7B profile-layer graph API | C/M/T/R-401 | BROKEN_REGRESSION | GRAPH-001 |
| T6-7C modes/navigation | C/T/R-401 | BROKEN_REGRESSION | GRAPH-001 |
| T6-7D epistemic styling | C/T/R-none | UI_ONLY | authenticated browser |
| T6-7E evidence inspector | C/T/R-none | UI_ONLY | authenticated browser |
| T6-7F longitudinal drift | C/T/R-none | UI_ONLY | authenticated browser |
| T6-7G profile comparison | C/T/R-none | UI_ONLY | authenticated browser |
| T6-7H capability/linkability/purpose/access panels | C/T/R-none | UI_ONLY | authenticated browser |
| T6-8A wording guardrails | C/T/R-none | TEST_ONLY | browser/API |
| T6-8B E2E scenarios | T/R-none | TEST_ONLY | authenticated browser |
