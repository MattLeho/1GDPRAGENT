from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
import time
import sys
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from api import security
from config import Settings


SECRET = "r1-test-internal-secret-with-sufficient-entropy"
PROFILE_ID = UUID("12345678-1234-4abc-8def-1234567890ab")


def _settings(secret: str = SECRET):
    return SimpleNamespace(
        internal_api_key=secret,
        internal_authority_clock_skew_seconds=60,
        internal_authority_replay_limit=100,
        redis_url="redis://shared-replay-test/0",
    )


def _signed_request(
    *, method: str = "GET", path: str = "/query/tools", query: str = "b=two&a=hello%20world",
    profile_id: UUID = PROFILE_ID, timestamp: int | None = None, nonce: str | None = None,
    signing_method: str | None = None, signing_path: str | None = None,
    signing_query: str | None = None, signing_profile: UUID | None = None,
) -> Request:
    timestamp = int(time.time()) if timestamp is None else timestamp
    nonce = nonce or f"nonce-{uuid4().hex}"
    payload = security.canonical_payload(
        version="v1", timestamp=timestamp, nonce=nonce, method=signing_method or method,
        path=signing_path or path, query=query if signing_query is None else signing_query,
        profile_id=signing_profile or profile_id,
    )
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    headers = {
        "content-type": "application/json",
        "x-gdpr-content-sha256": hashlib.sha256(b"").hexdigest(),
        "x-gdpr-internal-version": "v1",
        "x-gdpr-internal-timestamp": str(timestamp),
        "x-gdpr-internal-nonce": nonce,
        "x-gdpr-profile-id": str(profile_id),
        "x-gdpr-internal-key": signature,
    }
    scope = {
        "type": "http", "http_version": "1.1", "method": method,
        "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": query.encode(), "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234), "root_path": "",
        "headers": [(key.encode(), value.encode()) for key, value in headers.items()],
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def authority_settings(monkeypatch):
    monkeypatch.setattr(security, "get_settings", _settings)
    security.reset_replay_window_for_tests()


def test_valid_signature_exposes_verified_profile_and_canonicalizes_query():
    request = _signed_request(signing_query="a=hello+world&b=two")
    authority = security.verify_internal_request(request)
    assert authority.profile_id == PROFILE_ID
    assert security.require_profile_id(request) == PROFILE_ID


@pytest.mark.parametrize("header", [
    "x-gdpr-internal-key", "x-gdpr-internal-version", "x-gdpr-internal-timestamp",
    "x-gdpr-internal-nonce", "x-gdpr-profile-id",
    "x-gdpr-content-sha256",
])
def test_missing_authority_headers_fail_closed(header):
    request = _signed_request()
    request.scope["headers"] = [(key, value) for key, value in request.scope["headers"] if key.decode() != header]
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(request)
    assert error.value.status_code == 401


def test_missing_key_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: _settings(""))
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(_signed_request())
    assert error.value.status_code == 503


@pytest.mark.parametrize("header,value", [
    ("x-gdpr-profile-id", "not-a-uuid"),
    ("x-gdpr-internal-timestamp", "today"),
    ("x-gdpr-internal-version", "v2"),
    ("x-gdpr-internal-key", "not-a-signature"),
])
def test_malformed_authority_headers_fail_closed(header, value):
    request = _signed_request()
    request.scope["headers"] = [(key, value.encode() if key.decode() == header else old) for key, old in request.scope["headers"]]
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(request)
    assert error.value.status_code == 401


@pytest.mark.parametrize("kwargs", [
    {"method": "POST", "signing_method": "GET"},
    {"path": "/query", "signing_path": "/query/tools"},
    {"query": "a=changed", "signing_query": "a=original"},
    {"signing_profile": UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")},
])
def test_method_path_query_and_profile_tampering_is_rejected(kwargs):
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(_signed_request(**kwargs))
    assert error.value.status_code == 401


def test_exact_mutation_body_tampering_is_rejected_before_replay_acceptance():
    original=b'{"value":1}'
    request=_signed_request(method="POST")
    digest=hashlib.sha256(original).hexdigest()
    request.scope["headers"]=[
        (key, digest.encode() if key.decode()=="x-gdpr-content-sha256" else value)
        for key,value in request.scope["headers"]
    ]
    raw_headers={key.decode():value.decode() for key,value in request.scope["headers"]}
    nonce=raw_headers["x-gdpr-internal-nonce"]
    payload=security.canonical_payload(version="v1",timestamp=int(raw_headers["x-gdpr-internal-timestamp"]),nonce=nonce,method="POST",path="/query/tools",query="b=two&a=hello%20world",profile_id=PROFILE_ID,body_digest=digest)
    signature=hmac.new(SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
    request.scope["headers"]=[(key,signature.encode() if key.decode()=="x-gdpr-internal-key" else value) for key,value in request.scope["headers"]]
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(request,body=b'{"value":2}')
    assert error.value.status_code==401
    # A failed digest check must not burn the nonce; the authentic bytes still succeed.
    assert security.verify_internal_request(request,body=original).profile_id==PROFILE_ID


@pytest.mark.parametrize("offset", [-61, 61])
def test_expired_and_future_authority_are_rejected(offset):
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(_signed_request(timestamp=int(time.time()) + offset))
    assert error.value.status_code == 401


def test_replay_is_rejected_after_first_use():
    nonce = f"nonce-{uuid4().hex}"
    security.verify_internal_request(_signed_request(nonce=nonce))
    with pytest.raises(HTTPException) as error:
        security.verify_internal_request(_signed_request(nonce=nonce))
    assert error.value.status_code == 409


def test_redis_replay_store_is_atomic_across_verifier_instances_and_restart(monkeypatch):
    shared: set[str] = set()
    class FakeClient:
        def set(self, key, value, *, nx, ex):
            assert nx is True and ex >= 120
            if key in shared: return None
            shared.add(key); return True
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(from_url=lambda *args, **kwargs: FakeClient()))
    first = security._RedisReplayStore()
    restarted_worker = security._RedisReplayStore()
    nonce = f"nonce-{uuid4().hex}"
    assert first.accept(nonce, skew_seconds=60) is True
    assert restarted_worker.accept(nonce, skew_seconds=60) is False


def test_redis_replay_store_fails_closed_when_shared_store_is_unavailable(monkeypatch):
    def unavailable(*args, **kwargs): raise OSError("redis unavailable")
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(from_url=unavailable))
    with pytest.raises(HTTPException) as error:
        security._RedisReplayStore().accept(f"nonce-{uuid4().hex}", skew_seconds=60)
    assert error.value.status_code == 503


