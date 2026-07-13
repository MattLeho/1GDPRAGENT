"""Review-first controller erasure candidates routed into canonical requests."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client

from .models import ControllerErasureCandidate, ReviewStatus


class ControllerErasureDenied(RuntimeError):
    pass


class ControllerErasureService:
    """Creates draft erasure requests only; it never sends them."""

    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def create_candidate(
        self, deletion_plan_item_id: UUID, *, controller_key: str,
    ) -> ControllerErasureCandidate:
        controller_key = controller_key.strip()
        if not controller_key:
            raise ControllerErasureDenied("controller key is required")
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """SELECT dpi.*,dp.status plan_status,dp.dry_run,rd.classification,rd.review_status
                   FROM deletion_plan_items dpi
                   JOIN deletion_plans dp ON dp.id=dpi.deletion_plan_id
                   JOIN retention_decisions rd ON rd.id=dpi.retention_decision_id
                   WHERE dpi.id=$1 FOR UPDATE OF dpi""", deletion_plan_item_id,
            )
            if not row:
                raise ControllerErasureDenied("deletion plan item does not exist")
            if row["action"] != "controller_erasure_candidate" or row["item_group"] != "eligible":
                raise ControllerErasureDenied("plan item is not an eligible controller-erasure candidate")
            if row["plan_status"] != "approved" or row["dry_run"]:
                raise ControllerErasureDenied("candidate creation requires an approved non-dry-run plan")
            if row["review_status"] != "approved" or row["classification"] not in {"LOW_VALUE_BULK", "SPAM"}:
                raise ControllerErasureDenied("retention decision is not approved low-value/spam")
            candidate = await connection.fetchrow(
                """INSERT INTO controller_erasure_candidates(id,deletion_plan_item_id,controller_key)
                   VALUES($1,$2,$3) ON CONFLICT(deletion_plan_item_id) DO UPDATE
                   SET controller_key=EXCLUDED.controller_key RETURNING *""",
                uuid4(), deletion_plan_item_id, controller_key,
            )
        return _candidate(candidate)

    async def review_and_create_draft(
        self, candidate_id: UUID, *, actor: str, confirmation: str,
        company_name: str | None = None, company_url: str | None = None,
    ) -> ControllerErasureCandidate:
        if not actor.strip() or confirmation != "CREATE DRAFT ERASURE REQUEST":
            raise ControllerErasureDenied("review requires actor and exact draft confirmation")
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                "SELECT * FROM controller_erasure_candidates WHERE id=$1 FOR UPDATE", candidate_id,
            )
            if not row:
                raise ControllerErasureDenied("controller-erasure candidate does not exist")
            if row["existing_request_id"]:
                return _candidate(row)
            preference = await connection.fetchrow(
                "SELECT enabled,configuration FROM workflow_preferences WHERE workflow_key='request.drafting'",
            )
            configuration = {}
            if preference:
                configuration = json.loads(preference["configuration"]) if isinstance(preference["configuration"], str) else dict(preference["configuration"])
            explicitly_enabled = bool(
                preference and preference["enabled"] and
                configuration.get("reviewed_auto_erasure_enabled") is True
            )
            controller = row["controller_key"]
            request_id = await connection.fetchval(
                """INSERT INTO requests(company_name,company_url,domain,status,request_type)
                   VALUES($1,$2,$3,'draft','erasure') RETURNING id""",
                (company_name or controller).strip(), company_url,
                controller,
            )
            row = await connection.fetchrow(
                """UPDATE controller_erasure_candidates SET review_status='approved',
                   automatic_execution_enabled=$2,existing_request_id=$3 WHERE id=$1 RETURNING *""",
                candidate_id, explicitly_enabled, request_id,
            )
            await connection.execute(
                "UPDATE deletion_plan_items SET stage='executed' WHERE id=$1 AND stage='eligible_for_delete'",
                row["deletion_plan_item_id"],
            )
        return _candidate(row)


def _candidate(row) -> ControllerErasureCandidate:
    return ControllerErasureCandidate(
        id=row["id"], deletion_plan_item_id=row["deletion_plan_item_id"],
        controller_key=row["controller_key"], existing_request_id=row["existing_request_id"],
        review_status=ReviewStatus(row["review_status"]),
        automatic_execution_enabled=row["automatic_execution_enabled"],
        created_at=row["created_at"] if row["created_at"] else datetime.now(timezone.utc),
    )
