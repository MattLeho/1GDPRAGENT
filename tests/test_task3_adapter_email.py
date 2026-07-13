from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ingestion.adapters.email_calendar import EmailCalendarAdapter
from ingestion.models import ExtractionContext, FileTypeTruth, FileTypeTruthValue, QuarantineStatus


def _context(path: Path) -> ExtractionContext:
    return ExtractionContext(
        artifact_id=uuid4(),
        analysis_run_id=uuid4(),
        export_snapshot_id=uuid4(),
        source_path=str(path),
    )


def _truth() -> FileTypeTruth:
    return FileTypeTruth(status=FileTypeTruthValue.UNKNOWN, evidence=(), reason="test")


def test_eml_nested_mime_keeps_alternatives_and_attachment_descriptor(tmp_path: Path):
    path = tmp_path / "nested.eml"
    path.write_bytes(
        b"From: Sender <sender@example.test>\r\n"
        b"To: Recipient <recipient@example.test>\r\n"
        b"Message-ID: <nested@example.test>\r\n"
        b"References: <root@example.test> <parent@example.test>\r\n"
        b"Subject: Nested MIME\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=outer\r\n\r\n"
        b"--outer\r\nContent-Type: multipart/alternative; boundary=inner\r\n\r\n"
        b"--inner\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nPlain body\r\n"
        b"--inner\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>HTML body</p>\r\n"
        b"--inner--\r\n"
        b"--outer\r\nContent-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename=report.pdf\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\nJVBERi0xLjQ=\r\n"
        b"--outer--\r\n"
    )

    adapter = EmailCalendarAdapter()
    assert adapter.probe(str(path), _truth()).detected_format == "eml"
    result = adapter.extract(str(path), _context(path))

    bodies = [unit for unit in result.units if unit.unit_type == "email_body"]
    assert [(body.metadata["content_type"], body.text) for body in bodies] == [
        ("text/plain", "Plain body"),
        ("text/html", "<p>HTML body</p>"),
    ]
    assert [body.evidence_locator.locator["part"] for body in bodies] == ["1.1", "1.2"]
    assert len(result.embedded_members) == 1
    assert result.embedded_members[0].member_path == "report.pdf"
    assert result.embedded_members[0].media_type == "application/pdf"
    assert result.embedded_members[0].content == b"%PDF-1.4"
    assert "content" not in result.embedded_members[0].model_dump()
    assert result.embedded_members[0].evidence_locator.locator == {
        "message": 0, "part": "2", "filename": "report.pdf",
    }
    attachment = next(unit for unit in result.units if unit.unit_type == "email_attachment")
    assert attachment.evidence_locator.locator == {"message": 0, "part": "2", "filename": "report.pdf"}


def test_email_attachment_payload_is_bounded_without_losing_descriptor(tmp_path: Path):
    path = tmp_path / "bounded.eml"
    path.write_bytes(
        b"From: sender@example.test\r\nMIME-Version: 1.0\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Disposition: attachment; filename=data.bin\r\n\r\n12345"
    )
    context = _context(path).model_copy(update={"configuration": {"max_email_attachment_bytes": 4}})

    result = EmailCalendarAdapter().extract(str(path), context)

    member = result.embedded_members[0]
    assert member.declared_size == 5
    assert member.content is None
    assert member.metadata["content_retained"] is False
    assert member.evidence_locator.locator == {"message": 0, "part": "1", "filename": "data.bin"}
    assert "max_email_attachment_bytes=4" in result.warnings[0]


def test_mbox_duplicate_message_ids_remain_visible_per_message(tmp_path: Path):
    path = tmp_path / "mail.mbox"
    path.write_bytes(
        b"From sender@example.test Sat Jan 01 00:00:00 2022\n"
        b"From: sender@example.test\nTo: one@example.test\nMessage-ID: <duplicate@example.test>\nSubject: One\n\nFirst\n"
        b"From sender@example.test Sat Jan 01 00:01:00 2022\n"
        b"From: sender@example.test\nTo: two@example.test\nMessage-ID: <duplicate@example.test>\nSubject: Two\n\nSecond\n"
    )

    result = EmailCalendarAdapter().extract(str(path), _context(path))
    ids = [unit for unit in result.units if unit.metadata.get("header") == "message-id"]

    assert [unit.value for unit in ids] == ["<duplicate@example.test>", "<duplicate@example.test>"]
    assert [unit.evidence_locator.locator["message"] for unit in ids] == [0, 1]
    assert result.metadata["message_count"] == 2


