"""PostgreSQL-backed schema/parser review workflow.

Unknown fingerprints create at most one bounded interpretation request per
interpretation version.  Proposed parser specs remain inert until a separate
human approval operation records an approver.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Literal, Mapping
from uuid import UUID

from .models import DeclarativeParserSpec, ModelAdjudicationBundle, ReviewStatus, StructureFingerprint
from .parser_runtime import validate_parser_spec
from .sampling import build_schema_interpretation_bundle


@dataclass(frozen=True, slots=True)
class RegistryMatch:
    fingerprint_id: str
    entry_id: UUID
    parser_spec_id: UUID
    spec: DeclarativeParserSpec
    review_status: ReviewStatus

    @property
    def executable(self) -> bool:
        return self.review_status is ReviewStatus.APPROVED


@dataclass(frozen=True, slots=True)
class InterpretationRequest:
    request_id: UUID
    created: bool


@dataclass(frozen=True, slots=True)
class SchemaResolution:
    outcome: Literal["known", "interpretation_required"]
    approved: RegistryMatch | None = None
    interpretation: InterpretationRequest | None = None
    bundle: ModelAdjudicationBundle | None = None


def canonical_spec(spec: DeclarativeParserSpec) -> tuple[dict[str, Any], str]:
    validate_parser_spec(spec)
    payload = spec.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return payload, hashlib.sha256(encoded).hexdigest()


class SchemaRegistry:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def resolve(
        self, fingerprint: StructureFingerprint, records: Iterable[Mapping[str, Any]], *,
        analysis_run_id: UUID, source_artifact_ids: tuple[UUID, ...],
        interpretation_version: str = "1", maximum_sample_bytes: int = 32_768,
    ) -> SchemaResolution:
        """Bypass interpretation for known schemas, otherwise enqueue once."""
        approved = await self.approved_match(fingerprint.fingerprint_id)
        if approved is not None:
            return SchemaResolution(outcome="known", approved=approved)
        fingerprint_id = await self.ensure_fingerprint(
            fingerprint_hash=fingerprint.fingerprint_id, family=fingerprint.family,
            provider_id=fingerprint.provider_id, provider_version=fingerprint.provider_version,
            canonical_shape=fingerprint.canonical_shape, sample_count=fingerprint.sample_count,
        )
        bundle = build_schema_interpretation_bundle(
            records, analysis_run_id=analysis_run_id, source_artifact_ids=source_artifact_ids,
            fingerprint_id=fingerprint.fingerprint_id, maximum_sample_bytes=maximum_sample_bytes,
        )
        request = await self.ensure_interpretation_request(
            analysis_run_id=analysis_run_id, structure_fingerprint_id=fingerprint_id,
            interpretation_version=interpretation_version, bundle=bundle,
        )
        return SchemaResolution(outcome="interpretation_required", interpretation=request, bundle=bundle)

    async def approved_match(self, fingerprint_hash: str) -> RegistryMatch | None:
        row = await self.connection.fetchrow(
            """SELECT sre.id entry_id,dps.id parser_spec_id,dps.spec,sre.review_status
            FROM structure_fingerprints sf
            JOIN schema_registry_entries sre ON sre.structure_fingerprint_id=sf.id
            JOIN declarative_parser_specs dps ON dps.id=sre.parser_spec_id
            WHERE sf.fingerprint_hash=$1 AND sre.review_status='approved' AND dps.review_status='approved'
            ORDER BY dps.approved_at DESC,dps.parser_version DESC LIMIT 1""", fingerprint_hash,
        )
        if row is None:
            return None
        raw_spec = json.loads(row["spec"]) if isinstance(row["spec"], str) else row["spec"]
        return RegistryMatch(
            fingerprint_id=fingerprint_hash, entry_id=row["entry_id"],
            parser_spec_id=row["parser_spec_id"], spec=DeclarativeParserSpec.model_validate(raw_spec),
            review_status=ReviewStatus(row["review_status"]),
        )

    async def ensure_fingerprint(self, *, fingerprint_hash: str, family: str, provider_id: str, provider_version: str, canonical_shape: dict[str, Any], sample_count: int) -> UUID:
        return await self.connection.fetchval(
            """INSERT INTO structure_fingerprints(fingerprint_hash,family,provider_id,provider_version,canonical_shape,sample_count)
            VALUES($1,$2,$3,$4,$5::jsonb,$6) ON CONFLICT(fingerprint_hash) DO UPDATE SET sample_count=GREATEST(structure_fingerprints.sample_count,EXCLUDED.sample_count)
            RETURNING id""", fingerprint_hash, family, provider_id, provider_version,
            json.dumps(canonical_shape, sort_keys=True), sample_count,
        )

    async def ensure_interpretation_request(self, *, analysis_run_id: UUID, structure_fingerprint_id: UUID, interpretation_version: str, bundle: ModelAdjudicationBundle, execution_record_id: UUID | None = None) -> InterpretationRequest:
        manifest = bundle.model_dump(mode="json")
        row = await self.connection.fetchrow(
            """WITH inserted AS (
              INSERT INTO schema_interpretation_requests(analysis_run_id,structure_fingerprint_id,interpretation_version,execution_record_id,sample_manifest)
              VALUES($1,$2,$3,$4,$5::jsonb) ON CONFLICT(structure_fingerprint_id,interpretation_version) DO NOTHING RETURNING id
            ) SELECT id,TRUE created FROM inserted
            UNION ALL SELECT id,FALSE created FROM schema_interpretation_requests
              WHERE structure_fingerprint_id=$2 AND interpretation_version=$3 AND NOT EXISTS(SELECT 1 FROM inserted)
            LIMIT 1""", analysis_run_id, structure_fingerprint_id, interpretation_version,
            execution_record_id, json.dumps(manifest, sort_keys=True),
        )
        return InterpretationRequest(row["id"], row["created"])

    async def propose(self, spec: DeclarativeParserSpec) -> UUID:
        payload, spec_hash = canonical_spec(spec)
        return await self.connection.fetchval(
            """WITH inserted AS (
              INSERT INTO declarative_parser_specs(parser_id,parser_version,file_family,spec,spec_hash,review_status)
              VALUES($1,$2,$3,$4::jsonb,$5,'proposed')
              ON CONFLICT(parser_id,parser_version) DO NOTHING RETURNING id
            ) SELECT id FROM inserted UNION ALL
              SELECT id FROM declarative_parser_specs WHERE parser_id=$1 AND parser_version=$2
            LIMIT 1""", spec.parser_id, spec.parser_version, spec.file_family,
            json.dumps(payload, sort_keys=True), spec_hash,
        )

    async def approve(self, *, parser_spec_id: UUID, approved_by: str, approved_at: datetime | None = None) -> None:
        if not approved_by.strip():
            raise ValueError("approved_by is required")
        result = await self.connection.execute(
            """UPDATE declarative_parser_specs SET review_status='approved',approved_by=$2,approved_at=COALESCE($3,NOW())
            WHERE id=$1 AND review_status='proposed'""", parser_spec_id, approved_by, approved_at,
        )
        if result != "UPDATE 1":
            raise ValueError("only a proposed parser can be approved")

    async def bind(self, *, structure_fingerprint_id: UUID, parser_spec_id: UUID, source_service: str | None, data_domain: str, file_family: str, normalised_event_type: str) -> UUID:
        return await self.connection.fetchval(
            """WITH inserted AS (
              INSERT INTO schema_registry_entries
              (structure_fingerprint_id,source_service,data_domain,file_family,parser_spec_id,normalised_event_type,review_status)
              SELECT $1,$2,$3,$4,$5,$6,'approved' FROM declarative_parser_specs WHERE id=$5 AND review_status='approved'
              ON CONFLICT(structure_fingerprint_id,parser_spec_id) DO NOTHING RETURNING id
            ) SELECT id FROM inserted UNION ALL SELECT id FROM schema_registry_entries
              WHERE structure_fingerprint_id=$1 AND parser_spec_id=$5 LIMIT 1""", structure_fingerprint_id, source_service, data_domain,
            file_family, parser_spec_id, normalised_event_type,
        )
