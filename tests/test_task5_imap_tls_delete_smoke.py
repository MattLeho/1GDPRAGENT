from __future__ import annotations

from datetime import datetime, timedelta, timezone
import imaplib
import ipaddress
import socket
import ssl
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from connectors.imap_delete import IMAPTrashDeletion
from connectors.models import ConnectorInstance, ConnectorStatus


def _certificate(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]), critical=False).sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "imap-cert.pem", tmp_path / "imap-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    return cert_path, key_path


class TLSTestIMAP:
    def __init__(self, cert, key):
        self.commands = []
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0)); self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); self.context.load_cert_chain(cert, key)
        self.thread = threading.Thread(target=self._serve, daemon=True); self.thread.start()

    def _serve(self):
        raw, _ = self.server.accept()
        with self.context.wrap_socket(raw, server_side=True) as client:
            stream = client.makefile("rwb"); stream.write(b"* OK deterministic test IMAP ready\r\n"); stream.flush()
            while line := stream.readline():
                command = line.decode(errors="replace").rstrip(); self.commands.append(command)
                parts = command.split(); tag = parts[0]; verb = parts[1].upper() if len(parts) > 1 else ""
                if verb == "LOGIN": response = f"{tag} OK LOGIN completed\r\n"
                elif verb == "CAPABILITY": response = f"* CAPABILITY IMAP4rev1 MOVE\r\n{tag} OK CAPABILITY completed\r\n"
                elif verb == "SELECT": response = f"* 1 EXISTS\r\n* OK [UIDVALIDITY 777] valid\r\n{tag} OK [READ-WRITE] SELECT completed\r\n"
                elif verb == "UID": response = f"* OK [COPYUID 777 42 99] moved\r\n{tag} OK MOVE completed\r\n"
                elif verb == "LOGOUT": response = f"* BYE closing\r\n{tag} OK LOGOUT completed\r\n"
                else: response = f"{tag} BAD unsupported\r\n"
                stream.write(response.encode()); stream.flush()
                if verb == "LOGOUT": break

    def close(self):
        self.thread.join(timeout=5); self.server.close()


@pytest.mark.asyncio
async def test_real_tls_imap_move_to_trash_never_expunge(tmp_path):
    cert, key = _certificate(tmp_path); server = TLSTestIMAP(cert, key)
    context = ssl.create_default_context(cafile=str(cert)); context.check_hostname = True
    instance = ConnectorInstance(
        id=uuid4(), definition_key="email.imap", definition_version="1",
        account_key="user@example.test", display_name="TLS smoke", status=ConnectorStatus.CONNECTED,
        enabled_permissions=("mail.metadata",),
        configuration={"host":"localhost","port":server.port,"username":"user@example.test","scope":"metadata_only","trash_mailbox":"Trash"},
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    adapter = IMAPTrashDeletion(
        credential_store=SimpleNamespace(load=AsyncMock(return_value="secret")),
        client_factory=lambda host, port: imaplib.IMAP4_SSL(host, port, ssl_context=context),
    )
    try:
        result = await adapter.execute(instance, {"mailbox":"INBOX","uid":42,"uidvalidity":"777"})
    finally:
        server.close()
    assert result.provider_action == "move_to_trash" and result.reversible
    transcript = "\n".join(server.commands).upper()
    assert "UID MOVE 42" in transcript
    assert "EXPUNGE" not in transcript and " STORE " not in transcript
