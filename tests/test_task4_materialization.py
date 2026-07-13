from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import asyncpg

from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.materialization import (
    activity_density_buckets, affected_bucket_starts, benchmark_cold_warm,
    floor_bucket, materialisation_cache_key, PeriodMaterializer,
)
from insights.models import InsightPeriod, PeriodGranularity, TemporalMode
from insights.repository import EventPartition
from insights.repository import InsightRepository
from test_task1_database_integration import migrated_database


UTC = timezone.utc
START = datetime(2025, 1, 1, 12, tzinfo=UTC)


def _event(at: datetime) -> ActivityEvent:
    event_id = uuid4()
    return ActivityEvent(event_id=event_id, record_signature=event_id.hex * 2,
        subject_id="subject-1", export_snapshot_id=uuid4(), artifact_id=uuid4(),
        data_domain="fixture", event_type="query", action_class=ActionClass.SEARCHED,
        occurred_at=at, temporal_precision=TemporalPrecision.SECOND,
        parser_id="fixture", parser_version="1", source_locator_id=uuid4())


@pytest.mark.parametrize(("granularity", "expected"), [
    (PeriodGranularity.DAY, datetime(2025, 1, 1, tzinfo=UTC)),
    (PeriodGranularity.WEEK, datetime(2024, 12, 30, tzinfo=UTC)),
    (PeriodGranularity.MONTH, datetime(2025, 1, 1, tzinfo=UTC)),
    (PeriodGranularity.QUARTER, datetime(2025, 1, 1, tzinfo=UTC)),
    (PeriodGranularity.YEAR, datetime(2025, 1, 1, tzinfo=UTC)),
])
def test_calendar_bucket_floor(granularity, expected):
    assert floor_bucket(START, granularity) == expected


def test_density_scans_events_once_and_emits_empty_calendar_buckets():
    events = (_event(START), _event(START + timedelta(days=2)))
    bins = activity_density_buckets(events, from_at=START, to_at=START + timedelta(days=3),
                                    granularity=PeriodGranularity.DAY)
    assert [item.event_count for item in bins] == [1, 0, 1, 0]
    assert sum(item.event_count for item in bins) == 2
    assert set(bins[0].evidence_event_ids) == {events[0].event_id}


def test_cache_key_is_versioned_partition_and_compare_sensitive():
    period = InsightPeriod(mode=TemporalMode.PERIOD, granularity=PeriodGranularity.MONTH,
                           from_at=START, to_at=START + timedelta(days=31))
    first = materialisation_cache_key(subject_id="s", period=period, module_key="overview",
                                      partition_hashes=("b" * 64, "a" * 64))
    reordered = materialisation_cache_key(subject_id="s", period=period, module_key="overview",
                                          partition_hashes=("a" * 64, "b" * 64))
    changed = materialisation_cache_key(subject_id="s", period=period, module_key="overview",
                                        partition_hashes=("a" * 64, "c" * 64))
    assert first == reordered and first != changed


def test_affected_partition_recompute_is_bucket_scoped():
    partition = EventPartition(uuid4(), uuid4(), "/lake/a.parquet", "a" * 64,
                               START + timedelta(days=2), START + timedelta(days=3), 20)
    starts = affected_bucket_starts((partition,), from_at=START, to_at=START + timedelta(days=10),
                                    granularity=PeriodGranularity.DAY)
    assert starts == (datetime(2025, 1, 3, tzinfo=UTC), datetime(2025, 1, 4, tzinfo=UTC))


@pytest.mark.asyncio
async def test_cold_warm_benchmark_helper_preserves_results():
    calls = []
    async def loader(warm):
        calls.append(warm); return {"warm": warm}
    result = await benchmark_cold_warm(loader)
    assert calls == [False, True]
    assert result.cold_value == {"warm": False} and result.warm_value == {"warm": True}
    assert result.cold_seconds >= 0 and result.warm_seconds >= 0


