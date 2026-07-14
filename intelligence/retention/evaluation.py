"""Live, deterministic retention evaluation over canonical connector evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from email import policy as email_policy
from email.message import Message
from email.parser import BytesParser
import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from db.postgres import PostgresClient, get_postgres_client
from evidence.purged import local_storage_path

from .features import EmailRetentionInput, extract_email_retention_features
from .models import RetentionDecision, RetentionPolicy
from .policy import RetentionCandidate, RetentionRepository, policy_matches


PIPELINE_VERSION = "task5-retention-evaluation-v1"


class RetentionEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    analysis_run_id: UUID
    policies_evaluated: int = Field(ge=0)
    artifacts_considered: int = Field(ge=0)
    decisions: tuple[RetentionDecision, ...] = ()


def _decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _boolean(metadata: dict[str, Any], key: str) -> bool:
    return metadata.get(key) is True


def _integer(metadata: dict[str, Any], key: str, default: int) -> int:
    value = metadata.get(key, default)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


def _rate(metadata: dict[str, Any], key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
        return float(value)
    return None


def _message_body(message: Message) -> str:
    if message.is_multipart():
        parts = (
            part for part in message.walk()
            if part.get_content_type() == "text/plain"
            and part.get_content_disposition() != "attachment"
        )
        part = next(parts, None)
        if part is None:
            return ""
    else:
        part = message
    try:
        return str(part.get_content() or "")
    except (LookupError, UnicodeDecodeError):
        raw = part.get_payload(decode=True) or b""
        return raw.decode(part.get_content_charset() or "utf-8", errors="replace")


def _email_document(payload: bytes, media_type: str) -> tuple[dict[str, Any], dict[str, str]]:
    if media_type.casefold() == "message/rfc822":
        message = BytesParser(policy=email_policy.default).parsebytes(payload)
        headers = {str(key): str(value) for key, value in message.items()}
        return {
            "subject": str(message.get("Subject") or ""),
            "text_body": _message_body(message),
            "attachments": [
                {"file_name": part.get_filename()}
                for part in message.walk() if part.get_filename()
            ],
        }, headers
    if media_type.casefold() == "application/json":
        value = json.loads(payload.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("scoped email document must be a JSON object")
        headers = value.get("headers") if isinstance(value.get("headers"), dict) else {}
        return value, {str(key): str(item) for key, item in headers.items()}
    return {}, {}


def build_email_retention_input(
    *, payload: bytes | None, media_type: str, source_metadata: dict[str, Any],
    occurred_at: datetime | None, observed_at: datetime, as_of: datetime,
) -> EmailRetentionInput:
    """Convert only canonical source bytes and connector metadata into features."""

    document: dict[str, Any] = {}
    headers: dict[str, str] = {}
    if payload is not None:
        try:
            document, headers = _email_document(payload, media_type)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            # Unreadable content cannot justify a positive destructive class.
            document, headers = {}, {}
    flags = tuple(str(value) for value in source_metadata.get("flags", ()) if isinstance(value, str))
    labels = tuple(str(value) for value in source_metadata.get("labels", ()) if isinstance(value, str))
    folded_flags = {value.casefold() for value in flags}
    mailbox = str(source_metadata.get("mailbox") or document.get("mailbox") or "")
    mailbox_folded = mailbox.casefold()
    instant = occurred_at or observed_at
    inactive_days = max(0, int((as_of - instant).total_seconds() // 86400))
    attachments = document.get("attachments")
    has_attachment = bool(attachments) or _boolean(source_metadata, "has_attachment")
    subject = str(document.get("subject") or source_metadata.get("subject") or "")[:1000]
    body = str(document.get("text_body") or source_metadata.get("body_excerpt") or "")[:2000]
    list_headers = {key.casefold(): value for key, value in headers.items()}
    newsletter = bool(list_headers.get("list-id") or list_headers.get("list-unsubscribe"))
    bulk = newsletter or list_headers.get("precedence", "").casefold() in {"bulk", "list", "junk"}
    return EmailRetentionInput(
        starred=_boolean(source_metadata, "starred") or "\\flagged" in folded_flags,
        labels=tuple(sorted(set((*flags, *labels)))),
        direction=str(source_metadata.get("direction") or "unknown"),
        user_replied=_boolean(source_metadata, "user_replied"),
        thread_message_count=max(1, _integer(source_metadata, "thread_message_count", 1)),
        last_activity_at=instant,
        has_attachment=has_attachment,
        subject=subject,
        body_excerpt=body,
        known_human_correspondent=_boolean(source_metadata, "known_human_correspondent"),
        active_project_linkage=_boolean(source_metadata, "active_project_linkage"),
        calendar_event_linkage=_boolean(source_metadata, "calendar_event_linkage"),
        bulk_candidate=_boolean(source_metadata, "bulk_candidate") or bulk,
        newsletter_candidate=_boolean(source_metadata, "newsletter_candidate") or newsletter,
        repeated_template=_boolean(source_metadata, "repeated_template"),
        reply_rate=_rate(source_metadata, "reply_rate"),
        observed_link_engagement=_boolean(source_metadata, "observed_link_engagement"),
        inactive_days=inactive_days,
        provider_spam_label=(
            _boolean(source_metadata, "provider_spam_label")
            or bool(folded_flags & {"\\junk", "\\spam"})
            or mailbox_folded in {"junk", "spam", "junk email"}
        ),
    )


class RetentionEvaluationService:
    """Match enabled profile policies and persist review-first decisions."""

    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()
        self.repository = RetentionRepository(self.postgres)

    async def evaluate(
        self, *, profile_id: UUID, as_of: datetime | None = None,
        policy_id: UUID | None = None, policy_version: int | None = None,
        limit: int = 1000,
    ) -> RetentionEvaluationResult:
        if not 1 <= limit <= 10_000:
            raise ValueError("retention evaluation limit must be between 1 and 10000")
        if (policy_id is None) != (policy_version is None):
            raise ValueError("policy_id and policy_version must be supplied together")
        evaluated_at = as_of or datetime.now(timezone.utc)
        if evaluated_at.tzinfo is None:
            raise ValueError("retention evaluation as_of must be timezone-aware")
        run_rows = await self.postgres.execute(
            """INSERT INTO analysis_runs(run_type,profile_id,status,pipeline_version,configuration,started_at)
               VALUES('retention_evaluation',$1,'running',$2,$3::jsonb,NOW()) RETURNING id""",
            profile_id, PIPELINE_VERSION,
            json.dumps({"as_of": evaluated_at.isoformat(), "limit": limit}, sort_keys=True),
        )
        run_id = run_rows[0]["id"]
        try:
            policies = await self._policies(profile_id, policy_id, policy_version)
            rows = await self.postgres.execute(
                """SELECT crr.source_artifact_id,crr.data_class,crr.occurred_at,crr.observed_at,
                          crr.media_type,crr.source_metadata,crr.source_record_id,
                          ci.id connector_instance_id,ci.connector_key,ci.account_key,cb.storage_uri
                   FROM connector_raw_records crr
                   JOIN connector_instances ci ON ci.id=crr.connector_instance_id
                   JOIN source_artifacts sa ON sa.id=crr.source_artifact_id
                   JOIN export_snapshots es ON es.id=sa.export_snapshot_id
                   JOIN content_blobs cb ON cb.id=sa.content_blob_id
                   WHERE crr.ingestion_status='ingested' AND crr.source_artifact_id IS NOT NULL
                     AND ci.profile_id=$1 AND es.profile_id=$1 AND crr.data_class='email.message'
                   ORDER BY crr.observed_at,crr.id LIMIT $2""",
                profile_id, limit,
            )
            decisions: list[RetentionDecision] = []
            for row in rows:
                metadata = dict(_decoded(row["source_metadata"]) or {})
                attributes = {
                    **metadata,
                    "mailbox": metadata.get("mailbox"),
                    "account_key": row["account_key"],
                    "connector_instance_id": str(row["connector_instance_id"]),
                    "source_record_id": row["source_record_id"],
                }
                payload = self._read_payload(row["storage_uri"])
                email_input = build_email_retention_input(
                    payload=payload, media_type=row["media_type"], source_metadata=metadata,
                    occurred_at=row["occurred_at"], observed_at=row["observed_at"], as_of=evaluated_at,
                )
                candidate = RetentionCandidate(
                    source_artifact_id=row["source_artifact_id"], profile_id=profile_id,
                    connector_key=row["connector_key"], data_class=row["data_class"],
                    occurred_at=row["occurred_at"], observed_at=row["observed_at"],
                    attributes=attributes, features=extract_email_retention_features(email_input),
                )
                for retention_policy in policies:
                    if policy_matches(retention_policy, candidate, as_of=evaluated_at)[0]:
                        decisions.append(await self.repository.record_decision(
                            retention_policy, candidate, analysis_run_id=run_id,
                            as_of=evaluated_at, adjudication=None,
                        ))
            await self.postgres.execute(
                "UPDATE analysis_runs SET status='completed',completed_at=NOW() WHERE id=$1", run_id,
            )
            return RetentionEvaluationResult(
                analysis_run_id=run_id, policies_evaluated=len(policies),
                artifacts_considered=len(rows), decisions=tuple(decisions),
            )
        except Exception as exc:
            await self.postgres.execute(
                "UPDATE analysis_runs SET status='failed',completed_at=NOW(),error=$2 WHERE id=$1",
                run_id, str(exc),
            )
            raise

    async def _policies(
        self, profile_id: UUID, policy_id: UUID | None, policy_version: int | None,
    ) -> tuple[RetentionPolicy, ...]:
        filters = " AND id=$2 AND policy_version=$3" if policy_id is not None else ""
        args = (profile_id, policy_id, policy_version) if policy_id is not None else (profile_id,)
        rows = await self.postgres.execute(
            "SELECT * FROM retention_policies WHERE profile_id=$1 AND enabled=TRUE" + filters
            + " ORDER BY id,policy_version", *args,
        )
        if policy_id is not None and not rows:
            raise LookupError("enabled retention policy does not exist for this profile")
        return tuple(self._policy(row) for row in rows)

    @staticmethod
    def _read_payload(storage_uri: str) -> bytes | None:
        try:
            return local_storage_path(storage_uri).read_bytes()
        except (OSError, ValueError):
            return None

    @staticmethod
    def _policy(row: Any) -> RetentionPolicy:
        from datetime import timedelta
        return RetentionPolicy(
            id=row["id"], version=row["policy_version"], profile_id=row["profile_id"],
            name=row["name"], scope=dict(_decoded(row["scope"])),
            connector_keys=tuple(_decoded(row["connector_keys"])),
            data_classes=tuple(_decoded(row["data_classes"])),
            minimum_age=timedelta(seconds=row["minimum_age_seconds"]),
            eligibility_threshold=float(row["eligibility_threshold"]), action=row["action"],
            schedule=_decoded(row["schedule"]) if row["schedule"] else None,
            grace_period=timedelta(seconds=row["grace_period_seconds"]),
            configuration=dict(_decoded(row["configuration"])), enabled=row["enabled"],
        )
