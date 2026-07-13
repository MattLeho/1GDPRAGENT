from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from connectors.models import (
    ConnectorInstance, ConnectorMode, ConnectorPermission, ConnectorStatus, PermissionAccess,
    SourceConnectorDefinition,
)
from retention.models import (
    DeletionItemGroup, DeletionPlan, DeletionPlanItem, DeletionStage,
    RetentionAction, RetentionClass, RetentionDecision, ReviewStatus,
)


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def test_connector_capabilities_and_permissions_are_mechanical():
    definition = SourceConnectorDefinition(
        key="browser.chromium", version="1", display_name="Chrome History",
        provider="chromium", connector_type="browser_history",
        modes=(ConnectorMode.INCREMENTAL_POLL,), data_classes=("browser_visit",),
        permissions=(ConnectorPermission(
            key="history.read", access=PermissionAccess.READ,
            data_class="browser_visit", description="Visited URLs and visit times",
            required=True, enabled_by_default=True,
        ),), supports_backfill=True, supports_incremental=True,
    )
    assert definition.supports_incremental and not definition.supports_source_delete
    with pytest.raises(ValidationError):
        ConnectorPermission(
            key="page.body", access=PermissionAccess.NOT_READ,
            data_class="page_content", description="Page content",
            enabled_by_default=True,
        )
    with pytest.raises(ValidationError):
        SourceConnectorDefinition(
            key="bad.connector", version="1", display_name="Bad", provider="bad",
            connector_type="bad", modes=(ConnectorMode.SNAPSHOT_IMPORT,), data_classes=("x",),
            permissions=(), supports_incremental=True,
        )
    with pytest.raises(ValidationError):
        ConnectorInstance(
            id=uuid4(), definition_key="email.imap", definition_version="1",
            display_name="Mail", status=ConnectorStatus.DISCONNECTED,
            configuration={"password": "must-not-be-here"},
            created_at=NOW, updated_at=NOW,
        )


def _decision(classification: RetentionClass) -> RetentionDecision:
    return RetentionDecision(
        id=uuid4(), source_artifact_id=uuid4(), classification=classification,
        deterministic_evidence={"fixture": True}, confidence=1, policy_id=uuid4(),
        policy_version=1, analysis_run_id=uuid4(), review_status=ReviewStatus.PENDING,
        created_at=NOW,
    )


def test_unsure_is_protected_and_cannot_enter_destructive_stage():
    unsure = _decision(RetentionClass.UNSURE)
    assert unsure.protected
    with pytest.raises(ValidationError):
        DeletionPlanItem(
            id=uuid4(), source_artifact_id=unsure.source_artifact_id,
            retention_decision_id=unsure.id, group=DeletionItemGroup.UNCERTAIN,
            action=RetentionAction.LOCAL_PURGE, reasons=("ambiguous",),
            stage=DeletionStage.ELIGIBLE_FOR_DELETE,
        )


def test_source_delete_requires_declared_capability_and_plans_default_dry_run():
    low_value = _decision(RetentionClass.LOW_VALUE_BULK)
    with pytest.raises(ValidationError):
        DeletionPlanItem(
            id=uuid4(), source_artifact_id=low_value.source_artifact_id,
            retention_decision_id=low_value.id, group=DeletionItemGroup.ELIGIBLE,
            action=RetentionAction.SOURCE_DELETE, reasons=("fixture",),
            source_delete_capability=False,
        )
    plan = DeletionPlan(
        id=uuid4(), policy_id=low_value.policy_id, policy_version=1,
        analysis_run_id=low_value.analysis_run_id, created_at=NOW,
    )
    assert plan.dry_run is True


def test_retention_contract_has_no_interest_field():
    fields = set(RetentionDecision.model_fields)
    assert not {"interest", "interest_score", "observed_interest", "importance"} & fields


def test_python_typescript_and_migration_safety_values_stay_aligned():
    root = Path(__file__).resolve().parents[1]
    connector_ts = (root / "frontend/lib/connectors/types.ts").read_text(encoding="utf-8")
    retention_ts = (root / "frontend/lib/retention/types.ts").read_text(encoding="utf-8")
    migration = (root / "database/migrations/021_task5_connector_retention_contracts.sql").read_text(encoding="utf-8")
    for value in ConnectorMode:
        assert value.value in connector_ts
    for value in RetentionClass:
        assert value.value in retention_ts and value.value in migration
    for value in RetentionAction:
        assert value.value in retention_ts and value.value in migration
    assert "dry_run BOOLEAN NOT NULL DEFAULT TRUE" in migration
    assert "CHECK(item_group='eligible' OR stage IN ('candidate','review','cancelled'))" in migration
    assert "CHECK(NOT automatic_execution_enabled OR review_status='approved')" in migration
