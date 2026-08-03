# R0 disposable migration fixtures

These pytest fixtures create uniquely named PostgreSQL databases, run the canonical
`database/migrate.py` runner twice, verify preservation of a small representative
row set, and drop only the database they created.  They are deliberately not a
schema repair mechanism and never run DDL against the configured application
database.

Run from the repository root with a PostgreSQL `DATABASE_URL` whose role has
`CREATEDB` privilege:

```powershell
$env:DATABASE_URL = 'postgresql://.../gdpr_local'
pytest -q tests/migration_fixtures
```

Fixtures covered:

- `clean`: empty database and canonical migration history;
- `pre_task1`: route-era application tables with a request, chat message, data
  artifact, and user profile;
- `integer_profile`: the historical serial `user_profiles` and `user_documents`
  shape that migration `000a` must preserve and backfill;
- `current_representative`: a migrated current schema with a request, chat,
  canonical profile, connector definition/instance, execution run, evidence
  references, and an accepted graph-reference assertion.

The tests are skipped (rather than silently passed) when `DATABASE_URL` is not
set. They use the same migration runner as production and therefore also detect
checksum/history failures.
