from __future__ import annotations

import base64
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from openpyxl import Workbook
from PIL import Image

from evidence.locators import resolve_locator
from ingestion.adapters.archives import ArchiveAdapter
from ingestion.adapters.documents import DocumentsAdapter
from ingestion.adapters.email_calendar import EmailCalendarAdapter
from ingestion.adapters.geospatial_database import GeospatialDatabaseAdapter
from ingestion.adapters.media import MediaAdapter
from ingestion.adapters.structured_text import StructuredTextAdapter
from ingestion.models import ExtractionContext, QuarantineStatus


def _context(path: Path, artifact_id: UUID | None = None, **configuration: object) -> ExtractionContext:
    return ExtractionContext(
        artifact_id=artifact_id or uuid4(),
        analysis_run_id=uuid4(),
        export_snapshot_id=uuid4(),
        source_path=str(path),
        configuration=configuration,
    )


def _jpeg_bytes(*, with_exif: bool = False) -> bytes:
    output = io.BytesIO()
    exif = None
    if with_exif:
        exif = Image.Exif()
        exif[271] = "Fixture Camera Co"
        exif[272] = "Fixture Camera"
        exif[36867] = "2024:06:07 08:09:10"
        exif[36881] = "+01:00"
    save_options = {"exif": exif} if exif is not None else {}
    Image.new("RGB", (12, 8), "teal").save(output, format="JPEG", **save_options)
    return output.getvalue()


def _eml_with_attachment(filename: str, media_type: str, payload: bytes) -> bytes:
    encoded = base64.b64encode(payload)
    return (
        b"From: sender@example.test\r\n"
        b"To: recipient@example.test\r\n"
        b"Message-ID: <fixture@example.test>\r\n"
        b"Subject: fixture\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=fixture-boundary\r\n\r\n"
        b"--fixture-boundary\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Body\r\n"
        b"--fixture-boundary\r\n"
        + f"Content-Type: {media_type}\r\n".encode()
        + f"Content-Disposition: attachment; filename={filename}\r\n".encode()
        + b"Content-Transfer-Encoding: base64\r\n\r\n"
        + encoded
        + b"\r\n--fixture-boundary--\r\n"
    )


def test_zip_members_cross_into_json_image_and_email_adapters_with_resolvable_lineage(tmp_path: Path):
    json_bytes = b'{"events":[{"id":"evt-1"}]}'
    image_bytes = _jpeg_bytes()
    email_bytes = _eml_with_attachment("note.txt", "text/plain", b"attached note")
    archive_path = tmp_path / "takeout.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("records/events.json", json_bytes)
        archive.writestr("media/photo.jpg", image_bytes)
        archive.writestr("mail/message.eml", email_bytes)

    outer_id = uuid4()
    archive_result = ArchiveAdapter().extract(
        str(archive_path), _context(archive_path, outer_id, detected_format="zip")
    )

    assert archive_result.quarantine_status is QuarantineStatus.NONE
    assert [member.member_path for member in archive_result.embedded_members] == [
        "records/events.json",
        "media/photo.jpg",
        "mail/message.eml",
    ]
    resolved_members: dict[str, bytes] = {}
    for unit in archive_result.units:
        locator = unit.evidence_locator
        assert locator.locator_type == "archive_member"
        assert locator.locator == {
            "member_path": unit.structured_payload["member_path"],
            "outer_artifact_id": outer_id,
            "nested_member_chain": (),
            "member_ordinal": unit.ordinal,
        }
        resolved_members[unit.structured_payload["member_path"]] = resolve_locator(
            archive_path.read_bytes(), locator.locator_type, locator.locator
        )

    assert resolved_members == {
        "records/events.json": json_bytes,
        "media/photo.jpg": image_bytes,
        "mail/message.eml": email_bytes,
    }

    json_path = tmp_path / "events.json"
    json_path.write_bytes(resolved_members["records/events.json"])
    json_result = StructuredTextAdapter().extract(str(json_path), _context(json_path))
    assert json.loads(resolve_locator(
        json_path.read_bytes(),
        json_result.units[0].evidence_locator.locator_type,
        json_result.units[0].evidence_locator.locator,
    )) == {"events": [{"id": "evt-1"}]}

    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(resolved_members["media/photo.jpg"])
    image_result = MediaAdapter().extract(str(image_path), _context(image_path))
    assert resolve_locator(
        image_path.read_bytes(),
        image_result.units[0].evidence_locator.locator_type,
        image_result.units[0].evidence_locator.locator,
    ).startswith(b"\x89PNG")

    email_path = tmp_path / "message.eml"
    email_path.write_bytes(resolved_members["mail/message.eml"])
    email_result = EmailCalendarAdapter().extract(str(email_path), _context(email_path))
    body = next(unit for unit in email_result.units if unit.unit_type == "email_body")
    assert resolve_locator(
        email_path.read_bytes(), body.evidence_locator.locator_type, body.evidence_locator.locator
    ) == b"Body"


