"""Server-only access to Task 2 AES-GCM connector credentials."""
from __future__ import annotations

import base64
import hashlib
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from db.postgres import PostgresClient, get_postgres_client


class CredentialUnavailable(RuntimeError):
    pass


def _decode_base64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decrypt_task2_credential(ciphertext: str) -> str:
    try:
        version, iv_value, tag_value, data_value = ciphertext.split(":")
    except ValueError as exc:
        raise CredentialUnavailable("unsupported connector credential encoding") from exc
    if version != "aes-256-gcm-v1":
        raise CredentialUnavailable("unsupported connector credential encoding")
    secret = os.getenv("CREDENTIALS_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")
    if not secret:
        if os.getenv("NODE_ENV") == "production" or os.getenv("ENVIRONMENT") == "production":
            raise CredentialUnavailable("credential encryption key is not configured")
        secret = "gdpr-agent-local-development-credential-key"
    key = hashlib.sha256(secret.encode()).digest()
    try:
        plaintext = AESGCM(key).decrypt(
            _decode_base64url(iv_value),
            _decode_base64url(data_value) + _decode_base64url(tag_value),
            None,
        )
        return plaintext.decode("utf-8")
    except Exception as exc:
        raise CredentialUnavailable("connector credential cannot be decrypted") from exc


class CredentialStore:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def load(self, credential_id: UUID | None) -> str:
        if credential_id is None:
            raise CredentialUnavailable("connector credential is missing")
        rows = await self.postgres.execute(
            """SELECT secret_ciphertext,needs_reentry FROM connector_credentials
               WHERE id=$1""", credential_id,
        )
        if not rows or rows[0]["needs_reentry"] or not rows[0]["secret_ciphertext"]:
            raise CredentialUnavailable("connector credential is missing or requires re-entry")
        return decrypt_task2_credential(rows[0]["secret_ciphertext"])
