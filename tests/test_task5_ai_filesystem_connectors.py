from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
from PIL import Image
import pytest

from connectors.ai_conversations import AIConversationSnapshotConnector, parse_ai_export
from connectors.bridge import ConnectorIngestionBridge
from connectors.definitions import (
    AI_CONVERSATION_DEFINITION, FILESYSTEM_DEFINITION, PHOTO_FOLDER_DEFINITION,
)
from connectors.filesystem import FolderConnector
from connectors.models import ConnectorInstance, ConnectorStatus, SyncRunStatus
from connectors.registry import ConnectorRegistry
from connectors.repository import ConnectorRepository
from connectors.runtime import ConnectorRuntime
from db.postgres import PostgresClient
from features.pipeline import load_activity_event_partitions
from ingestion.storage import StorageRoots
from insights.models import SignalClass
from insights.signals import classify_event
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)
FIXTURES = Path(__file__).parent / "fixtures/task5_connectors"


def _instance(definition, configuration, permissions):
    return ConnectorInstance(
        id=uuid4(), definition_key=definition.key,
        definition_version=definition.version, display_name=definition.display_name,
        status=ConnectorStatus.CONNECTED, enabled_permissions=permissions,
        configuration=configuration, created_at=NOW, updated_at=NOW,
    )


def test_known_ai_export_fixtures_preserve_roles_turns_and_source_pointers():
    chatgpt = json.loads((FIXTURES / "chatgpt-conversations.json").read_text(encoding="utf-8"))
    claude = json.loads((FIXTURES / "claude-conversations.json").read_text(encoding="utf-8"))
    service, turns = parse_ai_export(chatgpt)
    assert service == "chatgpt"
    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    assert all(turn["conversation_id"] and turn["turn_id"] and turn["source_pointer"].startswith("/") for turn in turns)
    service, turns = parse_ai_export(claude)
    assert service == "claude"
    assert [turn["role"] for turn in turns] == ["system", "user", "assistant"]


