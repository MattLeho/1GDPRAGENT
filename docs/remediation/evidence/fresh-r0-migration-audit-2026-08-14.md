# Fresh R0 migration audit — 2026-08-14

**Audit mode:** independent read-only review of every disposable migration fixture.

## Findings

1. **P1 — overclaim:** the evidence said every successful history family migrated twice, but successful R1 and R2 fixtures still ran once.
2. **P1 — incomplete signature:** the former “schema signature” compared columns only and could not detect drift in defaults, constraints, indexes, views, functions, triggers, or enums.
3. **P2 — weak partial-history preservation:** the minimal R2 fixture checked columns but did not preserve a representative legacy row.

## Lead disposition

- Added one shared schema signature covering columns/defaults, constraints, indexes, views, routines, triggers, and enums.
- Routed every successful R0/R1/R2 history family through two migration passes and exact first/second signature comparison. The deliberately ambiguous R1 history remains a one-attempt expected failure by design.
- Seeded an unambiguously owned minimal legacy request and asserted its identity and company name survive.

**Verification:** `11 passed` in 34.85 seconds on disposable PostgreSQL databases.
