from __future__ import annotations

from pathlib import Path
import subprocess
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import asyncpg
import pytest

from test_task1_database_integration import migrated_database
from connectors.credentials import decrypt_task2_credential


@pytest.mark.asyncio
async def test_email_transport_requires_review_and_keeps_body_ciphertext(migrated_database):
    url, _, _ = migrated_database
    connection = await asyncpg.connect(url)
    try:
        row = await connection.fetchrow(
            """INSERT INTO email_transport_drafts(recipient,subject,body_ciphertext)
               VALUES('privacy@example.test','Access request','aes-256-gcm-v1:iv:tag:ciphertext')
               RETURNING *"""
        )
        assert row["status"] == "draft"
        assert row["body_ciphertext"].startswith("aes-256-gcm-v1:")
        with pytest.raises(asyncpg.CheckViolationError):
            await connection.execute(
                """UPDATE email_transport_drafts SET status='sent',sent_at=NOW(),
                   transport_message_id='<forged@example.test>' WHERE id=$1""", row["id"],
            )
        reviewed = await connection.fetchrow(
            """UPDATE email_transport_drafts SET status='reviewed',reviewed_by='user',reviewed_at=NOW()
               WHERE id=$1 RETURNING *""", row["id"],
        )
        assert reviewed["status"] == "reviewed" and reviewed["reviewed_at"]
    finally:
        await connection.close()


def test_built_in_transport_is_independent_of_n8n_and_records_state_machine():
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend/lib/connectors/email.ts").read_text(encoding="utf-8")
    workflow = (root / "frontend/lib/workflows/registry.ts").read_text(encoding="utf-8")
    assert "createBuiltInEmailDraft" in source
    assert "reviewBuiltInEmailDraft" in source
    assert "sendReviewedBuiltInEmail" in source
    assert "status='reviewed'" in source and "status='sent'" in source
    assert "callN8NWebhook" not in source
    assert "frontend:built-in-email-transport" in workflow
    assert "sendEmail" in workflow  # optional adapter remains registered separately


def test_built_in_smtp_transport_over_real_local_tls(tmp_path):
    root = Path(__file__).resolve().parents[1]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_path, cert_path = tmp_path / "key.pem", tmp_path / "cert.pem"
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    node = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    tsc = root / "frontend/node_modules/typescript/bin/tsc"
    build = tmp_path / "build"
    subprocess.run([
        str(node), str(tsc), str(root / "frontend/lib/connectors/smtp-transport.ts"),
        "--outDir", str(build), "--module", "commonjs", "--target", "ES2022",
        "--esModuleInterop", "--types", "node", "--typeRoots",
        str(root / "frontend/node_modules/@types"), "--skipLibCheck",
    ], cwd=root, check=True, capture_output=True, text=True)
    result = subprocess.run([
        str(node), str(root / "tests/fixtures/task5_smtp_smoke.cjs"),
        str(build / "smtp-transport.js"), str(key_path), str(cert_path),
    ], cwd=root, check=True, capture_output=True, text=True, timeout=30)
    assert '"tls":true' in result.stdout and '"accepted":true' in result.stdout


def test_python_imap_credential_reader_matches_frontend_encryption(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    node = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    tsc = root / "frontend/node_modules/typescript/bin/tsc"
    build = tmp_path / "credential-build"
    subprocess.run([
        str(node), str(tsc), str(root / "frontend/lib/secure-credentials.ts"),
        "--outDir", str(build), "--module", "commonjs", "--target", "ES2022",
        "--esModuleInterop", "--types", "node", "--typeRoots",
        str(root / "frontend/node_modules/@types"), "--skipLibCheck",
    ], cwd=root, check=True, capture_output=True, text=True)
    environment = dict(os.environ, CREDENTIALS_ENCRYPTION_KEY="task5-cross-runtime-key")
    result = subprocess.run([
        str(node), "-e",
        f"console.log(require({str(build / 'secure-credentials.js')!r}).encryptCredential('imap-app-password'))",
    ], cwd=root, env=environment, check=True, capture_output=True, text=True)
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", "task5-cross-runtime-key")
    assert decrypt_task2_credential(result.stdout.strip()) == "imap-app-password"