@pytest.mark.asyncio
async def test_period_materializer_single_scan_then_immutable_warm_cache():
    events = (_event(START), _event(START + timedelta(days=1)))
    partition = EventPartition(uuid4(), uuid4(), "/lake/events.parquet", "d" * 64,
                               START, START + timedelta(days=1), 2)
    class Repository:
        def __init__(self):
            self.cached = None; self.scans = 0; self.bucket_rows = 0; self.evidence_rows = 0
        async def discover_event_partitions(self, **kwargs): return (partition,)
        async def cached_payload(self, key, version): return self.cached
        def load_activity_events(self, *args, **kwargs): self.scans += 1; return events
        async def persist_materialisation(self, **kwargs):
            self.cached = {"materialisation_id": uuid4(), "payload": kwargs["payload"]}
            return self.cached["materialisation_id"]
        async def persist_aggregate_buckets(self, materialisation_id, **kwargs):
            rows = tuple(kwargs["buckets"]); self.bucket_rows += len(rows); return len(rows)
        async def persist_evidence_index(self, materialisation_id, insight_id, evidence):
            rows = tuple(evidence); self.evidence_rows += len(rows); return len(rows)
    repository = Repository()
    period = InsightPeriod(mode=TemporalMode.PERIOD, granularity=PeriodGranularity.DAY,
                           from_at=START, to_at=START + timedelta(days=2))
    materializer = PeriodMaterializer(repository)
    cold = await materializer.materialize_activity_density(subject_id="subject-1", period=period)
    warm = await materializer.materialize_activity_density(subject_id="subject-1", period=period)
    assert cold.cache_hit is False and warm.cache_hit is True
    assert cold.payload == warm.payload and repository.scans == 1
    assert repository.bucket_rows > 0 and repository.evidence_rows == 2


@pytest.mark.asyncio
async def test_repository_prunes_partitions_and_keeps_cache_immutable(migrated_database):
    url, request_id, _ = migrated_database
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('insights',$1,'running','task4-v1') RETURNING id",
            request_id,
        )
        for offset, file_hash in ((-10, "a" * 64), (0, "b" * 64), (10, "c" * 64)):
            await connection.execute(
                """INSERT INTO event_partitions
                   (analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
                   VALUES($1,$2,$3,$4,'activity-event-v1',1,$5,$6,10)""",
                run_id, f"events/{offset}", f"/lake/{offset}.parquet", file_hash,
                START + timedelta(days=offset), START + timedelta(days=offset + 1),
            )
        await connection.execute(
            """INSERT INTO event_partitions
               (analysis_run_id,partition_key,storage_uri,file_hash,schema_version,row_count,min_occurred_at,max_occurred_at,byte_size)
               VALUES($1,'observations/0','/lake/observations.parquet',$2,'activity-event-observation-v1',1,$3,$4,10)""",
            run_id, "d" * 64, START, START + timedelta(days=1),
        )
        repository = InsightRepository(connection)
        partitions = await repository.discover_event_partitions(
            from_at=START, to_at=START + timedelta(days=2), analysis_run_ids=(run_id,),
        )
        assert [item.file_hash for item in partitions] == ["b" * 64]
        period = InsightPeriod(mode=TemporalMode.PERIOD, granularity=PeriodGranularity.DAY,
                               from_at=START, to_at=START + timedelta(days=2))
        cache_key = materialisation_cache_key(subject_id="subject-1", period=period,
                                              module_key="fixture", partition_hashes=("b" * 64,))
        first = await repository.persist_materialisation(
            subject_id="subject-1", period=period, module_key="fixture", cache_key=cache_key,
            partition_hashes=("b" * 64,), payload={"value": 1},
            derivation_method="fixture", derivation_version="1", analysis_run_id=run_id,
        )
        second = await repository.persist_materialisation(
            subject_id="subject-1", period=period, module_key="fixture", cache_key=cache_key,
            partition_hashes=("b" * 64,), payload={"value": 1},
            derivation_method="fixture", derivation_version="1", analysis_run_id=run_id,
        )
        assert first == second
        with pytest.raises(ValueError, match="immutable"):
            await repository.persist_materialisation(
                subject_id="subject-1", period=period, module_key="fixture", cache_key=cache_key,
                partition_hashes=("b" * 64,), payload={"value": 2},
                derivation_method="fixture", derivation_version="1", analysis_run_id=run_id,
            )
    finally:
        await connection.close()
