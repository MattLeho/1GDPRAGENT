"""Minimal structured adjudication bundles for unresolved retention items."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .features import RetentionFeatureBundle
from .models import RetentionClass


class RetentionAdjudicationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_key: Literal["email.retention_adjudication"] = "email.retention_adjudication"
    source_artifact_id: UUID
    processing_mode: Literal["strict_local", "local_first", "controlled_cloud"]
    local_only: bool
    deterministic_features: dict
    subject_excerpt: str = Field(max_length=300)
    allowed_classes: tuple[RetentionClass, ...]
    abstention_required_when_uncertain: bool = True


class RetentionAdjudicationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    classification: RetentionClass | None = None
    confidence: float = Field(ge=0, le=1)
    reasons: tuple[str, ...] = ()
    abstained: bool = False

    @model_validator(mode="after")
    def abstention_shape(self):
        if self.abstained and self.classification is not None:
            raise ValueError("an abstention cannot include a classification")
        if not self.abstained and self.classification is None:
            raise ValueError("structured adjudication requires a class or abstention")
        return self


def build_retention_adjudication_bundle(
    source_artifact_id: UUID, features: RetentionFeatureBundle, *,
    subject_excerpt: str, processing_mode: str,
) -> RetentionAdjudicationBundle:
    if features.classification is not RetentionClass.UNSURE:
        raise ValueError("semantic adjudication is only allowed for unresolved items")
    if processing_mode not in {"strict_local", "local_first", "controlled_cloud"}:
        raise ValueError("unknown processing mode")
    return RetentionAdjudicationBundle(
        source_artifact_id=source_artifact_id,
        processing_mode=processing_mode,
        local_only=processing_mode == "strict_local",
        deterministic_features=features.deterministic_evidence(),
        subject_excerpt=subject_excerpt[:300],
        allowed_classes=tuple(RetentionClass),
    )


def resolve_adjudication(result: RetentionAdjudicationResult | None) -> tuple[RetentionClass, float, dict | None]:
    if result is None or result.abstained or result.classification is None or result.confidence < 0.75:
        payload = result.model_dump(mode="json") if result else None
        return RetentionClass.UNSURE, 0.0, payload
    return result.classification, result.confidence, result.model_dump(mode="json")
