from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import asyncpg
import pytest

from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from evidence.models import EvidenceLocatorCreate, LocatorType
from ingestion.events import write_activity_events
from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.models import InsightPeriod, PeriodGranularity, TemporalMode
from insights.service import InsightService
from test_task1_database_integration import migrated_database


@pytest.mark.asyncio
async def test_every_insight_evidence_link_resolves_to_source(migrated_database, tmp_path):
    url, request_id, _ = migrated_database
    client = PostgresClient(url)
    connection = await asyncpg.connect(url)
    try:
        ledger = EvidenceLedger(client)
        profile_id=await connection.fetchval(
            "INSERT INTO profiles(identity_name) VALUES('Evidence fixture') RETURNING id",
        )
        subject_id=str(profile_id)
        run_id = await ledger.create_analysis_run(
            "task4-evidence", "task4-v1", request_id=request_id,profile_id=profile_id,
        )
        snapshot_id = await ledger.create_export_snapshot(
            run_id, "manual_import", request_id=request_id,profile_id=profile_id,
        )
        source = {"records": [{"topic": "robotics", "action": "created"}]}
        content = json.dumps(source).encode()
        source_path = tmp_path / "source.json"
        source_path.write_bytes(content)
        _, artifact_id = await ledger.record_source_artifact(
            snapshot_id, content, storage_uri=source_path.resolve().as_uri(),
            original_path="source.json", file_name="source.json",
            declared_mime="application/json", detected_mime="application/json",
            extension=".json", file_type_status="matched",
        )
        locator_id = await ledger.create_locator(EvidenceLocatorCreate(
            artifact_id=artifact_id, locator_type=LocatorType.JSON_POINTER,
            locator={"pointer":"/records/0/topic"},
        ), content)
        occurred = datetime(2025, 4, 1, tzinfo=timezone.utc)
        event_id = uuid4()
        event = ActivityEvent(
            event_id=event_id, record_signature=event_id.hex * 2, subject_id=subject_id,
            export_snapshot_id=snapshot_id, artifact_id=artifact_id, service="fixture",
            data_domain="projects", event_type="created", action_class=ActionClass.CREATED,
            occurred_at=occurred, temporal_precision=TemporalPrecision.SECOND,
            relationships={"topic_labels":["robotics"]}, parser_id="fixture",
            parser_version="1", source_locator_id=locator_id,
        )
        written = write_activity_events(tmp_path / "lake", (event,), analysis_run_id=run_id, partition_key="evidence")
        await connection.execute(
            """INSERT INTO event_partitions
            (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
            VALUES($1,$2,'events/evidence',$3,$4,$5,$6,$7,$8,$9)""",
            written.event_partition.partition_id,run_id,str(written.event_partition.path),
            written.event_partition.file_hash,written.event_partition.schema_version,
            written.event_partition.row_count,written.event_partition.min_occurred_at,
            written.event_partition.max_occurred_at,written.event_partition.byte_size,
        )
        service = InsightService(client)
        period = InsightPeriod(
            mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,
            from_at=occurred-timedelta(days=1),to_at=occurred+timedelta(days=2),
        )
        result = await service.get_snapshot(subject_id=subject_id,period=period)
        assert result.interests
        trace = await service.trace_insight(result.interests[0].insight_id,profile_id=profile_id)
        assert trace.detector_id == result.interests[0].detector_id
        assert trace.detector_version == result.interests[0].detector_version
        assert trace.calculated_features == result.interests[0].calculated_features
        assert trace.time_window == (result.interests[0].window_start, result.interests[0].window_end)
        assert trace.activity_events[0]["event_id"] == str(event_id)
        assert trace.source_artifacts[0]["id"] == artifact_id
        assert trace.evidence_locators[0]["id"] == locator_id
        assert trace.evidence_locators[0]["resolvable"] is True
        assert trace.evidence_locators[0]["resolved_byte_count"] == len(b'"robotics"')
        for item in service._derived_items(result):
            if not item.evidence:
                continue
            item_trace=await service.trace_insight(item.insight_id,profile_id=profile_id)
            assert item_trace.detector_id==item.detector_id
            assert item_trace.detector_version==item.detector_version
            assert item_trace.calculated_features==item.calculated_features
            assert item_trace.activity_events
            assert item_trace.evidence_locators
            assert all(locator["resolvable"] is True for locator in item_trace.evidence_locators)
    finally:
        await client.close()
        await connection.close()
