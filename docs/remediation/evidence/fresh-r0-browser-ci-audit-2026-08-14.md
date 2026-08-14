# Fresh R0 browser and CI audit — 2026-08-14

**Audit mode:** independent read-only review of the browser baseline, wrapper, and hosted workflow.

## Findings

1. **P1 — runner continuation:** persistent `errexit` could stop after an early failed gate and leave the JSON manifest incomplete.
2. **P1 — clean bootstrap:** the pnpm lifecycle build policy was incomplete; pnpm 11.9 was also paired with incompatible Node 20.
3. **P1 — green-journey evidence:** trace and screenshot retention was failure-only, so a successful hosted run could upload no journey evidence.
4. **P2 — hermetic credentials:** `GOOGLE_AI_API_KEY`, `GEMINI_API_KEY`, and `OPEN_ROUTER_API_KEY` aliases were not rejected.
5. **P2 — narrow matrix:** Settings was checked at 390x844, but Home was not.

## Lead disposition

- Made the wrapper continue explicitly and added an executable regression requiring the later gate and parseable `[1,0]` manifest.
- Added explicit pnpm build decisions, aligned hosted Node 22 with pnpm 11.9, and proved a clean frozen install in a disposable container (`1,054` packages, exit 0).
- Enabled trace and screenshots for executed R0 browser runs and attached per-journey screenshot plus console/network JSON.
- Rejected every known provider credential alias and added narrow Home overflow/critical-content assertions.

**Result:** clean install verified locally; production browser and hosted wrapper evidence remain pending.
