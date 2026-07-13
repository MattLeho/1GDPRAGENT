from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest

from execution import adapters as engine_adapters
from ingestion.events import write_activity_events
from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.materialization import PeriodMaterializer, benchmark_cold_warm
from insights.media import visual_task_requests
from insights.models import (
    InsightComparisonPeriod,
    InsightPeriod,
    MediaAnalysisMode,
    PeriodGranularity,
    TemporalMode,
)
from insights.repository import EventPartition, InsightRepository


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)
NAMESPACE = UUID("cbdf6d5c-0277-5125-8ed4-6fc43d373b28")
PARQUET_AVAILABLE = all(
    importlib.util.find_spec(package) is not None for package in ("pyarrow", "polars")
)


def _event(index: int, analysis_run_id: UUID) -> ActivityEvent:
    event_id = uuid5(NAMESPACE, f"event:{index}")
    return ActivityEvent(
        event_id=event_id,
        record_signature=uuid5(NAMESPACE, f"signature:{index}").hex * 2,
        subject_id="subject-1",
        export_snapshot_id=uuid5(NAMESPACE, f"snapshot:{analysis_run_id}"),
        artifact_id=uuid5(NAMESPACE, f"artifact:{index}"),
        service="synthetic",
        product="task4-performance-fixture",
        data_domain="activity",
        event_type="fixture.view",
        action_class=ActionClass.CONSUMED,
        occurred_at=START + timedelta(hours=index % (24 * 14), microseconds=index),
        occurred_at_original=(START + timedelta(hours=index % (24 * 14))).isoformat(),
        temporal_precision=TemporalPrecision.SECOND,
        timezone="UTC",
        timezone_evidence="explicit_offset",
        object_type="fixture-record",
        object_id=str(index),
        object_value={"index": index},
        parser_id="fixture.parser",
        parser_version="1",
        source_locator_id=uuid5(NAMESPACE, f"locator:{index}"),
    )


class _ParquetRepository(InsightRepository):
    """Small in-memory cache around the real repository Parquet reader."""

    def __init__(self, partition: EventPartition) -> None:
        super().__init__(connection=None)
        self.partition = partition
        self.cached: dict | None = None
        self.parquet_loads = 0
        self.persisted_bucket_count = 0
        self.persisted_evidence_count = 0

    async def discover_event_partitions(self, **_kwargs):
        return (self.partition,)

    async def cached_payload(self, cache_key, derivation_version):
        if self.cached is None:
            return None
        if (cache_key, derivation_version) != self.cached["identity"]:
            return None
        return {
            "materialisation_id": self.cached["materialisation_id"],
            "payload": self.cached["payload"],
        }

    def load_activity_events(self, *args, **kwargs):
        self.parquet_loads += 1
        return super().load_activity_events(*args, **kwargs)

    async def persist_materialisation(self, **kwargs):
        materialisation_id = uuid4()
        self.cached = {
            "identity": (kwargs["cache_key"], kwargs["derivation_version"]),
            "materialisation_id": materialisation_id,
            "payload": kwargs["payload"],
        }
        return materialisation_id

    async def persist_aggregate_buckets(self, _materialisation_id, **kwargs):
        rows = tuple(kwargs["buckets"])
        self.persisted_bucket_count += len(rows)
        return len(rows)

    async def persist_evidence_index(self, _materialisation_id, _insight_id, evidence):
        rows = tuple(evidence)
        self.persisted_evidence_count += len(rows)
        return len(rows)


def _period(*, mode: TemporalMode = TemporalMode.PERIOD) -> InsightPeriod:
    return InsightPeriod(
        mode=mode,
        granularity=PeriodGranularity.DAY,
        from_at=START,
        to_at=START + timedelta(days=14),
    )


def _synthetic_partition(tmp_path: Path, *, event_count: int = 500) -> EventPartition:
    run_id = uuid5(NAMESPACE, "analysis-run")
    result = write_activity_events(
        tmp_path / "lake",
        (_event(index, run_id) for index in range(event_count)),
        analysis_run_id=run_id,
        partition_key="task4-performance",
        observed_at=START + timedelta(days=15),
    )
    record = result.event_partition
    return EventPartition(
        partition_id=record.partition_id,
        analysis_run_id=record.analysis_run_id,
        storage_uri=record.path,
        file_hash=record.file_hash,
        min_occurred_at=record.min_occurred_at,
        max_occurred_at=record.max_occurred_at,
        row_count=record.row_count,
    )


