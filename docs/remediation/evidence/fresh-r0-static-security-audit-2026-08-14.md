# Fresh R0 static and security audit — 2026-08-14

**Audit mode:** independent read-only review plus adversarial probes of the R0 architecture verifiers.

## Findings

1. **P1 — provider false negatives:** default OpenAI imports, computed endpoint strings, and JavaScript module extensions escaped detection.
2. **P1 — Neo4j false negatives:** annotated query variables and derived transaction receivers escaped detection; JavaScript module extensions were omitted.
3. **P2 — Python authority evidence gap:** the scanner was file-level. The cited ONSIT endpoints are runtime-protected by the global middleware, so this was an evidence gap, not an authentication bypass.
4. **P2 — runtime-root drift:** not every scanner consumed the reviewed root policy, and runtime entrypoints were not inventoried.
5. **P2 — registry linkage:** expected finding IDs were not mechanically required to have a registered owner, status, and affected path.

## Lead disposition

- Added negative controls for both provider bypass styles and both Neo4j mutation styles, and scanned `.js`, `.mjs`, and `.cjs` where applicable.
- Made provider, mutation, and runtime-DDL scanners consume the reviewed root policy and asserted declared runtime entrypoints exist.
- Added the real internal-authority suite to the R0 static gate and recognised the exact global middleware contract.
- Required every expected finding ID/path to resolve to the stable issue registry.

**Verification:** complete static/security gate `70 passed` in 94.96 seconds.
