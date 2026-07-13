from __future__ import annotations

import json
from uuid import uuid4

import asyncpg
import pytest

from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from test_task1_database_integration import migrated_database


@pytest.mark.asyncio
async def test_task5_schema_enforces_dry_run_uncertain_and_capability_safety(migrated_database):
    url, request_id, file_id = migrated_database
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            """INSERT INTO source_connector_definitions
            (connector_key,definition_version,display_name,provider,connector_type,modes,data_classes,permissions)
            VALUES('synthetic.fixture','1','Synthetic','local','synthetic',$1::jsonb,$2::jsonb,$3::jsonb)""",
            json.dumps(["snapshot_import"]), json.dumps(["fixture"]), json.dumps([]),
        )
        connector_id = await connection.fetchval(
            """INSERT INTO connector_instances(connector_key,definition_version,display_name,status)
            VALUES('synthetic.fixture','1','Fixture','connected') RETURNING id"""
        )
        run_id = await connection.fetchval(
            """INSERT INTO analysis_runs(run_type,status,pipeline_version,configuration)
            VALUES('task5_contract','running','1','{}') RETURNING id"""
        )
        client = PostgresClient(url)
        ledger = EvidenceLedger(client)
        snapshot_id = await ledger.create_export_snapshot(
            run_id, "manual_import", request_id=request_id,
        )
        _, artifact_id = await ledger.record_source_artifact(
            snapshot_id, b"task5 fixture", storage_uri="fixture://task5",
            original_path="task5-fixture.txt", file_name="task5-fixture.txt",
        )
        await client.close()
        policy_id = await connection.fetchval(
            """INSERT INTO retention_policies(name,action)
            VALUES('Review uncertain','review_only') RETURNING id"""
        )
        decision_id = await connection.fetchval(
            """INSERT INTO retention_decisions
            (source_artifact_id,classification,deterministic_evidence,confidence,policy_id,policy_version,analysis_run_id)
            VALUES($1,'UNSURE','{}',0,$2,1,$3) RETURNING id""",
            artifact_id, policy_id, run_id,
        )
        plan = await connection.fetchrow(
            """INSERT INTO deletion_plans(policy_id,policy_version,analysis_run_id)
            VALUES($1,1,$2) RETURNING id,dry_run""", policy_id, run_id,
        )
        assert plan["dry_run"] is True
        with pytest.raises(asyncpg.CheckViolationError):
            await connection.execute(
                """INSERT INTO deletion_plan_items
                (deletion_plan_id,source_artifact_id,retention_decision_id,item_group,action,reasons,stage)
                VALUES($1,$2,$3,'uncertain','local_purge','[\"ambiguous\"]','eligible_for_delete')""",
                plan["id"], artifact_id, decision_id,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await connection.execute(
                """INSERT INTO deletion_plan_items
                (deletion_plan_id,source_artifact_id,retention_decision_id,item_group,action,reasons,source_delete_capability)
                VALUES($1,$2,$3,'eligible','source_delete','[\"fixture\"]',false)""",
                plan["id"], artifact_id, decision_id,
            )
        item_id = await connection.fetchval(
            """INSERT INTO deletion_plan_items
            (deletion_plan_id,source_artifact_id,retention_decision_id,item_group,action,reasons)
            VALUES($1,$2,$3,'uncertain','controller_erasure_candidate','[\"review\"]') RETURNING id""",
            plan["id"], artifact_id, decision_id,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await connection.execute(
                """INSERT INTO controller_erasure_candidates
                (deletion_plan_item_id,controller_key,review_status,automatic_execution_enabled)
                VALUES($1,'fixture-controller','pending',true)""", item_id,
            )
        assert connector_id
    finally:
        await connection.close()
