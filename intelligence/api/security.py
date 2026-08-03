"""Signed, replay-bounded authority for calls into the intelligence service."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import time
from urllib.parse import parse_qsl, quote, unquote
from uuid import UUID

from fastapi import HTTPException, Request

from config import get_settings


AUTHORITY_VERSION = "v1"
_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SIGNATURE_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class InternalAuthority:
    profile_id: UUID
    version: str
    timestamp: int
    nonce: str


class _RedisReplayStore:
    """Atomic, process-independent replay rejection backed by the shared Redis."""
    def accept(self, nonce: str, *, skew_seconds: int) -> bool:
        import redis
        settings = get_settings()
        try:
            client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
            # The timestamp may be accepted at either edge of the skew window, so retain
            # the nonce for twice the skew plus a small clock/transport allowance.
            return bool(client.set(f"gdpr:internal-authority:{AUTHORITY_VERSION}:{nonce}", "1", nx=True, ex=2 * skew_seconds + 5))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="internal API replay protection is unavailable") from exc


class _TestReplayStore:
    def __init__(self): self.entries: set[str] = set()
    def accept(self, nonce: str, *, skew_seconds: int) -> bool:
        if nonce in self.entries: return False
        self.entries.add(nonce); return True


_REPLAY_STORE = _RedisReplayStore()


def canonical_path(path: str) -> str:
    """Canonicalise each path segment using RFC 3986 percent encoding."""
    try:
        if re.search(r"%(?![0-9A-Fa-f]{2})", path):
            raise ValueError("malformed percent encoding")
        canonical: list[str] = []
        for raw_segment in path.split("/"):
            segment = unquote(raw_segment)
            if segment == ".":
                continue
            if segment == "..":
                if canonical and canonical[-1] != "": canonical.pop()
                continue
            canonical.append(quote(segment, safe="-._~"))
        value = "/".join(canonical) or "/"
        return value if value.startswith("/") else f"/{value}"
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid internal authority request path") from exc


def canonical_query(raw_query: str) -> str:
    pairs = [
        (quote(key, safe="-._~"), quote(value, safe="-._~"))
        for key, value in parse_qsl(raw_query, keep_blank_values=True, strict_parsing=False)
    ]
    pairs.sort(key=lambda pair: (pair[0], pair[1]))
    return "&".join(f"{key}={value}" for key, value in pairs)


def canonical_payload(
    *, version: str, timestamp: int, nonce: str, method: str,
    path: str, query: str, profile_id: UUID, content_type: str = "application/json",
    body_digest: str | None = None,
) -> str:
    body_digest = body_digest or hashlib.sha256(b"").hexdigest()
    return "\n".join((
        version, str(timestamp), nonce, method.upper(), canonical_path(path),
        canonical_query(query), str(profile_id), content_type.strip().lower(), body_digest,
    ))


def _header(request: Request, name: str) -> str:
    value = request.headers.get(name)
    if not value:
        raise HTTPException(status_code=401, detail="valid internal API authority required; complete signed headers are missing")
    return value


def verify_internal_request(request: Request, *, now: int | None = None, body: bytes = b"") -> InternalAuthority:
    settings = get_settings()
    secret = settings.internal_api_key
    if not secret:
        raise HTTPException(status_code=503, detail="internal API authority is not configured")

    version = _header(request, "x-gdpr-internal-version")
    timestamp_value = _header(request, "x-gdpr-internal-timestamp")
    nonce = _header(request, "x-gdpr-internal-nonce")
    profile_value = _header(request, "x-gdpr-profile-id")
    supplied_signature = _header(request, "x-gdpr-internal-key")
    supplied_body_digest = _header(request, "x-gdpr-content-sha256")
    if version != AUTHORITY_VERSION or not _NONCE_PATTERN.fullmatch(nonce):
        raise HTTPException(status_code=401, detail="invalid internal API authority headers")
    if not _SIGNATURE_PATTERN.fullmatch(supplied_signature) or not _SIGNATURE_PATTERN.fullmatch(supplied_body_digest):
        raise HTTPException(status_code=401, detail="invalid internal API authority signature")
    try:
        timestamp = int(timestamp_value)
        profile_id = UUID(profile_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid internal API authority headers") from exc

    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > settings.internal_authority_clock_skew_seconds:
        raise HTTPException(status_code=401, detail="internal API authority has expired or is not yet valid")
    actual_body_digest = hashlib.sha256(body).hexdigest()
    if not hmac.compare_digest(supplied_body_digest.lower(), actual_body_digest):
        raise HTTPException(status_code=401, detail="internal API request body digest does not match")
    payload = canonical_payload(
        version=version, timestamp=timestamp, nonce=nonce, method=request.method,
        path=request.url.path, query=request.url.query, profile_id=profile_id,
        content_type=request.headers.get("content-type", "application/json").strip().lower(), body_digest=actual_body_digest,
    )
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature.lower(), expected):
        raise HTTPException(status_code=401, detail="invalid internal API authority signature")
    if not _REPLAY_STORE.accept(nonce, skew_seconds=settings.internal_authority_clock_skew_seconds):
        raise HTTPException(status_code=409, detail="internal API authority replay rejected")
    authority = InternalAuthority(profile_id=profile_id, version=version, timestamp=timestamp, nonce=nonce)
    request.state.internal_authority = authority
    return authority


def require_internal_request(request: Request) -> InternalAuthority:
    authority = getattr(request.state, "internal_authority", None)
    return authority if isinstance(authority, InternalAuthority) else verify_internal_request(request)


def require_profile_id(request: Request) -> UUID:
    """Return only the profile UUID established by verified internal authority."""
    return require_internal_request(request).profile_id


def is_separately_authorized_ingress(request: Request) -> bool:
    """The extension sync route uses only its scoped, hashed pairing bearer token."""
    return request.method == "POST" and request.url.path == "/connectors/browser/sync"


def reset_replay_window_for_tests() -> None:
    global _REPLAY_STORE
    _REPLAY_STORE = _TestReplayStore()
