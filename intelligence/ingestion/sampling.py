"""Bounded, deterministic representative sampling for schema interpretation."""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from .models import ModelAdjudicationBundle


def _size(record: Mapping[str, Any]) -> int:
    return len(json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


def _paths(value: Any, prefix: str = "$", depth: int = 0) -> tuple[set[str], int]:
    paths: set[str] = set()
    maximum = depth
    if isinstance(value, Mapping):
        for key in sorted(value):
            path = f"{prefix}.{key}"
            paths.add(path)
            child, child_depth = _paths(value[key], path, depth + 1)
            paths.update(child)
            maximum = max(maximum, child_depth)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value[:32]:
            child, child_depth = _paths(item, prefix + "[]", depth + 1)
            paths.update(child)
            maximum = max(maximum, child_depth)
    return paths, maximum


def representative_samples(records: Iterable[Mapping[str, Any]], *, unusual_limit: int = 2) -> tuple[dict[str, Any], ...]:
    if unusual_limit < 0 or unusual_limit > 8:
        raise ValueError("unusual_limit must be between zero and eight")
    materialised = [dict(record) for record in records if isinstance(record, Mapping)]
    if not materialised:
        return ()
    metrics = [(_size(record), *_paths(record), index) for index, record in enumerate(materialised)]
    ordered_sizes = sorted((size, index) for size, _paths_value, _depth, index in metrics)
    chosen: list[int] = [0]
    chosen.append(ordered_sizes[(len(ordered_sizes) - 1) // 2][1])
    chosen.append(max(metrics, key=lambda item: (len(item[1]), -item[3]))[3])
    chosen.append(max(metrics, key=lambda item: (item[2], -item[3]))[3])
    path_frequency: dict[str, int] = {}
    for _size_value, paths, _depth, _index in metrics:
        for path in paths:
            path_frequency[path] = path_frequency.get(path, 0) + 1
    unusual = sorted(metrics, key=lambda item: (-sum(1 / path_frequency[path] for path in item[1]), item[3]))
    chosen.extend(item[3] for item in unusual[:unusual_limit])
    unique = list(dict.fromkeys(chosen))
    return tuple(materialised[index] for index in unique)


def build_schema_interpretation_bundle(
    records: Iterable[Mapping[str, Any]], *, analysis_run_id: UUID,
    source_artifact_ids: tuple[UUID, ...], fingerprint_id: str,
    maximum_sample_bytes: int = 32_768, unusual_limit: int = 2,
) -> ModelAdjudicationBundle:
    if maximum_sample_bytes <= 0:
        raise ValueError("maximum_sample_bytes must be positive")
    all_records = [dict(record) for record in records if isinstance(record, Mapping)]
    candidates = representative_samples(all_records, unusual_limit=unusual_limit)
    accepted: list[dict[str, Any]] = []
    used = 2
    for candidate in candidates:
        candidate_size = _size(candidate) + (1 if accepted else 0)
        if used + candidate_size <= maximum_sample_bytes:
            accepted.append(candidate)
            used += candidate_size
    if not accepted and candidates:
        accepted = [{"_sample_omitted": "record exceeds byte budget", "top_level_keys": sorted(candidates[0])[:64]}]
        if _size(accepted[0]) > maximum_sample_bytes:
            accepted = []
    return ModelAdjudicationBundle(
        task_key="schema.interpretation", analysis_run_id=analysis_run_id,
        source_artifact_ids=source_artifact_ids,
        purpose="Propose a constrained parser for an unknown structure fingerprint; proposal requires human approval.",
        samples=tuple(accepted), maximum_sample_bytes=maximum_sample_bytes,
        omitted_record_count=max(0, len(all_records) - len(accepted)), fingerprint_id=fingerprint_id,
    )
