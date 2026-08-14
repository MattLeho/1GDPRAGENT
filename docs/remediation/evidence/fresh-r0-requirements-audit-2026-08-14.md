# Fresh R0 requirements and registry audit — 2026-08-14

**Audit mode:** independent read-only review of the post-R2 checkout and R0 closure records.

## Findings

1. **P0 — stale classification:** the requirement ledger still described the 2026-07 pre-R1/R2 failures as current, contradicting the accepted R1 and R2 ledgers.
2. **P1 — scope expansion:** R0 had changed the registered later-plan `OPS-001` product wording instead of retaining it as an expected baseline defect.
3. **P1 — registry drift:** `AUTH-001`–`AUTH-004`, `PROFILE-001`, `DB-001`–`DB-003`, `GRAPH-001`, and `CONN-001` did not state their current post-R1/R2 disposition.
4. **P2 — unresolved evidence labels:** several current registry entries used prose labels rather than repository-relative evidence paths.

## Lead disposition

- Reconciled `R0_REQUIREMENT_LEDGER.md` against the accepted R1/R2 ledgers while retaining the original audit as frozen historical evidence.
- Reverted the `OPS-001` product change and made its browser reproduction a strict expected failure owned by R5/R7.
- Added explicit current statuses and resolvable evidence paths to the historical authority, profile, request, connector, and graph entries.

**Result:** findings repaired locally; final hosted evidence and acceptance decision remain pending.
