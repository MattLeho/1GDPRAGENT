# R0 migration baseline evidence

Audited: 17 July 2026 (local Docker PostgreSQL)

## Canonical path and live evidence

- The canonical runner is `database/migrate.py`; its migration history table is
  `gdpr_schema_migrations` and it checks applied filename/checksum immutability.
- The running `gdpr_postgres` instance reported 31 applied migrations, from
  version `000` through `029` (including the `000a` serial-profile preflight).
- The live `requests` table has no `updated_at` column. The dashboard aggregate
  query using `CASE WHEN status = 'completed' THEN updated_at` failed with
  PostgreSQL `ERROR: column "updated_at" does not exist`. This is direct runtime
  evidence for **DB-001 / BROKEN_REGRESSION**, assigned to R2; it is not repaired
  by this R0 work.
- Existing `tests/test_task1_database_integration.py::test_migrations_are_idempotent_and_preserve_legacy_rows`
  passed in the running intelligence container (7.52 seconds). It is useful but
  only covers one historical shape and cannot establish current request-query
  compatibility.

## R0 fixtures added

`tests/migration_fixtures/test_r0_migration_baseline.py` creates and drops unique
databases under a role with `CREATEDB`, so it cannot modify `gdpr_local`.

| Fixture | Evidence checked | Current purpose |
| --- | --- | --- |
| clean | all canonical migration records, `requests` table, second runner pass | clean-install baseline |
| pre_task1 | request, received-data, artifact, chat, integer-profile preservation | legacy upgrade baseline |
| integer_profile | preflight rename/backfill to UUID profile and document preservation | historical profile upgrade |
| current_representative | request, chat, profile, connector, evidence locator/assertion and graph reference remain after a second run | current-state idempotency |

Run with `pytest -q tests/migration_fixtures` after setting `DATABASE_URL`. The
fixture suite intentionally records migration/schema compatibility only; it does
not assert the dashboard's invalid `updated_at` query as valid.

## Reproducible commands

```powershell
$env:DATABASE_URL = 'postgresql://<createdb-role>:<password>@localhost:15432/gdpr_local'
pytest -q tests/migration_fixtures
pytest -q tests/test_task1_database_integration.py::test_migrations_are_idempotent_and_preserve_legacy_rows
python database/migrate.py
python database/migrate.py
```

## Executed R0 fixture evidence

On 2026-07-17, the independent migration verifier ran the disposable suite through the local Docker PostgreSQL service: **4 passed, 1 strict expected failure** in 10.84 seconds. The strict expected failure is the captured `DB-001` dashboard `updated_at` incompatibility; it intentionally becomes an XPASS failure when R2 repairs the query/schema contract.

## Remaining evidence limits / blockers

- The fixtures require a PostgreSQL role with `CREATEDB`; the local Docker role
  met that requirement and CI supplies an equivalent disposable PostgreSQL role.
- The root `migrations/`, `docker/init/01_schema.sql`, and `02_DATABASE_SCHEMA.sql`
  are documented as compatibility/reference artefacts. They were not used as the
  canonical migration input.
- No migration, production schema, or application query was changed by this work.
