from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.connectors import _pairing_origin_allowed, validate_connector_configuration
from starlette.requests import Request


def test_imap_configuration_rejects_blank_runtime_fields():
    with pytest.raises(ValidationError):
        validate_connector_configuration("email.imap", {"host": "", "username": ""})


def test_filesystem_configuration_rejects_relative_root():
    with pytest.raises(ValidationError):
        validate_connector_configuration("filesystem.scoped", {"roots": ["relative/folder"]})


def test_ai_export_configuration_requires_an_absolute_path():
    with pytest.raises(ValidationError):
        validate_connector_configuration("ai.conversation.snapshot", {"paths": []})
    with pytest.raises(ValidationError):
        validate_connector_configuration("ai.conversation.snapshot", {"paths": ["export.json"]})


def test_known_configuration_is_normalized_without_secrets():
    result = validate_connector_configuration(
        "email.imap",
        {"host": "imap.example.test", "username": "person@example.test", "scope": "headers_and_subject"},
    )
    assert result["port"] == 993
    assert "password" not in result


def test_browser_pairing_accepts_the_live_local_frontend_port():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/connectors/browser/pairings",
        "headers": [(b"origin", b"http://localhost:3002")],
    })

    assert _pairing_origin_allowed(request) is True
