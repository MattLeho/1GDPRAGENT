"""Provider-neutral quarantine/grace state machine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from db.postgres import PostgresClient, get_postgres_client

from .models import DeletionItemGroup, DeletionPlanItem, DeletionStage


class DeletionStageError(ValueError):
    pass


def transition_stage(
    item: DeletionPlanItem, target: DeletionStage, *,
    now: datetime | None = None, grace_period: timedelta = timedelta(days=30),
) -> DeletionPlanItem:
    now = now or datetime.now(timezone.utc)
    if target is DeletionStage.CANCELLED and item.stage is not DeletionStage.EXECUTED:
        return item.model_copy(update={"stage": target})
    if item.group is not DeletionItemGroup.ELIGIBLE:
        raise DeletionStageError("protected and uncertain items cannot enter destructive stages")
    if item.stage is DeletionStage.CANDIDATE and target is DeletionStage.REVIEW:
        return item.model_copy(update={"stage": target})
    if item.stage is DeletionStage.REVIEW and target is DeletionStage.QUARANTINE:
        if grace_period < timedelta(0):
            raise DeletionStageError("grace period cannot be negative")
        return item.model_copy(update={
            "stage": target, "quarantine_at": now,
            "grace_expires_at": now + grace_period,
        })
    if item.stage is DeletionStage.QUARANTINE and target is DeletionStage.ELIGIBLE_FOR_DELETE:
        if item.grace_expires_at is None or now < item.grace_expires_at:
            raise DeletionStageError("grace period has not expired")
        return item.model_copy(update={"stage": target})
    raise DeletionStageError(f"cannot transition {item.stage.value} to {target.value}")


class DeletionStagingService:
    """Persist the reviewed quarantine state machine under a row lock."""

    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def transition(
        self, item_id: UUID, target: DeletionStage, *, actor: str,
        confirmation: str, now: datetime | None = None,
    ) -> DeletionPlanItem:
        if not actor.strip():
            raise DeletionStageError("staging requires an actor")
        expected = {
            DeletionStage.REVIEW: "MARK FOR REVIEW",
            DeletionStage.QUARANTINE: "START QUARANTINE",
            DeletionStage.ELIGIBLE_FOR_DELETE: "CONFIRM GRACE EXPIRED",
            DeletionStage.CANCELLED: "CANCEL DELETION",
        }.get(target)
        if expected is None or confirmation != expected:
            raise DeletionStageError("staging requires the exact confirmation for the target stage")
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """SELECT dpi.*,dp.status plan_status,dp.dry_run,rp.grace_period_seconds
                   FROM deletion_plan_items dpi
                   JOIN deletion_plans dp ON dp.id=dpi.deletion_plan_id
                   JOIN retention_policies rp ON rp.id=dp.policy_id AND rp.policy_version=dp.policy_version
                   WHERE dpi.id=$1 FOR UPDATE OF dpi""", item_id,
            )
            if not row:
                raise DeletionStageError("deletion plan item does not exist")
            if target in {DeletionStage.QUARANTINE, DeletionStage.ELIGIBLE_FOR_DELETE}:
                if row["plan_status"] != "approved" or row["dry_run"]:
                    raise DeletionStageError("destructive staging requires an approved non-dry-run plan")
            item = _item_from_row(row)
            updated = transition_stage(
                item, target, now=now,
                grace_period=timedelta(seconds=row["grace_period_seconds"]),
            )
            await connection.execute(
                """UPDATE deletion_plan_items SET stage=$2,quarantine_at=$3,grace_expires_at=$4
                   WHERE id=$1""",
                item_id, updated.stage.value, updated.quarantine_at, updated.grace_expires_at,
            )
            return updated


def _item_from_row(row) -> DeletionPlanItem:
    import json
    reasons = json.loads(row["reasons"]) if isinstance(row["reasons"], str) else row["reasons"]
    return DeletionPlanItem(
        id=row["id"], source_artifact_id=row["source_artifact_id"],
        retention_decision_id=row["retention_decision_id"],
        group=row["item_group"], action=row["action"], reasons=tuple(reasons),
        source_delete_capability=row["source_delete_capability"], stage=row["stage"],
        quarantine_at=row["quarantine_at"], grace_expires_at=row["grace_expires_at"],
    )
