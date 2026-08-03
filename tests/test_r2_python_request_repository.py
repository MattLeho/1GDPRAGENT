from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from request_domain import RequestRepository


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.fetch_value = None
        self.command = "UPDATE 1"

    async def fetchval(self, sql, *args):
        self.calls.append((sql, args))
        return self.fetch_value

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        return self.command


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class FakePostgres:
    def __init__(self, connection: FakeConnection) -> None:
        self.pool = FakePool(connection)

    async def _get_pool(self):
        return self.pool


@pytest.mark.asyncio
async def test_request_ownership_and_creation_are_profile_scoped():
    connection = FakeConnection()
    repository = RequestRepository(FakePostgres(connection))
    profile_id, request_id = uuid4(), uuid4()

    connection.fetch_value = 1
    assert await repository.exists(profile_id, request_id)
    sql, args = connection.calls[-1]
    assert "FROM requests" in sql and "profile_id=$2" in sql
    assert args == (request_id, profile_id)

    connection.fetch_value = request_id
    created = await repository.create_draft(
        profile_id, company_name="Controller", company_url=None,
        domain="example.test", request_type="access",
    )
    assert created == request_id
    sql, args = connection.calls[-1]
    assert "INSERT INTO requests" in sql and "profile_id" in sql
    assert args[0] == profile_id
    assert "updated_at" not in sql


@pytest.mark.asyncio
async def test_child_writes_prove_request_ownership():
    connection = FakeConnection()
    repository = RequestRepository(FakePostgres(connection))
    profile_id, request_id = uuid4(), uuid4()

    connection.command = "INSERT 0 1"
    assert await repository.append_message(
        profile_id, request_id, sender="agent", content="grounded message",
    )
    sql, args = connection.calls[-1]
    assert "SELECT id" in sql and "profile_id=$2" in sql
    assert args[:2] == (request_id, profile_id)

    connection.command = "UPDATE 0"
    assert not await repository.append_notes(profile_id, request_id, "foreign")
    sql, args = connection.calls[-1]
    assert "WHERE id=$1 AND profile_id=$2" in sql
    assert args[:2] == (request_id, profile_id)


@pytest.mark.asyncio
async def test_received_processing_is_scoped_through_analysis_run_profile():
    connection = FakeConnection()
    repository = RequestRepository(FakePostgres(connection))
    received_id, run_id = uuid4(), uuid4()

    assert await repository.update_received_processing(
        received_id, run_id, status="completed", processing_stage="completed",
        processing_progress=120, error_message=None,
    )
    sql, args = connection.calls[-1]
    assert "rd.profile_id=ar.profile_id" in sql
    assert args[0:2] == (received_id, run_id)
    assert args[4] == 100
