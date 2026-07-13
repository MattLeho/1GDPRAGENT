from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(path):return (ROOT/path).read_text(encoding="utf-8")


def test_upload_routes_are_thin_registry_pipeline_clients_without_direct_ai():
    process=read("frontend/app/api/upload/process/route.ts")
    scan=read("frontend/app/api/upload/scan/route.ts")
    client=read("frontend/lib/ingestion/bulk.ts")
    combined=process+scan+client
    assert "processThroughBulkPipeline" in process and "processThroughBulkPipeline" in scan
    assert "/bulk-ingestion/process" in client and "executeTask({" in client
    for forbidden in ("GoogleGenAI","generateContent","inlineData","base64Data","gemini-"):
        assert forbidden not in combined
    assert "switch (action" not in process and "getMimeType" not in process+scan


def test_bulk_pipeline_orders_source_before_semantics_and_never_writes_graph():
    source=read("intelligence/ingestion/bulk.py")
    assert source.index("record_source_occurrence") < source.index("registry.resolve")
    assert "write_activity_events" in source and "catalogue_observations" in source
    assert "GraphProjectionService" not in source and "neo4j" not in source.lower()
    assert "specialist_task_requests" in source and "requested_tasks" in source


def test_legacy_model_summaries_are_not_backfilled_as_grounded_evidence():
    migration=read("database/migrations/015_task3_bulk_pipeline.sql")
    assert "legacy_model_summary" in migration and "unverified_legacy" in migration
    assert "WHERE ai_summary IS NOT NULL" in migration
