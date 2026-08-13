#!/usr/bin/env python3
"""Execute the TypeScript request repository against clean and upgraded databases."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

import asyncpg


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
MIGRATIONS = ROOT / "database" / "migrations"
R2_MIGRATION = MIGRATIONS / "031_r2_request_lifecycle.sql"
sys.path.insert(0, str(ROOT / "database"))
from migrate import migrate  # noqa: E402


def database_url() -> str:
    if value := os.getenv("DATABASE_URL"):
        return value
    values: dict[str, str] = {}
    for raw_line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return (
        f"postgresql://{quote(values['POSTGRES_USER'])}:{quote(values['POSTGRES_PASSWORD'])}"
        f"@localhost:{values['POSTGRES_HOST_PORT']}/{values['POSTGRES_DB']}"
    )


async def create_database(admin: asyncpg.Connection, base_url: str, label: str) -> tuple[str, str]:
    name = f"r2_query_{label}_{uuid.uuid4().hex[:10]}"
    if not name.startswith("r2_query_"):
        raise RuntimeError("refusing to create an unexpected database name")
    await admin.execute(f'CREATE DATABASE "{name}"')
    return name, f"{base_url.rsplit('/', 1)[0]}/{name}"


async def prepare_upgrade(url: str) -> None:
    with tempfile.TemporaryDirectory(prefix="r2-query-upgrade-") as temporary:
        before_r2 = Path(temporary)
        for source in sorted(MIGRATIONS.glob("*.sql")):
            if source.name < R2_MIGRATION.name:
                shutil.copy2(source, before_r2 / source.name)
        await migrate(url, before_r2)

    connection = await asyncpg.connect(url)
    try:
        profile_id = await connection.fetchval(
            "INSERT INTO profiles(identity_name) VALUES('R2 query historical profile') RETURNING id"
        )
        request_id = await connection.fetchval(
            "INSERT INTO requests(company_name,status,profile_id,deadline_date,next_action_date) "
            "VALUES('Historical query controller','completed',$1,'2024-03-01','2024-02-07') RETURNING id",
            profile_id,
        )
        await connection.execute(
            "INSERT INTO request_chat_messages(request_id,sender,message) VALUES($1,'user','historical chat')",
            request_id,
        )
        await connection.execute(
            "INSERT INTO received_data(request_id,file_name,profile_id) VALUES($1,'historical.zip',$2)",
            request_id,
            profile_id,
        )
        await connection.execute(
            "INSERT INTO messages(request_id,sender,content) VALUES($1,'company','historical response')",
            request_id,
        )
        await connection.execute(
            "INSERT INTO request_events(request_id,event_type) VALUES($1,'historical')", request_id
        )
    finally:
        await connection.close()
    await migrate(url, MIGRATIONS)


async def prepare_already_applied_r2(url: str) -> None:
    """Prove an installation with recorded 031 can accept later migrations."""
    with tempfile.TemporaryDirectory(prefix="r2-query-through-031-") as temporary:
        through_r2 = Path(temporary)
        for source in sorted(MIGRATIONS.glob("*.sql")):
            if source.name <= R2_MIGRATION.name:
                shutil.copy2(source, through_r2 / source.name)
        await migrate(url, through_r2)
    await migrate(url, MIGRATIONS)


def run_vitest(url: str, label: str) -> None:
    node = os.getenv("NODE_EXE") or shutil.which("node")
    if not node:
        raise RuntimeError("node is required (set NODE_EXE or add it to PATH)")
    environment = os.environ.copy()
    environment["R2_TEST_DATABASE_URL"] = url
    command = [
        node,
        str(FRONTEND / "node_modules" / "vitest" / "vitest.mjs"),
        "run",
        "tests/r2-request-repository.integration.test.ts",
    ]
    print(f"Running request query matrix against {label} database", flush=True)
    subprocess.run(command, cwd=FRONTEND, env=environment, check=True)


def run_python_repository(url: str, label: str) -> None:
    environment = os.environ.copy()
    environment["R2_TEST_DATABASE_URL"] = url
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "database"), str(ROOT / "intelligence")))
    print(f"Running Python request query matrix against {label} database", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_r2_python_request_repository_integration.py", "-vv"],
        cwd=ROOT,
        env=environment,
        check=True,
    )


async def main() -> None:
    base_url = database_url()
    admin = await asyncpg.connect(base_url)
    databases: list[tuple[str, str]] = []
    try:
        clean = await create_database(admin, base_url, "clean")
        upgrade = await create_database(admin, base_url, "upgrade")
        applied_r2 = await create_database(admin, base_url, "applied_r2")
        databases.extend([clean, upgrade, applied_r2])
        await migrate(clean[1], MIGRATIONS)
        await prepare_upgrade(upgrade[1])
        await prepare_already_applied_r2(applied_r2[1])
        for name, url in databases:
            await asyncio.to_thread(run_vitest, url, name)
            await asyncio.to_thread(run_python_repository, url, name)
    finally:
        for name, _url in databases:
            if not name.startswith("r2_query_"):
                raise RuntimeError("refusing to drop an unexpected database name")
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1", name
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await admin.close()


if __name__ == "__main__":
    asyncio.run(main())