def test_mbox_pdf_attachment_is_a_child_descriptor_and_exactly_resolvable(tmp_path: Path):
    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
    first = _eml_with_attachment("report.pdf", "application/pdf", pdf_bytes)
    mbox_path = tmp_path / "mail.mbox"
    mbox_path.write_bytes(
        b"From sender@example.test Sat Jan 01 00:00:00 2022\n"
        + first.replace(b"\r\n", b"\n")
        + b"\nFrom second@example.test Sat Jan 01 00:01:00 2022\n"
        b"From: second@example.test\nTo: recipient@example.test\n"
        b"Message-ID: <second@example.test>\nSubject: second\n\nNo attachment\n"
    )

    result = EmailCalendarAdapter().extract(str(mbox_path), _context(mbox_path))
    attachment = next(unit for unit in result.units if unit.unit_type == "email_attachment")

    assert len(result.embedded_members) == 1
    descriptor = result.embedded_members[0]
    assert descriptor.member_path == "report.pdf"
    assert descriptor.media_type == "application/pdf"
    assert descriptor.declared_size == len(pdf_bytes)
    assert descriptor.metadata["message"] == 0
    assert descriptor.metadata["part"] == "2"
    assert attachment.evidence_locator.locator == {
        "message": 0,
        "part": "2",
        "filename": "report.pdf",
    }
    assert resolve_locator(
        mbox_path.read_bytes(),
        attachment.evidence_locator.locator_type,
        attachment.evidence_locator.locator,
    ) == pdf_bytes


def test_duplicate_embedded_image_retains_two_parent_occurrences(tmp_path: Path):
    image_bytes = _jpeg_bytes(with_exif=True)
    results = []
    resolved = []
    parent_ids = [uuid4(), uuid4()]
    for index, parent_id in enumerate(parent_ids):
        path = tmp_path / f"parent-{index}.eml"
        path.write_bytes(_eml_with_attachment("shared.jpg", "image/jpeg", image_bytes))
        result = EmailCalendarAdapter().extract(str(path), _context(path, parent_id))
        results.append(result)
        attachment = next(unit for unit in result.units if unit.unit_type == "email_attachment")
        resolved.append(resolve_locator(
            path.read_bytes(), attachment.evidence_locator.locator_type, attachment.evidence_locator.locator
        ))

    assert parent_ids[0] != parent_ids[1]
    assert all(len(result.embedded_members) == 1 for result in results)
    assert [result.embedded_members[0].member_path for result in results] == ["shared.jpg", "shared.jpg"]
    assert resolved == [image_bytes, image_bytes]
    assert len({hashlib.sha256(item).hexdigest() for item in resolved}) == 1


def test_xlsx_dates_urls_and_opaque_ids_preserve_values_and_resolvable_cell_locators(tmp_path: Path):
    path = tmp_path / "identifiers.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Activity"
    sheet.append(["occurred_at", "url", "opaque_id"])
    sheet.append([
        datetime(2024, 6, 7, 8, 9, 10),
        "https://example.test/path?account=abc123",
        "A9f_7Qx-opaque-001",
    ])
    workbook.save(path)
    workbook.close()

    result = DocumentsAdapter().extract(str(path), _context(path, detected_format="xlsx"))
    cells = {unit.evidence_locator.locator["address"]: unit for unit in result.units}

    assert cells["A2"].evidence_locator.locator == {
        "sheet": "Activity", "row": 2, "column": 1, "address": "A2"
    }
    assert cells["A2"].structured_payload["value"] == "2024-06-07T08:09:10"
    assert cells["B2"].value == "https://example.test/path?account=abc123"
    assert cells["C2"].value == "A9f_7Qx-opaque-001"
    assert json.loads(resolve_locator(
        path.read_bytes(), "spreadsheet_cell", cells["A2"].evidence_locator.locator
    )) == {"formula": None, "value": "2024-06-07 08:09:10"}
    assert json.loads(resolve_locator(
        path.read_bytes(), "spreadsheet_cell", cells["B2"].evidence_locator.locator
    )) == {"formula": None, "value": "https://example.test/path?account=abc123"}
    assert json.loads(resolve_locator(
        path.read_bytes(), "spreadsheet_cell", cells["C2"].evidence_locator.locator
    )) == {"formula": None, "value": "A9f_7Qx-opaque-001"}