@pytest.mark.skipif(not PARQUET_AVAILABLE, reason="Task 4 Parquet benchmark dependencies are not installed")
@pytest.mark.asyncio
async def test_real_parquet_cold_warm_materialisation_is_reproducible_and_warm_avoids_scan(tmp_path):
    partition = _synthetic_partition(tmp_path)
    repository = _ParquetRepository(partition)
    materializer = PeriodMaterializer(repository)

    report = await benchmark_cold_warm(
        lambda _warm: materializer.materialize_activity_density(
            subject_id="subject-1", period=_period()
        )
    )

    cold, warm = report.cold_value, report.warm_value
    assert cold.cache_hit is False and warm.cache_hit is True
    assert cold.payload == warm.payload
    assert cold.cache_key == warm.cache_key and cold.insight_id == warm.insight_id
    assert repository.parquet_loads == 1
    assert repository.persisted_evidence_count == 500
    assert repository.persisted_bucket_count > 0
    assert report.cold_seconds >= 0 and report.warm_seconds >= 0
    print("TASK4_PERIOD_BENCHMARK " + json.dumps({
        "events": 500,
        "cold_seconds": report.cold_seconds,
        "warm_seconds": report.warm_seconds,
        "parquet_scans": repository.parquet_loads,
        "payload_event_count": cold.payload["event_count"],
    }, sort_keys=True))

    # A separate cold materialisation over the same immutable partition must
    # reproduce the cache identity and API payload byte-for-byte.
    independent = await PeriodMaterializer(_ParquetRepository(partition)).materialize_activity_density(
        subject_id="subject-1", period=_period()
    )
    assert independent.cache_key == cold.cache_key
    assert independent.insight_id == cold.insight_id
    assert independent.payload == cold.payload


@pytest.mark.skipif(not PARQUET_AVAILABLE, reason="Task 4 Parquet benchmark dependencies are not installed")
@pytest.mark.asyncio
async def test_compare_selection_changes_cache_identity_and_period_timing_is_reported(tmp_path):
    partition = _synthetic_partition(tmp_path, event_count=50)
    current = _period(mode=TemporalMode.COMPARE)
    baseline_one = InsightPeriod(
        mode=TemporalMode.PERIOD,
        granularity=PeriodGranularity.DAY,
        from_at=START - timedelta(days=14),
        to_at=START,
    )
    baseline_two = baseline_one.model_copy(
        update={"from_at": START - timedelta(days=28), "to_at": START - timedelta(days=14)}
    )

    first = await PeriodMaterializer(_ParquetRepository(partition)).materialize_activity_density(
        subject_id="subject-1",
        period=current,
        comparison=InsightComparisonPeriod(current=current, baseline=baseline_one),
    )
    second_repository = _ParquetRepository(partition)
    timed = await benchmark_cold_warm(
        lambda _warm: PeriodMaterializer(second_repository).materialize_activity_density(
            subject_id="subject-1",
            period=current,
            comparison=InsightComparisonPeriod(current=current, baseline=baseline_two),
        )
    )

    assert first.cache_key != timed.cold_value.cache_key
    assert timed.cold_value.cache_key == timed.warm_value.cache_key
    assert timed.cold_seconds >= 0 and timed.warm_seconds >= 0
    assert second_repository.parquet_loads == 1


def test_metadata_default_and_selective_planning_make_zero_provider_or_external_calls(monkeypatch, tmp_path):
    calls = {"network": 0, "process": 0}

    def forbidden_network(*_args, **_kwargs):
        calls["network"] += 1
        raise AssertionError("media planning attempted a network/provider call")

    def forbidden_process(*_args, **_kwargs):
        calls["process"] += 1
        raise AssertionError("media planning attempted an external process")

    monkeypatch.setattr(engine_adapters, "urlopen", forbidden_network)
    monkeypatch.setattr(engine_adapters.subprocess, "run", forbidden_process)
    artifact_id, locator_id = uuid4(), uuid4()

    assert visual_task_requests(artifact_id, locator_id) == ()
    selective = visual_task_requests(
        artifact_id, locator_id, MediaAnalysisMode.SELECTIVE_VISUAL
    )
    assert {item.task_key for item in selective} == {
        "image.origin_classification",
    }
    assert calls == {"network": 0, "process": 0}

    # The deterministic selective route is local in-process too. Running it
    # proves that origin classification does not silently fall through to a
    # provider when selective work is explicitly requested.
    pytest.importorskip("PIL")
    from PIL import Image

    image_path = tmp_path / "Screenshot 2025-01-01.png"
    Image.new("RGB", (32, 20), "white").save(image_path)
    result = engine_adapters.invoke_engine(
        "deterministic_image_origin",
        "image.origin_classification",
        {"file_path": str(image_path)},
        None,
        {},
    )
    assert result["origin"] == "screenshot"
    assert result["physical_presence_supported"] is False
    assert calls == {"network": 0, "process": 0}
