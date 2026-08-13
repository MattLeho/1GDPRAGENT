"""Regression inventory for stateful Intelligence profile consumption."""
from pathlib import Path

ROOT = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_ingest_and_validation_persist_signed_profile_authority():
    ingest = source("intelligence/api/ingest.py")
    request_repository = source("intelligence/request_domain/repository.py")
    validate = source("intelligence/api/validate.py")
    assert ingest.count("Depends(require_profile_id)") >= 2
    assert "RequestRepository().exists(profile_id,body.request_id)" in ingest
    assert "SELECT 1 FROM requests WHERE id=$1 AND profile_id=$2" in request_repository
    assert '"profile_id": str(profile_id)' in ingest
    assert "profile_id=profile_id" in ingest
    assert validate.count("Depends(require_profile_id)") >= 2
    assert validate.count("profile_id=profile_id") >= 2


def test_onsit_ids_and_connector_credentials_are_profile_scoped():
    onsit = source("intelligence/api/onsit.py")
    connectors = source("intelligence/api/connectors.py")
    assert onsit.count("Depends(require_profile_id)") >= 4
    assert "get_status(scan_id,profile_id)" in onsit
    assert "profile_id=profile_id" in onsit
    assert "cancel_scan(scan_id,profile_id)" in onsit
    assert "AND profile_id=$2" in connectors
    assert "profile_id=body.profile_id" not in connectors


def test_context_artifacts_and_browser_pairing_have_distinct_authority_paths():
    insights = source("intelligence/api/insights.py")
    connectors = source("intelligence/api/connectors.py")
    main = source("intelligence/main.py")
    assert "es.profile_id=$2" in insights
    assert "source artifact does not exist" in insights
    browser_sync = connectors.split('@router.post("/browser/sync")', 1)[1]
    assert "Depends(require_profile_id)" not in browser_sync
    assert "Bearer " in browser_sync
    assert "is_separately_authorized_ingress(request)" in main


def test_bulk_worker_revalidates_profile_run_snapshot_and_file_linkage():
    tasks = source("intelligence/tasks.py")
    assert "async def _require_bulk_job_profile" in tasks
    assert "es.analysis_run_id=ar.id AND es.profile_id=ar.profile_id" in tasks
    assert "RequestRepository(postgres).received_data_exists(profile_id,received_data_id)" in tasks
    assert "run_async(_require_bulk_job_profile(data))" in tasks
    assert 'data["profile_id"]' in tasks


def test_worker_handoffs_inventory_carries_profile_authority():
    ingest = source("intelligence/api/ingest.py")
    bulk = source("intelligence/api/bulk_ingestion.py")
    connectors = source("intelligence/api/connectors.py")
    onsit = source("intelligence/tasks.py")
    assert '"profile_id": str(profile_id)' in ingest
    assert '"profile_id":str(profile_id)' in bulk
    assert '"profile_id": str(profile_id)' in connectors
    assert 'if not profile_id: raise ValueError("profile authority is required")' in onsit
