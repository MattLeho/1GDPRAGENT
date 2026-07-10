#!/usr/bin/env python3
"""Apply GDPR Agent PostgreSQL migrations exactly once, in filename order."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sys
from pathlib import Path

import asyncpg


MIGRATION_RE = re.compile(r"^(\d{3}[a-z]?)_[a-z0-9_]+\.sql$")
LOCK_KEY = 0x3147445052414745  # stable application-specific advisory lock


def discover_migrations(directory: Path) -> list[Path]:
    migrations = sorted(path for path in directory.glob("*.sql") if MIGRATION_RE.match(path.name))
    versions = [MIGRATION_RE.match(path.name).group(1) for path in migrations]  # type: ignore[union-attr]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration version detected")
    return migrations


async def migrate(database_url: str, directory: Path) -> None:
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute("SELECT pg_advisory_lock($1)", LOCK_KEY)
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS gdpr_schema_migrations (
                version TEXT PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                checksum_sha256 TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        for path in discover_migrations(directory):
            version = MIGRATION_RE.match(path.name).group(1)  # type: ignore[union-attr]
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            applied = await connection.fetchrow(
                "SELECT filename, checksum_sha256 FROM gdpr_schema_migrations WHERE version = $1",
                version,
            )
            if applied:
                if applied["filename"] != path.name or applied["checksum_sha256"] != checksum:
                    raise RuntimeError(
                        f"Applied migration {version} differs from {path.name}; migrations are immutable"
                    )
                continue

            async with connection.transaction():
                await connection.execute(sql)
                await connection.execute(
                    """
                    INSERT INTO gdpr_schema_migrations(version, filename, checksum_sha256)
                    VALUES ($1, $2, $3)
                    """,
                    version,
                    path.name,
                    checksum,
                )
            print(f"Applied {path.name}", flush=True)
    finally:
        try:
            await connection.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
        finally:
            await connection.close()


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    directory = Path(os.environ.get("MIGRATIONS_DIR", Path(__file__).with_name("migrations")))
    asyncio.run(migrate(database_url, directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
