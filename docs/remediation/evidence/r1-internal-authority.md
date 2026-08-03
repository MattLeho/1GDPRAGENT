# R1 internal service authority evidence

Date: 2026-07-17

## Implemented boundary

- `x-gdpr-internal-key` now carries an HMAC-SHA256 signature, never `INTERNAL_API_KEY` itself.
- The signed canonical payload is seven newline-delimited fields: version, Unix timestamp, nonce, uppercase HTTP method, RFC 3986 canonical path, sorted RFC 3986 canonical query, and canonical profile UUID.
- Required companion headers are `x-gdpr-internal-version`, `x-gdpr-internal-timestamp`, `x-gdpr-internal-nonce`, and `x-gdpr-profile-id`.
- Python verifies signatures with `hmac.compare_digest`, permits 60 seconds of clock skew, and rejects nonce replay in a locked, TTL-pruned cache bounded to 10,000 entries by default.
- One `InternalAuthority` object is attached to request state. `require_profile_id` exposes only its verified UUID; it never re-reads an unverified body/query profile.
- FastAPI middleware protects all routes except `/`, `/health`, `/health/ready`, `/docs`, `/docs/oauth2-redirect`, `/openapi.json`, and `/redoc`.
- `POST /connectors/browser/sync` is the sole non-HMAC ingress. It remains protected by the browser bridge's separately scoped, hashed pairing bearer token; this exemption grants no access to another route.
- `ENVIRONMENT=production` with no `INTERNAL_API_KEY` fails during settings construction. In other environments, protected requests return 503 when it is absent.
- Bulk-ingestion run creation and Personal Insights subject selection now derive profile/subject from verified authority. Caller profile/subject values cannot override it.

## Verification

`docker exec -e PYTHONPATH=/app:/database gdpr_intelligence pytest -q /tests/integration/test_r1_internal_authority.py`

Result: **20 passed** in 7.86s. Coverage includes valid signature; missing headers and secret; malformed UUID, timestamp, version, and signature; method/path/query/profile tamper; expired and future timestamps; replay; missing production secret; representative ingestion, Insights, and evidence routers without authority; and public root access.

`pnpm exec vitest run tests/r1-internal-authority.test.ts`

Result: **3 passed** in 1.11s. Coverage includes deterministic canonical signing, proof that the raw secret is not transmitted, binding to method/path/query/profile, and missing-secret failure.

`pnpm typecheck`

Result: **passed** with no diagnostics.

Compatibility run:

`docker exec -e PYTHONPATH=/app:/database gdpr_intelligence pytest -q /tests/integration/test_r1_internal_authority.py /tests/test_task4_api.py /tests/test_task5_task6_predecessor_authority.py`

Result: **27 passed, 1 failed**. The remaining failure is an obsolete source-string assertion for the independently owned session signer (`createHmac('sha256',secret())`), not an internal-authority runtime failure.

## Frontend proxy migration inventory

Already using the signed helper when this evidence was recorded:

- `frontend/app/api/connectors/[[...path]]/route.ts`
- `frontend/app/api/gdpr-agent/analyze-policy/route.ts`
- `frontend/app/api/graph/chat/route.ts`
- `frontend/app/api/onsit/vendor-dpo-discovery/route.ts`
- `frontend/app/api/retention/[[...path]]/route.ts`

Every remaining Intelligence call below must pass its authenticated profile, exact target URL (including query), and actual method to `intelligenceAuthorityHeaders`:

- `frontend/app/api/insights/[module]/route.ts`
- `frontend/app/api/insights/context-events/route.ts`
- `frontend/app/api/insights/evidence/[id]/route.ts`
- `frontend/app/api/insights/media-location-confirmations/route.ts`
- `frontend/app/api/graph/upsert-identity/route.ts`
- `frontend/app/api/graph/nodes/route.ts`
- `frontend/app/api/graph/nodes/merge/route.ts`
- `frontend/app/api/graph/nodes/bulk/route.ts`
- `frontend/app/api/onsit/bulk/route.ts`
- `frontend/app/api/onsit/discover/route.ts`
- `frontend/app/api/onsit/findings/[id]/route.ts` (GET and DELETE)
- `frontend/app/api/onsit/status/[taskId]/route.ts`
- `frontend/app/api/onsit/vendor-domain-search/route.ts`
- `frontend/lib/graph/upsert.ts`
- `frontend/lib/execution/router.ts` (invoke and health)
- `frontend/lib/ingestion/bulk.ts` (process and specialist-results)

These call sites are owned by the route/integration agents and were intentionally not edited by the internal-authority agent.
