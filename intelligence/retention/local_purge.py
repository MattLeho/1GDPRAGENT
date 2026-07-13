"""Provenance-preserving local blob purge with explicit tombstones."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client
from evidence.locators import resolve_locator
from evidence.purged import local_storage_path
from ingestion.storage import StorageRoots

from .models import LocalPurgeExecution


class LocalPurgeDenied(RuntimeError):
    pass


class LocalPurgeService:
    def __init__(
        self, postgres: PostgresClient | None = None, *, roots: StorageRoots | None = None,
    ) -> None:
        self.postgres = postgres or get_postgres_client()
        self.roots = (roots or StorageRoots.from_env()).ensure()

    async def execute(self, deletion_plan_item_id: UUID) -> LocalPurgeExecution:
        pool = await self.postgres._get_pool()
        execution_id = uuid4(); now = datetime.now(timezone.utc)
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """SELECT dpi.*,dp.status plan_status,dp.dry_run,rd.classification,rd.review_status,
                   sa.content_blob_id,cb.sha256,cb.byte_size,cb.storage_uri,
                   (SELECT COUNT(*) FROM source_artifacts other WHERE other.content_blob_id=sa.content_blob_id) blob_references
                FROM deletion_plan_items dpi JOIN deletion_plans dp ON dp.id=dpi.deletion_plan_id
                JOIN retention_decisions rd ON rd.id=dpi.retention_decision_id
                JOIN source_artifacts sa ON sa.id=dpi.source_artifact_id
                JOIN content_blobs cb ON cb.id=sa.content_blob_id WHERE dpi.id=$1""",
                deletion_plan_item_id,
            )
            if not row:
                raise LocalPurgeDenied("local purge plan item does not exist")
            self._preflight(row)
            if row["blob_references"] != 1:
                raise LocalPurgeDenied("content blob is shared by another SourceArtifact")
            path = local_storage_path(row["storage_uri"])
            blobs_root = self.roots.blobs.resolve()
            try:
                path.relative_to(blobs_root)
            except ValueError as exc:
                raise LocalPurgeDenied("only the connector's local content-addressed copy may be purged") from exc
            if not path.is_file():
                raise LocalPurgeDenied("local source content is already unavailable")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise LocalPurgeDenied("local content hash no longer matches the evidence ledger")
            required = await self._required_locators(connection, row["source_artifact_id"])
            segments = []
            for locator in required:
                raw_locator = json.loads(locator["locator"]) if isinstance(locator["locator"], str) else dict(locator["locator"])
                resolved = resolve_locator(content, locator["locator_type"], raw_locator)
                digest = hashlib.sha256(resolved).hexdigest()
                if digest != locator["raw_hash"]:
                    raise LocalPurgeDenied(f"required locator {locator['id']} no longer verifies")
                segments.append((locator["id"], resolved, digest))
            retained_unique = {segment[1] for segment in segments}
            if sum(len(value) for value in retained_unique) >= len(content) and content:
                raise LocalPurgeDenied("required evidence spans retain the full source; purge would not minimise data")
            basis = await self._basis(connection, row["source_artifact_id"], required)

        quarantine = path.with_name(f".{path.name}.purging-{execution_id}")
        path.replace(quarantine)
        committed = False
        try:
            async with pool.acquire() as connection, connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", str(deletion_plan_item_id))
                duplicate = await connection.fetchval(
                    "SELECT id FROM local_purge_executions WHERE deletion_plan_item_id=$1", deletion_plan_item_id,
                )
                if duplicate:
                    raise LocalPurgeDenied("local purge already executed")
                for locator_id, resolved, digest in segments:
                    await connection.execute(
                        """INSERT INTO minimized_evidence_segments(
                           evidence_locator_id,source_artifact_id,resolved_bytes,resolved_hash)
                           VALUES($1,$2,$3,$4) ON CONFLICT(evidence_locator_id) DO NOTHING""",
                        locator_id, row["source_artifact_id"], resolved, digest,
                    )
                await connection.execute(
                    """INSERT INTO content_purge_tombstones(
                       source_artifact_id,original_content_blob_id,original_sha256,content_purged_at,retained_evidence_basis)
                       VALUES($1,$2,$3,$4,$5::jsonb)""",
                    row["source_artifact_id"], row["content_blob_id"], row["sha256"], now,
                    json.dumps(basis, sort_keys=True),
                )
                await connection.execute(
                    """INSERT INTO local_purge_executions(
                       id,deletion_plan_item_id,source_artifact_id,content_purged_at,
                       retained_evidence_basis,evidence_locators_preserved)
                       VALUES($1,$2,$3,$4,$5::jsonb,TRUE)""",
                    execution_id, deletion_plan_item_id, row["source_artifact_id"], now,
                    json.dumps(basis, sort_keys=True),
                )
                await connection.execute(
                    "UPDATE deletion_plan_items SET stage='executed' WHERE id=$1 AND stage='eligible_for_delete'",
                    deletion_plan_item_id,
                )
            committed = True
            quarantine.unlink()
        except Exception:
            if not committed and quarantine.exists() and not path.exists():
                quarantine.replace(path)
            raise
        return LocalPurgeExecution(
            id=execution_id, deletion_plan_item_id=deletion_plan_item_id,
            source_artifact_id=row["source_artifact_id"], content_purged_at=now,
            retained_evidence_basis=basis, evidence_locators_preserved=True,
        )

    @staticmethod
    def _preflight(row) -> None:
        if row["dry_run"] or row["plan_status"] != "approved":
            raise LocalPurgeDenied("local purge requires an approved non-dry-run plan")
        if row["item_group"] != "eligible" or row["stage"] != "eligible_for_delete" or row["action"] != "local_purge":
            raise LocalPurgeDenied("local purge item is not eligible after grace")
        if row["review_status"] != "approved" or row["classification"] not in {"LOW_VALUE_BULK", "SPAM"}:
            raise LocalPurgeDenied("retention decision is not approved low-value/spam")

    @staticmethod
    async def _required_locators(connection, artifact_id: UUID):
        return await connection.fetch(
            """SELECT DISTINCT el.* FROM evidence_locators el WHERE el.artifact_id=$1 AND el.verified AND (
                 EXISTS(SELECT 1 FROM assertion_evidence ae JOIN assertions a ON a.id=ae.assertion_id
                        WHERE ae.evidence_locator_id=el.id AND a.status='accepted')
              OR EXISTS(SELECT 1 FROM insight_evidence_index iei
                        WHERE iei.locator_id=el.id)
              OR EXISTS(SELECT 1 FROM activity_event_observations aeo
                        WHERE aeo.source_locator_id=el.id)
              OR EXISTS(SELECT 1 FROM media_location_candidates mlc
                        WHERE mlc.evidence_locator_id=el.id)
            ) ORDER BY el.id""", artifact_id,
        )

    @staticmethod
    async def _basis(connection, artifact_id: UUID, required) -> dict:
        row = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM assertion_evidence ae JOIN assertions a ON a.id=ae.assertion_id
               JOIN evidence_locators el ON el.id=ae.evidence_locator_id WHERE el.artifact_id=$1 AND a.status='accepted') accepted_assertions,
              (SELECT COUNT(*) FROM insight_evidence_index WHERE artifact_id=$1) historical_insights,
              (SELECT COUNT(*) FROM activity_event_observations WHERE artifact_id=$1) event_observations,
              (SELECT COUNT(*) FROM media_location_candidates WHERE artifact_id=$1) media_candidates""", artifact_id,
        )
        return {
            "retained_locator_ids": [str(value["id"]) for value in required],
            "accepted_assertions": row["accepted_assertions"],
            "historical_insights": row["historical_insights"],
            "event_observations": row["event_observations"],
            "media_candidates": row["media_candidates"],
            "full_source_unavailable": True,
            "unretained_locator_resolution": "explicitly unavailable after reviewed purge",
        }
