# Browser/session baseline workstream

**Scope:** R0 regression infrastructure only. Application, package, and runner configuration were intentionally left unchanged.

## Delivered evidence harness

- `tests/browser/r0-authenticated-baseline.spec.ts` supplies eight authenticated Playwright contracts. It is intentionally expected to expose the pre-remediation defects recorded as `AUTH-001`, `AUTH-002`, `CONN-001`, `GRAPH-001`, `PROFILE-001`, `DB-001`, `MODEL-001`, `UI-001`, and `OPS-001`.
- `tests/browser/README.md` records exact runtime inputs and evidence retention requirements.
- The fixture uses real login rather than storage-state injection. It calls protected APIs with missing and malformed cookies and then clears the active browser session to test the stale browser journey.

## Cases and expected baseline signal

| Test | Contract | Current-audit failure it can reproduce |
| --- | --- | --- |
| `R0-AUTH-001` | protected endpoints reject absent/malformed sessions and stale UI redirects | session authority drift |
| `R0-AUTH-002` | authenticated connector source selector contains definitions | empty connector selector / forwarding failure |
| `R0-AUTH-003` | `/api/graph` is not 401 for the signed-in user | Graph API 401 |
| `R0-PROFILE-001` | profile save updates the still-mounted shell header | stale header after save |
| `R0-DB-001` | home route emits no `updated_at` database error | missing `requests.updated_at` |
| `R0-MODEL-001` | request chat does not call Google/Gemini directly | Google-default chat routing |
| `R0-UI-001` | settings at 390px has no document horizontal overflow | narrow-container breakage |
| `R0-OPS-001` | no literal always-online health label appears | hard-coded online indicator |

## Limits / handoff

No Playwright dependency or runner config existed in the checked-out frontend package when this workstream was prepared. The CI workstream must add the runner/configuration and invoke this suite with a clean migrated application plus disposable authenticated fixtures. Until that job emits artifacts, runtime pass/fail evidence remains unproven; the specifications are runnable infrastructure, not a completed production-behaviour claim.
