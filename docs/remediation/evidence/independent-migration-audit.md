# Independent R0 migration-fixture audit

Auditor: independent migration verifier (did not author the migration fixtures).

Audited: 17 July 2026. Scope was read-only except for this report.

## Direct execution evidence

The current disposable fixture suite was run against the existing local Docker
PostgreSQL service, from the repository copy mounted read-only in the
`gdpr_intelligence` container:

```text
docker exec -w /workspace gdpr_intelligence sh -lc \
  'PYTHONPATH=/workspace/database:/app python -m pytest -q tests/migration_fixtures'
```

Result: **4 passed in 14.29s**. Pytest emitted one non-functional warning because
the container cannot write `/workspace/.pytest_cache`; that does not affect the
fixture databases or assertions. The test process exited successfully and the
fixture cleanup completed.

This supersedes the statement in `subagent-migration-baseline.md` that the full
four-fixture run still needs a writable test runner and a role with `CREATEDB`.
The mounted source is read-only, but the Docker database role did have sufficient
authority and all four fixtures ran. The evidence page should be corrected to
record this successful execution (while retaining the cache-warning limitation).

## What is verified

| R0 expectation | Evidence | Verdict |
| --- | --- | --- |
| Fixture isolation | Each test creates a UUID-suffixed `r0_<label>_<random>` database from `DATABASE_URL`, applies migrations only to that URL, terminates connections only for that exact name, then drops that exact database. | Verified, subject to the PostgreSQL role being trusted to have `CREATEDB`. |
| Canonical runner | Fixtures import and call `database/migrate.py:migrate`; they do not execute SQL files independently. | Verified. |
| Four required fixture states | `clean`, `pre_task1`, `integer_profile`, and `current_representative` each have an independently executed test. | Verified. |
| Twice-run/idempotency | `_apply_twice` calls the runner twice in every test, including after representative current data are inserted. | Verified. |
| Clean-install history | Clean fixture asserts history row count equals all migration files and `requests` exists. | Verified, but narrow. |
| Legacy preservation | Pre-Task-1 fixture preserves a request, received data, translated chat row, and migrated integer profile. Integer-profile fixture verifies UUID backfill plus document reassignment. | Verified for the sampled rows only. |
| Current representative preservation | Current fixture preserves sampled request, chat, connector instance, and assertion-evidence link after a further two runs. | Verified for the sampled rows only. |
| CI execution path | `.github/workflows/r0-baseline.yml` supplies a disposable PostgreSQL service and `DATABASE_URL`; `scripts/r0-run-all.sh` invokes `r0-migration-fixtures.sh`. This is a reproducible CI path. | Statically verified; GitHub Actions execution was not available to this audit. |

## Findings requiring repair before R0 acceptance

### R0-MIG-AUDIT-001 — fixture suite does not capture the required schema diff or current-query failure

Severity: medium. Assigned remediation: R0 test/evidence infrastructure (with
the substantive `requests.updated_at` defect remaining assigned to R2/DB-001).

The R0 plan requires the migration baseline to capture *schema diff, migration
history, preserved rows and current query failures*. The suite asserts history
count and selected rows but has no schema snapshot/diff assertion and does not
execute the known dashboard query that references `requests.updated_at`. The
existing evidence document records that query failure as a manual runtime claim,
not fixture output. Therefore the tests establish idempotent migration and sampled
preservation, but do **not** fully establish the promised migration compatibility
baseline.

Required minimal R0 repair:

1. Add a deterministic expected-schema check (or an explicit schema snapshot
   comparison) for every fixture after the first and second migration pass.
2. Add an explicit current-schema compatibility test which records the
   `requests.updated_at` dashboard query failure as an expected baseline defect,
   linked to DB-001, rather than treating it as a manual-only observation.
3. Update the stable issue registry with this audit finding, or merge it into an
   existing R0 infrastructure issue without losing the distinction from DB-001.

### R0-MIG-AUDIT-002 — current representative coverage overclaims connector/evidence preservation

Severity: low. Assigned remediation: R0 test/evidence infrastructure.

The current fixture inserts a connector definition, connector instance, profile,
analysis run, export snapshot, content blob, source artifact, evidence locator,
assertion and graph-reference assertion. Its post-migration assertions check only
the request, chat, connector instance, and assertion-evidence link. It does not
assert that the connector definition, content blob/source artifact/evidence
locator, or accepted graph-reference assertion survives. The prose describing
this as representative preservation should be narrowed, or the missing sampled
assertions should be added.

## Evidence limits that remain honest

- Passing this fixture suite proves only the four prepared shapes and sampled
  rows, not arbitrary customer schemas or all application queries.
- The running CI workflow was inspected but not executed on GitHub during this
  audit; its actual hosted artefact upload remains unproven here.
- The fixture setup necessarily connects to the configured PostgreSQL server to
  create disposable databases. It must only be pointed at a server where this
  authority is appropriate.

## Acceptance recommendation

**Do not mark the migration-baseline portion of R0 fully accepted yet.** The
disposable fixtures, isolation and twice-run preservation claims are now backed
by direct execution evidence, but R0-MIG-AUDIT-001 leaves two explicit plan
requirements unimplemented, and R0-MIG-AUDIT-002 makes the current-representative
coverage narrower than its description.
