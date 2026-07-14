"""Authorised, local-only ingestion of immutable policy source versions.

This module intentionally has no HTTP client or model integration.  A caller must
provide the exact bytes it is authorised to persist.  The bytes are stored in the
canonical content-addressed store and every policy version remains connected to
the Task 1 evidence ledger.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from db.postgres import PostgresClient, get_postgres_client
from evidence.locators import resolve_locator
from evidence.models import LocatorType, validate_locator_shape
from ingestion.storage import StorageRoots, write_raw_blob


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PolicyTextSpan(_FrozenModel):
    """An exact UTF-8 byte range suitable for grounding a later Claim."""

    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)
    expected_text: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> "PolicyTextSpan":
        if self.byte_end <= self.byte_start:
            raise ValueError("byte_end must exceed byte_start")
        if self.line_start is not None and self.line_end is not None and self.line_end < self.line_start:
            raise ValueError("line_end must not precede line_start")
        return self


class PolicySourceMetadata(_FrozenModel):
    policy_key: str = Field(min_length=1)
    version_label: str = Field(min_length=1)
    retrieved_at: datetime
    authorisation_basis: str = Field(min_length=1)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    source_uri: str | None = None
    file_name: str = Field(default="policy.txt", min_length=1)
    declared_mime: str = Field(default="text/plain", min_length=1)
    source_organisation: str | None = None
    source_product: str | None = None
    source_service: str | None = None
    profile_id: UUID | None = None
    request_id: UUID | None = None
    controller_key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates_and_name(self) -> "PolicySourceMetadata":
        dates = (self.retrieved_at, self.effective_from, self.effective_to)
        if any(value is not None and value.tzinfo is None for value in dates):
            raise ValueError("policy dates must be timezone-aware")
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        name = PurePosixPath(self.file_name.replace("\\", "/"))
        if name.name != str(name) or name.name in {".", ".."}:
            raise ValueError("file_name must be a basename")
        return self


class PolicySourceIngestionResult(_FrozenModel):
    policy_source_version_id: UUID
    analysis_run_id: UUID
    export_snapshot_id: UUID
    content_blob_id: UUID
    source_artifact_id: UUID
    evidence_locator_ids: tuple[UUID, ...]
    content_hash: str
    byte_size: int
    storage_uri: str
    created: bool


class PolicySourceIngestionService:
    """Persist caller-supplied policy bytes through canonical evidence tables."""

    PIPELINE_VERSION = "task6-policy-source-v1"

    def __init__(
        self,
        postgres: PostgresClient | None = None,
        *,
        blob_root: str | Path | None = None,
    ) -> None:
        self.postgres = postgres or get_postgres_client()
        self.blob_root = Path(blob_root) if blob_root is not None else StorageRoots.from_env().blobs

    async def ingest(
        self,
        content: bytes,
        metadata: PolicySourceMetadata,
        *,
        text_spans: tuple[PolicyTextSpan, ...] = (),
    ) -> PolicySourceIngestionResult:
        if not isinstance(content, bytes):
            raise TypeError("content must be exact caller-supplied bytes")
        if not content:
            raise ValueError("policy source content must not be empty")

        # Policy evidence must be resolvable as text.  Decode each requested span
        # separately below as well, which rejects offsets inside a UTF-8 codepoint.
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("policy source bytes must be valid UTF-8") from exc

        spans = text_spans or (PolicyTextSpan(byte_start=0, byte_end=len(content)),)
        locator_rows: list[tuple[dict[str, Any], str, str]] = []
        seen_locators: set[tuple[str, str]] = set()
        for span in spans:
            locator = span.model_dump(exclude={"expected_text"}, exclude_none=True)
            locator = validate_locator_shape(LocatorType.TEXT_SPAN, locator)
            resolved = resolve_locator(content, LocatorType.TEXT_SPAN, locator)
            try:
                resolved_text = resolved.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("text span boundaries must align to UTF-8 characters") from exc
            if span.expected_text is not None and resolved_text != span.expected_text:
                raise ValueError("exact quoted text does not match the resolved policy span")
            method = "exact_quote_match" if span.expected_text is not None else "mechanical_resolution"
            raw_hash = hashlib.sha256(resolved).hexdigest()
            key = (json.dumps(locator, sort_keys=True, separators=(",", ":")), raw_hash)
            if key not in seen_locators:
                locator_rows.append((locator, raw_hash, method))
                seen_locators.add(key)

        blob = write_raw_blob(self.blob_root, content)
        digest = blob.sha256
        lock_key = f"{metadata.policy_key}\x1f{metadata.version_label}\x1f{digest}"
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            # Serialise the check/create path without requiring another shared
            # migration.  The table's unique constraint remains the final guard.
            await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", lock_key)
            existing = await connection.fetchrow(
                """SELECT psv.id policy_source_version_id,sa.id source_artifact_id,
                          sa.export_snapshot_id,es.analysis_run_id,cb.id content_blob_id,
                          cb.byte_size,cb.storage_uri
                     FROM policy_source_versions psv
                     JOIN source_artifacts sa ON sa.id=psv.source_artifact_id
                     JOIN export_snapshots es ON es.id=sa.export_snapshot_id
                     JOIN content_blobs cb ON cb.id=sa.content_blob_id
                    WHERE psv.policy_key=$1 AND psv.version_label=$2 AND psv.content_hash=$3""",
                metadata.policy_key, metadata.version_label, digest,
            )
            if existing:
                if int(existing["byte_size"]) != len(content):
                    raise ValueError("existing policy content hash has a different byte size")
                for locator, raw_hash, method in locator_rows:
                    locator_id = await connection.fetchval(
                        """SELECT id FROM evidence_locators
                            WHERE artifact_id=$1 AND locator_type='text_span'
                              AND locator=$2::jsonb AND raw_hash=$3
                            ORDER BY created_at,id LIMIT 1""",
                        existing["source_artifact_id"], json.dumps(locator), raw_hash,
                    )
                    if locator_id is None:
                        await connection.execute(
                            """INSERT INTO evidence_locators(
                                   artifact_id,locator_type,locator,raw_hash,verified,verification_method)
                               VALUES($1,'text_span',$2::jsonb,$3,true,$4)""",
                            existing["source_artifact_id"], json.dumps(locator), raw_hash, method,
                        )
                locator_ids = await connection.fetch(
                    "SELECT id FROM evidence_locators WHERE artifact_id=$1 ORDER BY created_at,id",
                    existing["source_artifact_id"],
                )
                return PolicySourceIngestionResult(
                    policy_source_version_id=existing["policy_source_version_id"],
                    analysis_run_id=existing["analysis_run_id"],
                    export_snapshot_id=existing["export_snapshot_id"],
                    content_blob_id=existing["content_blob_id"],
                    source_artifact_id=existing["source_artifact_id"],
                    evidence_locator_ids=tuple(row["id"] for row in locator_ids),
                    content_hash=digest, byte_size=len(content),
                    storage_uri=existing["storage_uri"], created=False,
                )

            run_id = uuid4()
            snapshot_id = uuid4()
            artifact_id = uuid4()
            configuration = {
                "policy_key": metadata.policy_key,
                "version_label": metadata.version_label,
                "authorisation_basis": metadata.authorisation_basis,
                "network_fetch": False,
                "model_call": False,
            }
            await connection.execute(
                """INSERT INTO analysis_runs(id,run_type,profile_id,request_id,status,pipeline_version,
                                               configuration,started_at,completed_at)
                   VALUES($1,'policy_source_ingestion',$2,$3,'completed',$4,$5::jsonb,NOW(),NOW())""",
                run_id, metadata.profile_id, metadata.request_id, self.PIPELINE_VERSION,
                json.dumps(configuration),
            )
            snapshot_metadata = {
                **metadata.extra,
                "policy_key": metadata.policy_key,
                "version_label": metadata.version_label,
                "source_uri": metadata.source_uri,
                "authorisation_basis": metadata.authorisation_basis,
            }
            await connection.execute(
                """INSERT INTO export_snapshots(id,profile_id,request_id,controller_key,source_type,
                                                 exported_at,analysis_run_id,metadata)
                   VALUES($1,$2,$3,$4,'manual_import',$5,$6,$7::jsonb)""",
                snapshot_id, metadata.profile_id, metadata.request_id, metadata.controller_key,
                metadata.retrieved_at, run_id, json.dumps(snapshot_metadata),
            )
            blob_row = await connection.fetchrow(
                """INSERT INTO content_blobs(sha256,byte_size,storage_uri) VALUES($1,$2,$3)
                   ON CONFLICT(sha256) DO UPDATE SET sha256=EXCLUDED.sha256
                   RETURNING id,byte_size,storage_uri""",
                digest, len(content), blob.path.resolve().as_uri(),
            )
            if int(blob_row["byte_size"]) != len(content):
                raise ValueError("content hash already exists with a different byte size")
            suffixes = "".join(Path(metadata.file_name).suffixes).lower() or None
            await connection.execute(
                """INSERT INTO source_artifacts(
                       id,export_snapshot_id,content_blob_id,original_path,file_name,declared_mime,
                       detected_mime,extension,file_type_status,canonical_hash,source_organisation,
                       source_product,source_service)
                   VALUES($1,$2,$3,$4,$5,$6,$6,$7,'matched',$8,$9,$10,$11)""",
                artifact_id, snapshot_id, blob_row["id"],
                f"policies/{metadata.policy_key}/{metadata.version_label}/{metadata.file_name}",
                metadata.file_name, metadata.declared_mime, suffixes, digest,
                metadata.source_organisation, metadata.source_product, metadata.source_service,
            )
            locator_ids: list[UUID] = []
            for locator, raw_hash, method in locator_rows:
                locator_id = await connection.fetchval(
                    """INSERT INTO evidence_locators(
                           artifact_id,locator_type,locator,raw_hash,verified,verification_method)
                       VALUES($1,'text_span',$2::jsonb,$3,true,$4) RETURNING id""",
                    artifact_id, json.dumps(locator), raw_hash, method,
                )
                locator_ids.append(locator_id)
            version_id = await connection.fetchval(
                """INSERT INTO policy_source_versions(
                       source_artifact_id,policy_key,version_label,effective_from,effective_to,
                       retrieved_at,source_uri,content_hash)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
                artifact_id, metadata.policy_key, metadata.version_label,
                metadata.effective_from, metadata.effective_to, metadata.retrieved_at,
                metadata.source_uri, digest,
            )
            return PolicySourceIngestionResult(
                policy_source_version_id=version_id, analysis_run_id=run_id,
                export_snapshot_id=snapshot_id, content_blob_id=blob_row["id"],
                source_artifact_id=artifact_id, evidence_locator_ids=tuple(locator_ids),
                content_hash=digest, byte_size=len(content),
                storage_uri=blob_row["storage_uri"], created=True,
            )
