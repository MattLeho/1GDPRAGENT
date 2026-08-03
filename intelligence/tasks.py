"""
Celery Task Definitions

This module defines background tasks for the intelligence service.
Tasks are executed by Celery workers connected to Redis.
"""

import asyncio
from datetime import datetime, timezone
from celery import Celery
from config import get_settings

settings = get_settings()

# Create Celery app
app = Celery(
    "intelligence",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery with best practices
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Time limits
    task_time_limit=3600,           # Hard limit: 1 hour
    task_soft_time_limit=3300,      # Soft limit: 55 minutes (allows cleanup)
    # Reliability
    task_acks_late=True,            # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Requeue on worker crash
    task_acks_on_failure_or_timeout=True,
    # Performance
    worker_prefetch_multiplier=1,   # Fair task distribution
    worker_max_tasks_per_child=1000,  # Restart workers periodically (memory leaks)
    beat_schedule={
        "connector-recurring-sync": {
            "task": "intelligence.connectors.schedule_due",
            "schedule": 60.0,
            "options": {"expires": 55.0},
        },
    },
)


def run_async(coro):
    """Helper to run async functions in sync Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _require_bulk_job_profile(data: dict):
    """Revalidate queued run/snapshot/file linkage at worker execution time."""
    from uuid import UUID
    from db.postgres import get_postgres_client
    profile_id = UUID(data["profile_id"])
    received_data_id = UUID(data["received_data_id"]) if data.get("received_data_id") else None
    rows = await get_postgres_client().execute(
        """SELECT 1 FROM analysis_runs ar
           JOIN export_snapshots es ON es.id=$2 AND es.analysis_run_id=ar.id AND es.profile_id=ar.profile_id
           WHERE ar.id=$1 AND ar.profile_id=$3
             AND ($4::uuid IS NULL OR EXISTS (
                 SELECT 1 FROM received_data rd WHERE rd.id=$4 AND rd.profile_id=$3
             ))""",
        UUID(data["analysis_run_id"]), UUID(data["export_snapshot_id"]), profile_id, received_data_id,
    )
    if not rows:
        raise LookupError("bulk ingestion job authority linkage is invalid")
    return profile_id


# === IMPLEMENTED TASKS (Phase 2) ===


@app.task(bind=True, name="intelligence.health_check")
def health_check(self):
    """Simple health check task to verify Celery is working."""
    return {"status": "ok", "task_id": self.request.id}


@app.task(bind=True, name="intelligence.bulk_ingestion.process_file")
def bulk_ingestion_process_file(self, data: dict) -> dict:
    """Run the deterministic Task 3 pipeline with late acknowledgement/retry safety."""
    from dataclasses import asdict
    from uuid import UUID
    from ingestion.bulk import BulkIngestionService
    run_async(_require_bulk_job_profile(data))
    result=run_async(BulkIngestionService().process_file(
        data["file_path"],analysis_run_id=UUID(data["analysis_run_id"]),
        export_snapshot_id=UUID(data["export_snapshot_id"]),
        declared_mime=data.get("declared_mime"),original_path=data.get("original_path"),
        requested_tasks=tuple(data.get("requested_tasks") or ()),
        received_data_id=UUID(data["received_data_id"]) if data.get("received_data_id") else None,
    ))
    return asdict(result)


@app.task(
    bind=True, name="intelligence.connectors.sync",
    autoretry_for=(OSError, TimeoutError), retry_backoff=True,
    retry_backoff_max=900, retry_kwargs={"max_retries": 4},
)
def connector_sync(self, data: dict) -> dict:
    """Task 2/Celery execution entrypoint for scheduled connector runs."""
    from uuid import UUID
    from connectors.application import ConnectorApplication
    from connectors.models import SyncRunKind
    async def owned_run():
        application=ConnectorApplication()
        instance_id=UUID(data["connector_instance_id"]); profile_id=UUID(data["profile_id"])
        instance=await application.repository.get_instance(instance_id)
        if instance.profile_id != profile_id: raise LookupError("connector instance does not exist")
        return await application.run_instance(
            instance_id, kind=SyncRunKind(data.get("kind", "sync")),
            cursor_key=data.get("cursor_key", "default"),
        )
    result = run_async(owned_run())
    return result.model_dump(mode="json")


@app.task(bind=True, name="intelligence.connectors.schedule_due")
def connector_schedule_due(self, limit: int = 100) -> dict:
    """Claim due connector instances and enqueue their existing sync task."""
    from connectors.scheduler import ConnectorScheduler

    return run_async(ConnectorScheduler().enqueue_due(
        connector_sync.delay,
        now=datetime.now(timezone.utc),
        limit=limit,
    ))


@app.task(bind=True, name="intelligence.ingest_to_graph")
def ingest_to_graph_task(self, data: dict) -> dict:
    """
    Knowledge Graph Ingestion Task.
    
    Args:
        data: Dict with company_name, request_id, extracted_data, categories, source
        
    Returns:
        Ingestion result with stats
    """
    from agents.kg_ingestor import KGIngestorAgent, IngestRequest
    
    agent = KGIngestorAgent()
    request = IngestRequest(
        company_name=data.get("company_name", "Unknown"),
        request_id=data.get("request_id", ""),
        extracted_data=data.get("extracted_data", []),
        categories=data.get("categories", {}),
        source=data.get("source", "celery"),
        source_artifact=data.get("source_artifact", {}),
        profile_id=__import__("uuid").UUID(data["profile_id"]),
    )
    
    result = run_async(agent.ingest(request))
    
    return {
        "success": result.success,
        "request_id": result.request_id,
        "company_name": result.company_name,
        "total_items": result.total_items,
        "statements_executed": result.statements_executed,
        "statements_errored": result.statements_errored,
        "errors": result.errors,
        "candidate_assertion_ids": result.candidate_assertion_ids,
    }


@app.task(bind=True, name="intelligence.validate_triple")
def validate_triple_task(self, data: dict) -> dict:
    """
    MAKGED Triple Validation Task.
    
    Args:
        data: Dict with triple and context
        
    Returns:
        Validation result with decision
    """
    from validators.makged import MAKGEDValidator, Triple
    
    triple = Triple.from_dict(data.get("triple", {}))
    context = data.get("context", "")
    max_rounds = data.get("max_rounds", 3)
    
    validator = MAKGEDValidator(max_rounds=max_rounds)
    result = run_async(validator.validate(triple, context))
    
    return {
        "success": result.success,
        "decision": result.decision.value,
        "votes": result.votes,
        "rounds": result.rounds,
        "cypher_statement": result.cypher_statement,
    }


@app.task(bind=True, name="intelligence.shadow_query")
def shadow_query_task(self, data: dict) -> dict:
    """
    Shadow Oracle Query Task.
    
    Args:
        data: Dict with question and user_id
        
    Returns:
        Query result with answer
    """
    from agents.shadow_oracle import ShadowOracleAgent
    
    agent = ShadowOracleAgent()
    result = run_async(agent.query(
        question=data.get("question", ""),
        user_id=data.get("user_id", "root"),
    ))
    
    return {
        "question": result.question,
        "answer": result.answer,
        "evidence": result.evidence,
        "confidence": result.confidence,
    }


# === PLACEHOLDER TASKS (Future Phases) ===


@app.task(bind=True, name="intelligence.onsit.discover")
def onsit_discover(self, seeds: list, enrichers: list = None, profile_id: str | None = None) -> dict:
    """
    ONSIT Discovery Task.
    
    Performs OSINT discovery to find public information.
    
    Args:
        seeds: List of seed strings (emails, domains, usernames)
        enrichers: Optional list of specific enrichers to use
        
    Returns:
        Discovery result with findings
    """
    from onsit.orchestrator import ONSITOrchestrator
    
    orchestrator = ONSITOrchestrator()
    
    async def run_discovery():
        if not profile_id: raise ValueError("profile authority is required")
        authority_profile=__import__("uuid").UUID(profile_id)
        scan_id = await orchestrator.start_discovery(
            seeds=seeds,
            enrichers=enrichers,
            profile_id=authority_profile,
        )
        
        # Wait for completion (poll status)
        import asyncio
        for _ in range(60):  # Max 60 seconds
            status = await orchestrator.get_status(scan_id,authority_profile)
            if status and status.status in ("completed", "failed"):
                break
            await asyncio.sleep(1)
        
        # Get results
        findings = await orchestrator.get_findings(scan_id, limit=500,profile_id=authority_profile)
        status = await orchestrator.get_status(scan_id,authority_profile)
        
        return {
            "scan_id": scan_id,
            "status": status.status if status else "unknown",
            "findings_count": len(findings),
            "findings": [
                {
                    "type": f.entity_type.value,
                    "label": f.label,
                    "source": f.source,
                }
                for f in findings
            ],
        }
    
    return run_async(run_discovery())


@app.task(name="intelligence.extraction.extract_spo")
def extract_spo_triples(text: str, source_id: str) -> dict:
    """
    SPO Triple Extraction Task (Phase 4)
    
    Extracts subject-predicate-object triples from text using LLM.
    """
    # TODO: Implement in Phase 4
    return {"status": "not_implemented", "source_id": source_id}

