from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task3_roles_reuse_task2_router_with_bounded_bundles():
    source = read("frontend/lib/execution/task3.ts")
    for task in (
        "schema.interpretation", "semantic.adjudication", "semantic.topic_labelling",
        "image.caption", "image.landmark_candidate", "media.summary", "graph.explanation",
    ):
        assert task in source
    assert "executeTask({" in source
    assert "maximum_sample_bytes" in source and "Buffer.byteLength" in source
    assert "262_144" in source
    assert "JSON.parse(candidate)" in source and "structured_output_valid:false" in source
    assert "GoogleGenAI" not in source and "generateRLMResponse" not in source


def test_semantic_residue_endpoints_only_submit_candidates_not_facts():
    schema = read("frontend/app/api/ingestion/schema-interpretation/route.ts")
    feature = read("frontend/app/api/ingestion/feature-adjudication/route.ts")
    assert "executeTask3Bundle" in schema and "review_status:'proposed'" in schema
    assert "review_status:'approved'" not in schema
    assert "semantic.adjudication" in feature and "semantic.topic_labelling" in feature
    assert "executeTask3Bundle" in feature
    assert "GoogleGenAI" not in schema + feature


def test_privacy_modes_fail_closed_for_external_candidates():
    router = read("frontend/lib/execution/router.ts")
    assert "privacy.processing_mode === 'strict_local'" in router
    assert "privacy.processing_mode === 'local_first'" in router
    assert "!privacy.external_fallback_enabled || !explicitlyFallback" in router
    assert "privacy.processing_mode === 'controlled_cloud' && !privacy.approved_external_engines.includes(candidate.engine.engine_id)" in router
    assert "PRIVACY_POLICY_BLOCK" in router and "startExecutionRecord" in router


def test_unknown_provider_cannot_fall_through_to_google():
    adapters = read("frontend/lib/rlm/provider-adapters.ts")
    normalizer = adapters.split("export function normalizeRLMProvider", 1)[1].split("export function providerSupportsToolCalling", 1)[0]
    assert "Unsupported provider" in normalizer
    assert "return 'google'" not in normalizer
    router = read("frontend/lib/execution/router.ts")
    assert "provider:engine.provider" in router
    assert "route.provider !== engine.provider" in router


def test_python_runtime_has_only_local_service_adapters_not_second_cloud_registry():
    adapters = read("intelligence/execution/adapters.py")
    assert "parakeet_local" in adapters and "whisper_local" in adapters and "local_ocr" in adapters
    for cloud in ("api.openai.com", "openrouter.ai", "generativelanguage.googleapis.com", "api-inference.huggingface.co", "integrate.api.nvidia.com"):
        assert cloud not in adapters


def test_private_benchmark_invokes_the_audited_router_and_records_execution_metadata():
    route = read("frontend/app/api/ingestion/benchmark-invoke/route.ts")
    executor = read("intelligence/benchmark/task2_executor.py")
    assert "executeTask3Bundle" in route and "execution_records" in route
    assert "fixture_authorisation" in route and "synthetic" in route and "user_approved" in route
    assert "execution_location" in route and "configured_cost" in route and "peak_memory_bytes" in route
    assert "/api/ingestion/benchmark-invoke" in executor
    assert "openai" not in executor.lower() and "google" not in executor.lower()
