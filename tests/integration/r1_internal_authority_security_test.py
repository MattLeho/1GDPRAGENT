"""Hermetic adversarial checks for the intelligence service's signed authority.

No application, database, model provider, or external service is started by this suite.
"""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[2]
INTELLIGENCE = ROOT / "intelligence"
if str(INTELLIGENCE) not in sys.path:
    sys.path.insert(0, str(INTELLIGENCE))

from api import security  # noqa: E402


SECRET = "r1-hermetic-internal-authority-key"
PROFILE = UUID("2d495690-80f4-45a6-973e-6f5a8f98ee12")
NOW = 1_800_000_000


def settings(secret: str = SECRET):
    return SimpleNamespace(
        internal_api_key=secret,
        internal_authority_clock_skew_seconds=60,
        internal_authority_replay_limit=100,
    )


def signed_headers(*, nonce: str, method: str = "GET", path: str = "/insights/evidence/a", query: str = ""):
    payload = security.canonical_payload(
        version="v1", timestamp=NOW, nonce=nonce, method=method,
        path=path, query=query, profile_id=PROFILE,
    )
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {
        "content-type": "application/json",
        "x-gdpr-content-sha256": hashlib.sha256(b"").hexdigest(),
        "x-gdpr-internal-version": "v1",
        "x-gdpr-internal-timestamp": str(NOW),
        "x-gdpr-internal-nonce": nonce,
        "x-gdpr-profile-id": str(PROFILE),
        "x-gdpr-internal-key": signature,
    }


def request(*, headers: dict[str, str] | None = None, method: str = "GET", path: str = "/insights/evidence/a", query: str = ""):
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({
        "type": "http", "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": query.encode(), "headers": raw_headers,
        "client": ("127.0.0.1", 1), "server": ("intelligence", 8000),
    })


@pytest.fixture(autouse=True)
def isolated_authority(monkeypatch):
    security.reset_replay_window_for_tests()
    monkeypatch.setattr(security, "get_settings", lambda: settings())


def assert_http(call, status: int, phrase: str):
    with pytest.raises(HTTPException) as caught:
        call()
    assert caught.value.status_code == status
    assert phrase in str(caught.value.detail).lower()


def test_missing_internal_authority_is_rejected():
    assert_http(lambda: security.verify_internal_request(request(), now=NOW), 401, "complete")


def test_tampered_signature_is_rejected():
    headers = signed_headers(nonce="r1_tampered_signature_nonce")
    headers["x-gdpr-internal-key"] = "0" * 64
    assert_http(lambda: security.verify_internal_request(request(headers=headers), now=NOW), 401, "signature")


def test_signature_is_bound_to_method_path_query_and_profile():
    headers = signed_headers(nonce="r1_method_binding_nonce")
    assert_http(
        lambda: security.verify_internal_request(request(headers=headers, method="POST"), now=NOW),
        401, "signature",
    )


def test_stale_and_future_authority_are_rejected():
    for current in (NOW + 61, NOW - 61):
        headers = signed_headers(nonce=f"r1_time_nonce_{current}")
        assert_http(lambda: security.verify_internal_request(request(headers=headers), now=current), 401, "expired")


def test_replayed_authority_is_rejected_after_first_acceptance():
    headers = signed_headers(nonce="r1_replay_nonce_unique_001")
    first = security.verify_internal_request(request(headers=headers), now=NOW)
    assert first.profile_id == PROFILE
    assert_http(lambda: security.verify_internal_request(request(headers=headers), now=NOW), 409, "replay")


def test_verified_profile_is_the_only_profile_authority():
    headers = signed_headers(nonce="r1_profile_authority_nonce_001")
    authority_request = request(headers=headers)
    security.verify_internal_request(authority_request, now=NOW)
    assert security.require_profile_id(authority_request) == PROFILE


def test_missing_internal_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: settings(""))
    headers = signed_headers(nonce="r1_missing_secret_nonce_001")
    assert_http(lambda: security.verify_internal_request(request(headers=headers), now=NOW), 503, "not configured")
