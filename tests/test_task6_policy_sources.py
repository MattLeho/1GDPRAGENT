from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from db.postgres import PostgresClient
from evidence.locators import resolve_locator
from privacy.policy_sources import (
    PolicySourceIngestionService, PolicySourceMetadata, PolicyTextSpan,
)
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)


def metadata(**overrides):
    values = dict(
        policy_key="example-privacy-policy", version_label="2026-07",
        retrieved_at=NOW, effective_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        source_uri="https://example.invalid/privacy", file_name="privacy.txt",
        declared_mime="text/plain", source_organisation="Example Controller",
        authorisation_basis="user supplied a saved policy copy",
    )
    values.update(overrides)
    return PolicySourceMetadata(**values)


def test_policy_input_rejects_unsafe_or_ambiguous_content(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        metadata(retrieved_at=datetime(2026, 7, 13))
    with pytest.raises(ValueError, match="basename"):
        metadata(file_name="../privacy.txt")
    service = PolicySourceIngestionService(blob_root=tmp_path)
    with pytest.raises(ValueError, match="UTF-8"):
        # Validation occurs before any database or filesystem write.
        import asyncio
        asyncio.run(service.ingest(b"\xff", metadata()))
    assert not any(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_policy_source_preserves_exact_bytes_dates_and_resolvable_spans(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client = PostgresClient(url)
    service = PolicySourceIngestionService(client, blob_root=tmp_path / "blobs")
    content = "Intro\nWe use account data to provide the service.\nEnd\n".encode()
    quote = b"account data to provide the service"
    start = content.index(quote)
    result = await service.ingest(
        content, metadata(),
        text_spans=(PolicyTextSpan(
            byte_start=start, byte_end=start + len(quote), expected_text=quote.decode(),
            line_start=2, line_end=2,
        ),),
    )
    try:
        assert result.created and result.content_hash == hashlib.sha256(content).hexdigest()
        stored = Path(result.storage_uri.removeprefix("file:///"))
        # url2pathname is unnecessary for this test path (no escaped characters).
        if not stored.exists():
            from urllib.parse import unquote, urlparse
            from urllib.request import url2pathname
            stored = Path(url2pathname(unquote(urlparse(result.storage_uri).path)))
        assert stored.read_bytes() == content

        connection = await asyncpg.connect(url)
        try:
            row = await connection.fetchrow(
                """SELECT psv.*,sa.canonical_hash,cb.sha256,cb.byte_size,es.exported_at,
                          ar.status,ar.configuration,el.locator_type,el.locator,el.verified,
                          el.verification_method,el.raw_hash
                     FROM policy_source_versions psv
                     JOIN source_artifacts sa ON sa.id=psv.source_artifact_id
                     JOIN content_blobs cb ON cb.id=sa.content_blob_id
                     JOIN export_snapshots es ON es.id=sa.export_snapshot_id
                     JOIN analysis_runs ar ON ar.id=es.analysis_run_id
                     JOIN evidence_locators el ON el.artifact_id=sa.id
                    WHERE psv.id=$1""", result.policy_source_version_id,
            )
            assert row["effective_from"] == datetime(2026, 7, 1, tzinfo=timezone.utc)
            assert row["retrieved_at"] == NOW and row["exported_at"] == NOW
            assert row["content_hash"].strip() == result.content_hash
            assert row["canonical_hash"].strip() == result.content_hash
            assert row["sha256"].strip() == result.content_hash and row["byte_size"] == len(content)
            assert row["status"] == "completed"
            configuration = row["configuration"]
            if isinstance(configuration, str):
                configuration = json.loads(configuration)
            assert configuration["network_fetch"] is False
            assert configuration["model_call"] is False
            assert row["locator_type"] == "text_span" and row["verified"] is True
            assert row["verification_method"] == "exact_quote_match"
            assert row["raw_hash"].strip() == hashlib.sha256(quote).hexdigest()
            locator=row["locator"]
            if isinstance(locator,str):
                locator=json.loads(locator)
            assert resolve_locator(content, row["locator_type"], dict(locator)) == quote
        finally:
            await connection.close()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_policy_source_ingestion_is_idempotent_and_versions_changed_bytes(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client = PostgresClient(url)
    service = PolicySourceIngestionService(client, blob_root=tmp_path / "blobs")
    content = b"Policy version one"
    try:
        first = await service.ingest(content, metadata())
        repeated = await service.ingest(content, metadata(retrieved_at=datetime(2026, 7, 14, tzinfo=timezone.utc)))
        extra_span = await service.ingest(
            content, metadata(),
            text_spans=(PolicyTextSpan(byte_start=0, byte_end=6, expected_text="Policy"),),
        )
        exact_repeat = await service.ingest(
            content, metadata(),
            text_spans=(PolicyTextSpan(byte_start=0, byte_end=6, expected_text="Policy"),),
        )
        changed = await service.ingest(b"Policy version one, corrected", metadata())
        assert not repeated.created
        assert repeated.policy_source_version_id == first.policy_source_version_id
        assert repeated.source_artifact_id == first.source_artifact_id
        assert len(extra_span.evidence_locator_ids) == 2
        assert exact_repeat.evidence_locator_ids == extra_span.evidence_locator_ids
        assert changed.created and changed.policy_source_version_id != first.policy_source_version_id

        connection = await asyncpg.connect(url)
        try:
            counts = await connection.fetchrow(
                """SELECT (SELECT count(*) FROM policy_source_versions WHERE policy_key=$1) versions,
                          (SELECT count(*) FROM source_artifacts sa JOIN policy_source_versions psv
                             ON psv.source_artifact_id=sa.id WHERE psv.policy_key=$1) artifacts,
                          (SELECT count(*) FROM analysis_runs WHERE run_type='policy_source_ingestion') runs""",
                "example-privacy-policy",
            )
            assert dict(counts) == {"versions": 2, "artifacts": 2, "runs": 2}
        finally:
            await connection.close()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_policy_span_must_match_exact_authorised_bytes(tmp_path):
    service = PolicySourceIngestionService(blob_root=tmp_path)
    content = "café policy".encode()
    with pytest.raises(ValueError, match="align"):
        await service.ingest(content, metadata(), text_spans=(PolicyTextSpan(byte_start=0, byte_end=4),))
    with pytest.raises(ValueError, match="quoted text"):
        await service.ingest(
            content, metadata(),
            text_spans=(PolicyTextSpan(byte_start=0, byte_end=5, expected_text="wrong"),),
        )
    assert not any(tmp_path.iterdir())
