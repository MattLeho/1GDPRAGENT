import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HOOK = ROOT / "frontend/components/insights/useInsightDashboard.ts"
PAGE = ROOT / "frontend/app/dashboard/insights/page.tsx"
DASHBOARD = ROOT / "frontend/components/insights/PersonalInsightsDashboard.tsx"

# A clock read with no argument (`new Date()`), as opposed to a snapshot
# revival such as `new Date(initialNow)`.
PER_RENDER_CLOCK = re.compile(r"new\s+Date\s*\(\s*\)")


def test_default_temporal_selection_is_stable_for_one_url_state():
    """The default temporal selection must be derived from one fixed instant.

    `parseInsightSelection` falls back to a one-year window ending "now" when the
    URL carries no explicit period. If that "now" is read on every render, each
    completed request yields a new selection key and immediately starts another
    seven-module refresh, and the server render disagrees with the first client
    render. The selection is therefore memoized on the URL string plus a single
    `initialNow` snapshot supplied by the server component.
    """
    source = HOOK.read_text(encoding="utf-8")

    # The snapshot is an input to the hook, never minted inside it.
    assert "export function useInsightDashboard(initialNow: string)" in source

    # One memo, keyed on the URL state and the snapshot, is the only place the
    # selection is derived.
    assert "const searchParamsKey = searchParams.toString();" in source
    assert "const selection = useMemo(" in source
    assert "parseInsightSelection(new URLSearchParams(searchParamsKey), new Date(initialNow))" in source
    assert "[initialNow, searchParamsKey]" in source

    # Recomputing the selection on every render would defeat the memo.
    assert "const selection = parseInsightSelection(" not in source

    # No per-render clock may leak into the hook at all: `new Date(initialNow)`
    # is a snapshot revival, `new Date()` is a fresh reading.
    assert not PER_RENDER_CLOCK.search(source), (
        "useInsightDashboard must not read the wall clock; the temporal default "
        "comes from the initialNow snapshot."
    )


def test_insights_page_supplies_one_server_side_now_snapshot():
    """The snapshot is taken once per page request on the server.

    A client component would re-read the clock during hydration and disagree with
    the markup the server produced; a server component takes the instant once and
    hands the same string to both renders.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert "'use client'" not in page
    assert '"use client"' not in page
    assert "const initialNow = new Date().toISOString();" in page
    assert "initialNow={initialNow}" in page

    dashboard = DASHBOARD.read_text(encoding="utf-8")
    # The dashboard forwards the server snapshot; it does not mint its own.
    assert "{ initialNow }: { initialNow: string }" in dashboard
    assert "useInsightDashboard(initialNow)" in dashboard
    assert not PER_RENDER_CLOCK.search(dashboard), (
        "PersonalInsightsDashboard must not read the wall clock; initialNow "
        "arrives as a prop from the server component."
    )


def test_temporal_and_density_surfaces_use_theme_tokens_not_light_only_panels():
    temporal = (ROOT / "frontend/components/insights/TemporalControl.tsx").read_text(encoding="utf-8")
    density = (ROOT / "frontend/components/insights/ActivityDensityTimeline.tsx").read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    for source in (temporal, density):
        assert "bg-card" in source
        assert "border-border" in source
        assert "text-muted-foreground" in source
        assert "bg-white" not in source
    assert "dark:[color-scheme:dark]" in temporal
    assert "text-foreground" in dashboard
    assert "bg-white" not in dashboard
