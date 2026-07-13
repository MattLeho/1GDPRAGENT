from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from benchmark.contracts import BenchmarkCase, BenchmarkInvocation, BenchmarkMetric
from benchmark.harness import (
    BenchmarkValidationError,
    load_benchmark_cases,
    run_benchmarks,
    validate_benchmark_cases,
    write_benchmark_reports,
)


FIXTURE = Path(__file__).parent / "fixtures" / "task3_benchmark" / "labelled_cases.json"


def _scores(report):
    return {score.metric: score for score in report.scores}


class FixtureExecutor:
    outputs = {
        "schema-search-v1": {
            "parser_spec": {
                "timestamp_selector": "/time",
                "object_selector": "/query",
                "event_type": "search.performed",
            },
            "locator_validity": True,
        },
        "adjudicate-email-v1": {
            "labels": ["DIRECT_IDENTIFIER"],
            "locator_validity": True,
        },
        "adjudicate-unknown-v1": {"abstain": True, "reason": "insufficient evidence"},
        "topic-label-v1": {"labels": ["privacy"]},
    }

    async def invoke(self, case: BenchmarkCase) -> BenchmarkInvocation:
        external = case.task_key == "semantic.topic_labelling"
        return BenchmarkInvocation(
            case_id=case.case_id,
            task_key=case.task_key,
            engine_id="fixture-external" if external else "fixture-local",
            provider="fixture",
            model="fixture-v1",
            execution_location="external" if external else "local",
            output=self.outputs[case.case_id],
            execution_record_id=f"execution-{case.case_id}",
            latency_ms=20.0 if external else 10.0,
            peak_memory_bytes=None if case.expected_abstain else 4096,
            configured_cost={"estimated_usd": 0.02 if external else 0, "currency": "USD"},
        )


def test_loads_only_bounded_labelled_synthetic_cases():
    cases = load_benchmark_cases(FIXTURE)
    assert len(cases) == 4
    assert {case.fixture_authorisation for case in cases} == {"synthetic"}
    assert all(case.bundle.source_artifact_ids for case in cases)


def test_rejects_duplicate_unprovenance_and_oversized_cases():
    cases = load_benchmark_cases(FIXTURE)
    with pytest.raises(BenchmarkValidationError, match="duplicate"):
        validate_benchmark_cases((cases[0], cases[0]))
    with pytest.raises(BenchmarkValidationError, match="source artifact"):
        validate_benchmark_cases((cases[0].model_copy(update={
            "bundle": cases[0].bundle.model_copy(update={"source_artifact_ids": ()}),
        }),))
    with pytest.raises(BenchmarkValidationError, match="declares a sample limit"):
        validate_benchmark_cases((cases[0],), max_bundle_bytes=512)
    with pytest.raises(BenchmarkValidationError, match="limit is 2"):
        validate_benchmark_cases(cases, max_cases=2)


@pytest.mark.asyncio
async def test_harness_measures_required_metrics_and_never_recommends_models(tmp_path):
    cases = load_benchmark_cases(FIXTURE)
    created = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    reports = await run_benchmarks(cases, FixtureExecutor(), clock=lambda: created)
    assert len(reports) == 3
    assert {report.task_key for report in reports} == {
        "schema.interpretation",
        "semantic.adjudication",
        "semantic.topic_labelling",
    }
    assert all(report.selection_recommendation is None for report in reports)
    assert all(report.created_at == created for report in reports)
    assert all({score.metric for score in report.scores} == set(BenchmarkMetric) for report in reports)

    schema = next(report for report in reports if report.task_key == "schema.interpretation")
    schema_scores = _scores(schema)
    assert schema_scores[BenchmarkMetric.SCHEMA_INTERPRETATION_ACCURACY].value == 1.0
    assert schema_scores[BenchmarkMetric.LOCATOR_VALIDITY].value == 1.0
    assert schema_scores[BenchmarkMetric.STRUCTURED_OUTPUT_VALIDITY].value == 1.0
    assert schema_scores[BenchmarkMetric.LATENCY].value == 10.0
    assert schema_scores[BenchmarkMetric.PEAK_MEMORY].value == 4096
    assert json.loads(schema_scores[BenchmarkMetric.EXECUTION_LOCATION].value) == {
        "external": 0,
        "local": 1,
    }

    adjudication = next(report for report in reports if report.task_key == "semantic.adjudication")
    adjudication_scores = _scores(adjudication)
    assert adjudication_scores[BenchmarkMetric.CLASSIFICATION_ACCURACY].value == 1.0
    assert adjudication_scores[BenchmarkMetric.ABSTENTION_QUALITY].value == 1.0
    assert adjudication_scores[BenchmarkMetric.STRUCTURED_OUTPUT_VALIDITY].value == 1.0
    cost = json.loads(adjudication_scores[BenchmarkMetric.CONFIGURED_COST].value)
    assert cost["numeric_totals"]["estimated_usd"] == 0
    assert cost["metadata_values"]["currency"] == ["USD"]

    topic = next(report for report in reports if report.task_key == "semantic.topic_labelling")
    assert json.loads(_scores(topic)[BenchmarkMetric.EXECUTION_LOCATION].value) == {
        "external": 1,
        "local": 0,
    }

    paths = write_benchmark_reports(tmp_path, reports)
    assert len(paths) == 3 and all(path.is_file() for path in paths)
    persisted = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert {item["task_key"] for item in persisted} == {report.task_key for report in reports}
    assert all(item["selection_recommendation"] is None for item in persisted)
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.asyncio
async def test_malformed_structured_output_is_scored_not_promoted():
    case = load_benchmark_cases(FIXTURE)[1]

    class InvalidExecutor:
        async def invoke(self, item):
            return BenchmarkInvocation(
                case_id=item.case_id,
                task_key=item.task_key,
                engine_id="fixture-local",
                provider="fixture",
                execution_location="local",
                output={"labels": "DIRECT_IDENTIFIER", "locator_validity": "yes"},
                latency_ms=1,
            )

    report = (await run_benchmarks((case,), InvalidExecutor()))[0]
    scores = _scores(report)
    assert scores[BenchmarkMetric.STRUCTURED_OUTPUT_VALIDITY].value == 0.0
    assert scores[BenchmarkMetric.CLASSIFICATION_ACCURACY].value == 0.0
    assert scores[BenchmarkMetric.LOCATOR_VALIDITY].value == 0.0


@pytest.mark.asyncio
async def test_executor_cannot_misattributed_case_identity():
    case = load_benchmark_cases(FIXTURE)[0]

    class MismatchedExecutor:
        async def invoke(self, item):
            return BenchmarkInvocation(
                case_id="different-case",
                task_key=item.task_key,
                engine_id="fixture-local",
                provider="fixture",
                execution_location="local",
                output={"parser_spec": {}},
                latency_ms=1,
            )

    with pytest.raises(BenchmarkValidationError, match="identity"):
        await run_benchmarks((case,), MismatchedExecutor())
