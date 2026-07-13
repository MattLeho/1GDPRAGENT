"""Authenticated, replay-safe local protocol for the Chromium extension."""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from db.postgres import PostgresClient, get_postgres_client

from .bridge import ConnectorIngestionBridge
from .definitions import BROWSER_HISTORY_DEFINITION
from .models import ConnectorRawRecord, SyncRunKind, SyncRunStatus
from .repository import ConnectorRepository


PROTOCOL_NAME = "gdpr-agent-connector"
PROTOCOL_VERSION = 1
MAX_RECORD_BYTES = 1_000_000
ALLOWED_METADATA = {
    "browser_profile_connector_id", "local_or_synced_origin",
    "referring_visit_id", "transition_type",
}
ALLOWED_PAYLOAD_FIELDS = {
    "browser_profile_connector_id", "referring_visit_id", "transition_type",
    "url", "visit_id", "visit_time",
}


class BrowserBridgeError(RuntimeError):
    pass


class BrowserBridgeAuthenticationError(BrowserBridgeError):
    pass


class BrowserBridgeReplayInProgress(BrowserBridgeError):
    pass


class BrowserVisitRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_record_id: str = Field(min_length=1, max_length=1000)
    source_record_version: str = Field(default="1", min_length=1, max_length=100)
    record_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_class: str
    occurred_at: datetime
    observed_at: datetime
    media_type: str
    payload_base64: str = Field(min_length=1, max_length=1_400_000)
    source_metadata: dict[str, Any]
    required_permissions: tuple[str, ...]

    @field_validator("occurred_at", "observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("bridge timestamps must include timezone")
        return value


class BrowserBridgeFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: str
    version: int
    message_id: UUID
    connector_instance_id: UUID
    sent_at: datetime
    records: tuple[BrowserVisitRecord, ...] = Field(min_length=1, max_length=250)

    @field_validator("sent_at")
    @classmethod
    def sent_timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("sent_at must include timezone")
        return value


class BrowserBridgeAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: str = PROTOCOL_NAME
    version: int = PROTOCOL_VERSION
    message_id: UUID
    status: str = "acknowledged"
    record_signatures: tuple[str, ...]
    ingested: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    events_produced: int = Field(ge=0)


class PairingToken(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pairing_id: UUID
    connector_instance_id: UUID
    token: str
    created_at: datetime


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class BrowserBridgeService:
    def __init__(
        self, postgres: PostgresClient | None = None, *,
        bridge: ConnectorIngestionBridge | None = None,
    ) -> None:
        self.postgres = postgres or get_postgres_client()
        self.repository = ConnectorRepository(self.postgres)
        self.bridge = bridge or ConnectorIngestionBridge(self.postgres)

    async def create_pairing(self, connector_instance_id: UUID, label: str) -> PairingToken:
        if not label.strip():
            raise ValueError("pairing label is required")
        await self.repository.declare_definition(BROWSER_HISTORY_DEFINITION)
        instance = await self.repository.get_instance(connector_instance_id)
        if instance.definition_key != BROWSER_HISTORY_DEFINITION.key:
            raise BrowserBridgeError("pairing requires a Chromium browser-history connector instance")
        token = secrets.token_urlsafe(32)
        rows = await self.postgres.execute(
            """INSERT INTO browser_bridge_pairings(connector_instance_id,token_hash,label)
               VALUES($1,$2,$3) RETURNING id,created_at""",
            connector_instance_id, _token_hash(token), label.strip(),
        )
        return PairingToken(
            pairing_id=rows[0]["id"], connector_instance_id=connector_instance_id,
            token=token, created_at=rows[0]["created_at"],
        )

    async def revoke_pairing(self, pairing_id: UUID) -> bool:
        rows = await self.postgres.execute(
            """UPDATE browser_bridge_pairings SET revoked_at=COALESCE(revoked_at,NOW())
               WHERE id=$1 RETURNING id""", pairing_id,
        )
        return bool(rows)

    async def receive(
        self, frame: BrowserBridgeFrame, bearer_token: str,
    ) -> BrowserBridgeAcknowledgement:
        if frame.protocol != PROTOCOL_NAME or frame.version != PROTOCOL_VERSION:
            raise BrowserBridgeError("unsupported browser bridge protocol/version")
        pairing = await self._authenticate(bearer_token, frame.connector_instance_id)
        replay = await self._claim_message(pairing["id"], frame)
        if replay is not None:
            return BrowserBridgeAcknowledgement.model_validate(replay)

        analysis_run_id = sync_run = None
        ingested = duplicates = events = 0
        cursor_before: dict[str, Any] = {}
        try:
            analysis_run_id = await self._start_analysis(frame.connector_instance_id)
            cursor = await self.repository.get_cursor(frame.connector_instance_id, "browser-history")
            cursor_before = dict(cursor.position) if cursor else {}
            sync_run = await self.repository.start_sync_run(
                frame.connector_instance_id, analysis_run_id, SyncRunKind.SYNC, cursor_before,
            )
            max_visit = cursor_before.get("last_visit_time")
            for item in frame.records:
                record, visit_time = self._record(item, frame.connector_instance_id)
                result = await self.bridge.ingest(record, sync_run_id=sync_run.id)
                duplicates += int(result.duplicate)
                ingested += int(not result.duplicate)
                events += result.event_count
                max_visit = max(max_visit, visit_time) if max_visit else visit_time
            cursor_after = {
                "last_visit_time": max_visit,
                "last_message_id": str(frame.message_id),
            }
            await self.repository.upsert_cursor(
                frame.connector_instance_id, cursor_after, cursor_key="browser-history",
                version=cursor.version if cursor else 1, source_watermark=max_visit,
            )
            await self.repository.finish_sync_run(
                sync_run.id, status=SyncRunStatus.COMPLETED, cursor_after=cursor_after,
                artefacts_discovered=len(frame.records), events_produced=events,
                duplicates_skipped=duplicates, errors=0,
            )
            await self.postgres.execute(
                "UPDATE analysis_runs SET status='completed',completed_at=NOW() WHERE id=$1",
                analysis_run_id,
            )
            acknowledgement = BrowserBridgeAcknowledgement(
                message_id=frame.message_id,
                record_signatures=tuple(item.record_signature for item in frame.records),
                ingested=ingested, duplicates=duplicates, events_produced=events,
            )
            await self.postgres.execute(
                """UPDATE browser_bridge_messages SET status='acknowledged',response=$3::jsonb,
                   completed_at=NOW() WHERE pairing_id=$1 AND message_id=$2""",
                pairing["id"], frame.message_id,
                acknowledgement.model_dump_json(),
            )
            await self.postgres.execute(
                "UPDATE browser_bridge_pairings SET last_seen_at=NOW() WHERE id=$1", pairing["id"],
            )
            return acknowledgement
        except Exception as exc:
            error = {"error": type(exc).__name__, "message": str(exc)}
            if sync_run is not None:
                try:
                    await self.repository.finish_sync_run(
                        sync_run.id, status=SyncRunStatus.FAILED, cursor_after=cursor_before,
                        artefacts_discovered=ingested + duplicates, events_produced=events,
                        duplicates_skipped=duplicates, errors=1, error=error,
                    )
                except Exception:
                    pass
            if analysis_run_id is not None:
                await self.postgres.execute(
                    "UPDATE analysis_runs SET status='failed',completed_at=NOW(),error=$2 WHERE id=$1",
                    analysis_run_id, str(exc),
                )
            await self.postgres.execute(
                """UPDATE browser_bridge_messages SET status='failed',response=$3::jsonb,
                   completed_at=NOW() WHERE pairing_id=$1 AND message_id=$2""",
                pairing["id"], frame.message_id, _json(error),
            )
            raise

    async def _authenticate(self, token: str, connector_instance_id: UUID):
        if not token or len(token) < 32:
            raise BrowserBridgeAuthenticationError("invalid browser bridge bearer token")
        rows = await self.postgres.execute(
            """SELECT * FROM browser_bridge_pairings
               WHERE token_hash=$1 AND connector_instance_id=$2 AND revoked_at IS NULL""",
            _token_hash(token), connector_instance_id,
        )
        if not rows:
            raise BrowserBridgeAuthenticationError("invalid or revoked browser bridge pairing")
        return rows[0]

    async def _claim_message(self, pairing_id: UUID, frame: BrowserBridgeFrame) -> dict[str, Any] | None:
        frame_hash = hashlib.sha256(
            _json(frame.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()
        rows = await self.postgres.execute(
            """INSERT INTO browser_bridge_messages(
                 pairing_id,message_id,connector_instance_id,protocol_version,frame_hash,status,record_count)
               VALUES($1,$2,$3,$4,$5,'receiving',$6)
               ON CONFLICT(pairing_id,message_id) DO UPDATE SET
                 status='receiving',response=NULL,completed_at=NULL
               WHERE browser_bridge_messages.status='failed'
                 AND browser_bridge_messages.frame_hash=EXCLUDED.frame_hash
               RETURNING status,response""",
            pairing_id, frame.message_id, frame.connector_instance_id,
            frame.version, frame_hash, len(frame.records),
        )
        if rows:
            return None
        existing = await self.postgres.execute(
            "SELECT status,response,frame_hash FROM browser_bridge_messages WHERE pairing_id=$1 AND message_id=$2",
            pairing_id, frame.message_id,
        )
        if existing and existing[0]["frame_hash"] != frame_hash:
            raise BrowserBridgeError("message ID replayed with different frame content")
        if existing and existing[0]["status"] == "acknowledged":
            value = existing[0]["response"]
            return json.loads(value) if isinstance(value, str) else dict(value)
        raise BrowserBridgeReplayInProgress("browser bridge message is already being processed")

    async def _start_analysis(self, connector_instance_id: UUID) -> UUID:
        instance = await self.repository.get_instance(connector_instance_id)
        rows = await self.postgres.execute(
            """INSERT INTO analysis_runs(run_type,profile_id,status,pipeline_version,configuration,started_at)
               VALUES('connector_sync',$1,'running','task5-browser-v1',$2::jsonb,NOW()) RETURNING id""",
            instance.profile_id, _json({"connector_instance_id": str(connector_instance_id)}),
        )
        return rows[0]["id"]

    @staticmethod
    def _record(item: BrowserVisitRecord, connector_instance_id: UUID) -> tuple[ConnectorRawRecord, str]:
        if item.data_class != "browser.visit" or item.media_type != "application/json":
            raise BrowserBridgeError("browser bridge accepts browser.visit JSON records only")
        if item.required_permissions != ("history.read",):
            raise BrowserBridgeError("browser visits require exactly history.read")
        if set(item.source_metadata) != ALLOWED_METADATA:
            raise BrowserBridgeError("browser visit metadata contains unsupported fields")
        try:
            payload = base64.b64decode(item.payload_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise BrowserBridgeError("invalid base64 browser visit payload") from exc
        if not payload or len(payload) > MAX_RECORD_BYTES:
            raise BrowserBridgeError("browser visit payload is empty or exceeds the local limit")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrowserBridgeError("browser visit payload must be UTF-8 JSON") from exc
        if not isinstance(document, dict) or set(document) != ALLOWED_PAYLOAD_FIELDS:
            raise BrowserBridgeError("browser visit payload contains unsupported/page-content fields")
        if document["browser_profile_connector_id"] != item.source_metadata["browser_profile_connector_id"]:
            raise BrowserBridgeError("browser profile connector identity mismatch")
        visit_time = str(document["visit_time"])
        return ConnectorRawRecord(
            connector_instance_id=connector_instance_id,
            source_record_id=item.source_record_id,
            source_record_version=item.source_record_version,
            record_signature=item.record_signature,
            data_class=item.data_class, occurred_at=item.occurred_at,
            observed_at=item.observed_at, media_type=item.media_type,
            payload=payload, source_metadata=item.source_metadata,
            required_permissions=item.required_permissions,
        ), visit_time
