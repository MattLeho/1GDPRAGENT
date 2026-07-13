"""Conservative retention and destructive-operation contracts."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RetentionClass(str, Enum):
    KEEP_LEGAL_OR_REGULATORY = "KEEP_LEGAL_OR_REGULATORY"
    KEEP_FINANCIAL = "KEEP_FINANCIAL"
    KEEP_IDENTITY_OR_SECURITY = "KEEP_IDENTITY_OR_SECURITY"
    KEEP_PROJECT_RECORD = "KEEP_PROJECT_RECORD"
    KEEP_ACTIVE_CONVERSATION = "KEEP_ACTIVE_CONVERSATION"
    KEEP_PERSONAL_SIGNIFICANCE = "KEEP_PERSONAL_SIGNIFICANCE"
    LOW_VALUE_BULK = "LOW_VALUE_BULK"
    SPAM = "SPAM"
    UNSURE = "UNSURE"


class RetentionAction(str, Enum):
    LOCAL_PURGE = "local_purge"
    SOURCE_DELETE = "source_delete"
    CONTROLLER_ERASURE_CANDIDATE = "controller_erasure_candidate"
    REVIEW_ONLY = "review_only"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeletionItemGroup(str, Enum):
    ELIGIBLE = "eligible"
    PROTECTED = "protected"
    UNCERTAIN = "uncertain"


class DeletionStage(str, Enum):
    CANDIDATE = "candidate"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    ELIGIBLE_FOR_DELETE = "eligible_for_delete"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class RetentionPolicy(FrozenModel):
    id: UUID
    version: int = Field(ge=1)
    profile_id: UUID | None = None
    name: str = Field(min_length=1)
    scope: dict[str, Any] = Field(default_factory=dict)
    connector_keys: tuple[str, ...] = ()
    data_classes: tuple[str, ...] = ()
    minimum_age: timedelta = Field(ge=timedelta(0))
    eligibility_threshold: float = Field(default=1.0, ge=0, le=1)
    action: RetentionAction
    schedule: dict[str, Any] | None = None
    grace_period: timedelta = Field(default=timedelta(days=30), ge=timedelta(0))
    configuration: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class RetentionDecision(FrozenModel):
    id: UUID
    source_artifact_id: UUID
    classification: RetentionClass
    deterministic_evidence: dict[str, Any]
    semantic_adjudication: dict[str, Any] | None = None
    confidence: float = Field(ge=0, le=1)
    policy_id: UUID
    policy_version: int = Field(ge=1)
    analysis_run_id: UUID
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime

    @property
    def protected(self) -> bool:
        return self.classification not in {RetentionClass.LOW_VALUE_BULK, RetentionClass.SPAM}


class DeletionPlanItem(FrozenModel):
    id: UUID
    source_artifact_id: UUID
    retention_decision_id: UUID
    group: DeletionItemGroup
    action: RetentionAction
    reasons: tuple[str, ...]
    source_delete_capability: bool = False
    stage: DeletionStage = DeletionStage.CANDIDATE
    quarantine_at: datetime | None = None
    grace_expires_at: datetime | None = None

    @model_validator(mode="after")
    def safe_eligibility(self):
        if self.group is not DeletionItemGroup.ELIGIBLE and self.stage in {
            DeletionStage.QUARANTINE, DeletionStage.ELIGIBLE_FOR_DELETE, DeletionStage.EXECUTED,
        }:
            raise ValueError("protected and uncertain items cannot enter destructive stages")
        if self.action is RetentionAction.SOURCE_DELETE and not self.source_delete_capability:
            raise ValueError("source deletion requires a declared connector capability")
        return self


class DeletionPlan(FrozenModel):
    id: UUID
    policy_id: UUID
    policy_version: int = Field(ge=1)
    analysis_run_id: UUID
    dry_run: bool = True
    items: tuple[DeletionPlanItem, ...] = ()
    created_at: datetime


class SourceDeletionExecution(FrozenModel):
    id: UUID
    deletion_plan_item_id: UUID
    connector_instance_id: UUID
    provider_action: str
    reversible: bool = True
    provider_response_id: str | None = None
    provider_status: str
    executed_at: datetime


class LocalPurgeExecution(FrozenModel):
    id: UUID
    deletion_plan_item_id: UUID
    source_artifact_id: UUID
    content_purged_at: datetime
    retained_evidence_basis: dict[str, Any]
    evidence_locators_preserved: bool

    @model_validator(mode="after")
    def locators_must_survive(self):
        if not self.evidence_locators_preserved:
            raise ValueError("local purge cannot silently break EvidenceLocators")
        return self


class ControllerErasureCandidate(FrozenModel):
    id: UUID
    deletion_plan_item_id: UUID
    controller_key: str
    existing_request_id: UUID | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    automatic_execution_enabled: bool = False
    created_at: datetime

