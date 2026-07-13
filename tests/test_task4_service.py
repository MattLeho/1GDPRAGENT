from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import asyncpg
import pytest

from db.postgres import PostgresClient
from ingestion.events import write_activity_events
from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.models import InsightComparisonPeriod, InsightPeriod, PeriodGranularity, TemporalMode
from insights.materialization import materialisation_cache_key
from insights.repository import InsightRepository
from insights.service import SNAPSHOT_VERSION
from insights.service import InsightService
from test_task1_database_integration import migrated_database


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def event(kind: str, at: datetime, *, action=ActionClass.OTHER, service="fixture", topic=None, value=None):
    event_id = uuid4()
    return ActivityEvent(
        event_id=event_id, record_signature=event_id.hex * 2, subject_id="subject-1",
        export_snapshot_id=uuid4(), artifact_id=uuid4(), service=service,
        data_domain="ai_conversation" if "authored" in kind or "assistant" in kind else ("search" if action is ActionClass.SEARCHED else "email"),
        event_type=kind, action_class=action, occurred_at=at,
        temporal_precision=TemporalPrecision.SECOND, object_value=value,
        relationships={"topic_labels":[topic]} if topic else {},
        parser_id="fixture", parser_version="1", source_locator_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_snapshot_is_one_scan_cached_and_enforces_signal_hierarchy(migrated_database, tmp_path):
    url, request_id, _ = migrated_database
    connection = await asyncpg.connect(url)
    client = PostgresClient(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('task4-snapshot',$1,'running','task4-v1') RETURNING id",
            request_id,
        )
        events = []
        for index in range(110):
            events.append(event("newsletter_received", START + timedelta(minutes=index), topic="ambient-only"))
        events.extend((
            event("query", START + timedelta(days=12), action=ActionClass.SEARCHED, service="browser", topic="one-curiosity", value={"query":"isolated secret"}),
            event("query", START + timedelta(days=15), action=ActionClass.SEARCHED, service="browser", topic="robotics", value={"query":"robot motor"}),
            event("query", START + timedelta(days=16), action=ActionClass.SEARCHED, service="search", topic="robotics", value={"query":"robot motor control"}),
            event("query", START + timedelta(days=17), action=ActionClass.SEARCHED, service="docs", topic="robotics", value={"query":"robot motor control code"}),
            event("assistant_generated", START + timedelta(days=18), topic="assistant-only", value={"role":"assistant","text":"secret"}),
            event("user_authored", START + timedelta(days=19), topic="robotics", value={"role":"user","text":"secret"}),
            event("file_created", START + timedelta(days=20), action=ActionClass.CREATED, topic="robotics"),
            event("code_committed", START + timedelta(days=21), action=ActionClass.CODED, topic="robotics"),
        ))
        written = write_activity_events(tmp_path, events, analysis_run_id=run_id, partition_key="fixture")
        await connection.execute(
            """INSERT INTO event_partitions
            (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
            VALUES($1,$2,'events/fixture',$3,$4,$5,$6,$7,$8,$9)""",
            written.event_partition.partition_id,run_id,str(written.event_partition.path),
            written.event_partition.file_hash,written.event_partition.schema_version,
            written.event_partition.row_count,written.event_partition.min_occurred_at,
            written.event_partition.max_occurred_at,written.event_partition.byte_size,
        )
        assertion_id=await connection.fetchval(
            """INSERT INTO assertions
            (subject_type,subject_ref,predicate,object_type,object_value,assertion_type,data_class,
             status,epistemic_basis,confidence,ingested_at,derivation_method,derivation_version,analysis_run_id)
            VALUES('Person','subject-1','interest topic robotics','literal','\"robotics\"'::jsonb,
                   'classification','declared','accepted','human_confirmed',1,NOW(),'fixture','1',$1)
            RETURNING id""",run_id,
        )
        state_id=await connection.fetchval(
            """INSERT INTO temporal_states
            (analysis_run_id,subject_id,history_type,state_type,state_key,valid_from,valid_to,
             dimensions,evidence_event_ids,detector_id,detector_version)
            VALUES($1,'subject-1','personal_behavioural','engagement_profile','robotics',$2,$3,
                   '{"investigation":3}'::jsonb,'[]'::jsonb,'fixture','1') RETURNING id""",
            run_id,START,START+timedelta(days=30),
        )
        aggregate_id=await connection.fetchval(
            """INSERT INTO temporal_aggregates
            (analysis_run_id,subject_id,history_type,aggregate_type,aggregate_key,window_start,window_end,
             values,source_event_count,detector_id,detector_version)
            VALUES($1,'subject-1','personal_behavioural','engagement_profile','all-actions',$2,$3,
                   '{"investigation":3}'::jsonb,3,'fixture','1') RETURNING id""",
            run_id,START,START+timedelta(days=30),
        )
        service = InsightService(client)
        period = InsightPeriod(
            mode=TemporalMode.PERIOD,granularity=PeriodGranularity.WEEK,
            from_at=START,to_at=START + timedelta(days=30),
        )
        cold = await service.get_snapshot(subject_id="subject-1",period=period)
        warm = await service.get_snapshot(subject_id="subject-1",period=period)
        assert cold == warm
        repository=InsightRepository(connection)
        partitions=await repository.discover_event_partitions(from_at=period.from_at,to_at=period.to_at)
        source_tokens=tuple(item.file_hash for item in partitions)+await repository.dependency_tokens(subject_id="subject-1",from_at=period.from_at,to_at=period.to_at)
        cache_key=materialisation_cache_key(
            subject_id="subject-1",period=period,comparison=None,module_key="snapshot",
            partition_hashes=source_tokens,derivation_version=SNAPSHOT_VERSION,
        )
        independently_rebuilt=await service._build_snapshot(
            repository=repository,connection=connection,subject_id="subject-1",period=period,
            comparison=None,partitions=partitions,baseline_partitions=(),cache_key=cache_key,
            source_tokens=source_tokens,
        )
        assert independently_rebuilt==cold
        assert cold.overview.total_event_count == len(events)
        assert cold.overview.engagement.ambient_exposure == 111  # newsletter + assistant output
        assert len(cold.overview.engagement.evidence)==100
        assert cold.overview.engagement.calculated_features["evidence_reference_count"]==120
        indexed_engagement=await connection.fetchval(
            "SELECT count(*) FROM insight_evidence_index WHERE insight_id=$1",cold.overview.engagement.insight_id,
        )
        assert indexed_engagement==120
        assert cold.overview.engagement.creation == 1
        assert cold.overview.engagement.implementation == 1
        topic_ids = {item.topic_id for item in cold.interests}
        assert "robotics" in topic_ids
        assert "ambient-only" not in topic_ids
        assert "assistant-only" not in topic_ids
        assert "one-curiosity" not in topic_ids
        assert cold.canonical_source_counts["accepted_assertions"] == 1
        assert cold.canonical_source_counts["temporal_states"] == 1
        assert cold.canonical_source_counts["temporal_aggregates"] == 1
        robotics=next(item for item in cold.interests if item.topic_id=="robotics")
        assert any(ref.kind.value=="assertion" and ref.ref_id==assertion_id for ref in robotics.evidence)
        assert await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM insight_evidence_index WHERE insight_id=$1 AND evidence_kind='temporal_state' AND evidence_ref_id=$2)",
            cold.overview.engagement.insight_id,state_id,
        )
        assert await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM insight_evidence_index WHERE insight_id=$1 AND evidence_kind='temporal_aggregate' AND evidence_ref_id=$2)",
            cold.overview.engagement.insight_id,aggregate_id,
        )
        assert cold.search.abandoned_one_offs == 1
        assert "isolated secret" not in cold.model_dump_json()
        assert await connection.fetchval("SELECT count(*) FROM insight_materialisations WHERE subject_id='subject-1'") == 1
        assert await connection.fetchval("SELECT count(*) FROM insight_evidence_index") > 0
    finally:
        await client.close()
        await connection.close()


