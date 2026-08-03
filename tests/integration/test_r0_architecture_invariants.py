"""Fail-closed, parameterised R0 architecture invariants.

The production-root assertions intentionally remain red while documented
security regressions exist.  The fixture assertions below prove that the
verifiers reject representative forbidden code rather than merely matching the
current repository's filenames.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/r0_architecture_invariants"
IGNORED_PARTS = frozenset({"node_modules", ".next", "__pycache__"})
SENSITIVE_ROOTS = ("settings", "requests", "request-threads", "upload", "execution", "identities", "graph", "insights", "onsit")
PUBLIC_NEXT = frozenset({"frontend/app/api/auth/check-setup/route.ts", "frontend/app/api/auth/login/route.ts", "frontend/app/api/auth/logout/route.ts", "frontend/app/api/auth/register/route.ts"})
PUBLIC_PYTHON = frozenset({"intelligence/api/health.py", "intelligence/api/security.py"})


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


def python_authority_offenders(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in source_files(root / "intelligence/api", {".py"}):
        rel = relative(root, path)
        source = path.read_text(encoding="utf-8")
        if rel not in PUBLIC_PYTHON and "APIRouter" in source and not re.search(r"Depends\s*\(\s*require_internal_request\s*\)", source):
            offenders.append(rel)
    return sorted(offenders)


PROVIDER_MARKERS = re.compile(r"(?:GoogleGenAI|genai\.Client|GenerativeModel|\bOpenAI\s*\(|from\s+openai\s+import|anthropic|generativelanguage|api\.openai\.com|openrouter\.ai)", re.I)


def provider_offenders(root: Path) -> list[str]:
    approved = {root / "frontend/lib/rlm/provider-adapters.ts", root / "intelligence/execution/adapters.py"}
    offenders = []
    for base in (root / "frontend", root / "intelligence"):
        for path in source_files(base, {".ts", ".tsx", ".py"}):
            if path not in approved and PROVIDER_MARKERS.search(path.read_text(encoding="utf-8")):
                offenders.append(relative(root, path))
    return sorted(offenders)


MUTATION = r"(?:CREATE|MERGE|SET|DELETE|REMOVE|DROP)"
GRAPH_MUTATING_CALL = re.compile(r"(?:session\.run|(?:self\.)?neo4j\.execute|(?:self\.)?neo4j\.execute_(?:write|query))\s*\(\s*(?:f?[`\"']).*?\b" + MUTATION + r"\b", re.I | re.S)


def neo4j_mutation_offenders(root: Path) -> list[str]:
    approved = root / "intelligence/graph/projection.py"
    offenders = []
    for base in (root / "frontend", root / "intelligence"):
        for path in source_files(base, {".ts", ".tsx", ".py"}):
            source = path.read_text(encoding="utf-8")
            if path != approved and GRAPH_MUTATING_CALL.search(source):
                offenders.append(relative(root, path))
    return sorted(offenders)


def runtime_ddl_offenders(root: Path) -> list[str]:
    ddl = re.compile(r"\b(?:CREATE|DROP)\s+(?:CONSTRAINT|INDEX)\b", re.I)
    return sorted(relative(root, path) for base in (root / "frontend", root / "intelligence") for path in source_files(base, {".ts", ".tsx", ".py"}) if ddl.search(path.read_text(encoding="utf-8")))


def test_verifiers_reject_synthetic_negative_controls():
    assert next_authority_offenders(FIXTURES) == ["frontend/app/api/graph/route.ts"]
    assert python_authority_offenders(FIXTURES) == ["intelligence/api/private.py"]
    assert provider_offenders(FIXTURES) == ["frontend/lib/bypass.ts"]
    assert neo4j_mutation_offenders(FIXTURES) == ["intelligence/graph/writer.py"]
    assert runtime_ddl_offenders(FIXTURES) == ["intelligence/graph/writer.py"]


def test_sensitive_next_routes_have_an_awaited_authority_contract():
    offenders = next_authority_offenders(ROOT)
    assert not offenders, "Sensitive Next routes lack awaited requireApiSession: " + ", ".join(offenders)


def test_python_routers_require_internal_authority_dependency():
    offenders = python_authority_offenders(ROOT)
    assert not offenders, "Python routers lack Depends(require_internal_request): " + ", ".join(offenders)


def test_provider_generation_is_limited_to_canonical_task_router_adapters():
    offenders = provider_offenders(ROOT)
    assert not offenders, "Direct model-provider calls bypass canonical adapters: " + ", ".join(offenders)


def test_neo4j_mutations_are_confined_to_projection_service():
    offenders = neo4j_mutation_offenders(ROOT)
    assert not offenders, "Direct Neo4j mutation path(s) outside projection service: " + ", ".join(offenders)


def test_neo4j_schema_ddl_is_not_executed_at_runtime():
    offenders = runtime_ddl_offenders(ROOT)
    assert not offenders, "Runtime Neo4j schema DDL is prohibited: " + ", ".join(offenders)
