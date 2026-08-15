"""Contract tests for R0 entry points; these keep CI coverage explicit."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess


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
    assert "r0-gates.json" in runner
    assert "r0-run-all.log" in runner
    assert "test-results/" in workflow


def test_pnpm_is_installed_before_setup_node_requests_the_pnpm_cache():
    workflow = _read(".github/workflows/r0-baseline.yml")
    pnpm_setup = workflow.index("uses: pnpm/action-setup@v4")
    node_setup = workflow.index("uses: actions/setup-node@v4")
    pnpm_cache = workflow.index("cache: pnpm", node_setup)
    assert pnpm_setup < node_setup < pnpm_cache
    assert 'version: 11.9.0' in workflow
    assert 'node-version: "22"' in workflow


def test_ci_security_sentinels_are_purpose_distinct():
    workflow = _read(".github/workflows/r0-baseline.yml")
    values = {}
    for name in ("SESSION_SIGNING_KEY", "INTERNAL_API_KEY", "CREDENTIAL_KEY", "CREDENTIALS_ENCRYPTION_KEY"):
        line = next(line for line in workflow.splitlines() if line.strip().startswith(f"{name}:"))
        values[name] = line.split(":", 1)[1].strip().strip('"')
    assert all(values.values())
    assert len(set(values.values())) == len(values), values


def test_ci_provisions_the_graph_dependency_used_by_the_full_python_suite():
    workflow = _read(".github/workflows/r0-baseline.yml")
    assert "neo4j:" in workflow
    assert "image: neo4j:5-community" in workflow
    assert "NEO4J_URI: bolt://localhost:7687" in workflow
    assert "NEO4J_PASSWORD: r0-ci-neo4j-password" in workflow


def test_clean_install_build_policy_is_explicit_for_every_known_lifecycle_package():
    policy = _read("frontend/pnpm-workspace.yaml")
    for package in ("@google/genai", "@vaadin/vaadin-usage-statistics", "esbuild", "protobufjs", "sharp", "unrs-resolver"):
        assert package in policy
    assert "set this to true or false" not in policy


def test_runner_continues_after_failure_and_writes_parseable_manifest(tmp_path):
    if os.name == "nt":
        import pytest
        pytest.skip("runner semantics are exercised in the hosted Linux environment")
    bash = shutil.which("bash")
    if not bash:
        import pytest
        pytest.skip("bash execution is verified on the hosted Linux R0 runner")
    marker = tmp_path / "later-gate-ran"
    commands = tmp_path / "gates.txt"
    commands.write_text(f"false\nprintf later > {marker}\n", encoding="utf-8")
    results = tmp_path / "results"
    completed = subprocess.run(
        [bash, str(ROOT / "scripts/r0-run-all.sh")],
        cwd=ROOT,
        env={**os.environ, "R0_GATE_COMMANDS_FILE": str(commands), "R0_RESULTS_DIR": str(results)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert marker.read_text(encoding="utf-8") == "later"
    manifest = json.loads((results / "r0-gates.json").read_text(encoding="utf-8"))
    assert [gate["exit_status"] for gate in manifest["gates"]] == [1, 0]


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
    for suite in (
        "test_r0_architecture_invariants.py",
        "r1_route_coverage_test.py",
        "r1_internal_authority_security_test.py",
    ):
        assert suite in static_gate
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
    assert "frontend/.next/BUILD_ID" in browser
    assert "pnpm start" in browser
    assert "pnpm dev" not in browser
    assert "r0-global-setup.ts" in config
    assert "R0_EXECUTE_BROWSER" in config
    assert "R0_MANAGED_BROWSER_STACK: \"1\"" in workflow
    assert "R0_TEST_MODE: \"1\"" in workflow
    assert "pnpm run test:browser" in browser
    assert "exec setsid pnpm start" in browser
    assert "kill -KILL" in browser
    assert "pnpm pkg get" not in browser
    assert "node -e" in browser
    assert "scripts?.['test:browser']" in browser


def test_browser_preflight_reads_package_manifest_without_pnpm_property_path_parsing(tmp_path):
    if os.name == "nt":
        import pytest
        pytest.skip("SIGPIPE and Bash pipeline semantics are exercised on Linux")
    bash = shutil.which("bash")
    if not bash:
        import pytest
        pytest.skip("bash execution is verified on the hosted Linux R0 runner")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "browser-ran"
    fake_pnpm = fake_bin / "pnpm"
    fake_pnpm.write_text(_read("tests/fixtures/r0-ci/fake-pnpm-preflight"), encoding="utf-8")
    fake_pnpm.chmod(0o755)
    completed = subprocess.run(
        [bash, str(ROOT / "scripts/r0-browser.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "R0_MANAGED_BROWSER_STACK": "0",
            "R0_FAKE_BROWSER_MARKER": str(marker),
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    assert marker.read_text(encoding="utf-8") == "ran"


def test_browser_fixture_and_journey_contracts_are_fail_closed():
    setup = _read("tests/browser/r0-global-setup.ts")
    spec = _read("tests/browser/r0-authenticated-baseline.spec.ts")
    assert "default_profile_id" in setup
    assert "INSERT INTO requests(company_name, status, profile_id)" in setup
    assert "'x-gdpr-csrf': '1'" in setup
    assert "mutationHeaders" in spec
    assert "unexpectedConsoleErrors" in spec
    assert "toEqual([])" in spec
    for credential in ("GOOGLE_AI_API_KEY", "GEMINI_API_KEY", "OPEN_ROUTER_API_KEY"):
        assert credential in setup
    assert "r1-adversarial-session-api.test.ts" in _read("scripts/r0-frontend.sh")


def test_browser_test_mode_covers_graph_stats_and_health_wording_is_truthful():
    stats = _read("frontend/app/api/graph/stats/route.ts")
    layout = _read("frontend/components/layout/DashboardLayout.tsx")

    assert "process.env.R0_TEST_MODE === '1'" in stats
    assert "dbStatus: 'r0-test-double'" in stats
    assert "System Online" not in layout
    assert "Health not checked" in layout
    assert "OPS-001" in _read("tests/browser/r0-authenticated-baseline.spec.ts")
    assert "test.fail(true" not in _read("tests/browser/r0-authenticated-baseline.spec.ts")