@pytest.mark.asyncio
async def test_compare_mode_calculates_one_coherent_period_delta(migrated_database, tmp_path):
    url, request_id, _ = migrated_database
    connection = await asyncpg.connect(url)
    client = PostgresClient(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('task4-compare',$1,'running','task4-v1') RETURNING id",
            request_id,
        )
        baseline_events = tuple(event("query", START + timedelta(days=index), action=ActionClass.SEARCHED, topic="robotics", value={"query":f"robot {index}"}) for index in range(6)) + tuple(
            event("query",START+timedelta(days=10+index),action=ActionClass.SEARCHED,topic="legacy-topic",value={"query":f"legacy topic {index}"}) for index in range(3)
        )
        current_events = tuple(event("query", START + timedelta(days=35+index), action=ActionClass.SEARCHED, topic="robotics", value={"query":f"robot return {index}"}) for index in range(3))
        for key, rows in (("baseline", baseline_events), ("current", current_events)):
            written = write_activity_events(tmp_path / key, rows, analysis_run_id=run_id, partition_key=key)
            await connection.execute(
                """INSERT INTO event_partitions
                (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                written.event_partition.partition_id,run_id,f"events/{key}",str(written.event_partition.path),
                written.event_partition.file_hash,written.event_partition.schema_version,
                written.event_partition.row_count,written.event_partition.min_occurred_at,
                written.event_partition.max_occurred_at,written.event_partition.byte_size,
            )
        current = InsightPeriod(mode=TemporalMode.COMPARE,granularity=PeriodGranularity.MONTH,from_at=START+timedelta(days=31),to_at=START+timedelta(days=60))
        baseline = InsightPeriod(mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,from_at=START,to_at=START+timedelta(days=30))
        comparison = InsightComparisonPeriod(current=current,baseline=baseline)
        snapshot = await InsightService(client).get_snapshot(subject_id="subject-1",period=current,comparison=comparison)
        assert snapshot.comparison == comparison
        assert snapshot.overview.engagement.comparison_delta["active_investigation"] == -6.0
        assert snapshot.overview.total_event_count == 3
        robotics=next(item for item in snapshot.interests if item.topic_id=="robotics")
        assert robotics.previous_period_dimensions
        assert set(robotics.comparison_delta)=={"intensity","persistence","recurrence","breadth","novelty","context_dispersion"}
        assert any(item.change_type=="DECLINING" and item.state_key=="legacy-topic" for item in snapshot.changes)
    finally:
        await client.close()
        await connection.close()


@pytest.mark.asyncio
async def test_late_import_is_placed_by_occurrence_time_through_service_api(migrated_database,tmp_path):
    url,request_id,_=migrated_database
    connection=await asyncpg.connect(url);client=PostgresClient(url)
    try:
        run_id=await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('late-import',$1,'running','task4-v2') RETURNING id",
            request_id,
        )
        occurred=datetime(2018,5,1,tzinfo=timezone.utc)
        late_event=event("file_created",occurred,action=ActionClass.CREATED,topic="historical-project")
        written=write_activity_events(tmp_path,(late_event,),analysis_run_id=run_id,partition_key="late")
        await connection.execute(
            """INSERT INTO event_partitions
            (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
            VALUES($1,$2,'events/late',$3,$4,$5,$6,$7,$8,$9)""",
            written.event_partition.partition_id,run_id,str(written.event_partition.path),
            written.event_partition.file_hash,written.event_partition.schema_version,written.event_partition.row_count,
            written.event_partition.min_occurred_at,written.event_partition.max_occurred_at,written.event_partition.byte_size,
        )
        historical=InsightPeriod(mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,
                                 from_at=datetime(2018,5,1,tzinfo=timezone.utc),to_at=datetime(2018,6,1,tzinfo=timezone.utc))
        recent=InsightPeriod(mode=TemporalMode.PERIOD,granularity=PeriodGranularity.YEAR,
                             from_at=datetime(2026,1,1,tzinfo=timezone.utc),to_at=datetime(2027,1,1,tzinfo=timezone.utc))
        service=InsightService(client)
        old_snapshot=await service.get_snapshot(subject_id="subject-1",period=historical)
        new_snapshot=await service.get_snapshot(subject_id="subject-1",period=recent)
        assert old_snapshot.overview.total_event_count==1
        assert {item.topic_id for item in old_snapshot.interests}=={"historical-project"}
        assert new_snapshot.overview.total_event_count==0
    finally:
        await client.close();await connection.close()


@pytest.mark.asyncio
async def test_snapshot_reuses_only_unchanged_density_buckets_after_partition_invalidation(migrated_database,tmp_path):
    url,request_id,_=migrated_database
    connection=await asyncpg.connect(url);client=PostgresClient(url)
    try:
        run_id=await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('selective-buckets',$1,'running','task4-v2') RETURNING id",
            request_id,
        )
        async def add_partition(key,rows):
            written=write_activity_events(tmp_path/key,rows,analysis_run_id=run_id,partition_key=key)
            await connection.execute(
                """INSERT INTO event_partitions
                (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                written.event_partition.partition_id,run_id,f"events/{key}",str(written.event_partition.path),
                written.event_partition.file_hash,written.event_partition.schema_version,written.event_partition.row_count,
                written.event_partition.min_occurred_at,written.event_partition.max_occurred_at,written.event_partition.byte_size,
            )
        await add_partition("early",(event("query",START+timedelta(days=1),action=ActionClass.SEARCHED,topic="early"),))
        period=InsightPeriod(mode=TemporalMode.PERIOD,granularity=PeriodGranularity.WEEK,
                             from_at=START,to_at=START+timedelta(days=28))
        service=InsightService(client)
        first=await service.get_snapshot(subject_id="subject-1",period=period)
        await add_partition("late",(event("query",START+timedelta(days=16),action=ActionClass.SEARCHED,topic="late"),))
        second=await service.get_snapshot(subject_id="subject-1",period=period)
        assert first.overview.total_event_count==1
        assert second.overview.total_event_count==2
        rows=await connection.fetch(
            """SELECT b.bucket_start,b.values,b.source_event_count
               FROM insight_aggregate_buckets b
               JOIN insight_materialisations m ON m.id=b.materialisation_id
               WHERE m.subject_id='subject-1' AND m.module_key='snapshot'
                 AND m.id=(SELECT id FROM insight_materialisations WHERE subject_id='subject-1' AND module_key='snapshot' ORDER BY created_at DESC,id DESC LIMIT 1)
               ORDER BY b.bucket_start"""
        )
        decoded=[json.loads(row["values"]) if isinstance(row["values"],str) else dict(row["values"]) for row in rows]
        assert len(rows)==len(second.overview.density)==5
        assert "reused_from_materialisation_id" in decoded[0]
        assert "reused_from_materialisation_id" in decoded[1]
        assert "reused_from_materialisation_id" not in decoded[2]
        assert rows[2]["source_event_count"]==1
        assert "reused_from_materialisation_id" in decoded[3]
        assert "reused_from_materialisation_id" in decoded[4]
    finally:
        await client.close();await connection.close()


@pytest.mark.asyncio
async def test_return_after_nine_months_is_detected_without_prior_task4_query(migrated_database,tmp_path):
    url,request_id,_=migrated_database
    connection=await asyncpg.connect(url);client=PostgresClient(url)
    try:
        run_id=await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('returning-topic',$1,'running','task4-v2') RETURNING id",
            request_id,
        )
        prior=event("file_created",datetime(2024,1,1,tzinfo=timezone.utc),action=ActionClass.CREATED,topic="robotics")
        current=tuple(event("file_created",datetime(2024,10,1+index,tzinfo=timezone.utc),action=ActionClass.CREATED,topic="robotics") for index in range(2))
        for key,rows in (("prior",(prior,)),("current",current)):
            written=write_activity_events(tmp_path/key,rows,analysis_run_id=run_id,partition_key=key)
            await connection.execute(
                """INSERT INTO event_partitions
                (id,analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
                written.event_partition.partition_id,run_id,f"events/{key}",str(written.event_partition.path),
                written.event_partition.file_hash,written.event_partition.schema_version,written.event_partition.row_count,
                written.event_partition.min_occurred_at,written.event_partition.max_occurred_at,written.event_partition.byte_size,
            )
        period=InsightPeriod(mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,
                             from_at=datetime(2024,10,1,tzinfo=timezone.utc),to_at=datetime(2024,11,1,tzinfo=timezone.utc))
        snapshot=await InsightService(client).get_snapshot(subject_id="subject-1",period=period)
        assert snapshot.interests[0].topic_id=="robotics"
        assert snapshot.interests[0].change=="returning"
    finally:
        await client.close();await connection.close()
