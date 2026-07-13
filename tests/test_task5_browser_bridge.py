from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from uuid import uuid4

import asyncpg
import pytest

from connectors.bridge import ConnectorIngestionBridge
from connectors.browser_bridge import (
    BrowserBridgeAuthenticationError, BrowserBridgeError, BrowserBridgeFrame,
    BrowserBridgeService,
)
from connectors.definitions import BROWSER_HISTORY_DEFINITION
from connectors.models import ConnectorStatus
from connectors.repository import ConnectorRepository
from connectors.signatures import connector_record_signature
from db.postgres import PostgresClient
from ingestion.storage import StorageRoots
from test_task1_database_integration import migrated_database


VISITED = datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc)
OBSERVED = datetime(2026, 7, 13, 14, 0, tzinfo=timezone.utc)


def _record(instance_id, *, include_page_content=False):
    document = {
        "browser_profile_connector_id": "browser-profile-1",
        "referring_visit_id": "41", "transition_type": "link",
        "url": "https://example.test/path?q=1", "visit_id": "42",
        "visit_time": "2024-03-09T16:00:00.000Z",
    }
    if include_page_content:
        document["page_body"] = "must never be accepted"
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    metadata = {
        "browser_profile_connector_id": "browser-profile-1",
        "local_or_synced_origin": "local", "referring_visit_id": "41",
        "transition_type": "link",
    }
    signature = connector_record_signature(
        source_record_id="browser-profile-1:42", source_record_version="1",
        payload=payload, data_class="browser.visit", occurred_at=VISITED,
        media_type="application/json", source_metadata=metadata,
    )
    return {
        "source_record_id": "browser-profile-1:42", "source_record_version": "1",
        "record_signature": signature, "data_class": "browser.visit",
        "occurred_at": VISITED.isoformat(), "observed_at": OBSERVED.isoformat(),
        "media_type": "application/json",
        "payload_base64": base64.b64encode(payload).decode(),
        "source_metadata": metadata, "required_permissions": ["history.read"],
    }


def _frame(instance_id, record, *, message_id=None):
    return BrowserBridgeFrame.model_validate({
        "protocol": "gdpr-agent-connector", "version": 1,
        "message_id": str(message_id or uuid4()),
        "connector_instance_id": str(instance_id),
        "sent_at": OBSERVED.isoformat(), "records": [record],
    })


@pytest.mark.asyncio
async def test_browser_bridge_pairing_ack_replay_and_local_evidence(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client = PostgresClient(url)
    repository = ConnectorRepository(client)
    await repository.declare_definition(BROWSER_HISTORY_DEFINITION)
    instance = await repository.create_instance(
        BROWSER_HISTORY_DEFINITION, display_name="Local Chromium",
        enabled_permissions=("history.read",), status=ConnectorStatus.CONNECTED,
        configuration={"browser_profile_connector_id": "browser-profile-1", "page_content_capture": False},
    )
    service = BrowserBridgeService(
        client, bridge=ConnectorIngestionBridge(
            client, roots=StorageRoots.from_base(tmp_path / "browser-bridge"),
        ),
    )
    pairing = await service.create_pairing(instance.id, "Chromium test profile")
    frame = _frame(instance.id, _record(instance.id))

    first = await service.receive(frame, pairing.token)
    assert first.status == "acknowledged"
    assert first.ingested == 1 and first.duplicates == 0
    assert first.events_produced == 1
    replay = await service.receive(frame, pairing.token)
    assert replay == first
    altered = _frame(instance.id, _record(instance.id), message_id=frame.message_id)
    altered = altered.model_copy(update={"sent_at": OBSERVED.replace(minute=1)})
    with pytest.raises(BrowserBridgeError, match="different frame content"):
        await service.receive(altered, pairing.token)

    with pytest.raises(BrowserBridgeAuthenticationError):
        await service.receive(_frame(instance.id, _record(instance.id)), "x" * 43)

    connection = await asyncpg.connect(url)
    try:
        counts = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM browser_bridge_messages WHERE connector_instance_id=$1) messages,
              (SELECT COUNT(*) FROM connector_raw_records WHERE connector_instance_id=$1) raw_records,
              (SELECT COUNT(*) FROM connector_sync_runs WHERE connector_instance_id=$1) sync_runs,
              (SELECT COALESCE(SUM(row_count),0) FROM event_partitions ep JOIN analysis_runs ar ON ar.id=ep.analysis_run_id
               WHERE ar.configuration->>'connector_instance_id'=$2 AND ep.partition_key LIKE 'events/%') event_rows,
              (SELECT COUNT(*) FROM evidence_locators el JOIN source_artifacts sa ON sa.id=el.artifact_id
               JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.metadata->>'connector_instance_id'=$2 AND el.verified) locators""",
            instance.id, str(instance.id),
        )
        assert dict(counts) == {"messages": 1, "raw_records": 1, "sync_runs": 1, "event_rows": 1, "locators": 1}
        stored_hash = await connection.fetchval(
            "SELECT token_hash FROM browser_bridge_pairings WHERE id=$1", pairing.pairing_id,
        )
        assert pairing.token not in stored_hash and len(stored_hash) == 64
    finally:
        await connection.close()

    assert await service.revoke_pairing(pairing.pairing_id)
    with pytest.raises(BrowserBridgeAuthenticationError, match="revoked"):
        await service.receive(_frame(instance.id, _record(instance.id)), pairing.token)
    await client.close()


@pytest.mark.asyncio
async def test_browser_bridge_rejects_page_content_even_with_valid_signature(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client = PostgresClient(url)
    repository = ConnectorRepository(client)
    await repository.declare_definition(BROWSER_HISTORY_DEFINITION)
    instance = await repository.create_instance(
        BROWSER_HISTORY_DEFINITION, display_name="No content",
        enabled_permissions=("history.read",), status=ConnectorStatus.CONNECTED,
    )
    service = BrowserBridgeService(
        client, bridge=ConnectorIngestionBridge(
            client, roots=StorageRoots.from_base(tmp_path / "browser-bridge"),
        ),
    )
    pairing = await service.create_pairing(instance.id, "No page content")
    with pytest.raises(BrowserBridgeError, match="page-content"):
        await service.receive(_frame(instance.id, _record(instance.id, include_page_content=True)), pairing.token)
    assert await repository.get_cursor(instance.id, "browser-history") is None
    await client.close()