def test_eml_malformed_headers_are_preserved_without_crashing(tmp_path: Path):
    path = tmp_path / "malformed.eml"
    path.write_bytes(
        b"From: sender@example.test\r\n"
        b"To: recipient@example.test\r\n"
        b"Date: definitely-not-a-date\r\n"
        b"Subject: malformed\r\n"
        b"Broken header without colon\r\n"
        b"\r\nBody\r\n"
    )

    result = EmailCalendarAdapter().extract(str(path), _context(path))
    date = next(unit for unit in result.units if unit.metadata.get("header") == "date")

    assert date.value == "definitely-not-a-date"
    assert date.metadata["parsed_date"] is None
    assert result.quarantine_status is QuarantineStatus.NONE
    assert result.warnings


def test_ics_preserves_timezone_recurrence_and_alarm_without_expansion(tmp_path: Path):
    path = tmp_path / "calendar.ics"
    path.write_text(
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:event-1\r\n"
        "DTSTART;TZID=Europe/London:20260329T093000\r\n"
        "DTEND;TZID=Europe/London:20260329T103000\r\n"
        "RRULE:FREQ=WEEKLY;COUNT=5;BYDAY=SU\r\n"
        "ORGANIZER;CN=Owner:mailto:owner@example.test\r\n"
        "ATTENDEE;CN=Guest:mailto:guest@example.test\r\n"
        "LOCATION:London\r\n"
        "SUMMARY:Recurring event\r\n"
        "DESCRIPTION:Calendar description\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT15M\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:Reminder\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n",
        encoding="utf-8",
        newline="",
    )

    result = EmailCalendarAdapter().extract(str(path), _context(path))
    by_name = {unit.structured_payload["name"]: unit for unit in result.units if unit.evidence_locator.locator["component"] == "VEVENT"}

    start = by_name["DTSTART"].structured_payload
    assert start["timezone_semantics"] == "tzid"
    assert start["tzid"] == "Europe/London"
    assert start["normalised"].endswith("+01:00")
    recurrence = by_name["RRULE"].structured_payload
    assert recurrence["raw"] == "FREQ=WEEKLY;COUNT=5;BYDAY=SU"
    assert recurrence["rule"] == {"FREQ": "WEEKLY", "COUNT": "5", "BYDAY": "SU"}
    assert recurrence["expanded"] is False
    assert result.metadata["recurrence_expanded"] is False
    alarm_names = {
        unit.structured_payload["name"]
        for unit in result.units
        if unit.evidence_locator.locator["component"] == "VALARM"
    }
    assert alarm_names == {"TRIGGER", "ACTION", "DESCRIPTION"}
    assert all(unit.evidence_locator.locator.get("uid") == "event-1" for unit in result.units)


def test_vcf_preserves_known_and_custom_properties_without_relationship_claims(tmp_path: Path):
    path = tmp_path / "contacts.vcf"
    path.write_text(
        "BEGIN:VCARD\r\n"
        "VERSION:4.0\r\n"
        "FN:Alex Example\r\n"
        "N:Example;Alex;;;\r\n"
        "EMAIL;TYPE=work:alex@example.test\r\n"
        "TEL;TYPE=cell:+441234567890\r\n"
        "ORG:Example Ltd\r\n"
        "ADR;TYPE=work:;;1 Example Road;London;;;UK\r\n"
        "BDAY:1990-01-02\r\n"
        "X-SOCIAL-PROFILE;TYPE=mastodon:https://social.example/@alex\r\n"
        "END:VCARD\r\n",
        encoding="utf-8",
        newline="",
    )

    result = EmailCalendarAdapter().extract(str(path), _context(path))
    custom = next(unit for unit in result.units if unit.evidence_locator.locator["property"] == "X-SOCIAL-PROFILE")

    assert result.metadata["card_count"] == 1
    assert custom.structured_payload["classification"] == "unknown_property"
    assert custom.structured_payload["parameters"] == {"TYPE": ["mastodon"]}
    assert custom.value == "https://social.example/@alex"
    assert custom.metadata["custom"] is True
    assert all("relationship" not in unit.structured_payload for unit in result.units)
