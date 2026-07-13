"""Benchmark executor that delegates exclusively to Task 2's audited router API."""
from __future__ import annotations

from typing import Any

import httpx

from .contracts import BenchmarkCase, BenchmarkInvocation


class Task2RouterBenchmarkExecutor:
    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None, timeout_seconds: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.timeout_seconds = timeout_seconds

    async def invoke(self, case: BenchmarkCase) -> BenchmarkInvocation:
        payload: dict[str, Any] = {
            "case_id": case.case_id,
            "fixture_authorisation": case.fixture_authorisation,
            "bundle": case.bundle.model_dump(mode="json"),
        }
        if self.client is not None:
            response = await self.client.post("/api/ingestion/benchmark-invoke", json=payload)
        else:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                response = await client.post("/api/ingestion/benchmark-invoke", json=payload)
        response.raise_for_status()
        return BenchmarkInvocation.model_validate(response.json())
