"""Deterministic private benchmark evaluation for Task 3 semantic residue.

The harness deliberately knows nothing about providers or routing.  Its only
execution dependency is the injected :class:`BenchmarkExecutor`, which is the
adapter boundary to Task 2's canonical router.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable

from .contracts import (
    BenchmarkCase,
    BenchmarkExecutor,
    BenchmarkInvocation,
    BenchmarkMetric,
    BenchmarkScore,
    TaskBenchmarkReport,
)


DEFAULT_MAX_CASES = 1_000
DEFAULT_MAX_BUNDLE_BYTES = 262_144
DEFAULT_MAX_FIXTURE_BYTES = 4 * 1024 * 1024


class BenchmarkValidationError(ValueError):
    """Raised when a private benchmark input exceeds or violates its boundary."""


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BenchmarkValidationError("benchmark content must be JSON serialisable") from exc


def validate_benchmark_cases(
    cases: Sequence[BenchmarkCase],
    *,
    max_cases: int = DEFAULT_MAX_CASES,
    max_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
) -> tuple[BenchmarkCase, ...]:
    """Validate authorisation, provenance, uniqueness, and bounded sample data."""
    if max_cases <= 0 or max_bundle_bytes <= 0:
        raise BenchmarkValidationError("benchmark limits must be positive")
    if not cases:
        raise BenchmarkValidationError("at least one benchmark case is required")
    if len(cases) > max_cases:
        raise BenchmarkValidationError(
            f"benchmark contains {len(cases)} cases; limit is {max_cases}"
        )

    validated: list[BenchmarkCase] = []
    case_ids: set[str] = set()
    for position, candidate in enumerate(cases):
        try:
            case = candidate if isinstance(candidate, BenchmarkCase) else BenchmarkCase.model_validate(candidate)
        except Exception as exc:
            raise BenchmarkValidationError(f"invalid benchmark case at position {position}") from exc
        if case.case_id in case_ids:
            raise BenchmarkValidationError(f"duplicate benchmark case_id: {case.case_id}")
        case_ids.add(case.case_id)
        if case.fixture_authorisation not in {"synthetic", "user_approved"}:
            raise BenchmarkValidationError(
                f"case {case.case_id} is not synthetic or user-approved"
            )
        if not case.bundle.source_artifact_ids:
            raise BenchmarkValidationError(
                f"case {case.case_id} requires a source artifact reference"
            )
        if case.bundle.maximum_sample_bytes > max_bundle_bytes:
            raise BenchmarkValidationError(
                f"case {case.case_id} declares a sample limit above {max_bundle_bytes} bytes"
            )
        actual_sample_bytes = len(_json_bytes(case.bundle.samples))
        if actual_sample_bytes > case.bundle.maximum_sample_bytes:
            raise BenchmarkValidationError(
                f"case {case.case_id} samples exceed the bundle's declared byte limit"
            )
        if actual_sample_bytes > max_bundle_bytes:
            raise BenchmarkValidationError(
                f"case {case.case_id} samples exceed the harness byte limit"
            )
        validated.append(case)
    return tuple(validated)


def load_benchmark_cases(
    path: str | Path,
    *,
    max_fixture_bytes: int = DEFAULT_MAX_FIXTURE_BYTES,
    max_cases: int = DEFAULT_MAX_CASES,
    max_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
) -> tuple[BenchmarkCase, ...]:
    """Load a bounded JSON fixture containing an array of benchmark cases."""
    fixture = Path(path)
    if fixture.suffix.lower() != ".json":
        raise BenchmarkValidationError("benchmark fixtures must be JSON files")
    if max_fixture_bytes <= 0:
        raise BenchmarkValidationError("fixture byte limit must be positive")
    try:
        size = fixture.stat().st_size
    except OSError as exc:
        raise BenchmarkValidationError(f"cannot inspect benchmark fixture: {fixture}") from exc
    if size > max_fixture_bytes:
        raise BenchmarkValidationError(
            f"benchmark fixture is {size} bytes; limit is {max_fixture_bytes}"
        )
    try:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkValidationError(f"invalid benchmark fixture: {fixture}") from exc
    if not isinstance(payload, list):
        raise BenchmarkValidationError("benchmark fixture root must be an array")
    return validate_benchmark_cases(
        payload,
        max_cases=max_cases,
        max_bundle_bytes=max_bundle_bytes,
    )


def _output_mapping(invocation: BenchmarkInvocation) -> Mapping[str, Any] | None:
    return invocation.output if isinstance(invocation.output, Mapping) else None


def _abstained(invocation: BenchmarkInvocation) -> bool:
    output = _output_mapping(invocation)
    return bool(output is not None and output.get("abstain") is True)


def _labels(invocation: BenchmarkInvocation) -> tuple[str, ...] | None:
    output = _output_mapping(invocation)
    if output is None:
        return None
    labels = output.get("labels")
    if isinstance(labels, list) and all(isinstance(label, str) for label in labels):
        return tuple(labels)
    label = output.get("label")
    if isinstance(label, str):
        return (label,)
    return None


def _structured_output_is_valid(case: BenchmarkCase, invocation: BenchmarkInvocation) -> bool:
    if invocation.structured_error is not None:
        return False
    output = _output_mapping(invocation)
    if output is None:
        return False
    try:
        _json_bytes(output)
    except BenchmarkValidationError:
        return False
    if "abstain" in output and not isinstance(output["abstain"], bool):
        return False
    if "locator_validity" in output and not isinstance(output["locator_validity"], bool):
        return False
    if _abstained(invocation):
        return True
    if case.task_key == "schema.interpretation":
        return isinstance(output.get("parser_spec"), Mapping)
    return _labels(invocation) is not None


def _canonical_equal(left: Any, right: Any) -> bool:
    try:
        return _json_bytes(left) == _json_bytes(right)
    except BenchmarkValidationError:
        return False


def _ratio_score(
    metric: BenchmarkMetric,
    matches: Sequence[bool],
    *,
    empty_note: str,
) -> BenchmarkScore:
    denominator = len(matches)
    if denominator == 0:
        return BenchmarkScore(
            metric=metric,
            value=None,
            numerator=0,
            denominator=0,
            notes=empty_note,
        )
    numerator = sum(matches)
    return BenchmarkScore(
        metric=metric,
        value=numerator / denominator,
        numerator=numerator,
        denominator=denominator,
    )


def _cost_summary(invocations: Sequence[BenchmarkInvocation]) -> tuple[str, int]:
    numeric_totals: dict[str, float | int] = {}
    metadata: dict[str, set[str]] = defaultdict(set)
    populated = 0
    for invocation in invocations:
        if invocation.configured_cost:
            populated += 1
        for key, value in invocation.configured_cost.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric_totals[key] = numeric_totals.get(key, 0) + value
            else:
                metadata[key].add("null" if value is None else str(value))
    summary = {
        "invocations_with_metadata": populated,
        "metadata_values": {key: sorted(values) for key, values in sorted(metadata.items())},
        "numeric_totals": dict(sorted(numeric_totals.items())),
    }
    return json.dumps(summary, sort_keys=True, separators=(",", ":")), populated


def _scores(
    cases: Sequence[BenchmarkCase],
    invocations: Sequence[BenchmarkInvocation],
) -> tuple[BenchmarkScore, ...]:
    paired = tuple(zip(cases, invocations, strict=True))

    classification = [
        set(_labels(invocation) or ()) == set(case.expected_labels)
        for case, invocation in paired
        if case.expected_labels
    ]
    schema = [
        _canonical_equal(
            (_output_mapping(invocation) or {}).get("parser_spec"),
            case.expected_parser_spec,
        )
        for case, invocation in paired
        if case.expected_parser_spec is not None
    ]
    locator = [
        (_output_mapping(invocation) or {}).get("locator_validity")
        is case.expected_locator_validity
        for case, invocation in paired
        if case.expected_locator_validity is not None
    ]
    abstention = [
        _abstained(invocation) is case.expected_abstain
        for case, invocation in paired
    ]
    structured = [
        _structured_output_is_valid(case, invocation)
        for case, invocation in paired
    ]

    latency = sum(invocation.latency_ms for invocation in invocations) / len(invocations)
    measured_memory = [
        invocation.peak_memory_bytes
        for invocation in invocations
        if invocation.peak_memory_bytes is not None
    ]
    locations = {
        location: sum(invocation.execution_location == location for invocation in invocations)
        for location in ("local", "external")
    }
    cost, populated_cost = _cost_summary(invocations)

    return (
        _ratio_score(
            BenchmarkMetric.CLASSIFICATION_ACCURACY,
            classification,
            empty_note="no cases supplied expected labels",
        ),
        _ratio_score(
            BenchmarkMetric.SCHEMA_INTERPRETATION_ACCURACY,
            schema,
            empty_note="no cases supplied an expected parser spec",
        ),
        _ratio_score(
            BenchmarkMetric.LOCATOR_VALIDITY,
            locator,
            empty_note="no cases supplied expected locator validity",
        ),
        _ratio_score(
            BenchmarkMetric.ABSTENTION_QUALITY,
            abstention,
            empty_note="no abstention cases",
        ),
        _ratio_score(
            BenchmarkMetric.STRUCTURED_OUTPUT_VALIDITY,
            structured,
            empty_note="no structured outputs",
        ),
        BenchmarkScore(
            metric=BenchmarkMetric.LATENCY,
            value=latency,
            denominator=len(invocations),
            notes="mean supplied invocation latency in milliseconds",
        ),
        BenchmarkScore(
            metric=BenchmarkMetric.PEAK_MEMORY,
            value=max(measured_memory) if measured_memory else None,
            denominator=len(measured_memory),
            notes="maximum supplied peak-memory value in bytes; unmeasured invocations omitted",
        ),
        BenchmarkScore(
            metric=BenchmarkMetric.EXECUTION_LOCATION,
            value=json.dumps(locations, sort_keys=True, separators=(",", ":")),
            denominator=len(invocations),
            notes="invocation counts by audited execution location",
        ),
        BenchmarkScore(
            metric=BenchmarkMetric.CONFIGURED_COST,
            value=cost,
            denominator=populated_cost,
            notes="sum of configured numeric metadata; this is not a public price lookup",
        ),
    )


async def run_benchmarks(
    cases: Sequence[BenchmarkCase],
    executor: BenchmarkExecutor,
    *,
    report_version: str = "task3-benchmark-v1",
    max_cases: int = DEFAULT_MAX_CASES,
    max_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
    clock: Callable[[], datetime] | None = None,
) -> tuple[TaskBenchmarkReport, ...]:
    """Invoke bounded cases and return reports per task and execution identity."""
    validated = validate_benchmark_cases(
        cases,
        max_cases=max_cases,
        max_bundle_bytes=max_bundle_bytes,
    )
    if not report_version:
        raise BenchmarkValidationError("report_version must not be empty")
    now = clock or (lambda: datetime.now(timezone.utc))

    completed: list[tuple[BenchmarkCase, BenchmarkInvocation]] = []
    for case in validated:
        invocation = await executor.invoke(case)
        if not isinstance(invocation, BenchmarkInvocation):
            try:
                invocation = BenchmarkInvocation.model_validate(invocation)
            except Exception as exc:
                raise BenchmarkValidationError(
                    f"executor returned an invalid invocation for {case.case_id}"
                ) from exc
        if invocation.case_id != case.case_id or invocation.task_key != case.task_key:
            raise BenchmarkValidationError(
                f"executor invocation identity does not match case {case.case_id}"
            )
        if not invocation.engine_id or not invocation.provider:
            raise BenchmarkValidationError(
                f"executor omitted engine/provider identity for {case.case_id}"
            )
        completed.append((case, invocation))

    cohorts: dict[
        tuple[str, str, str, str | None],
        list[tuple[BenchmarkCase, BenchmarkInvocation]],
    ] = defaultdict(list)
    for case, invocation in completed:
        identity = (
            case.task_key,
            invocation.engine_id,
            invocation.provider,
            invocation.model,
        )
        cohorts[identity].append((case, invocation))

    reports: list[TaskBenchmarkReport] = []
    for identity in sorted(cohorts, key=lambda item: tuple(value or "" for value in item)):
        task_key, engine_id, provider, model = identity
        cohort = cohorts[identity]
        cohort_cases = tuple(item[0] for item in cohort)
        cohort_invocations = tuple(item[1] for item in cohort)
        reports.append(
            TaskBenchmarkReport(
                report_version=report_version,
                task_key=task_key,
                engine_id=engine_id,
                provider=provider,
                model=model,
                created_at=now(),
                case_count=len(cohort),
                scores=_scores(cohort_cases, cohort_invocations),
                invocations=cohort_invocations,
                selection_recommendation=None,
            )
        )
    return tuple(reports)


def _report_filename(report: TaskBenchmarkReport) -> str:
    identity = "|".join(
        (report.task_key, report.engine_id, report.provider, report.model or "")
    )
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", f"{report.task_key}-{report.engine_id}").strip("-.")
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{slug or 'benchmark'}-{digest}.json"


def write_benchmark_reports(
    output_directory: str | Path,
    reports: Sequence[TaskBenchmarkReport],
) -> tuple[Path, ...]:
    """Atomically persist machine-readable per-task reports."""
    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for candidate in reports:
        report = (
            candidate
            if isinstance(candidate, TaskBenchmarkReport)
            else TaskBenchmarkReport.model_validate(candidate)
        )
        destination = root / _report_filename(report)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        payload = report.model_dump_json(indent=2)
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        written.append(destination)
    return tuple(written)
