"""Review-first dry-run deletion plan construction; never executes deletion."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Mapping
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client

from .models import (
    DeletionItemGroup, DeletionPlan, DeletionPlanItem, DeletionStage,
    RetentionAction, RetentionClass, RetentionDecision, RetentionPolicy,
)


@dataclass(frozen=True, slots=True)
class DeletionPlanSummary:
    eligible: int
    protected: int
    uncertain: int
    estimated_source_deletion: int


def build_deletion_plan(
    policy: RetentionPolicy, decisions: tuple[RetentionDecision, ...], *,
    analysis_run_id: UUID, source_delete_capabilities: Mapping[UUID, bool] | None = None,
    created_at: datetime | None = None,
) -> tuple[DeletionPlan, DeletionPlanSummary]:
    capabilities = source_delete_capabilities or {}
    plan_id = uuid4(); items = []
    for decision in decisions:
        reasons = [f"retention_class:{decision.classification.value}", f"confidence:{decision.confidence:.3f}"]
        if decision.classification is RetentionClass.UNSURE:
            group = DeletionItemGroup.UNCERTAIN
            action = RetentionAction.REVIEW_ONLY
            reasons.append("UNSURE defaults to keep/review")
        elif decision.protected:
            group = DeletionItemGroup.PROTECTED
            action = RetentionAction.REVIEW_ONLY
            reasons.append("protected retention class")
        else:
            group = DeletionItemGroup.ELIGIBLE
            action = policy.action
        capability = bool(capabilities.get(decision.source_artifact_id, False))
        if action is RetentionAction.SOURCE_DELETE and not capability:
            group = DeletionItemGroup.PROTECTED
            action = RetentionAction.REVIEW_ONLY
            reasons.append("source connector lacks tested source-delete capability")
        items.append(DeletionPlanItem(
            id=uuid4(), source_artifact_id=decision.source_artifact_id,
            retention_decision_id=decision.id, group=group, action=action,
            reasons=tuple(reasons), source_delete_capability=capability,
            stage=DeletionStage.CANDIDATE,
        ))
    plan = DeletionPlan(
        id=plan_id, policy_id=policy.id, policy_version=policy.version,
        analysis_run_id=analysis_run_id, dry_run=True, items=tuple(items),
        created_at=created_at or datetime.now(timezone.utc),
    )
    summary = DeletionPlanSummary(
        eligible=sum(item.group is DeletionItemGroup.ELIGIBLE for item in items),
        protected=sum(item.group is DeletionItemGroup.PROTECTED for item in items),
        uncertain=sum(item.group is DeletionItemGroup.UNCERTAIN for item in items),
        estimated_source_deletion=sum(
            item.group is DeletionItemGroup.ELIGIBLE and item.action is RetentionAction.SOURCE_DELETE
            for item in items
        ),
    )
    return plan, summary


class DeletionPlanRepository:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def save(self, plan: DeletionPlan) -> DeletionPlan:
        await self.postgres.execute(
            """INSERT INTO deletion_plans(id,policy_id,policy_version,analysis_run_id,dry_run,status,created_at)
               VALUES($1,$2,$3,$4,$5,'draft',$6) ON CONFLICT(id) DO NOTHING""",
            plan.id, plan.policy_id, plan.policy_version, plan.analysis_run_id,
            plan.dry_run, plan.created_at,
        )
        for item in plan.items:
            await self.postgres.execute(
                """INSERT INTO deletion_plan_items(
                   id,deletion_plan_id,source_artifact_id,retention_decision_id,item_group,
                   action,reasons,source_delete_capability,stage,quarantine_at,grace_expires_at)
                   VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11) ON CONFLICT(id) DO NOTHING""",
                item.id, plan.id, item.source_artifact_id, item.retention_decision_id,
                item.group.value, item.action.value, json.dumps(item.reasons),
                item.source_delete_capability, item.stage.value,
                item.quarantine_at, item.grace_expires_at,
            )
        return plan

    async def review_decision(
        self, decision_id: UUID, *, actor: str, approved: bool,
        reasons: tuple[str, ...] = (),
    ) -> None:
        if not actor.strip():
            raise ValueError("decision review requires an actor")
        status = "approved" if approved else "rejected"
        rows = await self.postgres.execute(
            """WITH updated AS (
                 UPDATE retention_decisions SET review_status=$2 WHERE id=$1 AND review_status='pending' RETURNING id
               ), audit AS (
                 INSERT INTO retention_decision_reviews(retention_decision_id,actor,review_status,reasons)
                 SELECT id,$3,$2,$4::jsonb FROM updated
               ) SELECT id FROM updated""",
            decision_id, status, actor.strip(), json.dumps(reasons),
        )
        if not rows:
            raise ValueError("only a pending retention decision can be reviewed")

    async def review_plan(self, plan_id: UUID, *, actor: str, confirmation: str) -> None:
        if not actor.strip() or confirmation != "REVIEW PLAN":
            raise ValueError("plan review requires actor and exact confirmation")
        rows = await self.postgres.execute(
            """WITH updated AS (
                 UPDATE deletion_plans SET status='reviewed',reviewed_at=NOW()
                 WHERE id=$1 AND status='draft' AND dry_run RETURNING id
               ), audit AS (
                 INSERT INTO deletion_plan_reviews(deletion_plan_id,actor,decision,confirmation)
                 SELECT id,$2,'reviewed',$3 FROM updated
               ) SELECT id FROM updated""",
            plan_id, actor.strip(), confirmation,
        )
        if not rows:
            raise ValueError("only a draft dry-run plan can be reviewed")

    async def approve_plan(self, plan_id: UUID, *, actor: str, confirmation: str) -> None:
        if not actor.strip() or confirmation != "APPROVE DESTRUCTIVE ACTIONS":
            raise ValueError("approval requires actor and exact destructive confirmation")
        rows = await self.postgres.execute(
            """WITH updated AS (
               UPDATE deletion_plans SET status='approved',dry_run=FALSE,approved_at=NOW()
                 WHERE id=$1 AND status='reviewed' AND dry_run
                   AND NOT EXISTS (
                     SELECT 1 FROM deletion_plan_items dpi
                     JOIN retention_decisions rd ON rd.id=dpi.retention_decision_id
                     WHERE dpi.deletion_plan_id=$1 AND dpi.item_group='eligible'
                       AND rd.review_status<>'approved'
                   ) RETURNING id
               ), audit AS (
                 INSERT INTO deletion_plan_reviews(deletion_plan_id,actor,decision,confirmation)
                 SELECT id,$2,'approved',$3 FROM updated
               ) SELECT id FROM updated""",
            plan_id, actor.strip(), confirmation,
        )
        if not rows:
            raise ValueError("only a reviewed dry-run plan with every eligible decision approved can be approved")
