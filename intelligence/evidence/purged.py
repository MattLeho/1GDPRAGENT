"""Resolve evidence through full content or retained minimised segments."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
from uuid import UUID

from .locators import LocatorResolutionError, resolve_locator


def local_storage_path(storage_uri: str) -> Path:
    parsed = urlparse(storage_uri)
    if parsed.scheme != "file":
        raise LocatorResolutionError("only local file evidence storage is supported")
    return Path(url2pathname(unquote(parsed.path))).resolve()


async def resolve_persisted_locator(connection, locator_id: UUID) -> bytes:
    retained = await connection.fetchrow(
        "SELECT resolved_bytes FROM minimized_evidence_segments WHERE evidence_locator_id=$1",
        locator_id,
    )
    if retained:
        return bytes(retained["resolved_bytes"])
    row = await connection.fetchrow(
        """SELECT el.locator_type,el.locator,cb.storage_uri,
           EXISTS(SELECT 1 FROM content_purge_tombstones cpt WHERE cpt.source_artifact_id=el.artifact_id) purged
           FROM evidence_locators el JOIN source_artifacts sa ON sa.id=el.artifact_id
           JOIN content_blobs cb ON cb.id=sa.content_blob_id WHERE el.id=$1""",
        locator_id,
    )
    if not row:
        raise LocatorResolutionError("evidence locator does not exist")
    if row["purged"]:
        raise LocatorResolutionError("full source content was purged; this locator was not retained")
    import json
    locator = json.loads(row["locator"]) if isinstance(row["locator"], str) else dict(row["locator"])
    return resolve_locator(local_storage_path(row["storage_uri"]).read_bytes(), row["locator_type"], locator)
