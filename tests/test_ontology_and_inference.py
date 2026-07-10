from extraction.schemas import InferenceConfig, PipelineConfig
from graph.ontology import canonical_entity_key, stable_node_id


def test_inference_is_opt_in_and_cannot_default_to_graph_truth():
    config=InferenceConfig()
    assert not config.use_llm_for_inference
    assert not config.apply_transitive
    assert not config.use_lexical_similarity
    assert not PipelineConfig().enable_inference


def test_subject_controller_profile_and_hypothesis_ids_are_separate():
    assert stable_node_id("Subject","matt") != stable_node_id("ControllerProfile","matt")
    assert stable_node_id("Subject","matt") != stable_node_id("Claim","matt")


def test_raw_value_equality_does_not_merge_identifier_types_or_scopes():
    email=canonical_entity_key("email","123")
    phone=canonical_entity_key("phone","123")
    opaque_a=canonical_entity_key("identifier","123",identifier_type="device_id",controller="a")
    opaque_b=canonical_entity_key("identifier","123",identifier_type="device_id",controller="b")
    assert len({email,phone,opaque_a,opaque_b})==4
