from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from connectors.email_intelligence import (
    BulkMailCandidate, NewsletterCandidate, detect_bulk_newsletter_candidates,
)
from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.models import SignalClass
from insights.signals import classify_event, effective_signal_weight


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _event(event_type, *, occurred_at=NOW, direction="inbound", action=ActionClass.COMMUNICATED, relationships=None):
    return ActivityEvent(
        event_id=uuid4(), record_signature="a" * 64, subject_id="profile-1",
        export_snapshot_id=uuid4(), artifact_id=uuid4(), service="IMAP", product="email.imap",
        data_domain="email", event_type=event_type, action_class=action,
        occurred_at=occurred_at, occurred_at_original=occurred_at.isoformat(),
        temporal_precision=TemporalPrecision.SECOND, object_type="email_message",
        object_id="<message@example.test>", object_value={"direction": direction},
        relationships=relationships or {}, parser_id="task5.email-message",
        parser_version="1", source_locator_id=uuid4(),
    )


def test_email_exposure_engagement_and_decay_semantics_are_conservative():
    received = classify_event(_event("EMAIL_RECEIVED"))
    opened = classify_event(_event("EMAIL_OPENED_CANDIDATE", action=ActionClass.CONSUMED))
    clicked = classify_event(_event("EMAIL_LINK_CLICKED", occurred_at=NOW - timedelta(days=90)))
    inbound_reply = classify_event(_event("EMAIL_REPLIED", direction="inbound"))
    outbound_reply = classify_event(_event("EMAIL_REPLIED", direction="outbound"))
    unsubscribed = classify_event(_event("EMAIL_UNSUBSCRIBED"))

    assert received.signal_class is SignalClass.AMBIENT_EXPOSURE and not received.interest_contributing
    assert opened.signal_class is SignalClass.AMBIENT_EXPOSURE and not opened.interest_contributing
    assert inbound_reply.signal_class is SignalClass.AMBIENT_EXPOSURE and not inbound_reply.interest_contributing
    assert outbound_reply.signal_class is SignalClass.COMMUNICATION and outbound_reply.interest_contributing
    assert unsubscribed.signal_class is SignalClass.DISENGAGEMENT and not unsubscribed.interest_contributing
    assert clicked.interest_contributing
    decayed = effective_signal_weight(clicked, as_of=NOW, email_half_life_days=45)
    assert 0 < decayed < clicked.weight
    assert effective_signal_weight(received, as_of=NOW) == 0
    # Decay weakens current observed engagement; it never becomes negative or a
    # fabricated disinterest state.
    assert effective_signal_weight(clicked, as_of=NOW + timedelta(days=3650)) >= 0


def test_bulk_and_newsletter_detection_emits_candidates_never_spam():
    candidates = detect_bulk_newsletter_candidates(
        {"List-Unsubscribe": "<mailto:leave@example.test>", "List-Id": "updates.example.test", "Precedence": "bulk"},
        sender="no-reply@example.test", repeated_sender_count=20,
        repeated_subject_count=8, visible_recipient_count=30, reply_rate=0.0,
    )
    assert any(isinstance(value, NewsletterCandidate) for value in candidates)
    assert any(isinstance(value, BulkMailCandidate) for value in candidates)
    assert all(value.status == "candidate" and value.automatic_spam is False for value in candidates)
    assert all("list_unsubscribe" in value.deterministic_signals for value in candidates)

    assert detect_bulk_newsletter_candidates(
        {}, sender="person@example.test", repeated_sender_count=1,
    ) == ()
