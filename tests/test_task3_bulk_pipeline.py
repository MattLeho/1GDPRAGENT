from __future__ import annotations

from pathlib import Path
import json
from urllib.parse import urlparse
from urllib.request import url2pathname

import asyncpg
import pytest
from PIL import Image

from db.postgres import PostgresClient
import ingestion.bulk as bulk_module
from ingestion.bulk import BulkIngestionService
from ingestion.models import DeclarativeParserSpec, TemporalPrecision
from ingestion.schema_registry import SchemaRegistry
from ingestion.storage import StorageRoots
from test_task1_database_integration import migrated_database
from api.bulk_ingestion import _persist_specialist_units


@pytest.mark.asyncio
async def test_bulk_pipeline_persists_source_units_unknown_schema_and_resumes(tmp_path, migrated_database, monkeypatch):
    url, request_id, _file_id = migrated_database
    imports = tmp_path / "imports"
    imports.mkdir()
    source = imports / "events.json"
    source.write_text('[{"subject":{"id":"p"},"time":"2024-01-01","value":1},{"subject":{"id":"p"},"time":"2024-01-02","value":2}]', encoding="utf-8")
    client = PostgresClient(url)
    service = BulkIngestionService(
        client, roots=StorageRoots.from_base(tmp_path / "data"),
        import_roots=(imports.resolve(),),
    )
    process_calls = 0
    blob_write_calls = 0
    original_process = service.processor.process
    original_blob_write = bulk_module.write_raw_blob

    def process_spy(*args, **kwargs):
        nonlocal process_calls
        process_calls += 1
        return original_process(*args, **kwargs)

    def blob_write_spy(*args, **kwargs):
        nonlocal blob_write_calls
        blob_write_calls += 1
        return original_blob_write(*args, **kwargs)

    monkeypatch.setattr(service.processor, "process", process_spy)
    monkeypatch.setattr(bulk_module, "write_raw_blob", blob_write_spy)
    try:
        run_id, snapshot_id = await service.prepare_run(
            request_id=request_id, source_type="manual_import",
        )
        first = await service.process_file(
            str(source), analysis_run_id=run_id, export_snapshot_id=snapshot_id,
            declared_mime="application/json", original_path="events.json",
        )
        assert first.ingestion_status == "completed"
        assert first.detected_format == "json" and first.extraction_unit_count == 2
        assert first.schema_outcome == "interpretation_required"
        assert first.interpretation_request_id is not None and first.event_count == 0
        second = await service.process_file(
            str(source), analysis_run_id=run_id, export_snapshot_id=snapshot_id,
            declared_mime="application/json", original_path="events.json",
        )
        assert second.artifact_id == first.artifact_id
        assert second.interpretation_request_id == first.interpretation_request_id
        assert second == first
        assert process_calls == 1
        assert blob_write_calls == 1

        source.write_text('[{"subject":{"id":"changed"},"time":"2024-01-01","value":9}]', encoding="utf-8")
        with pytest.raises(ValueError, match="changed content"):
            await service.process_file(
                str(source), analysis_run_id=run_id, export_snapshot_id=snapshot_id,
                declared_mime="application/json", original_path="events.json",
            )
        assert blob_write_calls == 2
        assert process_calls == 1
        source.write_text('[{"subject":{"id":"p"},"time":"2024-01-01","value":1},{"subject":{"id":"p"},"time":"2024-01-02","value":2}]', encoding="utf-8")

        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM content_blobs") == 1
            assert await connection.fetchval("SELECT count(*) FROM source_artifacts WHERE export_snapshot_id=$1", snapshot_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM extraction_units WHERE artifact_id=$1", first.artifact_id) == 2
            assert await connection.fetchval("SELECT count(*) FROM evidence_locators WHERE artifact_id=$1 AND NOT verified", first.artifact_id) == 2
            assert await connection.fetchval("SELECT count(*) FROM schema_interpretation_requests WHERE analysis_run_id=$1", run_id) == 1
            assert await connection.fetchval("SELECT count(*) FROM pipeline_checkpoints WHERE analysis_run_id=$1 AND status='completed'", run_id) >= 5
            assert await connection.fetchval("SELECT status FROM file_ingestion_records WHERE artifact_id=$1", first.artifact_id) == "completed"

            registry=SchemaRegistry(connection)
            parser_id=await registry.propose(DeclarativeParserSpec(
                parser_id="fixture.bulk",parser_version="1",file_family="json",
                event_type="fixture.observed",data_domain="fixture",
                timestamp_selector="/time",temporal_precision=TemporalPrecision.DAY,
                subject_selector="/subject/id",object_selectors={"value":"/value"},
            ))
            await registry.approve(parser_spec_id=parser_id,approved_by="fixture-reviewer")
            fingerprint_db_id=await connection.fetchval(
                "SELECT id FROM structure_fingerprints WHERE fingerprint_hash=$1",first.fingerprint_id,
            )
            await registry.bind(
                structure_fingerprint_id=fingerprint_db_id,parser_spec_id=parser_id,
                source_service="Fixture",data_domain="fixture",file_family="json",
                normalised_event_type="fixture.observed",
            )
        finally:
            await connection.close()

        known_run,known_snapshot=await service.prepare_run(request_id=request_id,source_type="manual_import")
        parser_calls = 0
        original_execute_known_parser = service._execute_known_parser

        async def parser_spy(*args, **kwargs):
            nonlocal parser_calls
            parser_calls += 1
            return await original_execute_known_parser(*args, **kwargs)

        monkeypatch.setattr(service, "_execute_known_parser", parser_spy)
        known=await service.process_file(
            str(source),analysis_run_id=known_run,export_snapshot_id=known_snapshot,
            declared_mime="application/json",original_path="events.json",
        )
        assert known.schema_outcome=="known" and known.event_count==2
        known_replay=await service.process_file(
            str(source),analysis_run_id=known_run,export_snapshot_id=known_snapshot,
            declared_mime="application/json",original_path="events.json",
        )
        assert known_replay == known
        assert parser_calls == 1
        connection=await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM event_partitions WHERE analysis_run_id=$1",known_run)==2
            assert await connection.fetchval("SELECT count(*) FROM activity_event_observations WHERE export_snapshot_id=$1",known_snapshot)==2
            assert await connection.fetchval("SELECT count(*) FROM logical_event_signatures")==2
        finally:
            await connection.close()

        image_path=imports/"screenshot.png"
        Image.new("RGB",(32,18),"white").save(image_path)
        media_run,media_snapshot=await service.prepare_run(request_id=request_id,source_type="manual_import")
        media=await service.process_file(
            str(image_path),analysis_run_id=media_run,export_snapshot_id=media_snapshot,
            declared_mime="image/png",original_path="screenshot.png",
            requested_tasks=("image.ocr",),received_data_id=_file_id,
        )
        assert [task.task_key for task in media.specialist_tasks]==["image.ocr"]
        request_rows=await client.execute("SELECT * FROM specialist_task_requests WHERE id=$1",media.specialist_tasks[0].request_id)
        await _persist_specialist_units(client,dict(request_rows[0]),{
            "text":"Hello","words":[{"text":"Hello","confidence":98.0,"left":2,"top":3,"width":10,"height":5}],
            "engine":"local_ocr","model":"tesseract","derivation_version":"task2-ocr-v1",
        })
        connection=await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT count(*) FROM extraction_units WHERE artifact_id=$1 AND unit_type='ocr_word'",media.artifact_id)==1
            assert await connection.fetchval("SELECT extracted_text FROM received_data WHERE id=$1",_file_id)=="Hello"
            assert await connection.fetchval("SELECT provenance_status FROM received_data WHERE id=$1",_file_id)=="specialist_candidate"
        finally:
            await connection.close()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_mbox_attachment_creates_canonical_child_artifact_and_exact_parent_locator(tmp_path, migrated_database):
    url, request_id, _file_id = migrated_database
    imports = tmp_path / "imports"
    imports.mkdir()
    source = imports / "mail.mbox"
    source.write_bytes(
        b"From sender@example.test Sat Jan 01 00:00:00 2022\n"
        b"From: sender@example.test\nTo: recipient@example.test\n"
        b"Message-ID: <attachment@example.test>\nSubject: Attachment\n"
        b"MIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=box\n\n"
        b"--box\nContent-Type: text/plain\n\nBody\n"
        b"--box\nContent-Type: application/octet-stream\n"
        b"Content-Disposition: attachment; filename=evidence.bin\n"
        b"Content-Transfer-Encoding: base64\n\nAAEC/w==\n--box--\n"
    )
    client = PostgresClient(url)
    service = BulkIngestionService(
        client, roots=StorageRoots.from_base(tmp_path / "data"),
        import_roots=(imports.resolve(),),
    )
    try:
        run_id, snapshot_id = await service.prepare_run(request_id=request_id, source_type="manual_import")
        result = await service.process_file(
            str(source), analysis_run_id=run_id, export_snapshot_id=snapshot_id,
            declared_mime="application/mbox", original_path="mail.mbox",
        )
        replay = await service.process_file(
            str(source), analysis_run_id=run_id, export_snapshot_id=snapshot_id,
            declared_mime="application/mbox", original_path="mail.mbox",
        )
        assert replay == result

        connection = await asyncpg.connect(url)
        try:
            child = await connection.fetchrow(
                """SELECT sa.*,cb.sha256,cb.byte_size,cb.storage_uri FROM source_artifacts sa
                JOIN content_blobs cb ON cb.id=sa.content_blob_id
                WHERE sa.parent_artifact_id=$1""", result.artifact_id,
            )
            assert child is not None
            assert child["archive_member_path"] == "message-0/part-2/evidence.bin"
            assert child["original_path"] == "mail.mbox"
            assert child["file_name"] == "evidence.bin"
            assert child["byte_size"] == 4
            assert Path(url2pathname(urlparse(child["storage_uri"]).path)).read_bytes() == b"\x00\x01\x02\xff"
            locator = await connection.fetchrow(
                """SELECT eu.unit_type,el.locator_type,el.locator FROM extraction_units eu
                JOIN evidence_locators el ON el.id=eu.evidence_locator_id
                WHERE eu.artifact_id=$1 AND eu.unit_type='email_attachment'""", result.artifact_id,
            )
            assert locator["unit_type"] == "email_attachment"
            assert locator["locator_type"] == "email_attachment"
            locator_value = json.loads(locator["locator"]) if isinstance(locator["locator"], str) else dict(locator["locator"])
            assert locator_value == {"message": 0, "part": "2", "filename": "evidence.bin"}
            assert await connection.fetchval(
                "SELECT count(*) FROM source_artifacts WHERE parent_artifact_id=$1", result.artifact_id,
            ) == 1
        finally:
            await connection.close()
    finally:
        await client.close()