@pytest.mark.asyncio
async def test_ai_snapshot_connector_canonical_evidence_roles_and_restart(tmp_path, migrated_database):
    export = tmp_path / "conversations.json"
    shutil.copyfile(FIXTURES / "chatgpt-conversations.json", export)
    url, _, _ = migrated_database
    client = PostgresClient(url)
    repository = ConnectorRepository(client)
    await repository.declare_definition(AI_CONVERSATION_DEFINITION)
    instance = await repository.create_instance(
        AI_CONVERSATION_DEFINITION, display_name="AI export",
        enabled_permissions=("conversations.read",),
        configuration={"paths": [str(export)], "service": "auto"},
        status=ConnectorStatus.CONNECTED,
    )
    registry = ConnectorRegistry()
    registry.register(AI_CONVERSATION_DEFINITION, AIConversationSnapshotConnector)
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,status,pipeline_version,started_at) VALUES('connector_sync','running','task5-ai',NOW()) RETURNING id"
        )
    finally:
        await connection.close()
    runtime = ConnectorRuntime(
        registry, repository,
        ConnectorIngestionBridge(client, roots=StorageRoots.from_base(tmp_path / "ai-data")),
    )
    result = await runtime.run(instance.id, run_id)
    assert result.status is SyncRunStatus.COMPLETED
    assert result.artefacts_discovered == 3 and result.events_produced == 2
    restarted = await runtime.run(instance.id, run_id)
    assert restarted.artefacts_discovered == 0

    connection = await asyncpg.connect(url)
    try:
        counts = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM connector_raw_records WHERE connector_instance_id=$1) raw_records,
              (SELECT COUNT(*) FROM source_artifacts sa JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.metadata->>'connector_instance_id'=$2) artifacts,
              (SELECT COUNT(*) FROM source_artifacts sa JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.metadata->>'connector_instance_id'=$2 AND sa.parent_artifact_id IS NOT NULL) child_turns""",
            instance.id, str(instance.id),
        )
        assert dict(counts) == {"raw_records": 3, "artifacts": 3, "child_turns": 2}
        paths = [row["storage_uri"] for row in await connection.fetch(
            "SELECT storage_uri FROM event_partitions WHERE analysis_run_id=$1 AND schema_version='activity-event-v1'", run_id,
        )]
    finally:
        await connection.close()
    events = tuple(load_activity_event_partitions(paths))
    roles = {event.object_value["role"]: classify_event(event) for event in events}
    assert roles["user"].signal_class is SignalClass.ACTIVE_INVESTIGATION
    assert roles["user"].interest_contributing
    assert roles["assistant"].signal_class is SignalClass.AMBIENT_EXPOSURE
    assert not roles["assistant"].interest_contributing
    await client.close()


def test_photo_modes_and_scoped_filesystem_detection(tmp_path):
    root = tmp_path / "selected-root"; root.mkdir()
    image_path = root / "photo.png"
    Image.new("RGB", (4, 4), color=(12, 34, 56)).save(image_path)
    sidecar_path = root / "photo.png.json"
    sidecar_path.write_text((FIXTURES / "photo-sidecar.json").read_text(encoding="utf-8"), encoding="utf-8")
    hidden = root / "private"; hidden.mkdir(); (hidden / "secret.txt").write_text("secret", encoding="utf-8")

    metadata_instance = _instance(
        PHOTO_FOLDER_DEFINITION,
        {"roots": [str(root)], "mode": "metadata_only", "include": ["*.png", "*.png.json"], "exclude": []},
        ("media.metadata",),
    )
    metadata_batch = FolderConnector(metadata_instance).acquire(SimpleNamespace(cursor=None))
    assert len(metadata_batch.records) == 2
    media = next(record for record in metadata_batch.records if record.data_class == "photo.media")
    sidecar = next(record for record in metadata_batch.records if record.data_class == "photo.media_sidecar")
    assert media.required_permissions == ("media.metadata",)
    assert media.source_metadata["requested_tasks"] == []
    assert sidecar.source_metadata["sidecar_for"] == "photo.png"

    visual_instance = _instance(
        PHOTO_FOLDER_DEFINITION,
        {"roots": [str(root)], "mode": "selected_visual_analysis", "visual_analysis_paths": ["*.png"], "include": ["*.png"], "exclude": []},
        ("media.metadata", "media.visual_analysis"),
    )
    visual = FolderConnector(visual_instance).acquire(SimpleNamespace(cursor=None)).records[0]
    assert "media.visual_analysis" in visual.required_permissions
    assert visual.source_metadata["requested_tasks"] == ["image.caption"]


@pytest.mark.asyncio
async def test_filesystem_create_modify_remove_preserves_historical_evidence(tmp_path, migrated_database):
    root = tmp_path / "selected"; root.mkdir()
    file = root / "notes.txt"; file.write_text("version one", encoding="utf-8")
    url, _, _ = migrated_database
    client = PostgresClient(url); repository = ConnectorRepository(client)
    await repository.declare_definition(FILESYSTEM_DEFINITION)
    instance = await repository.create_instance(
        FILESYSTEM_DEFINITION, display_name="Selected files",
        enabled_permissions=("files.read",),
        configuration={"roots": [str(root)], "include": ["*.txt"], "exclude": ["private/*"], "max_size": 1024},
        status=ConnectorStatus.CONNECTED,
    )
    registry = ConnectorRegistry(); registry.register(FILESYSTEM_DEFINITION, FolderConnector)
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,status,pipeline_version,started_at) VALUES('connector_sync','running','task5-files',NOW()) RETURNING id"
        )
    finally:
        await connection.close()
    runtime = ConnectorRuntime(registry, repository, ConnectorIngestionBridge(client, roots=StorageRoots.from_base(tmp_path / "file-data")))
    created = await runtime.run(instance.id, run_id)
    assert created.artefacts_discovered == 1 and created.events_produced == 1
    file.write_text("version two", encoding="utf-8")
    modified = await runtime.run(instance.id, run_id)
    assert modified.artefacts_discovered == 1 and modified.events_produced == 1
    file.unlink()
    removed = await runtime.run(instance.id, run_id)
    assert removed.artefacts_discovered == 1 and removed.events_produced == 1
    assert removed.cursor_after == {"files": {}}

    connection = await asyncpg.connect(url)
    try:
        counts = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM connector_raw_records WHERE connector_instance_id=$1) raw_records,
              (SELECT COUNT(*) FROM source_artifacts sa JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.metadata->>'connector_instance_id'=$2) artifacts""",
            instance.id, str(instance.id),
        )
        # Both file versions and the removal observation remain immutable.
        assert dict(counts) == {"raw_records": 3, "artifacts": 3}
    finally:
        await connection.close(); await client.close()
