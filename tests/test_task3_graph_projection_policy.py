from graph.projection import GraphProjectionService


def test_task3_projection_allowlist_excludes_raw_activity_events():
    assert "ActivityEvent" not in GraphProjectionService.HIGH_VALUE_LABELS
    assert {
        "Subject", "ControllerProfile", "Organisation", "Account", "Identifier",
        "DataDomain", "Topic", "DataPoint", "TemporalState", "ProjectEpisode",
        "ProcessingActivity", "Purpose", "Capability", "SourceArtifact",
    } <= GraphProjectionService.HIGH_VALUE_LABELS


def test_task3_projection_source_has_controller_profile_separation_guard():
    source = __import__("inspect").getsource(GraphProjectionService.project_assertion)
    assert 'subject_label == "ControllerProfile" and object_label == "Subject"' in source
    assert "high-value privacy topology" in source
