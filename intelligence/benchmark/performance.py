"""Private, provider-free performance benchmark for the Task 3 architecture.

This is deliberately an architectural benchmark, not a model benchmark.  It
executes the local inventory, file-family, Parquet and deterministic feature
paths, while a counting boundary stands in for Task 2 semantic routing.  The
boundary records the work that *would* be submitted and has no provider or
network implementation.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
import tracemalloc
from typing import Callable, Iterable, Literal, Protocol
from uuid import UUID, uuid5

from pydantic import Field

from features.pipeline import FeatureDetector, extract_partition_features
from ingestion.checkpoints import checkpoint_key
from ingestion.inventory import ArchiveSafetyPolicy, iter_inventory
from ingestion.models import (
    ActivityEvent,
    ExtractionContext,
    FrozenModel,
    ModelAdjudicationBundle,
    PipelineStage,
)
from ingestion.processor import LocalFileProcessor, ProcessedFile
from ingestion.sampling import build_schema_interpretation_bundle
from ingestion.events import write_activity_events


BENCHMARK_NAMESPACE = UUID("fe1b9740-6f14-481d-ab62-c6cd3d3c5bd1")
RECORD_UNIT_TYPES = frozenset(
    {
        "record",
        "row",
        "message",
        "calendar_event",
        "contact",
        "feature",
        "database_row",
        "cue",
    }
)


class StageThroughput(FrozenModel):
    stage: str
    item_count: int = Field(ge=0)
    unit: str
    elapsed_seconds: float = Field(ge=0)
    items_per_second: float | None = Field(default=None, ge=0)


class SemanticCallObservation(FrozenModel):
    task_key: Literal["schema.interpretation", "semantic.adjudication"]
    residue_key: str
    payload_bytes: int = Field(ge=0)


class PerformanceBenchmarkReport(FrozenModel):
    report_version: str = "task3-performance-v1"
    fixture_authorisation: Literal["synthetic", "user_approved"]
    files_processed: int = Field(ge=0)
    bytes_inventoried: int = Field(ge=0)
    records_processed: int = Field(ge=0)
    events_written: int = Field(ge=0)
    semantic_calls: int = Field(ge=0)
    semantic_call_to_record_ratio: float = Field(ge=0)
    naive_per_record_call_baseline: int = Field(ge=0)
    semantic_calls_avoided: int = Field(ge=0)
    model_call_reduction_fraction: float = Field(ge=0, le=1)
    material_reduction_threshold: float = Field(gt=0, le=1)
    materially_lower_model_calls: bool
    stage_throughput: tuple[StageThroughput, ...]
    peak_memory_bytes: int | None = Field(default=None, ge=0)
    parquet_partition_count: int = Field(ge=0)
    parquet_row_count: int = Field(ge=0)
    parquet_total_bytes: int = Field(ge=0)
    restart_recovery_seconds: float = Field(ge=0)
    restart_items_skipped: int = Field(ge=0)
    restart_items_reprocessed: int = Field(ge=0)
    semantic_observations: tuple[SemanticCallObservation, ...]
    provider_invocations: int = Field(default=0, ge=0)
    network_invocations: int = Field(default=0, ge=0)


class SemanticCountingBoundary:
    """An injected semantic boundary that can only count bounded payloads."""

    def __init__(self) -> None:
        self._observations: list[SemanticCallObservation] = []

    @property
    def observations(self) -> tuple[SemanticCallObservation, ...]:
        return tuple(self._observations)

    @property
    def call_count(self) -> int:
        return len(self._observations)

    @property
    def provider_invocations(self) -> int:
        return 0

    @property
    def network_invocations(self) -> int:
        return 0

    def invoke(self, bundle: ModelAdjudicationBundle, *, residue_key: str) -> None:
        payload = bundle.model_dump(mode="json")
        payload_bytes = len(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        )
        self._observations.append(
            SemanticCallObservation(
                task_key=bundle.task_key,
                residue_key=residue_key,
                payload_bytes=payload_bytes,
            )
        )


class CheckpointBoundary(Protocol):
    def completed(
        self,
        *,
        stage: PipelineStage,
        item_key: str,
        content_hash: str | None,
        parser_version: str | None,
    ) -> bool: ...

    def mark_completed(
        self,
        *,
        stage: PipelineStage,
        item_key: str,
        content_hash: str | None,
        parser_version: str | None,
    ) -> None: ...


class MemoryCheckpointBoundary:
    """Benchmark checkpoint store using the production idempotency-key rules."""

    def __init__(self) -> None:
        self._completed: set[str] = set()

    @staticmethod
    def _key(
        *,
        stage: PipelineStage,
        item_key: str,
        content_hash: str | None,
        parser_version: str | None,
    ) -> str:
        return checkpoint_key(
            stage=stage,
            item_key=item_key,
            content_hash=content_hash,
            parser_version=parser_version,
        )

    def completed(self, **values) -> bool:
        return self._key(**values) in self._completed

    def mark_completed(self, **values) -> None:
        self._completed.add(self._key(**values))


@dataclass(frozen=True, slots=True)
class _RecoveryItem:
    item_key: str
    content_hash: str
    parser_version: str | None


def _measure(
    clock: Callable[[], float],
    stage: str,
    item_count: int,
    unit: str,
    operation: Callable[[], object],
) -> tuple[object, StageThroughput]:
    started = clock()
    result = operation()
    elapsed = max(0.0, clock() - started)
    rate = (item_count / elapsed) if elapsed > 0 else None
    return result, StageThroughput(
        stage=stage,
        item_count=item_count,
        unit=unit,
        elapsed_seconds=elapsed,
        items_per_second=rate,
    )


def _record_count(result: ProcessedFile) -> int:
    if result.extraction is None:
        return 0
    units = result.extraction.units
    record_like = sum(unit.unit_type in RECORD_UNIT_TYPES for unit in units)
    # A structured adapter can use a more specific unit name.  Counting all
    # extracted units is a conservative fallback; metadata-only files do not
    # manufacture records because they normally emit no units.
    return record_like if record_like else len(units)


def _structured_records(result: ProcessedFile) -> tuple[dict, ...]:
    if result.extraction is None:
        return ()
    return tuple(
        unit.structured_payload
        for unit in result.extraction.units
        if isinstance(unit.structured_payload, dict)
    )


def _context(analysis_run_id: UUID, relative_path: str, source_path: Path) -> ExtractionContext:
    return ExtractionContext(
        artifact_id=uuid5(BENCHMARK_NAMESPACE, f"artifact:{analysis_run_id}:{relative_path}"),
        analysis_run_id=analysis_run_id,
        export_snapshot_id=uuid5(BENCHMARK_NAMESPACE, f"snapshot:{analysis_run_id}"),
        source_path=str(source_path),
    )


def run_performance_benchmark(
    corpus_root: str | Path,
    output_root: str | Path,
    events: Iterable[ActivityEvent],
    *,
    analysis_run_id: UUID,
    fixture_authorisation: Literal["synthetic", "user_approved"] = "synthetic",
    approved_fingerprint_ids: Iterable[str] = (),
    detectors: Iterable[FeatureDetector] = (),
    semantic_boundary: SemanticCountingBoundary | None = None,
    checkpoint_boundary: CheckpointBoundary | None = None,
    material_reduction_threshold: float = 0.01,
    clock: Callable[[], float] = perf_counter,
    measure_peak_memory: bool = True,
) -> PerformanceBenchmarkReport:
    """Run a bounded local benchmark over a synthetic or explicitly approved corpus.

    ``events`` are already-normalised fixture events.  This keeps the benchmark
    focused on architecture and avoids embedding a source-specific semantic
    parser in the harness.  At least one event is required so that both event
    and observation Parquet paths are exercised.
    """

    if not 0 < material_reduction_threshold <= 1:
        raise ValueError("material_reduction_threshold must be in (0, 1]")
    root = Path(corpus_root).resolve()
    destination = Path(output_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    event_rows = tuple(events)
    if not event_rows:
        raise ValueError("at least one normalised fixture event is required")

    counter = semantic_boundary or SemanticCountingBoundary()
    checkpoints = checkpoint_boundary or MemoryCheckpointBoundary()
    processor = LocalFileProcessor()
    approved = frozenset(approved_fingerprint_ids)
    stage_metrics: list[StageThroughput] = []
    already_tracing = tracemalloc.is_tracing()
    if measure_peak_memory and not already_tracing:
        tracemalloc.start()
    if measure_peak_memory:
        tracemalloc.reset_peak()

    try:
        policy = ArchiveSafetyPolicy(workspace_root=root)
        inventory_value, metric = _measure(
            clock,
            "inventory",
            0,
            "files",
            lambda: tuple(iter_inventory(root, policy)),
        )
        inventory = tuple(inventory_value)
        # Inventory count is known only after the streaming iterator completes.
        elapsed = metric.elapsed_seconds
        stage_metrics.append(
            metric.model_copy(
                update={
                    "item_count": len(inventory),
                    "items_per_second": len(inventory) / elapsed if elapsed > 0 else None,
                }
            )
        )
        bytes_inventoried = sum(item.size for item in inventory)

        def process_files() -> tuple[ProcessedFile, ...]:
            processed: list[ProcessedFile] = []
            for entry in inventory:
                if entry.is_symlink:
                    continue
                source = root / Path(entry.relative_path)
                processed.append(
                    processor.process(source, _context(analysis_run_id, entry.relative_path, source))
                )
            return tuple(processed)

        processed_value, metric = _measure(
            clock,
            "deterministic_file_pipeline",
            len(inventory),
            "files",
            process_files,
        )
        processed = tuple(processed_value)
        stage_metrics.append(metric)
        records_processed = sum(_record_count(item) for item in processed)

        unknown_records: dict[str, list[dict]] = defaultdict(list)
        unknown_artifacts: dict[str, set[UUID]] = defaultdict(set)
        recovery_items: list[_RecoveryItem] = []
        for item in processed:
            parser_version = item.extraction.adapter_version if item.extraction else None
            recovery = _RecoveryItem(item.path.relative_to(root).as_posix(), item.raw_sha256, parser_version)
            recovery_items.append(recovery)
            checkpoints.mark_completed(
                stage=PipelineStage.FAMILY_EXTRACTION,
                item_key=recovery.item_key,
                content_hash=recovery.content_hash,
                parser_version=recovery.parser_version,
            )
            fingerprint = item.fingerprint
            if fingerprint is None or fingerprint.fingerprint_id in approved:
                continue
            unknown_records[fingerprint.fingerprint_id].extend(_structured_records(item))
            if item.extraction is not None:
                unknown_artifacts[fingerprint.fingerprint_id].add(item.extraction.artifact_id)

        for fingerprint_id in sorted(unknown_records):
            bundle = build_schema_interpretation_bundle(
                unknown_records[fingerprint_id],
                analysis_run_id=analysis_run_id,
                source_artifact_ids=tuple(sorted(unknown_artifacts[fingerprint_id], key=str)),
                fingerprint_id=fingerprint_id,
            )
            counter.invoke(bundle, residue_key=f"fingerprint:{fingerprint_id}")

        write_value, metric = _measure(
            clock,
            "event_lake_write",
            len(event_rows),
            "events",
            lambda: write_activity_events(
                destination,
                event_rows,
                analysis_run_id=analysis_run_id,
                partition_key="performance-fixture",
            ),
        )
        written = write_value
        stage_metrics.append(metric)

        feature_value, metric = _measure(
            clock,
            "feature_extraction",
            len(written.events),
            "events",
            lambda: extract_partition_features(
                written.event_partition.path,
                tuple(detectors),
                analysis_run_id=analysis_run_id,
            ),
        )
        features = feature_value
        stage_metrics.append(metric)
        for index, bundle in enumerate(features.adjudication_bundles):
            counter.invoke(bundle, residue_key=f"adjudication:{index}")

        restart_started = clock()
        restart_skipped = 0
        restart_reprocessed = 0
        for item in recovery_items:
            if checkpoints.completed(
                stage=PipelineStage.FAMILY_EXTRACTION,
                item_key=item.item_key,
                content_hash=item.content_hash,
                parser_version=item.parser_version,
            ):
                restart_skipped += 1
            else:
                restart_reprocessed += 1
        restart_elapsed = max(0.0, clock() - restart_started)
        stage_metrics.append(
            StageThroughput(
                stage="restart_recovery",
                item_count=len(recovery_items),
                unit="checkpoint_items",
                elapsed_seconds=restart_elapsed,
                items_per_second=(len(recovery_items) / restart_elapsed if restart_elapsed > 0 else None),
            )
        )

        peak_memory = tracemalloc.get_traced_memory()[1] if measure_peak_memory else None
    finally:
        if measure_peak_memory and not already_tracing:
            tracemalloc.stop()

    semantic_calls = counter.call_count
    baseline = records_processed
    ratio = semantic_calls / baseline if baseline else 0.0
    avoided = max(0, baseline - semantic_calls)
    reduction = avoided / baseline if baseline else 0.0
    partition_records = (written.event_partition, written.observation_partition)
    return PerformanceBenchmarkReport(
        fixture_authorisation=fixture_authorisation,
        files_processed=len(processed),
        bytes_inventoried=bytes_inventoried,
        records_processed=records_processed,
        events_written=len(written.events),
        semantic_calls=semantic_calls,
        semantic_call_to_record_ratio=ratio,
        naive_per_record_call_baseline=baseline,
        semantic_calls_avoided=avoided,
        model_call_reduction_fraction=reduction,
        material_reduction_threshold=material_reduction_threshold,
        materially_lower_model_calls=(baseline > 0 and ratio <= material_reduction_threshold),
        stage_throughput=tuple(stage_metrics),
        peak_memory_bytes=peak_memory,
        parquet_partition_count=len(partition_records),
        parquet_row_count=sum(item.row_count for item in partition_records),
        parquet_total_bytes=sum(item.byte_size for item in partition_records),
        restart_recovery_seconds=restart_elapsed,
        restart_items_skipped=restart_skipped,
        restart_items_reprocessed=restart_reprocessed,
        semantic_observations=counter.observations,
        provider_invocations=counter.provider_invocations,
        network_invocations=counter.network_invocations,
    )
