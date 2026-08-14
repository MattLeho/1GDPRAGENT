"""Fail-closed, parameterised R0 architecture invariants.

The production-root assertions intentionally remain red while documented
security regressions exist.  The fixture assertions below prove that the
verifiers reject representative forbidden code rather than merely matching the
current repository's filenames.
"""

from __future__ import annotations

import ast
import os
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/r0_architecture_invariants"
IGNORED_PARTS = frozenset({"node_modules", ".next", "__pycache__"})
SENSITIVE_ROOTS = ("settings", "requests", "request-threads", "upload", "execution", "identities", "graph", "insights", "onsit")
PUBLIC_NEXT = frozenset({"frontend/app/api/auth/check-setup/route.ts", "frontend/app/api/auth/login/route.ts", "frontend/app/api/auth/logout/route.ts", "frontend/app/api/auth/register/route.ts"})
PUBLIC_PYTHON = frozenset({"intelligence/api/health.py", "intelligence/api/security.py"})
PUBLIC_PYTHON_PATHS = frozenset({"/", "/health", "/health/ready", "/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"})
RUNTIME_POLICY = ROOT / "docs/remediation/evidence/r0-runtime-root-policy.json"
EXPECTED_FINDINGS = ROOT / "docs/remediation/evidence/r0-expected-static-findings.json"


def source_files(root: Path, suffixes: set[str]):
    for directory, children, filenames in os.walk(root):
        children[:] = [child for child in children if child not in IGNORED_PARTS]
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix in suffixes:
                yield path


def relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def next_authority_offenders(root: Path) -> list[str]:
    offenders: list[str] = []
    api = root / "frontend/app/api"
    for path in source_files(api, {".ts", ".tsx"}):
        rel = relative(root, path)
        if rel in PUBLIC_NEXT or not any(f"/api/{segment}/" in rel for segment in SENSITIVE_ROOTS):
            continue
        source = path.read_text(encoding="utf-8")
        if not re.search(r"await\s+requireApiSession\s*\(", source):
            offenders.append(rel)
    return sorted(offenders)


def has_fail_closed_global_python_authority(main: Path) -> bool:
    tree = ast.parse(main.read_text(encoding="utf-8"))
    public_paths: set[str] | None = None
    middleware: ast.AsyncFunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "_PUBLIC_PATHS" for target in node.targets):
            if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
                values = [item.value for item in node.value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]
                public_paths = set(values) if len(values) == len(node.value.elts) else None
        if isinstance(node, ast.AsyncFunctionDef):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id == "app"
                    and decorator.func.attr == "middleware"
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and decorator.args[0].value == "http"
                ):
                    middleware = node
    if public_paths != set(PUBLIC_PYTHON_PATHS) or middleware is None:
        return False
    body = ast.unparse(middleware)
    return all(marker in body for marker in (
        "request.url.path not in _PUBLIC_PATHS",
        "is_separately_authorized_ingress(request)",
        "verify_internal_request(request, body=await request.body())",
        "return await call_next(request)",
    ))


def python_authority_offenders(root: Path) -> list[str]:
    main = root / "intelligence/main.py"
    if main.exists() and has_fail_closed_global_python_authority(main):
        return []
    offenders: list[str] = []
    if main.exists():
        offenders.append(relative(root, main))
    for path in source_files(root / "intelligence/api", {".py"}):
        rel = relative(root, path)
        source = path.read_text(encoding="utf-8")
        if rel not in PUBLIC_PYTHON and "APIRouter" in source and not re.search(
            r"Depends\s*\(\s*(?:require_internal_request|require_profile_id)\s*\)", source
        ):
            offenders.append(rel)
    return sorted(offenders)


PROVIDER_MARKERS = re.compile(
    r"(?:GoogleGenAI|genai\.Client|GenerativeModel|\bOpenAI\s*\(|from\s+openai\s+import|"
    r"import\s+(?:[A-Za-z_$][\w$]*|\*\s+as\s+[A-Za-z_$][\w$]*|\{[^}]+\})\s+from\s*['\"](?:openai|@anthropic-ai/sdk)['\"]|"
    r"require\s*\(\s*['\"](?:openai|@anthropic-ai/sdk)['\"]\s*\)|"
    r"import\s*\{[^}]*\bOpenAI\b[^}]*\}\s*from\s*['\"]openai['\"]|"
    r"anthropic|\.generateContent\s*\(|\.generate_content\s*\(|"
    r"api\.openai\.com/v1/chat/completions|api\.anthropic\.com/v1/messages|"
    r"generativelanguage\.googleapis\.com/.+?:generateContent)",
    re.I,
)


