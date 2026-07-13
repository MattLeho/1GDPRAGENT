"""Strictly local URL decomposition for deterministic privacy features.

This module intentionally has no HTTP client and never resolves or fetches a URL.
"""

from __future__ import annotations

import hashlib
import ipaddress
import math
import re
from collections import Counter
from typing import Iterable
from urllib.parse import parse_qsl, unquote, urlsplit
from uuid import UUID

from pydantic import Field

from ingestion.models import FeatureCandidate, FeatureCandidateStatus, FrozenModel


DETECTOR_ID = "task3.url.decomposition"
DETECTOR_VERSION = "1.0.0"

_IDENTIFIER_KEY = re.compile(
    r"(?:^|[_\-.])(account|ad(?:vertising)?|client|cookie|customer|device|email|"
    r"id|identifier|phone|profile|session|token|uid|user)(?:$|[_\-.])",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9][0-9 ()\-.]{6,20}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_OPAQUE = re.compile(r"^[A-Za-z0-9_\-\.~]{16,}$")

# A deliberately small, static fallback for common multi-label public suffixes.
# It is preferable to network-backed suffix discovery in the ingestion path.
_COMMON_TWO_LABEL_SUFFIXES = frozenset(
    {
        "ac.uk", "co.uk", "gov.uk", "ltd.uk", "me.uk", "net.uk", "org.uk", "plc.uk",
        "asn.au", "com.au", "edu.au", "gov.au", "id.au", "net.au", "org.au",
        "ac.nz", "co.nz", "govt.nz", "net.nz", "org.nz",
        "co.jp", "ne.jp", "or.jp", "com.br", "com.cn", "com.hk", "com.sg",
        "co.in", "firm.in", "gen.in", "ind.in", "net.in", "org.in",
    }
)


class URLQueryValueCandidate(FrozenModel):
    query_key: str
    value: str
    value_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_types: tuple[str, ...]
    rules: tuple[str, ...]


class URLDecomposition(FrozenModel):
    original_value: str
    scheme: str | None = None
    hostname: str | None = None
    domain: str | None = None
    subdomain: str | None = None
    port: int | None = None
    path: str
    decoded_path: str
    query_keys: tuple[str, ...]
    query_pairs: tuple[tuple[str, str], ...]
    fragment: str | None = None
    query_identifier_candidates: tuple[URLQueryValueCandidate, ...] = ()
    is_absolute: bool


def _domain_parts(hostname: str | None) -> tuple[str | None, str | None]:
    if not hostname:
        return None, None
    host = hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
        return host, None
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) <= 2:
        return host, None
    suffix_width = 2 if ".".join(labels[-2:]) in _COMMON_TWO_LABEL_SUFFIXES else 1
    domain_width = suffix_width + 1
    if len(labels) <= domain_width:
        return host, None
    return ".".join(labels[-domain_width:]), ".".join(labels[:-domain_width])


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in counts.values())


def _query_identifier_candidate(key: str, value: str) -> URLQueryValueCandidate | None:
    types: list[str] = []
    rules: list[str] = []
    if _IDENTIFIER_KEY.search(key):
        types.append("identifier_key_hint")
        rules.append("versioned_identifier_query_key")
    if _EMAIL.fullmatch(value):
        types.append("email")
        rules.append("email_shape")
    try:
        ipaddress.ip_address(value.strip("[]"))
        types.append("ip_address")
        rules.append("ip_literal")
    except ValueError:
        pass
    if _UUID.fullmatch(value):
        types.append("uuid")
        rules.append("uuid_shape")
    elif _PHONE.fullmatch(value):
        types.append("phone")
        rules.append("phone_shape")
    elif _OPAQUE.fullmatch(value) and any(c.isalpha() for c in value) and any(c.isdigit() for c in value) and _entropy(value) >= 3.0:
        types.append("opaque_token")
        rules.append("length_character_mix_entropy")
    if not types:
        return None
    return URLQueryValueCandidate(
        query_key=key,
        value=value,
        value_sha256=hashlib.sha256(value.encode("utf-8")).hexdigest(),
        candidate_types=tuple(dict.fromkeys(types)),
        rules=tuple(rules),
    )


def decompose_url(value: str) -> URLDecomposition:
    """Parse a URL without performing DNS resolution, HTTP, or any other I/O."""
    if not isinstance(value, str) or not value:
        raise ValueError("URL value must be a non-empty string")
    if any(ord(character) < 32 for character in value):
        raise ValueError("URL value contains control characters")
    try:
        parsed = urlsplit(value, allow_fragments=True)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid URL: {error}") from error
    domain, subdomain = _domain_parts(hostname)
    pairs = tuple(parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=False))
    candidates = tuple(
        candidate
        for key, query_value in pairs
        if (candidate := _query_identifier_candidate(key, query_value)) is not None
    )
    return URLDecomposition(
        original_value=value,
        scheme=parsed.scheme.lower() or None,
        hostname=hostname.lower() if hostname else None,
        domain=domain,
        subdomain=subdomain,
        port=port,
        path=parsed.path,
        decoded_path=unquote(parsed.path),
        query_keys=tuple(dict.fromkeys(key for key, _ in pairs)),
        query_pairs=pairs,
        fragment=parsed.fragment or None,
        query_identifier_candidates=candidates,
        is_absolute=bool(parsed.scheme and parsed.netloc),
    )


def url_feature_candidate(
    value: str,
    *,
    source_event_ids: Iterable[UUID] = (),
    source_artifact_ids: Iterable[UUID] = (),
) -> FeatureCandidate:
    decomposition = decompose_url(value)
    return FeatureCandidate(
        feature_type="url_decomposition",
        detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION,
        source_event_ids=tuple(source_event_ids),
        source_artifact_ids=tuple(source_artifact_ids),
        calculated_values=decomposition.model_dump(mode="json"),
        rule_result=True,
        candidate_status=FeatureCandidateStatus.DETERMINISTIC,
    )
