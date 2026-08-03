# R1 independent internal-authority final audit

Date: 2026-07-18  
Auditor: independent subagent (did not implement the repaired area)  
Verdict: **PASS**

## Scope

Independent read-only audit of the Next.js signer, FastAPI verifier and middleware, exact-body binding, replay rejection, browser-sync exception, profile consumption, worker handoffs, route/caller discovery, secret separation, shared cross-runtime canonicalization vectors, and focused frontend/Python gates.

## Findings

- `frontend/lib/api-session.ts` and `intelligence/api/security.py` bind the v1 HMAC to timestamp, nonce, method, canonical path/query, canonical profile UUID, normalized content type, and SHA-256 of the exact transmitted request bytes. The verifier checks the body digest and signature before atomically accepting the nonce.
- Reviewed mutation callers pass the same string used as `fetch(...).body` into `intelligenceAuthorityHeaders`; bodyless calls sign the empty byte sequence.
- Replay rejection uses shared Redis `SET NX EX`, fails closed with 503 when Redis is unavailable, and retains nonces for the complete possible acceptance interval. Compose enables Redis AOF and persistent storage.
- `intelligence/main.py` protects every non-public route except exactly `POST /connectors/browser/sync`. The HTTP-boundary test proves a pairing-only bearer token reaches that scoped route without HMAC headers and cannot authorize `/query/tools`.
- The FastAPI route-table test enumerates every `APIRoute` and requires an explicit public, pairing-only, authenticated-stateless, or profile-consuming policy. Stateful and personal endpoints consume verified profile authority directly or through the authorised Insights dependency.
- Bulk-ingestion workers revalidate analysis-run, export-snapshot, profile, and optional received-data profile linkage before processing. Connector workers reload the instance and verify its canonical profile. Handoff inventory checks require verified profile authority in ingestion, bulk, and connector enqueue paths.
- Next.js caller discovery covers `localhost:8000`, `localhost:8001`, configured Intelligence URLs, direct clients, simple network aliases/member clients, and tainted local wrappers. Every currently discovered Next.js-to-Intelligence call is separately signed.
- TypeScript and Python consume the same packaged `frontend/tests/fixtures/r1_internal_authority_vectors.json`. The vectors cover duplicate/blank query values, Unicode, encoded slashes, plus/space handling, and dot segments; both runtimes reject malformed path escapes.
- Production configuration independently requires session signing, internal authority, and credential-encryption secrets. The internal signer has no fallback to either unrelated key and never transmits the raw key.
- Missing, malformed, stale, future, replayed, profile-tampered, path/query/method-tampered, and body-tampered authority fails closed with structured errors and without secret disclosure.

No blocking internal-authority finding remains in the audited R1 scope.

## Focused evidence

Executed against the mounted current worktree in the running Docker services:

```text
Frontend Vitest:
  tests/r1-internal-authority.test.ts
  tests/r1-internal-authority-call-sites.test.ts
  tests/r1-adversarial-session-api.test.ts
Result: 3 files passed, 23 tests passed

Python pytest:
  tests/integration/test_r1_internal_authority.py
  tests/integration/r1_internal_authority_security_test.py
  tests/integration/test_r1_internal_profile_consumption.py
  tests/test_task5_task6_predecessor_authority.py
Result: 44 passed
```

The frontend fixture was also checked directly inside the Next.js container at `/app/tests/fixtures/r1_internal_authority_vectors.json`; it is present and the cross-runtime test passes from that standard container path.

## Conclusion

The R1 internal-authority boundary meets its re-audit exit criteria: exact-body signed calls, shared fail-closed replay protection, canonical signed profile consumption by stateful endpoints and worker handoffs, a functioning pairing-only exception with no authority expansion, systematic route/caller coverage, distinct secrets, shared canonicalization vectors, and clean focused gates.
