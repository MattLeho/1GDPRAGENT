from pathlib import Path

ROOT=Path(__file__).parents[1]

def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_graph_api_exposes_complete_filter_contract_and_profile_scope():
    text=read("frontend/app/api/graph/route.ts")
    for name in ("asOf","compareTo","profileLayer","epistemicBasis","assertionStatus",
                 "capabilityStatus","purpose","sourceArtifact","controller","dataDomain"):
        assert name in text
    assert ".profile_id = $profileId" in text
    assert "requireApiSession" in text

def test_final_graph_ui_has_all_modes_layers_and_drift_views():
    controls=read("frontend/components/graph/PrivacyGraphControls.tsx")
    for label in ("NOW","THROUGH TIME","COMPARE","CONTROLLER PROFILE","CAPABILITIES","LINKABILITY","PURPOSE","ACCESS"):
        assert label in controls
    for label in ("WHO I SAY I AM","WHAT MY ACTIVITY EVIDENCES","WHAT THE CONTROLLER ASSIGNS","WHAT THE SYSTEM HYPOTHESISES"):
        assert label in controls
    panel=read("frontend/components/graph/PrivacyModePanel.tsx")
    for tool in ("get_personal_drift","get_controller_drift","get_understanding_drift"):
        assert tool in panel

def test_graph_chat_has_no_keyword_cypher_or_uncited_local_fallback():
    route=read("frontend/app/api/graph/chat/route.ts")
    component=read("frontend/components/graph/ShadowProfileChat.tsx")
    assert "runCypher" not in route and "lowerQuery" not in route
    assert "generateLocalResponse" not in component
    assert "citations" in component
    assert "Allowed tools:" in route and "Never return SQL or Cypher" in route
    assert "Ask an evidence-backed privacy question" in component

def test_grounded_extraction_has_no_direct_model_call_and_requires_canonical_locator():
    text=read("intelligence/api/extract.py")
    assert "langextract" not in text.casefold() and "gemini" not in text.casefold()
    assert "PolicySourceIngestionService" in text and "grounded_claim" in text
    assert "exact EvidenceLocator" in text
