from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest

from connectors.bridge import ConnectorIngestionBridge
from connectors.credentials import decrypt_task2_credential
from connectors.definitions import IMAP_EMAIL_DEFINITION
from connectors.imap import IMAPSourceConnector
from connectors.models import ConnectorInstance, ConnectorStatus, SyncRunKind, SyncRunStatus
from connectors.registry import ConnectorRegistry
from connectors.repository import ConnectorRepository
from connectors.runtime import ConnectorRuntime
from db.postgres import PostgresClient
from ingestion.storage import StorageRoots
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, 14, 0, tzinfo=timezone.utc)


def _message() -> bytes:
    message = EmailMessage()
    message["Message-ID"] = "<reply-42@example.test>"
    message["In-Reply-To"] = "<request-1@gdpr-agent.local>"
    message["References"] = "<request-1@gdpr-agent.local>"
    message["Date"] = "Sat, 09 Mar 2024 16:00:00 +0000"
    message["From"] = "Controller <privacy@example.test>"
    message["To"] = "User <user@example.test>"
    message["Subject"] = "Re: access request"
    message["List-Id"] = "controller-updates.example.test"
    message.set_content("Your access-request export is attached.")
    message.add_attachment(b'{"records":[{"id":1}]}', maintype="application", subtype="json", filename="export.json")
    return message.as_bytes()


class FakeIMAP:
    messages = {42: _message()}

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.commands = []
        self.selected = None

    def login(self, username, password):
        self.commands.append(("login", username, password))
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=False):
        self.commands.append(("select", mailbox, readonly))
        self.selected = mailbox
        return "OK", [str(len(self.messages)).encode()]

    def response(self, name):
        return name, [b"777"]

    def uid(self, command, *args):
        self.commands.append(("uid", command, *args))
        if command.casefold() == "search":
            start = int(str(args[-1]).split()[1].split(":")[0])
            return "OK", [b" ".join(str(uid).encode() for uid in self.messages if uid >= start)]
        uid = int(args[0])
        raw = self.messages[uid]
        return "OK", [(f"1 (UID {uid} FLAGS (\\Seen) RFC822.SIZE {len(raw)} BODY[] {{{len(raw)}}}".encode(), raw), b")"]

    def logout(self):
        self.commands.append(("logout",))
        return "BYE", [b"logout"]


def _instance(*, scope="full_message", enabled=None):
    enabled = enabled or ("mail.metadata", "mail.headers", "mail.body", "mail.attachments")
    return ConnectorInstance(
        id=uuid4(), definition_key=IMAP_EMAIL_DEFINITION.key,
        definition_version=IMAP_EMAIL_DEFINITION.version,
        account_key="user@example.test", display_name="Test IMAP",
        status=ConnectorStatus.CONNECTED, enabled_permissions=enabled,
        configuration={
            "host": "imap.example.test", "port": 993, "username": "user@example.test",
            "scope": scope, "mailboxes": ["INBOX"], "batch_size": 10,
        },
        created_at=NOW, updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_imap_is_read_only_incremental_scoped_and_signature_stable():
    fake = FakeIMAP("imap.example.test", 993)
    instance = _instance(scope="metadata_only", enabled=("mail.metadata",))
    connector = IMAPSourceConnector(
        instance, credential_store=SimpleNamespace(load=AsyncMock(return_value="app-password")),
        client_factory=lambda *_: fake,
    )
    request = SimpleNamespace(cursor=None)
    first = await connector.acquire(request)
    assert len(first.records) == 1
    record = first.records[0]
    assert record.required_permissions == ("mail.metadata",)
    assert record.media_type == "application/json"
    assert b"access request" not in record.payload and b"attached" not in record.payload
    assert b"export.json" in record.payload  # attachment lineage metadata, not content
    assert first.cursor_position == {"mailboxes": {"INBOX": {"uidvalidity": "777", "last_uid": 42}}}
    assert ("select", "INBOX", True) in fake.commands
    assert any("BODY.PEEK[]" in str(command) for command in fake.commands)
    assert not any("store" in str(command).casefold() for command in fake.commands)

    cursor = SimpleNamespace(position=first.cursor_position)
    second = await connector.acquire(SimpleNamespace(cursor=cursor))
    assert second.records == ()


@pytest.mark.asyncio
async def test_full_imap_message_flows_through_task3a_events_and_restart_cursor(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client = PostgresClient(url)
    repository = ConnectorRepository(client)
    await repository.declare_definition(IMAP_EMAIL_DEFINITION)
    candidate = _instance()
    instance = await repository.create_instance(
        IMAP_EMAIL_DEFINITION, display_name=candidate.display_name,
        enabled_permissions=candidate.enabled_permissions, account_key=candidate.account_key,
        configuration=candidate.configuration, status=ConnectorStatus.CONNECTED,
    )
    fake = FakeIMAP("imap.example.test", 993)
    registry = ConnectorRegistry()
    registry.register(
        IMAP_EMAIL_DEFINITION,
        lambda persisted: IMAPSourceConnector(
            persisted, credential_store=SimpleNamespace(load=AsyncMock(return_value="app-password")),
            client_factory=lambda *_: fake,
        ),
    )
    connection = await asyncpg.connect(url)
    try:
        analysis_run_id = await connection.fetchval(
            """INSERT INTO analysis_runs(run_type,status,pipeline_version,started_at)
               VALUES('connector_sync','running','task5-imap-v1',NOW()) RETURNING id"""
        )
    finally:
        await connection.close()
    runtime = ConnectorRuntime(
        registry, repository,
        ConnectorIngestionBridge(client, roots=StorageRoots.from_base(tmp_path / "imap-data")),
    )
    result = await runtime.run(instance.id, analysis_run_id, kind=SyncRunKind.SYNC)
    assert result.status is SyncRunStatus.COMPLETED
    assert result.artefacts_discovered == 1
    assert result.events_produced == 2  # evidence-supported reply plus Seen candidate
    assert result.cursor_after["mailboxes"]["INBOX"]["last_uid"] == 42

    restarted = await runtime.run(instance.id, analysis_run_id, kind=SyncRunKind.SYNC)
    assert restarted.cursor_before == result.cursor_after
    assert restarted.artefacts_discovered == 0

    connection = await asyncpg.connect(url)
    try:
        counts = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM connector_raw_records WHERE connector_instance_id=$1) raw_records,
              (SELECT COUNT(*) FROM source_artifacts sa JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.metadata->>'connector_instance_id'=$2) artifacts,
              (SELECT COUNT(*) FROM source_artifacts sa JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.metadata->>'connector_instance_id'=$2 AND sa.parent_artifact_id IS NOT NULL) attachments,
              (SELECT COALESCE(SUM(row_count),0) FROM event_partitions ep
               WHERE ep.analysis_run_id=$3 AND ep.partition_key LIKE 'events/connector-%') events""",
            instance.id, str(instance.id), analysis_run_id,
        )
        assert dict(counts) == {"raw_records": 1, "artifacts": 2, "attachments": 1, "events": 2}
    finally:
        await connection.close()
        await client.close()