def test_shared_cross_runtime_canonical_url_vectors_and_malformed_escape_policy():
    root = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[2]
    vectors = json.loads((root / "frontend/tests/fixtures/r1_internal_authority_vectors.json").read_text(encoding="utf-8"))
    for vector in vectors:
        parsed = urlsplit(vector["target"])
        assert security.canonical_path(parsed.path) == vector["path"]
        assert security.canonical_query(parsed.query) == vector["query"]
    with pytest.raises(HTTPException):
        security.canonical_path("/bad/%ZZ")


def test_missing_production_secret_rejected_at_configuration_startup():
    with pytest.raises(ValidationError, match="INTERNAL_API_KEY is required in production"):
        Settings(environment="production", internal_api_key="")
    with pytest.raises(ValidationError, match="INTERNAL_API_KEY is required in production"):
        Settings(node_env="production", internal_api_key="")


def test_representative_service_routers_are_protected_without_authority(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", SECRET)
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    for method, path in (("POST", "/ingest"), ("GET", "/insights/overview"), ("POST", "/evidence/project")):
        response = client.request(method, path)
        assert response.status_code in {401, 503}, (method, path, response.text)
    assert client.get("/").status_code == 200


def test_fastapi_route_table_has_an_explicit_authority_policy():
    import inspect
    from fastapi.routing import APIRoute, _IncludedRouter
    from main import app

    routes = []
    for item in app.routes:
        routes.extend(item.original_router.routes if isinstance(item, _IncludedRouter) else [item])
    public = {("GET", "/"), ("GET", "/health"), ("GET", "/health/ready")}
    pairing = {("POST", "/connectors/browser/sync")}
    authenticated_stateless = {
        ("POST", "/onsit/crawl"), ("POST", "/onsit/enrich"), ("GET", "/onsit/enrichers"),
        ("GET", "/extract/health"), ("GET", "/execution/engines/{engine_id}/health"),
        ("POST", "/execution/invoke"), ("GET", "/bulk-ingestion/support"),
        ("POST", "/evidence/entity-key"),
    }
    classified = set()
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        dependency_names = {getattr(dependency.call, "__name__", "") for dependency in route.dependant.dependencies}
        endpoint_source = inspect.getsource(route.endpoint)
        for method in route.methods:
            key = (method, route.path)
            if key in public | pairing | authenticated_stateless:
                classified.add(key); continue
            assert (
                "require_profile_id" in dependency_names
                or "authorised_insight_request" in dependency_names
                or "require_profile_id(" in endpoint_source
            ), f"{key} is neither profile-consuming nor explicitly classified stateless"
            classified.add(key)
    expected = {(method, route.path) for route in routes if isinstance(route, APIRoute) for method in route.methods}
    assert classified == expected


def test_pairing_only_sync_reaches_scoped_http_verifier_and_token_cannot_authorize_other_routes(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", SECRET)
    from fastapi.testclient import TestClient
    from main import app
    from connectors.browser_bridge import BrowserBridgeService

    async def accepted(self, frame, token):
        assert token == "pairing-only-token"
        return {"status": "acknowledged", "message_id": str(frame.message_id)}
    monkeypatch.setattr(BrowserBridgeService, "receive", accepted)
    frame = {
        "protocol": "gdpr-browser-bridge", "version": 1,
        "message_id": str(uuid4()), "connector_instance_id": str(uuid4()),
        "sent_at": "2026-07-18T12:00:00Z",
        "records": [{
            "source_record_id": "visit-1", "source_record_version": "1",
            "record_signature": "0" * 64, "data_class": "browser.history",
            "occurred_at": "2026-07-18T11:00:00Z", "observed_at": "2026-07-18T12:00:00Z",
            "media_type": "application/json", "payload_base64": "e30=",
            "source_metadata": {}, "required_permissions": [],
        }],
    }
    client = TestClient(app)
    accepted_response = client.post(
        "/connectors/browser/sync", json=frame,
        headers={"authorization": "Bearer pairing-only-token"},
    )
    assert accepted_response.status_code == 200, accepted_response.text
    rejected = client.get("/query/tools", headers={"authorization": "Bearer pairing-only-token"})
    assert rejected.status_code == 401
