"""Execute every Python request repository statement against disposable R2 databases."""
from __future__ import annotations

import os
from uuid import uuid4

import asyncpg
import pytest

from request_domain.repository import RequestRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("R2_TEST_DATABASE_URL"),
    reason="R2_TEST_DATABASE_URL is required for disposable database integration",
)


@pytest.mark.asyncio
async def test_python_request_repository_query_matrix() -> None:
    connection = await asyncpg.connect(os.environ["R2_TEST_DATABASE_URL"])
    try:
        database_name = await connection.fetchval("SELECT current_database()")
        assert database_name.startswith("r2_query_")

        profile_id = uuid4()
        other_profile_id = uuid4()
        await connection.execute(
            "INSERT INTO profiles(id,identity_name) VALUES($1,'Python R2'),($2,'Other Python R2')",
            profile_id,
            other_profile_id,
        )
        repository = RequestRepository()
        request_id = await repository.create_draft(
            profile_id,
            company_name="Python query controller",
            company_url="https://python-r2.example",
            domain="python-r2.example",
            request_type="access",
            notes="integration",
            connection=connection,
        )

        assert await repository.exists(profile_id, request_id, connection=connection)
        assert not await repository.exists(other_profile_id, request_id, connection=connection)
        assert await repository.append_message(
            profile_id, request_id, sender="company", content="response", connection=connection,
        )
        assert not await repository.append_message(
            other_profile_id, request_id, sender="company", content="foreign", connection=connection,
        )
        assert await repository.append_notes(profile_id, request_id, "reviewed", connection=connection)
        assert not await repository.append_notes(other_profile_id, request_id, "foreign", connection=connection)

        received_data_id = await connection.fetchval(
            "INSERT INTO received_data(request_id,file_name,profile_id) VALUES($1,'response.zip',$2) RETURNING id",
            request_id,
            profile_id,
        )
        analysis_run_id = await connection.fetchval(
            """INSERT INTO analysis_runs(profile_id,request_id,run_type,pipeline_version)
               VALUES($1,$2,'r2_query_matrix','test') RETURNING id""",
            profile_id,
            request_id,
        )
        foreign_run_id = await connection.fetchval(
            """INSERT INTO analysis_runs(profile_id,run_type,pipeline_version)
               VALUES($1,'r2_query_matrix','test') RETURNING id""",
            other_profile_id,
        )
        assert await repository.update_received_processing(
            received_data_id,
            analysis_run_id,
            status="completed",
            processing_stage="verified",
            processing_progress=150,
            error_message=None,
            connection=connection,
        )
        assert not await repository.update_received_processing(
            received_data_id,
            foreign_run_id,
            status="failed",
            processing_stage="foreign",
            processing_progress=1,
            error_message="must not apply",
            connection=connection,
        )
        row = await connection.fetchrow(
            "SELECT status,processing_stage,processing_progress FROM received_data WHERE id=$1",
            received_data_id,
        )
        assert dict(row) == {
            "status": "completed",
            "processing_stage": "verified",
            "processing_progress": 100,
        }
    finally:
        await connection.close()
