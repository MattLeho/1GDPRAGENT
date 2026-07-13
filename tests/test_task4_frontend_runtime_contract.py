from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_temporal_selection_is_stable_for_one_url_state():
    source = (ROOT / "frontend/components/insights/useInsightDashboard.ts").read_text(encoding="utf-8")
    assert "const searchParamsKey = searchParams.toString();" in source
    assert "const selection = useMemo(" in source
    assert "parseInsightSelection(new URLSearchParams(searchParamsKey))" in source
    assert "[searchParamsKey]" in source
    assert "const selection = parseInsightSelection(" not in source


def test_temporal_and_density_surfaces_use_theme_tokens_not_light_only_panels():
    temporal = (ROOT / "frontend/components/insights/TemporalControl.tsx").read_text(encoding="utf-8")
    density = (ROOT / "frontend/components/insights/ActivityDensityTimeline.tsx").read_text(encoding="utf-8")
    dashboard = (ROOT / "frontend/components/insights/PersonalInsightsDashboard.tsx").read_text(encoding="utf-8")
    for source in (temporal, density):
        assert "bg-card" in source
        assert "border-border" in source
        assert "text-muted-foreground" in source
        assert "bg-white" not in source
    assert "dark:[color-scheme:dark]" in temporal
    assert "text-foreground" in dashboard
    assert "bg-white" not in dashboard
