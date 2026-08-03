from __future__ import annotations

from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException

import api.bulk_ingestion as bulk_api
from api.bulk_ingestion import (
    ProcessFileBody, SpecialistResultBody, _require_owned_inputs,
    run_progress, specialist_result,
)
from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from test_task1_database_integration import migrated_database


@pytest.mark.asyncio
async def test_bulk_ingestion_ids_cannot_cross_profile_boundary(
    migrated_database, tmp_path, monkeypatch,
):
    url,request_id,received_data_id=migrated_database
    client=PostgresClient(url)
    monkeypatch.setattr(bulk_api,"get_postgres_client",lambda:client)
    connection=await asyncpg.connect(url)
    try:
        owner_profile=await connection.fetchval(
            "SELECT profile_id FROM requests WHERE id=$1",request_id,
        )
        foreign_profile=await connection.fetchval(
            "INSERT INTO profiles(identity_name) VALUES('Foreign ingestion profile') RETURNING id",
        )
        ledger=EvidenceLedger(client)
        foreign_run=await ledger.create_analysis_run(
            "r1-isolation","r1",profile_id=foreign_profile,
        )
        foreign_snapshot=await ledger.create_export_snapshot(
            foreign_run,"manual_import",profile_id=foreign_profile,
        )
        payload=b"foreign profile evidence"
        source=tmp_path/"foreign.txt"
        source.write_bytes(payload)
        _,foreign_artifact=await ledger.record_source_artifact(
            foreign_snapshot,payload,storage_uri=source.resolve().as_uri(),
            original_path=source.name,file_name=source.name,
        )
        specialist_id=await connection.fetchval(
            """INSERT INTO specialist_task_requests
               (analysis_run_id,artifact_id,task_key,input_manifest)
               VALUES($1,$2,'document.ocr','{}') RETURNING id""",
            foreign_run,foreign_artifact,
        )

        await _require_owned_inputs(
            owner_profile,request_id=request_id,received_data_id=received_data_id,
        )
        failures=[]
        for identifier in (foreign_run,uuid4()):
            with pytest.raises(HTTPException) as caught:
                await _require_owned_inputs(owner_profile,analysis_run_id=identifier)
            failures.append((caught.value.status_code,caught.value.detail))
        assert failures==[
            (404,"ingestion resource not found"),(404,"ingestion resource not found"),
        ]

        with pytest.raises(HTTPException) as progress_error:
            await run_progress(foreign_run,owner_profile)
        assert (progress_error.value.status_code,progress_error.value.detail)==(
            404,"ingestion run not found",
        )
        with pytest.raises(HTTPException) as specialist_error:
            await specialist_result(SpecialistResultBody(
                specialist_request_id=specialist_id,status="completed",output={"text":"leak"},
            ),owner_profile)
        assert (specialist_error.value.status_code,specialist_error.value.detail)==(
            404,"specialist request not found",
        )
        assert await connection.fetchval(
            "SELECT status FROM specialist_task_requests WHERE id=$1",specialist_id,
        )=="pending"

        # A legacy/caller-supplied profile field is ignored; authority is dependency-derived.
        parsed=ProcessFileBody(file_path="x",profile_id=str(foreign_profile))
        assert "profile_id" not in parsed.model_dump()
    finally:
        await client.close()
        await connection.close()
