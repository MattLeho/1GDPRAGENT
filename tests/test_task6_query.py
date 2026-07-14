from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from intelligence.privacy.query import ARGUMENT_TYPES, PrivacyToolCall, TOOL_NAMES


REQUIRED = {
 "get_current_profile","get_profile_at","compare_profile_periods","trace_assertion",
 "get_assertion_evidence","find_identifier_links","get_identifier_centrality",
 "simulate_identifier_removal","list_controller_assignments",
 "compare_behavioural_and_controller_profile","list_capability_exposure",
 "trace_capability_evidence","list_purpose_drift_candidates","trace_purpose_lineage",
 "list_open_privacy_hypotheses","compare_export_snapshots","get_personal_drift",
 "get_controller_drift","get_understanding_drift",
}


def test_registry_is_exactly_the_required_19_tools():
    assert set(TOOL_NAMES) == REQUIRED
    assert set(ARGUMENT_TYPES) == REQUIRED


def test_arbitrary_query_languages_and_extra_arguments_are_rejected():
    with pytest.raises(ValidationError):
        PrivacyToolCall(tool="run_cypher", arguments={"cypher":"MATCH (n) DELETE n"})
    with pytest.raises(ValidationError):
        ARGUMENT_TYPES["get_current_profile"].model_validate({"sql":"DROP TABLE assertions"})


def test_each_call_has_a_closed_argument_contract():
    now = datetime.now(timezone.utc)
    samples = {
        "get_profile_at":{"as_of":now}, "compare_profile_periods":{"from_at":now,"to_at":now},
        "trace_assertion":{"assertion_id":uuid4()}, "get_assertion_evidence":{"assertion_id":uuid4()},
        "find_identifier_links":{"identifier_ref":"email:test@example.invalid"},
        "get_identifier_centrality":{"identifier_node_id":uuid4()},
        "simulate_identifier_removal":{"identifier_node_id":uuid4()},
        "trace_capability_evidence":{"capability_key":"interest_inference"},
        "trace_purpose_lineage":{"purpose_id":uuid4()},
        "compare_export_snapshots":{"before_snapshot_id":uuid4(),"after_snapshot_id":uuid4()},
        "get_personal_drift":{"from_at":now,"to_at":now},
        "get_controller_drift":{"from_at":now,"to_at":now},
        "get_understanding_drift":{"from_at":now,"to_at":now},
    }
    for tool in TOOL_NAMES:
        ARGUMENT_TYPES[tool].model_validate(samples.get(tool, {}))


def test_legacy_natural_language_body_is_not_a_tool_call():
    with pytest.raises(ValidationError):
        PrivacyToolCall.model_validate({"question":"Who has my email?","user_id":"root"})