def test_image_without_exif_and_image_with_exif_remain_metadata_only_not_presence_claims(tmp_path: Path):
    plain_path = tmp_path / "screenshot.jpg"
    exif_path = tmp_path / "camera.jpg"
    plain_path.write_bytes(_jpeg_bytes())
    exif_path.write_bytes(_jpeg_bytes(with_exif=True))

    adapter = MediaAdapter()
    plain = adapter.extract(str(plain_path), _context(plain_path))
    tagged = adapter.extract(str(exif_path), _context(exif_path))

    assert plain.metadata["exif"] == {}
    assert "capture_timestamp" not in plain.metadata
    assert "gps" not in plain.metadata
    assert tagged.metadata["capture_timestamp"] == "2024:06:07 08:09:10"
    assert tagged.metadata["timezone"] == "+01:00"
    assert tagged.metadata["device"] == {
        "make": "Fixture Camera Co", "model": "Fixture Camera"
    }
    for result in (plain, tagged):
        assert result.units[0].metadata == {"metadata_only": True}
        semantic_keys = {str(key).lower() for key in result.metadata}
        assert not semantic_keys & {"physical_presence", "presence", "home", "visited"}
        assert resolve_locator(
            (plain_path if result is plain else exif_path).read_bytes(),
            result.units[0].evidence_locator.locator_type,
            result.units[0].evidence_locator.locator,
        ).startswith(b"\x89PNG")


def test_gpx_track_and_sqlite_rows_have_exact_resolvable_source_locators(tmp_path: Path):
    gpx_path = tmp_path / "track.gpx"
    gpx_path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<gpx version='1.1' creator='fixture' xmlns='http://www.topografix.com/GPX/1/1'>"
        "<trk><name>Morning route</name><trkseg>"
        "<trkpt lat='51.5000' lon='-0.1250'><ele>12</ele><time>2024-06-07T08:00:00Z</time></trkpt>"
        "<trkpt lat='51.5010' lon='-0.1240'><ele>13</ele><time>2024-06-07T08:01:00Z</time></trkpt>"
        "</trkseg></trk></gpx>",
        encoding="utf-8",
    )
    geo = GeospatialDatabaseAdapter().extract(str(gpx_path), _context(gpx_path, detected_format="gpx"))
    track = geo.units[0]
    assert track.evidence_locator.locator == {"feature": 0, "segment": 0}
    assert track.structured_payload["coordinates"] == [
        (-0.125, 51.5, 12.0),
        (-0.124, 51.501, 13.0),
    ]
    resolved_track = json.loads(resolve_locator(
        gpx_path.read_bytes(), track.evidence_locator.locator_type, track.evidence_locator.locator
    ))
    assert resolved_track["coordinates"] == [[-0.125, 51.5, 12.0], [-0.124, 51.501, 13.0]]
    assert not {"home", "visited", "physical_presence"} & {
        str(key).lower() for key in track.structured_payload
    }

    database_path = tmp_path / "events.sqlite"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, occurred_at TEXT, opaque_id TEXT)")
    connection.execute(
        "INSERT INTO events VALUES (?, ?, ?)",
        (7, "2024-06-07T08:09:10Z", "opaque-7"),
    )
    connection.commit()
    connection.close()

    database = GeospatialDatabaseAdapter().extract(
        str(database_path), _context(database_path, detected_format="sqlite")
    )
    row = next(unit for unit in database.units if unit.unit_type == "database_table_row")
    opaque = next(
        unit for unit in database.units
        if unit.unit_type == "database_cell" and unit.evidence_locator.locator["column"] == "opaque_id"
    )
    assert row.evidence_locator.locator == {"table": "events", "row_key": {"rowid": 7}}
    assert opaque.evidence_locator.locator == {
        "table": "events", "row_key": {"rowid": 7}, "column": "opaque_id"
    }
    assert json.loads(resolve_locator(
        database_path.read_bytes(), row.evidence_locator.locator_type, row.evidence_locator.locator
    )) == [7, "2024-06-07T08:09:10Z", "opaque-7"]
    assert json.loads(resolve_locator(
        database_path.read_bytes(), opaque.evidence_locator.locator_type, opaque.evidence_locator.locator
    )) == "opaque-7"


def test_corrupt_and_unsupported_inputs_remain_visible_without_convenience_success(tmp_path: Path):
    corrupt_path = tmp_path / "broken.json"
    corrupt_path.write_bytes(b'{"unfinished":')
    corrupt = StructuredTextAdapter().extract(str(corrupt_path), _context(corrupt_path))

    unsupported_path = tmp_path / "unknown.bin"
    unsupported_path.write_bytes(b"\x00\x01\x02not-a-supported-media-container")
    unsupported = MediaAdapter().extract(str(unsupported_path), _context(unsupported_path))

    assert corrupt.artifact_id is not None
    assert corrupt.detected_format == "json"
    assert corrupt.quarantine_status is QuarantineStatus.CORRUPT
    assert corrupt.units == ()
    assert corrupt.warnings
    assert unsupported.artifact_id is not None
    assert unsupported.detected_format == "unknown"
    assert unsupported.quarantine_status is QuarantineStatus.UNSUPPORTED
    assert unsupported.units == ()
    assert unsupported.warnings
    assert not any("upload" in warning.lower() or "llm" in warning.lower() for warning in unsupported.warnings)