def has_provider_call(source: str) -> bool:
    if PROVIDER_MARKERS.search(source):
        return True
    compact = re.sub(r"[\s'\"`+]", "", source).casefold()
    return any(domain in compact and endpoint in compact for domain, endpoint in (
        ("api.openai.com", "/v1/chat/completions"),
        ("api.anthropic.com", "/v1/messages"),
        ("openrouter.ai", "/api/v1/chat/completions"),
        ("openai.azure.com", "/chat/completions"),
        ("generativelanguage.googleapis.com", ":generatecontent"),
    ))


def scanner_bases(root: Path, category: str) -> list[Path]:
    if root != ROOT:
        return [root / "frontend", root / "intelligence"]
    policy = json.loads(RUNTIME_POLICY.read_text(encoding="utf-8"))
    return [root / item for item in policy["scanner_roots"][category]]


def provider_offenders(root: Path) -> list[str]:
    if root == ROOT:
        policy = json.loads(RUNTIME_POLICY.read_text(encoding="utf-8"))
        approved = {root / item["path"] for item in policy["approved_provider_adapters"]}
    else:
        approved = {root / "frontend/lib/rlm/provider-adapters.ts"}
    bases = scanner_bases(root, "providers")
    offenders = []
    for base in bases:
        if not base.exists():
            continue
        for path in source_files(base, {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py"}):
            if path not in approved and has_provider_call(path.read_text(encoding="utf-8")):
                offenders.append(relative(root, path))
    return sorted(offenders)


MUTATION = r"(?:CREATE|MERGE|SET|DELETE|REMOVE|DROP)"
GRAPH_RECEIVER = r"(?:session|tx|transaction|trx|neo4j|neo4j_client|graph_client|driver|self\.neo4j)"
GRAPH_METHOD = r"(?:run|execute|execute_write|execute_query|write_transaction)"
GRAPH_CALL = re.compile(
    rf"\b{GRAPH_RECEIVER}\.{GRAPH_METHOD}\s*\(",
    re.I,
)
GRAPH_ALIAS = re.compile(
    rf"\b(?P<alias>[A-Za-z_]\w*)\s*=\s*{GRAPH_RECEIVER}\.{GRAPH_METHOD}\b",
    re.I,
)
MUTATING_ASSIGNMENT = re.compile(
    rf"\b(?P<name>[A-Za-z_]\w*)(?:\s*:\s*[^=\n]+)?\s*=\s*f?(?:'''|\"\"\"|`|'|\").*?\b{MUTATION}\b.*?(?:'''|\"\"\"|`|'|\")",
    re.I | re.S,
)
MUTATING_DIRECT_CALL = re.compile(
    rf"\b{GRAPH_RECEIVER}\.{GRAPH_METHOD}\s*\(\s*f?(?:'''|\"\"\"|`|'|\").*?\b{MUTATION}\b",
    re.I | re.S,
)


def has_graph_mutation(source: str) -> bool:
    if MUTATING_DIRECT_CALL.search(source):
        return True
    mutation_variables = [match.group("name") for match in MUTATING_ASSIGNMENT.finditer(source)]
    derived_receivers = {
        match.group("name")
        for match in re.finditer(
            r"\b(?P<name>[A-Za-z_]\w*)\s*=\s*[^\n;]*(?:begin_transaction|transaction|session)\s*\(",
            source,
            re.I,
        )
    }
    receiver = rf"(?:{GRAPH_RECEIVER}|{'|'.join(map(re.escape, sorted(derived_receivers)))})" if derived_receivers else GRAPH_RECEIVER
    for name in mutation_variables:
        if re.search(rf"\b{receiver}\.{GRAPH_METHOD}\s*\(\s*{re.escape(name)}\b", source, re.I):
            return True
        for alias in (match.group("alias") for match in GRAPH_ALIAS.finditer(source)):
            if re.search(rf"\b{re.escape(alias)}\s*\(\s*{re.escape(name)}\b", source):
                return True
    return False


def neo4j_mutation_offenders(root: Path) -> list[str]:
    approved = root / "intelligence/graph/projection.py"
    offenders = []
    for base in scanner_bases(root, "neo4j"):
        for path in source_files(base, {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py"}):
            source = path.read_text(encoding="utf-8")
            if path != approved and has_graph_mutation(source):
                offenders.append(relative(root, path))
    return sorted(offenders)


def runtime_ddl_offenders(root: Path) -> list[str]:
    ddl = re.compile(r"\b(?:CREATE|DROP)\s+(?:CONSTRAINT|INDEX)\b", re.I)
    return sorted(relative(root, path) for base in scanner_bases(root, "runtime_ddl") for path in source_files(base, {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py"}) if ddl.search(path.read_text(encoding="utf-8")))


def test_verifiers_reject_synthetic_negative_controls():
    assert next_authority_offenders(FIXTURES) == ["frontend/app/api/graph/route.ts"]
    assert python_authority_offenders(FIXTURES) == ["intelligence/api/private.py"]
    assert provider_offenders(FIXTURES) == [
        "frontend/lib/aliased-provider.ts",
        "frontend/lib/bypass.ts",
        "frontend/lib/computed-provider.mjs",
        "frontend/lib/default-provider.js",
        "frontend/lib/direct-completion.ts",
    ]
    assert neo4j_mutation_offenders(FIXTURES) == [
        "intelligence/graph/alias_writer.py",
        "intelligence/graph/annotated_writer.py",
        "intelligence/graph/derived_transaction.py",
        "intelligence/graph/variable_writer.py",
        "intelligence/graph/writer.py",
    ]
    assert runtime_ddl_offenders(FIXTURES) == ["intelligence/graph/writer.py"]


def test_runtime_root_policy_is_reviewed_and_excludes_only_evidenced_legacy_code():
    policy = json.loads(RUNTIME_POLICY.read_text(encoding="utf-8"))
    assert policy["active_runtime_roots"] == ["frontend", "intelligence"]
    assert all(sorted(roots) == sorted(policy["active_runtime_roots"]) for roots in policy["scanner_roots"].values())
    assert policy["runtime_entrypoints"]
    inactive = {item["path"]: item for item in policy["inactive_legacy_roots"]}
    assert "agents/python" in inactive
    assert inactive["agents/python"]["evidence"]
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    main = (ROOT / "intelligence/main.py").read_text(encoding="utf-8")
    assert "./agents/python" not in compose
    assert "agents.python" not in main and "gdpr_agent" not in main


def test_expected_findings_have_stable_registry_owners_and_paths():
    expected = json.loads(EXPECTED_FINDINGS.read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "docs/remediation/issue-registry.json").read_text(encoding="utf-8"))
    issues = {issue["id"]: issue for issue in registry["issues"]}
    for category_name, category in expected.items():
        if category_name == "schema_version":
            continue
        for issue_id, paths in category.items():
            assert issue_id in issues
            issue = issues[issue_id]
            assert issue.get("plan") and issue.get("status")
            assert set(paths) <= set(issue.get("affected_paths", []))


def _expected(category: str) -> list[str]:
    findings = json.loads(EXPECTED_FINDINGS.read_text(encoding="utf-8"))[category]
    return sorted(path for paths in findings.values() for path in paths)


def test_sensitive_next_routes_have_an_awaited_authority_contract():
    offenders = next_authority_offenders(ROOT)
    assert not offenders, "Sensitive Next routes lack awaited requireApiSession: " + ", ".join(offenders)


def test_python_routers_require_internal_authority_dependency():
    offenders = python_authority_offenders(ROOT)
    assert not offenders, "Python routers lack canonical internal/profile authority: " + ", ".join(offenders)


def test_provider_generation_is_limited_to_canonical_task_router_adapters():
    offenders = provider_offenders(ROOT)
    assert offenders == _expected("provider_offenders"), (
        "Direct model-provider calls finding scope changed; register new/changed offenders explicitly: " + ", ".join(offenders)
    )


def test_neo4j_mutations_are_confined_to_projection_service():
    offenders = neo4j_mutation_offenders(ROOT)
    assert offenders == _expected("neo4j_mutation_offenders"), (
        "Direct Neo4j mutation finding scope changed; register new/changed offenders explicitly: " + ", ".join(offenders)
    )


def test_neo4j_schema_ddl_is_not_executed_at_runtime():
    offenders = runtime_ddl_offenders(ROOT)
    assert offenders == _expected("runtime_ddl_offenders"), (
        "Runtime Neo4j schema DDL finding scope changed; register new/changed offenders explicitly: " + ", ".join(offenders)
    )
