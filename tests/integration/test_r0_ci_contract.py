"""Contract tests for R0 entry points; these keep CI coverage explicit."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_r0_ci_workflow_invokes_all_required_gates_and_uploads_artifacts():
    workflow = _read(".github/workflows/r0-baseline.yml")
    runner = _read("scripts/r0-run-all.sh")
    for command in (
        "r0-compose-validate.sh",
        "r0-migration-fixtures.sh",
        "r0-python-suite.sh",
        "r0-static-invariants.sh",
        "r0-frontend.sh typecheck",
        "r0-frontend.sh lint",
        "r0-frontend.sh unit",
        "r0-frontend.sh build",
        "r0-browser.sh",
    ):
        assert command in runner, f"R0 CI must invoke {command}."
    assert "r0-run-all.sh" in workflow
    assert "actions/upload-artifact" in workflow
    assert "if: always()" in workflow


def test_r0_entry_points_do_not_silently_skip_missing_dependencies():
    for script in (
        "scripts/r0-migration-fixtures.sh",
        "scripts/r0-python-suite.sh",
        "scripts/r0-static-invariants.sh",
        "scripts/r0-frontend.sh",
        "scripts/r0-browser.sh",
        "scripts/r0-compose-validate.sh",
    ):
        content = _read(script)
        assert "set -euo pipefail" in content
        assert "require_" in content


def test_static_gate_includes_fail_closed_security_invariants():
    static_gate = _read("scripts/r0-static-invariants.sh")
    assert "tests/integration" in static_gate
    invariants = _read("tests/integration/test_r0_architecture_invariants.py")
    for invariant in (
        "requireApiSession",
        "Direct model-provider calls",
        "Direct Neo4j mutation",
        "Runtime Neo4j schema DDL",
    ):
        assert invariant in invariants


def test_browser_gate_provisions_an_isolated_authenticated_runtime():
    browser = _read("scripts/r0-browser.sh")
    workflow = _read(".github/workflows/r0-baseline.yml")
    config = _read("frontend/playwright.config.ts")
    assert "R0_MANAGED_BROWSER_STACK" in browser
    assert "R0_TEST_MODE" in browser
    assert "python database/migrate.py" in browser
    assert "r0-global-setup.ts" in config
    assert "R0_EXECUTE_BROWSER" in config
    assert "R0_MANAGED_BROWSER_STACK: \"1\"" in workflow
    assert "R0_TEST_MODE: \"1\"" in workflow
    assert "pnpm run test:browser" in browser
