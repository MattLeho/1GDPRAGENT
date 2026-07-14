from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from connectors.definitions import IMAP_EMAIL_DEFINITION
from connectors.models import PermissionAccess
from retention.controller_erasure import ControllerErasureDenied, ControllerErasureService
from retention.source_delete import SourceDeletionDenied, SourceDeletionService


def test_imap_source_delete_is_an_explicit_optional_permission():
    permission = next(
        item for item in IMAP_EMAIL_DEFINITION.permissions
        if item.key == "mail.source_delete"
    )

    assert permission.access is PermissionAccess.DELETE
    assert permission.required is False
    assert permission.enabled_by_default is False


def test_source_delete_preflight_requires_enabled_delete_permission():
    row = {
        "dry_run": False,
        "plan_status": "approved",
        "item_group": "eligible",
        "stage": "eligible_for_delete",
        "action": "source_delete",
        "source_delete_capability": True,
        "supports_source_delete": True,
        "enabled_permissions": ["mail.metadata"],
        "review_status": "approved",
        "classification": "LOW_VALUE_BULK",
    }

    with pytest.raises(SourceDeletionDenied, match="mail.source_delete"):
        SourceDeletionService._preflight(row)

    row["enabled_permissions"].append("mail.source_delete")
    SourceDeletionService._preflight(row)


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _AsyncContext(self.connection)


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Connection:
    def __init__(self, row):
        self.row = row
        self.fetchrow = AsyncMock(return_value=row)

    def transaction(self):
        return _AsyncContext(None)


class _Postgres:
    def __init__(self, row):
        self.connection = _Connection(row)

    async def _get_pool(self):
        return _Pool(self.connection)


@pytest.mark.asyncio
async def test_controller_erasure_candidate_requires_eligible_for_delete_stage():
    postgres = _Postgres({
        "action": "controller_erasure_candidate",
        "item_group": "eligible",
        "stage": "quarantine",
        "plan_status": "approved",
        "dry_run": False,
        "review_status": "approved",
        "classification": "LOW_VALUE_BULK",
    })

    with pytest.raises(ControllerErasureDenied, match="eligible_for_delete stage"):
        await ControllerErasureService(postgres).create_candidate(
            deletion_plan_item_id=object(), controller_key="controller.test",
        )

    assert postgres.connection.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_controller_erasure_draft_rechecks_eligible_for_delete_stage():
    postgres = _Postgres({
        "id": object(),
        "deletion_plan_item_id": object(),
        "controller_key": "controller.test",
        "existing_request_id": None,
        "review_status": "pending",
        "automatic_execution_enabled": False,
        "deletion_stage": "cancelled",
    })

    with pytest.raises(ControllerErasureDenied, match="eligible_for_delete stage"):
        await ControllerErasureService(postgres).review_and_create_draft(
            candidate_id=object(), actor="reviewer",
            confirmation="CREATE DRAFT ERASURE REQUEST",
        )

    assert postgres.connection.fetchrow.await_count == 1
