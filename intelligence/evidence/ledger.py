from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from db.postgres import PostgresClient, get_postgres_client

from .locators import resolve_locator
from .models import AssertionCreate, AssertionStatus, EvidenceLocatorCreate


class EvidenceLedger:
    def __init__(self, postgres: PostgresClient | None = None):
        self.postgres=postgres or get_postgres_client()

    async def create_analysis_run(self, run_type: str, pipeline_version: str, *, request_id: UUID | None=None, profile_id: UUID | None=None, configuration: dict | None=None, status: str="running") -> UUID:
        rows=await self.postgres.execute(
            """INSERT INTO analysis_runs(run_type,profile_id,request_id,status,pipeline_version,configuration,started_at)
               VALUES($1,$2,$3,$4,$5,$6::jsonb,NOW()) RETURNING id""",
            run_type,profile_id,request_id,status,pipeline_version,json.dumps(configuration or {}),
        )
        return rows[0]["id"]

    async def create_export_snapshot(self, analysis_run_id: UUID, source_type: str, *, request_id: UUID | None=None, profile_id: UUID | None=None, controller_key: str | None=None, exported_at: datetime | None=None, metadata: dict | None=None) -> UUID:
        rows=await self.postgres.execute(
            """INSERT INTO export_snapshots(profile_id,request_id,controller_key,source_type,exported_at,analysis_run_id,metadata)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb) RETURNING id""",
            profile_id,request_id,controller_key,source_type,exported_at,analysis_run_id,json.dumps(metadata or {}),
        )
        return rows[0]["id"]

    async def record_source_artifact(self, export_snapshot_id: UUID, content: bytes, *, storage_uri: str, original_path: str, file_name: str, parent_artifact_id: UUID | None=None, archive_member_path: str | None=None, declared_mime: str | None=None, detected_mime: str | None=None, extension: str | None=None, file_type_status: str="unknown", source_organisation: str | None=None, source_product: str | None=None, source_service: str | None=None) -> tuple[UUID,UUID]:
        digest=hashlib.sha256(content).hexdigest(); pool=await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            blob=await connection.fetchrow(
                """INSERT INTO content_blobs(sha256,byte_size,storage_uri) VALUES($1,$2,$3)
                   ON CONFLICT(sha256) DO UPDATE SET sha256=EXCLUDED.sha256 RETURNING id""",digest,len(content),storage_uri)
            artifact=await connection.fetchrow(
                """INSERT INTO source_artifacts(export_snapshot_id,parent_artifact_id,content_blob_id,original_path,archive_member_path,file_name,declared_mime,detected_mime,extension,file_type_status,canonical_hash,source_organisation,source_product,source_service)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                   RETURNING id""",
                export_snapshot_id,parent_artifact_id,blob["id"],original_path,archive_member_path,file_name,declared_mime,detected_mime,extension,file_type_status,digest,source_organisation,source_product,source_service)
            return blob["id"],artifact["id"]

    async def create_locator(self, data: EvidenceLocatorCreate, content: bytes) -> UUID:
        resolved=resolve_locator(content,data.locator_type,data.locator)
        raw_hash=hashlib.sha256(resolved).hexdigest()
        if data.expected_text is not None and resolved != data.expected_text.encode("utf-8"):
            raise ValueError("exact quoted text does not match the resolved source span")
        if data.expected_raw_hash is not None and raw_hash != data.expected_raw_hash:
            raise ValueError("resolved source span hash does not match the expected hash")
        verification_method="exact_quote_match" if data.expected_text is not None else ("structured_value_match" if data.expected_raw_hash is not None else "mechanical_resolution")
        rows=await self.postgres.execute(
            """INSERT INTO evidence_locators(artifact_id,locator_type,locator,raw_hash,verified,verification_method)
               VALUES($1,$2,$3::jsonb,$4,true,$5) RETURNING id""",
            data.artifact_id,data.locator_type.value,json.dumps(data.locator),raw_hash,verification_method,
        )
        return rows[0]["id"]

    async def create_assertion(self, data: AssertionCreate) -> UUID:
        pool=await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            return await self._insert_assertion(connection,data)

    async def _insert_assertion(self, connection, data: AssertionCreate, supersedes: UUID | None=None) -> UUID:
        row=await connection.fetchrow(
            """INSERT INTO assertions(subject_type,subject_ref,predicate,object_type,object_ref,object_value,assertion_type,data_class,status,epistemic_basis,confidence,valid_from,valid_to,temporal_precision,controller_observed_from,controller_observed_to,exported_at,ingested_at,derivation_method,derivation_version,analysis_run_id,supersedes_assertion_id)
               VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22) RETURNING id""",
            data.subject_type,data.subject_ref,data.predicate,data.object_type,data.object_ref,
            json.dumps(data.object_value) if data.object_value is not None else None,data.assertion_type,data.data_class.value,data.status.value,data.epistemic_basis.value,data.confidence,data.valid_from,data.valid_to,data.temporal_precision,data.controller_observed_from,data.controller_observed_to,data.exported_at,data.ingested_at,data.derivation_method,data.derivation_version,data.analysis_run_id,supersedes,
        )
        assertion_id=row["id"]
        if data.evidence_locator_ids:
            await connection.executemany("INSERT INTO assertion_evidence(assertion_id,evidence_locator_id) VALUES($1,$2)",[(assertion_id,item) for item in data.evidence_locator_ids])
        if data.source_assertion_ids:
            await connection.executemany("INSERT INTO assertion_derivations(assertion_id,source_assertion_id) VALUES($1,$2)",[(assertion_id,item) for item in data.source_assertion_ids])
        return assertion_id

    async def transition(self, assertion_id: UUID, status: AssertionStatus) -> None:
        await self.postgres.execute("UPDATE assertions SET status=$2 WHERE id=$1",assertion_id,status.value)

    async def supersede(self, old_id: UUID, replacement: AssertionCreate) -> UUID:
        if replacement.status is not AssertionStatus.ACCEPTED:
            raise ValueError("a superseding assertion must be accepted")
        pool=await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            old=await connection.fetchrow("SELECT status FROM assertions WHERE id=$1 FOR UPDATE",old_id)
            if not old or old["status"]!="accepted": raise ValueError("only an accepted assertion can be superseded")
            new_id=await self._insert_assertion(connection,replacement,old_id)
            await connection.execute("UPDATE assertions SET status='superseded',superseded_at=NOW() WHERE id=$1",old_id)
            return new_id

    @staticmethod
    def load_artifact_bytes(storage_uri: str) -> bytes:
        if not storage_uri.startswith("file://"): raise ValueError("only local file:// storage is supported")
        return Path(storage_uri[7:]).read_bytes()
