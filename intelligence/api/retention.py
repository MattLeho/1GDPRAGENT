"""Review-first retention and destructive-operation orchestration endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from db.postgres import get_postgres_client
from retention.controller_erasure import ControllerErasureService
from retention.deletion_plan import DeletionPlanRepository, build_deletion_plan
from retention.local_purge import LocalPurgeService
from retention.models import DeletionStage, RetentionAction, RetentionDecision, RetentionPolicy
from retention.source_delete import SourceDeletionService
from retention.staging import DeletionStagingService
from api.security import require_internal_request, require_profile_id


router = APIRouter(prefix="/retention", tags=["Retention"], dependencies=[Depends(require_internal_request)])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreatePolicy(StrictBody):
    id: UUID | None = None
    version: int = Field(default=1, ge=1)
    profile_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    scope: dict = Field(default_factory=dict)
    connector_keys: tuple[str, ...] = ()
    data_classes: tuple[str, ...] = ()
    minimum_age_seconds: int = Field(default=0, ge=0)
    eligibility_threshold: float = Field(default=1, ge=0, le=1)
    action: RetentionAction
    grace_period_seconds: int = Field(default=2592000, ge=0)
    configuration: dict = Field(default_factory=dict)
    enabled: bool = True


class BuildPlan(StrictBody):
    policy_id: UUID
    policy_version: int = Field(ge=1)
    analysis_run_id: UUID
    decision_ids: tuple[UUID, ...] = Field(min_length=1)


class EvaluateRetention(StrictBody):
    policy_id: UUID | None = None
    policy_version: int | None = Field(default=None, ge=1)
    as_of: datetime | None = None
    limit: int = Field(default=1000, ge=1, le=10_000)


class DecisionReview(StrictBody):
    actor: str = Field(min_length=1, max_length=200)
    approved: bool
    reasons: tuple[str, ...] = ()


class ExactReview(StrictBody):
    actor: str = Field(min_length=1, max_length=200)
    confirmation: str


class StageRequest(ExactReview):
    target: DeletionStage


class ControllerCandidateRequest(StrictBody):
    controller_key: str = Field(min_length=1, max_length=300)


class ControllerDraftRequest(ExactReview):
    company_name: str | None = Field(default=None, max_length=300)
    company_url: str | None = Field(default=None, max_length=1000)


@router.get("")
async def retention_overview(profile_id: UUID = Depends(require_profile_id)):
    postgres = get_postgres_client()
    policies = await postgres.execute("SELECT * FROM retention_policies WHERE profile_id=$1 ORDER BY updated_at DESC,id,policy_version DESC",profile_id)
    decisions = await postgres.execute("""SELECT rd.* FROM retention_decisions rd JOIN source_artifacts sa ON sa.id=rd.source_artifact_id JOIN export_snapshots es ON es.id=sa.export_snapshot_id WHERE es.profile_id=$1 ORDER BY rd.created_at DESC LIMIT 500""",profile_id)
    plans = await postgres.execute("""SELECT dp.* FROM deletion_plans dp JOIN retention_policies rp ON rp.id=dp.policy_id AND rp.policy_version=dp.policy_version WHERE rp.profile_id=$1 ORDER BY dp.created_at DESC LIMIT 100""",profile_id)
    items = await postgres.execute(
        "SELECT * FROM deletion_plan_items WHERE deletion_plan_id=ANY($1::uuid[]) ORDER BY item_group,id",
        [row["id"] for row in plans],
    ) if plans else []
    grouped = {}
    for item in items: grouped.setdefault(item["deletion_plan_id"], []).append(_json_row(item))
    result_plans = []
    for plan in plans:
        value = _json_row(plan); value["items"] = grouped.get(plan["id"], []); result_plans.append(value)
    return {
        "policies": [_json_row(row) for row in policies],
        "decisions": [_json_row(row) for row in decisions],
        "plans": result_plans,
    }


@router.post("/policies")
async def create_policy(body: CreatePolicy, profile_id: UUID = Depends(require_profile_id)):
    from retention.policy import RetentionRepository
    policy = RetentionPolicy(
        id=body.id or uuid4(), version=body.version, profile_id=profile_id,
        name=body.name, scope=body.scope, connector_keys=body.connector_keys,
        data_classes=body.data_classes, minimum_age=timedelta(seconds=body.minimum_age_seconds),
        eligibility_threshold=body.eligibility_threshold, action=body.action,
        grace_period=timedelta(seconds=body.grace_period_seconds),
        configuration=body.configuration, enabled=body.enabled,
    )
    await RetentionRepository().save_policy(policy)
    return policy


@router.post("/evaluate")
async def evaluate_retention(body: EvaluateRetention, profile_id: UUID = Depends(require_profile_id)):
    from retention.evaluation import RetentionEvaluationService
    try:
        return await RetentionEvaluationService().evaluate(
            profile_id=profile_id, as_of=body.as_of, policy_id=body.policy_id,
            policy_version=body.policy_version, limit=body.limit,
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans")
async def create_plan(body: BuildPlan, profile_id: UUID = Depends(require_profile_id)):
    postgres = get_postgres_client()
    try:
        policy = await _load_policy(postgres, body.policy_id, body.policy_version)
        if policy.profile_id != profile_id: raise LookupError("retention policy does not exist")
        rows = await postgres.execute(
            "SELECT * FROM retention_decisions WHERE id=ANY($1::uuid[])", list(body.decision_ids),
        )
        if len(rows) != len(set(body.decision_ids)):
            raise ValueError("one or more retention decisions do not exist")
        decisions = tuple(_decision(row) for row in rows)
        if any(
            item.policy_id != body.policy_id or item.policy_version != body.policy_version
            or item.analysis_run_id != body.analysis_run_id for item in decisions
        ):
            raise ValueError("all decisions must belong to the selected policy version and analysis run")
        capabilities = {}
        for row in await postgres.execute(
            """SELECT crr.source_artifact_id,bool_or(scd.supports_source_delete) capable
               FROM connector_raw_records crr JOIN connector_instances ci ON ci.id=crr.connector_instance_id
               JOIN source_connector_definitions scd ON scd.connector_key=ci.connector_key
                 AND scd.definition_version=ci.definition_version
               WHERE crr.source_artifact_id=ANY($1::uuid[]) GROUP BY crr.source_artifact_id""",
            [item.source_artifact_id for item in decisions],
        ):
            capabilities[row["source_artifact_id"]] = row["capable"]
        plan, summary = build_deletion_plan(
            policy, decisions, analysis_run_id=body.analysis_run_id,
            source_delete_capabilities=capabilities,
        )
        await DeletionPlanRepository(postgres).save(plan)
        return {"plan": plan, "summary": summary}
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/decisions/{decision_id}/review")
async def review_decision(decision_id: UUID, body: DecisionReview, profile_id: UUID = Depends(require_profile_id)):
    try:
        await _require_decision_profile(decision_id,profile_id)
        await DeletionPlanRepository().review_decision(
            decision_id, actor=f"profile:{profile_id}", approved=body.approved, reasons=body.reasons,
        )
        return {"reviewed": True}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/review")
async def review_plan(plan_id: UUID, body: ExactReview, profile_id: UUID = Depends(require_profile_id)):
    try:
        await _require_plan_profile(plan_id,profile_id)
        await DeletionPlanRepository().review_plan(plan_id, actor=f"profile:{profile_id}", confirmation=body.confirmation)
        return {"reviewed": True}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/approve")
async def approve_plan(plan_id: UUID, body: ExactReview, profile_id: UUID = Depends(require_profile_id)):
    try:
        await _require_plan_profile(plan_id,profile_id)
        await DeletionPlanRepository().approve_plan(plan_id, actor=f"profile:{profile_id}", confirmation=body.confirmation)
        return {"approved": True, "dry_run": False}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/items/{item_id}/stage")
async def stage_item(item_id: UUID, body: StageRequest, profile_id: UUID = Depends(require_profile_id)):
    try:
        await _require_item_profile(item_id,profile_id)
        return await DeletionStagingService().transition(
            item_id, body.target, actor=f"profile:{profile_id}", confirmation=body.confirmation,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/items/{item_id}/execute")
async def execute_item(item_id: UUID, body: ExactReview, profile_id: UUID = Depends(require_profile_id)):
    if body.confirmation != "EXECUTE REVIEWED ACTION":
        raise HTTPException(status_code=422, detail="exact execution confirmation required")
    await _require_item_profile(item_id,profile_id)
    row = await get_postgres_client().execute("SELECT action FROM deletion_plan_items WHERE id=$1", item_id)
    if not row: raise HTTPException(status_code=404, detail="deletion plan item not found")
    try:
        if row[0]["action"] == "local_purge": return await LocalPurgeService().execute(item_id)
        if row[0]["action"] == "source_delete": return await SourceDeletionService().execute(item_id)
        raise ValueError("this item requires the controller-erasure candidate workflow or review only")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/items/{item_id}/controller-erasure")
async def create_controller_candidate(item_id: UUID, body: ControllerCandidateRequest, profile_id: UUID = Depends(require_profile_id)):
    try:
        await _require_item_profile(item_id,profile_id)
        return await ControllerErasureService().create_candidate(item_id, controller_key=body.controller_key)
    except (ValueError, RuntimeError) as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/controller-erasure/{candidate_id}/draft")
async def create_controller_draft(candidate_id: UUID, body: ControllerDraftRequest, profile_id: UUID = Depends(require_profile_id)):
    try:
        rows=await get_postgres_client().execute("""SELECT 1 FROM controller_erasure_candidates c JOIN deletion_plan_items i ON i.id=c.deletion_plan_item_id JOIN deletion_plans p ON p.id=i.deletion_plan_id JOIN retention_policies rp ON rp.id=p.policy_id AND rp.policy_version=p.policy_version WHERE c.id=$1 AND rp.profile_id=$2""",candidate_id,profile_id)
        if not rows: raise LookupError("controller-erasure candidate does not exist")
        return await ControllerErasureService().review_and_create_draft(
            candidate_id, actor=f"profile:{profile_id}", confirmation=body.confirmation,
            company_name=body.company_name, company_url=body.company_url,
        )
    except (ValueError, RuntimeError) as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _load_policy(postgres, policy_id, version):
    rows = await postgres.execute(
        "SELECT * FROM retention_policies WHERE id=$1 AND policy_version=$2", policy_id, version,
    )
    if not rows: raise LookupError("retention policy does not exist")
    row = rows[0]
    return RetentionPolicy(
        id=row["id"], version=row["policy_version"], profile_id=row["profile_id"], name=row["name"],
        scope=_decoded(row["scope"]), connector_keys=tuple(_decoded(row["connector_keys"])),
        data_classes=tuple(_decoded(row["data_classes"])),
        minimum_age=timedelta(seconds=row["minimum_age_seconds"]),
        eligibility_threshold=float(row["eligibility_threshold"]), action=row["action"],
        schedule=_decoded(row["schedule"]) if row["schedule"] else None,
        grace_period=timedelta(seconds=row["grace_period_seconds"]),
        configuration=_decoded(row["configuration"]), enabled=row["enabled"],
    )


async def _require_plan_profile(plan_id: UUID, profile_id: UUID) -> None:
    rows=await get_postgres_client().execute("""SELECT 1 FROM deletion_plans p JOIN retention_policies rp ON rp.id=p.policy_id AND rp.policy_version=p.policy_version WHERE p.id=$1 AND rp.profile_id=$2""",plan_id,profile_id)
    if not rows: raise LookupError("deletion plan does not exist")


async def _require_item_profile(item_id: UUID, profile_id: UUID) -> None:
    rows=await get_postgres_client().execute("""SELECT 1 FROM deletion_plan_items i JOIN deletion_plans p ON p.id=i.deletion_plan_id JOIN retention_policies rp ON rp.id=p.policy_id AND rp.policy_version=p.policy_version WHERE i.id=$1 AND rp.profile_id=$2""",item_id,profile_id)
    if not rows: raise LookupError("deletion plan item does not exist")


async def _require_decision_profile(decision_id: UUID, profile_id: UUID) -> None:
    rows=await get_postgres_client().execute("""SELECT 1 FROM retention_decisions rd JOIN source_artifacts sa ON sa.id=rd.source_artifact_id JOIN export_snapshots es ON es.id=sa.export_snapshot_id WHERE rd.id=$1 AND es.profile_id=$2""",decision_id,profile_id)
    if not rows: raise LookupError("retention decision does not exist")


def _decision(row):
    return RetentionDecision(
        id=row["id"], source_artifact_id=row["source_artifact_id"], classification=row["classification"],
        deterministic_evidence=_decoded(row["deterministic_evidence"]),
        semantic_adjudication=_decoded(row["semantic_adjudication"]) if row["semantic_adjudication"] else None,
        confidence=float(row["confidence"]), policy_id=row["policy_id"],
        policy_version=row["policy_version"], analysis_run_id=row["analysis_run_id"],
        review_status=row["review_status"], created_at=row["created_at"],
    )


def _decoded(value): return json.loads(value) if isinstance(value, str) else value


def _json_row(row):
    value = dict(row)
    for key, item in tuple(value.items()):
        if isinstance(item, str) and item[:1] in {"{", "["}:
            try: value[key] = json.loads(item)
            except json.JSONDecodeError: pass
    return value
