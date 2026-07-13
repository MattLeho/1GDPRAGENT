"""Local connector service endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from connectors.browser_bridge import (
    BrowserBridgeAuthenticationError, BrowserBridgeError, BrowserBridgeFrame,
    BrowserBridgeReplayInProgress, BrowserBridgeService,
)
from connectors.application import ConnectorApplication
from connectors.lifecycle import connector_health
from connectors.models import ConnectorStatus, SyncRunKind


router = APIRouter(prefix="/connectors", tags=["Source connectors"])


class CreateBrowserPairing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_instance_id: UUID
    label: str = Field(min_length=1, max_length=200)


class CreateConnectorInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition_key: str
    definition_version: str = "1"
    display_name: str = Field(min_length=1, max_length=200)
    account_key: str = "default"
    profile_id: UUID | None = None
    enabled_permissions: tuple[str, ...] = ()
    configuration: dict = Field(default_factory=dict)
    credential_id: UUID | None = None


class UpdatePermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled_permissions: tuple[str, ...]
    actor: str = Field(min_length=1, max_length=200)


@router.get("")
async def list_connectors(profile_id: UUID | None = None):
    app = ConnectorApplication()
    definitions = await app.declare_definitions()
    instances = await app.repository.list_instances(profile_id=profile_id)
    return {
        "definitions": [value.model_dump(mode="json") for value in definitions],
        "instances": [value.model_dump(mode="json") for value in instances],
    }


@router.post("")
async def create_connector(body: CreateConnectorInstance):
    app = ConnectorApplication()
    await app.declare_definitions()
    try:
        definition = app.registry.get_definition(body.definition_key, body.definition_version)
        credential_id = body.credential_id
        if body.definition_key == "email.imap" and credential_id is None:
            rows = await app.postgres.execute(
                """SELECT id FROM connector_credentials
                   WHERE connector_key IN ('email.imap','email') AND account_key=$1
                     AND secret_ciphertext IS NOT NULL AND NOT needs_reentry
                   ORDER BY (connector_key='email.imap') DESC,updated_at DESC LIMIT 1""",
                body.account_key.strip().casefold(),
            )
            credential_id = rows[0]["id"] if rows else None
        initial_status = (
            ConnectorStatus.AUTHENTICATION_REQUIRED
            if body.definition_key == "email.imap" and credential_id is None
            else ConnectorStatus.CONNECTED
        )
        return await app.repository.create_instance(
            definition, display_name=body.display_name,
            enabled_permissions=body.enabled_permissions, profile_id=body.profile_id,
            account_key=body.account_key, configuration=body.configuration,
            credential_id=credential_id,
            status=initial_status,
        )
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/instances/{instance_id}/sync")
async def sync_connector(instance_id: UUID, backfill: bool = False):
    try:
        app = ConnectorApplication()
        instance = await app.repository.get_instance(instance_id)
        definition = app.registry.get_definition(instance.definition_key, instance.definition_version)
        if instance.status not in {ConnectorStatus.CONNECTED, ConnectorStatus.DEGRADED}:
            raise ValueError(f"sync unavailable while connector is {instance.status.value}")
        if backfill and not definition.supports_backfill: raise ValueError("connector does not support backfill")
        if not backfill and not definition.supports_incremental: raise ValueError("connector does not support incremental sync")
        from tasks import connector_sync as connector_sync_task
        task = connector_sync_task.delay({
            "connector_instance_id": str(instance_id),
            "kind": (SyncRunKind.BACKFILL if backfill else SyncRunKind.SYNC).value,
            "cursor_key": "backfill" if backfill else "default",
        })
        return {"queued": True, "task_id": task.id}
    except (ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/instances/{instance_id}/status/{status}")
async def update_connector_status(instance_id: UUID, status: ConnectorStatus):
    try:
        return await ConnectorApplication().repository.set_status(instance_id, status)
    except (ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/instances/{instance_id}/permissions")
async def update_connector_permissions(instance_id: UUID, body: UpdatePermissions):
    app = ConnectorApplication()
    try:
        instance = await app.repository.get_instance(instance_id)
        definition = app.registry.get_definition(instance.definition_key, instance.definition_version)
        return await app.repository.set_enabled_permissions(
            instance_id, definition, body.enabled_permissions, actor=body.actor,
        )
    except (ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/instances/{instance_id}/health")
async def connector_instance_health(instance_id: UUID):
    try:
        instance = await ConnectorApplication().repository.get_instance(instance_id)
        return connector_health(instance)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _pairing_origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    return origin is None or origin in {
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
    }


@router.post("/browser/pairings")
async def create_browser_pairing(body: CreateBrowserPairing, request: Request):
    if not _pairing_origin_allowed(request):
        raise HTTPException(status_code=403, detail="pairing is restricted to the local GDPR Agent UI")
    try:
        return await BrowserBridgeService().create_pairing(body.connector_instance_id, body.label)
    except (ValueError, LookupError, BrowserBridgeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/browser/pairings/{pairing_id}")
async def revoke_browser_pairing(pairing_id: UUID, request: Request):
    if not _pairing_origin_allowed(request):
        raise HTTPException(status_code=403, detail="pairing is restricted to the local GDPR Agent UI")
    if not await BrowserBridgeService().revoke_pairing(pairing_id):
        raise HTTPException(status_code=404, detail="pairing not found")
    return {"revoked": True}


@router.post("/browser/sync")
async def browser_sync(
    frame: BrowserBridgeFrame,
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="browser bridge bearer token required")
    try:
        return await BrowserBridgeService().receive(frame, authorization[7:])
    except BrowserBridgeAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except BrowserBridgeReplayInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BrowserBridgeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
