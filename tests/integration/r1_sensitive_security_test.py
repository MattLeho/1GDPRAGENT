"""Independent static guard-order audit for every sensitive Next.js API method.

This complements route-handler unit tests: it discovers routes from disk, so a newly
added API cannot silently escape the unauthenticated coverage inventory.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "frontend" / "app" / "api"
PUBLIC = {
    ("auth/check-setup", "GET"),
    ("auth/login", "POST"),
    ("auth/logout", "POST"),
    ("auth/register", "POST"),
}
DIRECT_EXPORT = re.compile(r"export\s+async\s+function\s+(GET|POST|PUT|PATCH|DELETE)\b")
NAMED_FUNCTION = re.compile(r"(?:export\s+)?async\s+function\s+([A-Za-z_$][\w$]*)\b")
CONST_ALIAS = re.compile(r"export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\s*=\s*([A-Za-z_$][\w$]*)")
ESM_ALIAS = re.compile(r"([A-Za-z_$][\w$]*)\s+as\s+(GET|POST|PUT|PATCH|DELETE)")


def route_methods():
    for path in API_ROOT.rglob("route.ts"):
        route = path.parent.relative_to(API_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        functions = list(NAMED_FUNCTION.finditer(source))
        bodies = {}
        for index, match in enumerate(functions):
            end = functions[index + 1].start() if index + 1 < len(functions) else len(source)
            bodies[match.group(1)] = source[match.start():end]
        emitted = set()
        for match in DIRECT_EXPORT.finditer(source):
            method = match.group(1)
            emitted.add(method)
            yield route, method, bodies[method]
        for match in CONST_ALIAS.finditer(source):
            method, handler = match.groups()
            if method not in emitted and handler in bodies:
                emitted.add(method)
                yield route, method, bodies[handler]
        for match in ESM_ALIAS.finditer(source):
            handler, method = match.groups()
            if method not in emitted and handler in bodies:
                emitted.add(method)
                yield route, method, bodies[handler]


def test_every_non_public_api_method_checks_canonical_session_before_sensitive_work():
    discovered = list(route_methods())
    assert discovered, "no Next.js API methods discovered"
    for route, method, body in discovered:
        if (route, method) in PUBLIC:
            continue
        guard = body.find("await requireApiSession(")
        assert guard >= 0, f"{method} /api/{route} lacks canonical session authority"
        sensitive_positions = [position for token in ("pool.query(", ".query(`", "fetch(", "request.json(", "request.formData(")
                               if (position := body.find(token)) >= 0]
        if sensitive_positions:
            assert guard < min(sensitive_positions), f"{method} /api/{route} performs sensitive work before authority"


def test_mutation_guard_contract_enforces_origin_and_csrf_marker():
    source = (ROOT / "frontend/lib/api-session.ts").read_text(encoding="utf-8")
    assert "enforceSameOriginMutation(request)" in source
    assert "CSRF_ORIGIN_MISMATCH" in source
    assert "x-gdpr-csrf" in source
    assert "CSRF_REQUIRED" in source


def test_graph_query_parameters_cannot_shadow_canonical_profile_authority():
    source = (API_ROOT / "graph/route.ts").read_text(encoding="utf-8")
    unsafe = re.compile(r"profileId:\s*authority\.profileId,\s*\.\.\.Object\.fromEntries\(request\.nextUrl\.searchParams\)")
    assert not unsafe.search(source), "caller query profileId currently overwrites session authority"
