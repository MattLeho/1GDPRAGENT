"""Fail-closed authority boundary for user-scoped local service APIs."""
from __future__ import annotations

import hmac
from uuid import UUID

from fastapi import Header, HTTPException, Request

from config import get_settings


def require_internal_request(
    request: Request,
    x_gdpr_internal_key: str | None = Header(default=None),
) -> None:
    # The browser extension uses its separately scoped, hashed pairing bearer.
    if request.url.path == "/connectors/browser/sync" and request.method == "POST":
        return
    settings=get_settings()
    expected=settings.internal_api_key or settings.credential_key
    if not expected:
        raise HTTPException(status_code=503,detail="internal API authority is not configured")
    if not x_gdpr_internal_key or not hmac.compare_digest(x_gdpr_internal_key,expected):
        raise HTTPException(status_code=401,detail="valid internal API authority required")


def require_profile_id(x_gdpr_profile_id: str | None = Header(default=None)) -> UUID:
    if not x_gdpr_profile_id:
        raise HTTPException(status_code=401,detail="authenticated profile scope required")
    try:
        return UUID(x_gdpr_profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail="invalid profile scope") from exc
