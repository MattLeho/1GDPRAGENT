# Canonical database migrations

These ordered SQL files are the only operational schema source for 1GDPRAGENT. Run them with `python database/migrate.py`. Applied filenames and SHA-256 checksums are recorded in `gdpr_schema_migrations`; applied files are immutable.

The root `02_DATABASE_SCHEMA.sql`, `docker/init/01_schema.sql`, and root `migrations/` directory are compatibility/reference artefacts only. Application routes must never create or alter tables.
