from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTE_PATH = "frontend/app/api/insights/media-analysis/route.ts"
ROUTER_PATH = "frontend/lib/execution/router.ts"
REGISTRY_PATH = "frontend/lib/execution/registry.ts"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source)


def function_body(source: str, signature: str) -> str:
    """Return a TS function body using balanced braces, not a fragile line slice."""
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"', "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"Unbalanced function body for {signature}")


def test_metadata_only_returns_before_provenance_resolution_or_task_execution():
    route = read(ROUTE_PATH)
    post = compact(function_body(route, "export async function POST"))

    metadata_branch = "if(body.mode==='metadata_only'){returnNextResponse.json({mode:body.mode,tasks:[],external_calls:0});}"
    assert metadata_branch in post
    assert post.index(metadata_branch) < post.index("if(!body.analysisRunId")
    assert post.index(metadata_branch) < post.index("constsource=awaitpool.query")
    assert post.index(metadata_branch) < post.index("invokeAndPersist(")

    # The endpoint cannot bypass the central router with a provider SDK/fetch call.
    assert "generateRLMResponse" not in route
    assert "GoogleGenAI" not in route
    assert "invokeEngine(" not in route


def test_selective_visual_is_staged_from_origin_and_never_runs_all_tasks_blindly():
    post = compact(function_body(read(ROUTE_PATH), "export async function POST"))

    origin_call = "constorigin=awaitinvokeAndPersist('image.origin_classification',resolved,input);"
    assert origin_call in post
    assert post.index(origin_call) < post.index("constremaining=")
    assert "originValue==='screenshot'?['image.ocr','image.caption']" in post
    assert "originValue==='unknown'?['image.landmark_candidate']:[]" in post

    # A confident camera/download/generated classification has no selective
    # semantic follow-up because the terminal fallback is the empty list.
    assert post.count("invokeAndPersist('image.origin_classification'") == 1
    assert "for(consttaskKeyofremaining)" in post


def test_full_visual_runs_the_complete_bounded_visual_task_set():
    post = compact(function_body(read(ROUTE_PATH), "export async function POST"))
    assert "body.mode==='full_visual'?['image.ocr','image.caption','image.landmark_candidate']" in post

    requested = set(re.findall(r"'image\.(?:origin_classification|ocr|caption|landmark_candidate)'", post))
    assert requested == {
        "'image.origin_classification'",
        "'image.ocr'",
        "'image.caption'",
        "'image.landmark_candidate'",
    }


def test_each_visual_task_is_persisted_before_and_after_central_execution():
    route = read(ROUTE_PATH)
    helper = compact(function_body(route, "async function invokeAndPersist"))

    insert_at = helper.index("INSERTINTOspecialist_task_requests")
    execute_at = helper.index("constresult=awaitexecuteTask(")
    update_at = helper.index("UPDATEspecialist_task_requestsSETstatus=")
    assert insert_at < execute_at < update_at
    assert "ONCONFLICT(analysis_run_id,artifact_id,task_key)DOUPDATE" in helper
    assert "workflowKey:'task4.media-analysis'" in helper
    assert "sourceArtifactIds:[body.artifactId]" in helper
    assert "result.ok?'completed':result.error.code==='PRIVACY_POLICY_BLOCK'?'blocked':'failed'" in helper

    # One audited execution point is shared by origin and every staged task.
    assert route.count("executeTask({") == 1
    assert route.count("invokeAndPersist(") >= 3


def test_media_route_uses_the_fail_closed_task2_privacy_router():
    route = read(ROUTE_PATH)
    router = compact(read(ROUTER_PATH))

    assert "from'@/lib/execution/router'" in compact(route)
    assert "privacy.processing_mode==='strict_local'" in router
    assert "privacy.processing_mode==='local_first'&&(!privacy.external_fallback_enabled||!explicitlyFallback)" in router
    assert "privacy.processing_mode==='controlled_cloud'&&!privacy.approved_external_engines.includes(candidate.engine.engine_id)" in router
    assert "constblocked=external&&(" in router
    assert "PRIVACY_POLICY_BLOCK" in router
    assert "awaitfinishExecutionRecord(recordId,'blocked'" in router


def test_all_task4_visual_tasks_have_local_capable_default_routes():
    registry = compact(read(REGISTRY_PATH))
    definitions = {
        "image.origin_classification": "deterministic_image_origin",
        "image.ocr": "local_ocr",
        "image.caption": "local_visual",
        "image.landmark_candidate": "local_visual",
    }
    for task_key, default_engine in definitions.items():
        definition = re.search(
            rf"task\('{re.escape(task_key)}'.{{0,500}}?'({re.escape(default_engine)})'",
            registry,
        )
        assert definition, f"{task_key} must retain the local default {default_engine}"

    assert "engine_id:'deterministic_image_origin'" in registry
    assert "engine_id:'local_ocr'" in registry
    assert "engine_id:'local_visual'" in registry
    assert "execution_location:'local'" in registry
