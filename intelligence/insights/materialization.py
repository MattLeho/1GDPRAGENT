"""Period bucket construction and content-addressed Personal Insights caching."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from time import perf_counter
from typing import Any, Awaitable, Callable, Iterable
from uuid import UUID, uuid5

from ingestion.models import ActivityEvent
from insights.models import (
    ActivityDensityBin, EvidenceKind, InsightComparisonPeriod, InsightEvidenceRef,
    InsightPeriod, PeriodGranularity, TemporalMode,
)
from insights.repository import EventPartition


DERIVATION_METHOD = "task4.period-materialisation"
DERIVATION_VERSION = "1.0.0"
INSIGHT_NAMESPACE = UUID("d1aa4704-5904-59ef-927f-745330bce9ab")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def materialisation_cache_key(
    *, subject_id: str, period: InsightPeriod, module_key: str,
    partition_hashes: Iterable[str], derivation_version: str = DERIVATION_VERSION,
    comparison: InsightComparisonPeriod | None = None,
) -> str:
    payload = {
        "subject_id": subject_id, "period": period.model_dump(mode="json"),
        "comparison": comparison.model_dump(mode="json") if comparison else None,
        "module_key": module_key, "partition_hashes": sorted(set(partition_hashes)),
        "derivation_version": derivation_version,
    }
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("bucket boundaries must be timezone-aware")
    return value.astimezone(timezone.utc)


def floor_bucket(value: datetime, granularity: PeriodGranularity) -> datetime:
    value = _utc(value)
    if granularity is PeriodGranularity.DAY:
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity is PeriodGranularity.WEEK:
        return (value - timedelta(days=value.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity is PeriodGranularity.MONTH:
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity is PeriodGranularity.QUARTER:
        return value.replace(month=((value.month - 1) // 3) * 3 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity is PeriodGranularity.YEAR:
        return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError("custom periods cannot be materialised as calendar buckets")


def next_bucket(value: datetime, granularity: PeriodGranularity) -> datetime:
    if granularity is PeriodGranularity.DAY:
        return value + timedelta(days=1)
    if granularity is PeriodGranularity.WEEK:
        return value + timedelta(days=7)
    if granularity is PeriodGranularity.MONTH:
        return value.replace(year=value.year + (value.month == 12), month=1 if value.month == 12 else value.month + 1)
    if granularity is PeriodGranularity.QUARTER:
        month = value.month + 3
        return value.replace(year=value.year + (month > 12), month=month - 12 if month > 12 else month)
    if granularity is PeriodGranularity.YEAR:
        return value.replace(year=value.year + 1)
    raise ValueError("custom periods cannot be materialised as calendar buckets")


def activity_density_buckets(
    events: Iterable[ActivityEvent], *, from_at: datetime, to_at: datetime,
    granularity: PeriodGranularity,
) -> tuple[ActivityDensityBin, ...]:
    if to_at <= from_at:
        raise ValueError("to_at must be after from_at")
    grouped: dict[datetime, list] = {}
    for event in events:
        if event.occurred_at is None or not from_at <= event.occurred_at < to_at:
            continue
        grouped.setdefault(floor_bucket(event.occurred_at, granularity), []).append(event.event_id)
    bins = []
    cursor = floor_bucket(from_at, granularity)
    while cursor < to_at:
        end = next_bucket(cursor, granularity)
        ids = tuple(sorted(set(grouped.get(cursor, ())), key=str))
        bins.append(ActivityDensityBin(start_at=max(cursor, from_at), end_at=min(end, to_at),
                                       event_count=len(ids), evidence_event_ids=ids))
        cursor = end
    return tuple(bins)


def affected_bucket_starts(partitions: Iterable[EventPartition], *, from_at: datetime, to_at: datetime,
                           granularity: PeriodGranularity) -> tuple[datetime, ...]:
    """Identify only buckets touched by changed/new partitions."""
    affected = set()
    for partition in partitions:
        start = max(from_at, partition.min_occurred_at or from_at)
        end = min(to_at, (partition.max_occurred_at + timedelta(microseconds=1)) if partition.max_occurred_at else to_at)
        if end <= start:
            continue
        cursor = floor_bucket(start, granularity)
        while cursor < end:
            affected.add(cursor)
            cursor = next_bucket(cursor, granularity)
    return tuple(sorted(affected))


@dataclass(frozen=True, slots=True)
class CacheBenchmark:
    cold_seconds: float
    warm_seconds: float
    cold_value: Any
    warm_value: Any


async def benchmark_cold_warm(loader: Callable[[bool], Awaitable[Any]]) -> CacheBenchmark:
    started = perf_counter(); cold = await loader(False); cold_elapsed = perf_counter() - started
    started = perf_counter(); warm = await loader(True); warm_elapsed = perf_counter() - started
    return CacheBenchmark(cold_elapsed, warm_elapsed, cold, warm)


@dataclass(frozen=True, slots=True)
class PeriodMaterialisationResult:
    materialisation_id: UUID
    insight_id: UUID
    cache_key: str
    payload: dict[str, Any]
    cache_hit: bool
    partition_count: int


class PeriodMaterializer:
    """Build one module snapshot with one event scan, then serve it by cache key."""
    def __init__(self, repository, *, derivation_version: str = DERIVATION_VERSION) -> None:
        self.repository = repository
        self.derivation_version = derivation_version

    async def materialize_activity_density(
        self, *, subject_id: str, period: InsightPeriod,
        analysis_run_ids: Iterable[UUID] = (),
        comparison: InsightComparisonPeriod | None = None,
    ) -> PeriodMaterialisationResult:
        if period.mode is TemporalMode.POINT_IN_TIME or period.from_at is None or period.to_at is None:
            raise ValueError("activity density requires a bounded period")
        if period.granularity is PeriodGranularity.CUSTOM:
            raise ValueError("activity density requires a calendar granularity")
        partitions = await self.repository.discover_event_partitions(
            from_at=period.from_at, to_at=period.to_at, analysis_run_ids=analysis_run_ids,
        )
        hashes = tuple(partition.file_hash for partition in partitions)
        cache_key = materialisation_cache_key(
            subject_id=subject_id, period=period, module_key="activity_density",
            partition_hashes=hashes, derivation_version=self.derivation_version,
            comparison=comparison,
        )
        insight_id = uuid5(INSIGHT_NAMESPACE, cache_key)
        cached = await self.repository.cached_payload(cache_key, self.derivation_version)
        if cached is not None:
            return PeriodMaterialisationResult(
                cached["materialisation_id"], insight_id, cache_key, cached["payload"],
                True, len(partitions),
            )
        events = self.repository.load_activity_events(
            partitions, subject_id=subject_id, from_at=period.from_at, to_at=period.to_at,
        )
        bins = activity_density_buckets(
            events, from_at=period.from_at, to_at=period.to_at,
            granularity=period.granularity,
        )
        payload = {
            "module_key": "activity_density", "subject_id": subject_id,
            "period": period.model_dump(mode="json"),
            "bins": [item.model_dump(mode="json") for item in bins],
            "event_count": sum(item.event_count for item in bins),
            "derivation_version": self.derivation_version,
        }
        run_ids = tuple(sorted({partition.analysis_run_id for partition in partitions}, key=str))
        materialisation_id = await self.repository.persist_materialisation(
            subject_id=subject_id, period=period, module_key="activity_density",
            cache_key=cache_key, partition_hashes=hashes, payload=payload,
            derivation_method=DERIVATION_METHOD, derivation_version=self.derivation_version,
            analysis_run_id=run_ids[0] if len(run_ids) == 1 else None,
            compare_from_at=comparison.baseline.from_at if comparison else None,
            compare_to_at=comparison.baseline.to_at if comparison else None,
        )
        await self.repository.persist_aggregate_buckets(
            materialisation_id, subject_id=subject_id, granularity=period.granularity.value,
            aggregate_type="activity_density", aggregate_key="all-events",
            buckets=({"start_at": item.start_at, "end_at": item.end_at,
                      "values": {"event_count": item.event_count},
                      "evidence_event_ids": item.evidence_event_ids} for item in bins),
        )
        await self.repository.persist_evidence_index(
            materialisation_id, insight_id,
            (InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT, ref_id=event.event_id,
                                occurred_at=event.occurred_at, artifact_id=event.artifact_id,
                                locator_id=event.source_locator_id) for event in events),
        )
        return PeriodMaterialisationResult(
            materialisation_id, insight_id, cache_key, payload, False, len(partitions),
        )
