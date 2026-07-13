"""Frozen contracts for private, task-specific Task 3 benchmarks."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import Field, model_validator

from ingestion.models import FrozenModel, ModelAdjudicationBundle


class BenchmarkMetric(str, Enum):
    CLASSIFICATION_ACCURACY = "classification_accuracy"
    SCHEMA_INTERPRETATION_ACCURACY = "schema_interpretation_accuracy"
    LOCATOR_VALIDITY = "locator_validity"
    ABSTENTION_QUALITY = "abstention_quality"
    STRUCTURED_OUTPUT_VALIDITY = "structured_output_validity"
    LATENCY = "latency"
    PEAK_MEMORY = "peak_memory"
    EXECUTION_LOCATION = "execution_location"
    CONFIGURED_COST = "configured_cost"


class BenchmarkCase(FrozenModel):
    case_id: str = Field(min_length=1)
    task_key: Literal["schema.interpretation", "semantic.adjudication", "semantic.topic_labelling"]
    fixture_authorisation: Literal["synthetic", "user_approved"]
    bundle: ModelAdjudicationBundle
    expected_labels: tuple[str, ...] = ()
    expected_parser_spec: dict[str, Any] | None = None
    expected_abstain: bool = False
    expected_locator_validity: bool | None = None

    @model_validator(mode="after")
    def matching_task(self):
        if self.bundle.task_key != self.task_key:
            raise ValueError("benchmark case task and bundle task must match")
        return self


class BenchmarkInvocation(FrozenModel):
    case_id: str
    task_key: str
    engine_id: str
    provider: str
    model: str | None = None
    execution_location: Literal["local", "external"]
    output: Any | None = None
    structured_error: dict[str, Any] | None = None
    execution_record_id: str | None = None
    latency_ms: float = Field(ge=0)
    peak_memory_bytes: int | None = Field(default=None, ge=0)
    configured_cost: dict[str, float | int | str | None] = Field(default_factory=dict)


class BenchmarkScore(FrozenModel):
    metric: BenchmarkMetric
    value: float | int | str | None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=0)
    notes: str | None = None


class TaskBenchmarkReport(FrozenModel):
    report_version: str
    task_key: str
    engine_id: str
    provider: str
    model: str | None = None
    created_at: datetime
    case_count: int = Field(ge=0)
    scores: tuple[BenchmarkScore, ...]
    invocations: tuple[BenchmarkInvocation, ...]
    selection_recommendation: None = None


class BenchmarkExecutor(Protocol):
    async def invoke(self, case: BenchmarkCase) -> BenchmarkInvocation: ...
