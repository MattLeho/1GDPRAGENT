# R1 runtime acceptance evidence

Date: 18 July 2026  
Environment: disposable local acceptance stack; no non-disposable account or database was mutated.

## Acceptance result

- Frontend Vitest: **14 files, 87 tests passed**.
- R1 internal authority: **23/23 frontend container checks** and **44/44 Python checks passed**.
- Repaired Python compatibility slice: **25/25 passed**.
- Broad Python regression with the five documented R0/container checks deselected: **526 passed, 1 expected failure, 5 deselected**.
- TypeScript typecheck: **passed**.
- Next.js production build: **passed**, including all 62 generated application pages/routes.
- Migration fixtures: **6 passed, 1 expected failure** (the deliberately ambiguous legacy-ownership fixture).
- Clean install: PostgreSQL 16 empty database accepted migrations `000` through `030` in filename order with `ON_ERROR_STOP=1`.
- Browser acceptance: **4 passed, 0 failed, 0 skipped** against `http://localhost:3012` using a disposable bootstrap account.

The browser run proved active-shell invalid-session rejection and request cessation, accurate connector/graph authorization feedback, immediate persistent-header profile updates, and UI logout with exactly one central protected-state clear.

## Independent audits

- Route authority: **PASS** â€” 83/83 sensitive methods across 58/58 sensitive modules.
- Profile isolation: **PASS**.
- Session state: **PASS**.
- Internal authority: **PASS**.

## R0 boundary

The user stated that the R0 audit was completed separately. The repository-wide Python run was still executed as a regression check. Its remaining exclusions are three pre-existing R0 architecture-policy assertions and two Linux-container tests that hard-code a Windows Codex Node executable; these are not R1 acceptance failures. All R1-focused suites and all Python failures caused by R1 contract changes were repaired and rerun green.
