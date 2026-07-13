"""Incremental, read-only IMAP SourceConnector with scoped payloads."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from enum import Enum
import hashlib
import imaplib
import re
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from .credentials import CredentialStore
from .definitions import IMAP_EMAIL_DEFINITION
from .models import ConnectorInstance, ConnectorRawRecord
from .registry import ConnectorSyncBatch, ConnectorSyncRequest
from .signatures import canonical_json, connector_record_signature


class EmailScope(str, Enum):
    METADATA_ONLY = "metadata_only"
    HEADERS_AND_SUBJECT = "headers_and_subject"
    TEXT_BODY = "text_body"
    FULL_MESSAGE = "full_message"


class IMAPConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    host: str = Field(min_length=1)
    port: int = Field(default=993, ge=1, le=65535)
    username: str = Field(min_length=1)
    scope: EmailScope = EmailScope.METADATA_ONLY
    mailboxes: tuple[str, ...] = ("INBOX",)
    sent_mailboxes: tuple[str, ...] = ("Sent", "Sent Mail", "[Gmail]/Sent Mail")
    trash_mailbox: str = "Trash"
    batch_size: int = Field(default=250, ge=1, le=500)


@dataclass(frozen=True, slots=True)
class IMAPFetchedMessage:
    mailbox: str
    uidvalidity: str
    uid: int
    flags: tuple[str, ...]
    raw: bytes


_UID = re.compile(rb"\bUID\s+(\d+)", re.I)
_FLAGS = re.compile(rb"\bFLAGS\s+\(([^)]*)\)", re.I)
_RELEVANT_HEADERS = (
    "Message-ID", "References", "In-Reply-To", "From", "Sender", "Reply-To",
    "To", "Cc", "Bcc", "Date", "Subject", "List-Unsubscribe", "List-Id",
    "Precedence", "Auto-Submitted", "X-Auto-Response-Suppress",
)


class IMAPSourceConnector:
    definition = IMAP_EMAIL_DEFINITION

    def __init__(
        self, instance: ConnectorInstance, *, credential_store: CredentialStore | None = None,
        client_factory: Callable[..., Any] = imaplib.IMAP4_SSL,
    ) -> None:
        self.instance = instance
        self.config = IMAPConfiguration.model_validate(instance.configuration)
        self.credentials = credential_store or CredentialStore()
        self.client_factory = client_factory

    async def acquire(self, request: ConnectorSyncRequest) -> ConnectorSyncBatch:
        password = await self.credentials.load(self.instance.credential_id)
        return await asyncio.to_thread(self._acquire_blocking, request, password)

    def _acquire_blocking(self, request: ConnectorSyncRequest, password: str) -> ConnectorSyncBatch:
        client = self.client_factory(self.config.host, self.config.port)
        try:
            status, _ = client.login(self.config.username, password)
            if status != "OK":
                raise RuntimeError("IMAP authentication failed")
            before = dict(request.cursor.position) if request.cursor else {}
            mailbox_state = dict(before.get("mailboxes") or {})
            records: list[ConnectorRawRecord] = []
            after = {"mailboxes": dict(mailbox_state)}
            remaining = self.config.batch_size
            for mailbox in self.config.mailboxes:
                if remaining <= 0:
                    break
                fetched, state = self._mailbox(client, mailbox, mailbox_state.get(mailbox, {}), remaining)
                for item in fetched:
                    records.append(self._record(item))
                after["mailboxes"][mailbox] = state
                remaining -= len(fetched)
            watermark = max(
                (f"{name}:{state.get('uidvalidity')}:{state.get('last_uid', 0)}" for name, state in after["mailboxes"].items()),
                default=None,
            )
            return ConnectorSyncBatch(
                records=tuple(records), cursor_position=after,
                source_watermark=watermark,
            )
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _mailbox(self, client, mailbox: str, previous: dict[str, Any], limit: int):
        # readonly=True plus BODY.PEEK[] ensures acquisition does not mutate Seen.
        status, _ = client.select(mailbox, readonly=True)
        if status != "OK":
            raise RuntimeError(f"cannot select IMAP mailbox {mailbox!r}")
        response = client.response("UIDVALIDITY")
        raw_validity = response[1][0] if response and response[1] else b"unknown"
        uidvalidity = raw_validity.decode() if isinstance(raw_validity, bytes) else str(raw_validity)
        last_uid = int(previous.get("last_uid", 0)) if previous.get("uidvalidity") == uidvalidity else 0
        status, values = client.uid("search", None, f"UID {last_uid + 1}:*")
        if status != "OK":
            raise RuntimeError(f"cannot search IMAP mailbox {mailbox!r}")
        uids = [int(value) for value in (values[0].split() if values and values[0] else ())][:limit]
        fetched: list[IMAPFetchedMessage] = []
        for uid in uids:
            status, parts = client.uid("fetch", str(uid), "(UID FLAGS INTERNALDATE RFC822.SIZE BODY.PEEK[])")
            if status != "OK":
                raise RuntimeError(f"cannot fetch IMAP UID {uid}")
            header = raw = None
            for part in parts or ():
                if isinstance(part, tuple) and len(part) == 2:
                    header, raw = part
                    break
            if not isinstance(header, bytes) or not isinstance(raw, bytes):
                raise RuntimeError(f"IMAP UID {uid} returned no RFC message payload")
            uid_match = _UID.search(header)
            flags_match = _FLAGS.search(header)
            actual_uid = int(uid_match.group(1)) if uid_match else uid
            flags = tuple(flags_match.group(1).decode(errors="replace").split()) if flags_match else ()
            fetched.append(IMAPFetchedMessage(mailbox, uidvalidity, actual_uid, flags, raw))
        new_last = max([last_uid, *(item.uid for item in fetched)])
        return fetched, {"uidvalidity": uidvalidity, "last_uid": new_last}

    def _record(self, fetched: IMAPFetchedMessage) -> ConnectorRawRecord:
        message = BytesParser(policy=policy.default).parsebytes(fetched.raw)
        occurred = _message_date(message)
        direction = "outbound" if fetched.mailbox.casefold() in {value.casefold() for value in self.config.sent_mailboxes} else "inbound"
        document = _scoped_document(message, fetched, self.config.scope)
        if self.config.scope is EmailScope.FULL_MESSAGE:
            payload, media_type = fetched.raw, "message/rfc822"
        else:
            payload, media_type = canonical_json(document), "application/json"
        metadata = {
            "mailbox": fetched.mailbox, "uid": fetched.uid,
            "uidvalidity": fetched.uidvalidity, "flags": list(fetched.flags),
            "message_id": str(message.get("Message-ID") or ""),
            "direction": direction, "scope": self.config.scope.value,
            "account": self.config.username,
        }
        flags_hash = hashlib.sha256("\0".join(sorted(fetched.flags)).encode()).hexdigest()[:12]
        version = f"{fetched.uidvalidity}:{flags_hash}"
        source_id = f"{self.instance.account_key}:{fetched.mailbox}:{fetched.uidvalidity}:{fetched.uid}"
        permissions = ["mail.metadata"]
        if self.config.scope is not EmailScope.METADATA_ONLY:
            permissions.append("mail.headers")
        if self.config.scope in {EmailScope.TEXT_BODY, EmailScope.FULL_MESSAGE}:
            permissions.append("mail.body")
        if self.config.scope is EmailScope.FULL_MESSAGE:
            permissions.append("mail.attachments")
        signature = connector_record_signature(
            source_record_id=source_id, source_record_version=version,
            payload=payload, data_class="email.message", occurred_at=occurred,
            media_type=media_type, source_metadata=metadata,
        )
        return ConnectorRawRecord(
            connector_instance_id=self.instance.id, source_record_id=source_id,
            source_record_version=version, record_signature=signature,
            data_class="email.message", occurred_at=occurred,
            observed_at=datetime.now(timezone.utc), media_type=media_type,
            payload=payload, source_metadata=metadata,
            required_permissions=tuple(permissions),
        )


def _message_date(message: Message) -> datetime | None:
    try:
        value = parsedate_to_datetime(str(message.get("Date") or ""))
        if value and value.tzinfo is None:
            return None
        return value
    except (TypeError, ValueError, OverflowError):
        return None


def _attachment_metadata(message: Message) -> list[dict[str, Any]]:
    result = []
    for part in message.walk():
        if part.is_multipart() or not part.get_filename():
            continue
        payload = part.get_payload(decode=True) or b""
        result.append({
            "file_name": part.get_filename(), "content_type": part.get_content_type(),
            "content_disposition": part.get_content_disposition(), "byte_size": len(payload),
            "content_id": part.get("Content-ID"),
        })
    return result


def _text_body(message: Message) -> str | None:
    if message.is_multipart():
        candidates = [part for part in message.walk() if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment"]
        if not candidates:
            return None
        part = candidates[0]
    else:
        part = message
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _scoped_document(message: Message, fetched: IMAPFetchedMessage, scope: EmailScope) -> dict[str, Any]:
    addresses = {
        name.casefold().replace("-", "_"): [address for _, address in getaddresses(message.get_all(name, []))]
        for name in ("From", "To", "Cc", "Bcc", "Reply-To")
    }
    result: dict[str, Any] = {
        "mailbox": fetched.mailbox, "uid": fetched.uid, "uidvalidity": fetched.uidvalidity,
        "message_id": str(message.get("Message-ID") or ""), "date": str(message.get("Date") or ""),
        "participants": addresses, "attachments": _attachment_metadata(message),
    }
    if scope is not EmailScope.METADATA_ONLY:
        result["subject"] = str(message.get("Subject") or "")
        result["headers"] = {
            name: str(message.get(name)) for name in _RELEVANT_HEADERS if message.get(name) is not None
        }
    if scope is EmailScope.TEXT_BODY:
        result["text_body"] = _text_body(message)
    return result
