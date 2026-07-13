"""Deterministic bulk/newsletter candidates; never automatic spam labels."""
from __future__ import annotations

from hashlib import sha256
import json

from pydantic import BaseModel, ConfigDict, Field


class _Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_id: str
    sender: str
    deterministic_signals: tuple[str, ...]
    confidence: float = Field(ge=0, le=1)
    status: str = "candidate"
    automatic_spam: bool = False


class BulkMailCandidate(_Candidate):
    candidate_type: str = "bulk_mail"


class NewsletterCandidate(_Candidate):
    candidate_type: str = "newsletter"


def detect_bulk_newsletter_candidates(
    headers: dict[str, str], *, sender: str, repeated_sender_count: int = 1,
    repeated_subject_count: int = 1, visible_recipient_count: int = 1,
    reply_rate: float | None = None,
) -> tuple[BulkMailCandidate | NewsletterCandidate, ...]:
    normalised = {key.casefold(): str(value) for key, value in headers.items()}
    signals: list[str] = []
    if normalised.get("list-unsubscribe"):
        signals.append("list_unsubscribe")
    if normalised.get("list-id"):
        signals.append("list_id")
    if normalised.get("precedence", "").casefold() in {"bulk", "list", "junk"}:
        signals.append("bulk_precedence")
    sender_folded = sender.casefold()
    if any(marker in sender_folded for marker in ("no-reply", "noreply", "do-not-reply")):
        signals.append("no_reply_sender")
    if repeated_sender_count >= 5:
        signals.append("repeated_sender")
    if repeated_subject_count >= 3:
        signals.append("repeated_subject_template")
    if visible_recipient_count >= 10:
        signals.append("many_visible_recipients")
    if reply_rate is not None and repeated_sender_count >= 5 and reply_rate <= 0.05:
        signals.append("low_reply_rate")
    identity = sha256(json.dumps({"sender": sender_folded, "signals": sorted(signals)}, separators=(",", ":")).encode()).hexdigest()
    result: list[BulkMailCandidate | NewsletterCandidate] = []
    if {"list_unsubscribe", "list_id"} & set(signals):
        confidence = min(0.98, 0.58 + 0.1 * len(signals))
        result.append(NewsletterCandidate(
            candidate_id=f"newsletter:{identity}", sender=sender,
            deterministic_signals=tuple(signals), confidence=confidence,
        ))
    if len(signals) >= 2 or "bulk_precedence" in signals:
        confidence = min(0.95, 0.42 + 0.09 * len(signals))
        result.append(BulkMailCandidate(
            candidate_id=f"bulk:{identity}", sender=sender,
            deterministic_signals=tuple(signals), confidence=confidence,
        ))
    return tuple(result)
