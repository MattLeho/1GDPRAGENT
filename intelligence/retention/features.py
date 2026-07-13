"""Deterministic retention evidence, deliberately independent of interests."""
from __future__ import annotations

from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field

from .models import RetentionClass


class EmailRetentionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    starred: bool = False
    labels: tuple[str, ...] = ()
    direction: str = "unknown"
    user_replied: bool = False
    thread_message_count: int = Field(default=1, ge=1)
    last_activity_at: datetime | None = None
    has_attachment: bool = False
    subject: str = ""
    body_excerpt: str = Field(default="", max_length=2000)
    known_human_correspondent: bool = False
    active_project_linkage: bool = False
    calendar_event_linkage: bool = False
    bulk_candidate: bool = False
    newsletter_candidate: bool = False
    repeated_template: bool = False
    reply_rate: float | None = Field(default=None, ge=0, le=1)
    observed_link_engagement: bool = False
    inactive_days: int = Field(default=0, ge=0)
    provider_spam_label: bool = False


class RetentionFeatureBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    feature_version: str = "email-retention-features-v1"
    protective_signals: tuple[str, ...] = ()
    low_value_signals: tuple[str, ...] = ()
    classification: RetentionClass
    confidence: float = Field(ge=0, le=1)
    unresolved_reasons: tuple[str, ...] = ()

    def deterministic_evidence(self) -> dict:
        return self.model_dump(mode="json")


_PATTERNS = {
    "financial": re.compile(r"\b(invoice|receipt|bank|payment|paid|billing|statement|tax|vat)\b", re.I),
    "legal": re.compile(r"\b(contract|agreement|legal|solicitor|attorney|court|regulatory|compliance)\b", re.I),
    "identity_security": re.compile(r"\b(password|security|identity|verification|two[- ]factor|2fa|login|breach|recovery code)\b", re.I),
    "education": re.compile(r"\b(course|university|school|qualification|certificate|exam|tuition)\b", re.I),
    "employment": re.compile(r"\b(employment|employer|salary|payslip|interview|job offer|contractor)\b", re.I),
    "travel": re.compile(r"\b(booking|reservation|flight|hotel|train ticket|boarding pass|itinerary)\b", re.I),
}


def extract_email_retention_features(value: EmailRetentionInput) -> RetentionFeatureBundle:
    text = f"{value.subject}\n{value.body_excerpt}"
    protective: list[str] = []
    low: list[str] = []
    labels = {label.casefold() for label in value.labels}
    if value.starred:
        protective.append("starred")
    if labels & {"keep", "important", "archive/keep"}:
        protective.append("explicit_keep_label")
    if value.direction.casefold() == "outbound":
        protective.append("user_sent")
    if value.user_replied:
        protective.append("user_replied")
    if value.thread_message_count >= 3 and value.inactive_days <= 90:
        protective.append("active_multi_message_thread")
    if value.has_attachment:
        protective.append("attachment")
    for name, pattern in _PATTERNS.items():
        if pattern.search(text):
            protective.append(name)
    if value.known_human_correspondent:
        protective.append("known_human_correspondent")
    if value.active_project_linkage:
        protective.append("active_project_linkage")
    if value.calendar_event_linkage:
        protective.append("calendar_event_linkage")
    if value.bulk_candidate:
        low.append("bulk_candidate")
    if value.newsletter_candidate:
        low.append("newsletter_candidate")
    if value.repeated_template:
        low.append("repeated_template")
    if value.reply_rate is not None and value.reply_rate <= 0.05:
        low.append("low_reply_rate")
    if not value.observed_link_engagement:
        low.append("no_observed_link_engagement")
    if value.inactive_days >= 180:
        low.append("long_inactivity")
    if not value.has_attachment:
        low.append("no_attachment")
    if not any(signal in protective for signal in (
        "financial", "legal", "identity_security", "active_project_linkage",
    )):
        low.append("no_protected_relationship")

    signals = set(protective)
    if "legal" in signals:
        classification, confidence = RetentionClass.KEEP_LEGAL_OR_REGULATORY, 0.97
    elif "financial" in signals:
        classification, confidence = RetentionClass.KEEP_FINANCIAL, 0.95
    elif "identity_security" in signals:
        classification, confidence = RetentionClass.KEEP_IDENTITY_OR_SECURITY, 0.95
    elif "active_project_linkage" in signals or "employment" in signals or "education" in signals:
        classification, confidence = RetentionClass.KEEP_PROJECT_RECORD, 0.90
    elif signals & {"user_sent", "user_replied", "active_multi_message_thread"}:
        classification, confidence = RetentionClass.KEEP_ACTIVE_CONVERSATION, 0.90
    elif signals & {"starred", "explicit_keep_label", "known_human_correspondent", "calendar_event_linkage", "travel"}:
        classification, confidence = RetentionClass.KEEP_PERSONAL_SIGNIFICANCE, 0.85
    elif value.provider_spam_label and not protective:
        classification, confidence = RetentionClass.SPAM, 0.95
    elif (value.bulk_candidate or value.newsletter_candidate) and len(low) >= 4 and not protective:
        classification, confidence = RetentionClass.LOW_VALUE_BULK, min(0.95, 0.55 + len(low) * 0.06)
    else:
        classification, confidence = RetentionClass.UNSURE, 0.0
    unresolved = () if classification is not RetentionClass.UNSURE else (
        "deterministic evidence does not establish a protected or low-value class",
    )
    return RetentionFeatureBundle(
        protective_signals=tuple(sorted(set(protective))),
        low_value_signals=tuple(sorted(set(low))),
        classification=classification, confidence=confidence,
        unresolved_reasons=unresolved,
    )
