from pathlib import Path
from uuid import uuid4
import pytest

from privacy.contracts import (
    CapabilityExposureStatus,DeletionVerificationStatus,GraphEpistemicState,
    HypothesisStatus,PrivacyQueryResult,ProfileLayer,
)
from graph.projection import GraphProjectionService

ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_frozen_epistemic_statuses_are_exact():
    assert {x.value for x in CapabilityExposureStatus}=={
        "evidenced_from_export","documented","legally_authorised",
        "technically_possible","speculative","human_confirmed"}
    assert {x.value for x in GraphEpistemicState}=={
        "currently_observed","potentially_enabled","alleged_unverified"}
    assert {x.value for x in ProfileLayer}=={
        "self_declared","observed_behaviour","controller_profile","system_hypotheses"}
    assert {x.value for x in HypothesisStatus}=={
        "open","request_drafted","request_sent","confirmed","rejected","unresolved","superseded"}
    assert {x.value for x in DeletionVerificationStatus}=={
        "EXPECTED_REMOVED","CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT","STILL_OBSERVED","UNVERIFIABLE"}

def test_evidence_bearing_query_result_requires_citations():
    with pytest.raises(ValueError,match="citations"):
        PrivacyQueryResult(tool="get_current_profile",data={})
    assert PrivacyQueryResult(tool="health",data={},evidence_bearing=False).citations==()

def test_ontology_and_projection_freeze_task6_types():
    source=read("ontology/graph-ontology.json")
    for value in ("Authority","Dataset","PrivacyHypothesis","DeletionSimulation",
                  "ORIGINALLY_JUSTIFIED_BY","TECHNICALLY_COULD_ENABLE",
                  "HAS_LEGAL_GATEWAY_TO","USES_SUBPROCESSOR"):
        assert f'"{value}"' in source
    assert {"Dataset","LegalBasis","Authority"}<=GraphProjectionService.HIGH_VALUE_LABELS

def test_projection_uses_explicit_epistemics_and_temporal_provenance():
    source=read("intelligence/graph/projection.py")
    assert "r.edge_epistemic=$edge_epistemic" in source
    assert "REMOVE r.inferred" in source
    assert "r.inferred=" not in source
    for field in ("valid_from","controller_observed_from","exported_at","ingested_at",
                  "derivation_method","evidence_locator_ids"):
        assert f"r.{field}=" in source

def test_task6_migration_preserves_semantic_separation():
    source=read("database/migrations/028_task6_privacy_contracts.sql")
    for table in ("capability_candidates","identifier_statistics","edge_risks",
                  "policy_source_versions","policy_claims","purpose_distance_assessments",
                  "institutional_access_edges","privacy_hypotheses",
                  "deletion_simulations","deletion_verifications","privacy_query_audits"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in source
    assert "Possible purpose drift" in source
    assert "CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT" in source
    assert "GDPR violation detected" not in source
    assert "isInferred" not in source
