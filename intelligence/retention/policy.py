"""Versioned, idempotent and conservative retention policy evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from uuid import UUID, uuid4

from db.postgres import PostgresClient, get_postgres_client

from .adjudication import RetentionAdjudicationResult, resolve_adjudication
from .features import RetentionFeatureBundle
from .models import (
    RetentionAction, RetentionClass, RetentionDecision, RetentionPolicy, ReviewStatus,
)


@dataclass(frozen=True, slots=True)
class RetentionCandidate:
    source_artifact_id: UUID
    profile_id: UUID | None
    connector_key: str | None
    data_class: str
    occurred_at: datetime | None
    observed_at: datetime
    attributes: dict[str, Any]
    features: RetentionFeatureBundle


def policy_matches(policy: RetentionPolicy, candidate: RetentionCandidate, *, as_of: datetime) -> tuple[bool, tuple[str, ...]]:
    reasons = []
    if not policy.enabled:
        return False, ("policy_disabled",)
    if policy.profile_id is not None and candidate.profile_id != policy.profile_id:
        return False, ("profile_mismatch",)
    if policy.connector_keys and candidate.connector_key not in policy.connector_keys:
        return False, ("connector_mismatch",)
    if policy.data_classes and candidate.data_class not in policy.data_classes:
        return False, ("data_class_mismatch",)
    instant = candidate.occurred_at or candidate.observed_at
    if as_of - instant < policy.minimum_age:
        return False, ("minimum_age_not_met",)
    for key, expected in policy.scope.items():
        value = candidate.attributes.get(key)
        if isinstance(expected, list):
            if value not in expected:
                return False, (f"scope_mismatch:{key}",)
        elif value != expected:
            return False, (f"scope_mismatch:{key}",)
        reasons.append(f"scope_match:{key}")
    return True, tuple(reasons or ("policy_scope_matched",))


def evaluate_candidate(
    policy: RetentionPolicy, candidate: RetentionCandidate, *, as_of: datetime,
    adjudication: RetentionAdjudicationResult | None = None,
) -> tuple[RetentionClass, float, dict | None, tuple[str, ...]]:
    matched, reasons = policy_matches(policy, candidate, as_of=as_of)
    if not matched:
        raise ValueError("candidate does not match policy: " + ", ".join(reasons))
    classification = candidate.features.classification
    confidence = candidate.features.confidence
    semantic = None
    if classification is RetentionClass.UNSURE:
        classification, confidence, semantic = resolve_adjudication(adjudication)
    if classification in {RetentionClass.LOW_VALUE_BULK, RetentionClass.SPAM} and confidence < policy.eligibility_threshold:
        classification, confidence = RetentionClass.UNSURE, 0.0
        reasons = (*reasons, "eligibility_threshold_not_met")
    return classification, confidence, semantic, reasons


class RetentionRepository:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def save_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        await self.postgres.execute(
            """INSERT INTO retention_policies(
                 id,policy_version,profile_id,name,scope,connector_keys,data_classes,
                 minimum_age_seconds,eligibility_threshold,action,schedule,grace_period_seconds,
                 configuration,enabled)
               VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8,$9,$10,$11::jsonb,$12,$13::jsonb,$14)
               ON CONFLICT(id,policy_version) DO NOTHING""",
            policy.id, policy.version, policy.profile_id, policy.name,
            json.dumps(policy.scope, sort_keys=True), json.dumps(policy.connector_keys),
            json.dumps(policy.data_classes), int(policy.minimum_age.total_seconds()),
            policy.eligibility_threshold, policy.action.value,
            json.dumps(policy.schedule, sort_keys=True) if policy.schedule is not None else None,
            int(policy.grace_period.total_seconds()),
            json.dumps(policy.configuration, sort_keys=True), policy.enabled,
        )
        return policy

    async def record_decision(
        self, policy: RetentionPolicy, candidate: RetentionCandidate, *,
        analysis_run_id: UUID, as_of: datetime | None = None,
        adjudication: RetentionAdjudicationResult | None = None,
    ) -> RetentionDecision:
        classification, confidence, semantic, reasons = evaluate_candidate(
            policy, candidate, as_of=as_of or datetime.now(timezone.utc),
            adjudication=adjudication,
        )
        evidence = {
            **candidate.features.deterministic_evidence(),
            "policy_match_reasons": list(reasons),
        }
        rows = await self.postgres.execute(
            """INSERT INTO retention_decisions(
                 source_artifact_id,classification,deterministic_evidence,semantic_adjudication,
                 confidence,policy_id,policy_version,analysis_run_id,review_status)
               VALUES($1,$2,$3::jsonb,$4::jsonb,$5,$6,$7,$8,'pending')
               ON CONFLICT(source_artifact_id,policy_id,policy_version,analysis_run_id)
               DO UPDATE SET source_artifact_id=EXCLUDED.source_artifact_id RETURNING *""",
            candidate.source_artifact_id, classification.value,
            json.dumps(evidence, sort_keys=True),
            json.dumps(semantic, sort_keys=True) if semantic is not None else None,
            confidence, policy.id, policy.version, analysis_run_id,
        )
        row = rows[0]
        deterministic = json.loads(row["deterministic_evidence"]) if isinstance(row["deterministic_evidence"], str) else dict(row["deterministic_evidence"])
        raw_semantic = row["semantic_adjudication"]
        semantic_value = json.loads(raw_semantic) if isinstance(raw_semantic, str) else (dict(raw_semantic) if raw_semantic else None)
        return RetentionDecision(
            id=row["id"], source_artifact_id=row["source_artifact_id"],
            classification=row["classification"], deterministic_evidence=deterministic,
            semantic_adjudication=semantic_value, confidence=float(row["confidence"]),
            policy_id=row["policy_id"], policy_version=row["policy_version"],
            analysis_run_id=row["analysis_run_id"], review_status=row["review_status"],
            created_at=row["created_at"],
        )
