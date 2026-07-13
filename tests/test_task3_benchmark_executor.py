from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from benchmark.contracts import BenchmarkCase
from benchmark.task2_executor import Task2RouterBenchmarkExecutor
from ingestion.models import ModelAdjudicationBundle


@pytest.mark.asyncio
async def test_benchmark_executor_delegates_case_to_task2_router_api():
    run_id, artifact_id = uuid4(), uuid4()
    bundle = ModelAdjudicationBundle(
        task_key="schema.interpretation", analysis_run_id=run_id,
        source_artifact_ids=(artifact_id,), purpose="synthetic schema fixture",
        samples=({"keys": ["id", "time"]},), maximum_sample_bytes=1024,
        fingerprint_id="a" * 64,
    )
    case = BenchmarkCase(
        case_id="schema-001", task_key="schema.interpretation",
        fixture_authorisation="synthetic", bundle=bundle,
        expected_parser_spec={"event_type": "fixture.event"},
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "case_id":"schema-001", "task_key":"schema.interpretation",
            "engine_id":"ollama_generation", "provider":"ollama", "model":"fixture",
            "execution_location":"local", "output":{"event_type":"fixture.event"},
            "structured_error":None, "execution_record_id":str(uuid4()),
            "latency_ms":12.5, "peak_memory_bytes":2048, "configured_cost":{},
        })

    async with httpx.AsyncClient(
        base_url="http://task2-router.test", transport=httpx.MockTransport(handler),
    ) as client:
        invocation = await Task2RouterBenchmarkExecutor(
            "http://task2-router.test", client=client,
        ).invoke(case)
    assert captured["fixture_authorisation"] == "synthetic"
    assert captured["bundle"]["maximum_sample_bytes"] == 1024
    assert captured["bundle"]["source_artifact_ids"] == [str(artifact_id)]
    assert invocation.provider == "ollama" and invocation.execution_location == "local"
