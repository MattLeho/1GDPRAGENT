"""Reversible IMAP source deletion implemented as UID MOVE to Trash only."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import imaplib
from typing import Any, Callable

from .credentials import CredentialStore
from .imap import IMAPConfiguration
from .models import ConnectorInstance


@dataclass(frozen=True, slots=True)
class ProviderDeleteResult:
    provider_action: str
    reversible: bool
    provider_response_id: str | None
    provider_status: str


class IMAPTrashDeletion:
    def __init__(
        self, *, credential_store: CredentialStore | None = None,
        client_factory: Callable[..., Any] = imaplib.IMAP4_SSL,
    ) -> None:
        self.credentials = credential_store or CredentialStore()
        self.client_factory = client_factory

    async def execute(self, instance: ConnectorInstance, source_metadata: dict[str, Any]) -> ProviderDeleteResult:
        password = await self.credentials.load(instance.credential_id)
        return await asyncio.to_thread(self._execute, instance, source_metadata, password)

    def _execute(self, instance, metadata, password):
        config = IMAPConfiguration.model_validate(instance.configuration)
        trash = str(instance.configuration.get("trash_mailbox") or "Trash")
        mailbox = str(metadata.get("mailbox") or "")
        uid = int(metadata.get("uid"))
        expected_validity = str(metadata.get("uidvalidity") or "")
        if not mailbox or not expected_validity:
            raise ValueError("source deletion requires mailbox, UID and UIDVALIDITY provenance")
        client = self.client_factory(config.host, config.port)
        try:
            if client.login(config.username, password)[0] != "OK":
                raise RuntimeError("IMAP authentication failed")
            status, capabilities = client.capability()
            values = b" ".join(capabilities or ()).upper() if status == "OK" else b""
            if b"MOVE" not in values.split():
                raise RuntimeError("IMAP provider does not advertise reversible MOVE capability")
            if client.select(mailbox, readonly=False)[0] != "OK":
                raise RuntimeError("source mailbox cannot be selected for Trash move")
            response = client.response("UIDVALIDITY")
            actual = response[1][0] if response and response[1] else b""
            actual = actual.decode() if isinstance(actual, bytes) else str(actual)
            if actual != expected_validity:
                raise RuntimeError("UIDVALIDITY changed; source deletion is refused")
            escaped_trash = '"' + trash.replace("\\", "\\\\").replace('"', '\\"') + '"'
            status, response = client.uid("MOVE", str(uid), escaped_trash)
            if status != "OK":
                raise RuntimeError("IMAP Trash move was not acknowledged")
            response_id = " ".join(
                value.decode(errors="replace") if isinstance(value, bytes) else str(value)
                for value in (response or ())
            ) or None
            return ProviderDeleteResult("move_to_trash", True, response_id, "moved_to_trash")
        finally:
            try:
                client.logout()
            except Exception:
                pass
