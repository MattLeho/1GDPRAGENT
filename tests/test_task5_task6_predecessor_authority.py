"""Static regression checks for the Task 5 authority/profile predecessor repair."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path("/workspace") if Path("/workspace/docker-compose.yml").exists() else Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def route_functions(relative_path: str) -> dict[tuple[str, str], ast.AsyncFunctionDef]:
    tree = ast.parse(read(relative_path))
    routes: dict[tuple[str, str], ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
                and decorator.func.attr in {"get", "post", "put", "delete", "patch"}
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                continue
            routes[(str(decorator.args[0].value), decorator.func.attr.upper())] = node
    return routes


def test_connector_and_retention_routers_fail_closed_on_internal_authority():
    for relative_path in ("intelligence/api/connectors.py", "intelligence/api/retention.py"):
        source = read(relative_path)
        assert "dependencies=[Depends(require_internal_request)]" in source
        assert "require_internal_request" in source

    security = read("intelligence/api/security.py")
    assert "hmac.compare_digest" in security
    assert "internal API authority is not configured" in security
    assert "valid internal API authority required" in security


def test_browser_pairing_bearer_exception_is_exact_and_only_sync_lacks_profile_header():
    security = read("intelligence/api/security.py")
    assert 'request.url.path == "/connectors/browser/sync"' in security
    assert 'request.method == "POST"' in security
    assert "startswith(\"/connectors\")" not in security

    routes = route_functions("intelligence/api/connectors.py")
    assert routes, "connector routes must remain discoverable"
    without_profile = []
    for key, function in routes.items():
        signature = ast.unparse(function.args)
        if "Depends(require_profile_id)" not in signature:
            without_profile.append(key)
    assert without_profile == [("/browser/sync", "POST")]

    sync_source = ast.unparse(routes[("/browser/sync", "POST")])
    assert "Header(default=None)" in sync_source
    assert "authorization.startswith('Bearer ')" in sync_source
    assert "BrowserBridgeService().receive(frame, authorization[7:])" in sync_source


def test_profile_ownership_checks_cover_connector_and_retention_mutations():
    connectors = read("intelligence/api/connectors.py")
    assert "list_instances(profile_id=profile_id)" in connectors
    assert "enabled_permissions=body.enabled_permissions, profile_id=profile_id" in connectors
    assert connectors.count("instance.profile_id != profile_id") >= 5
    assert "ci.profile_id=$2" in connectors

    retention = read("intelligence/api/retention.py")
    for helper in ("_require_plan_profile", "_require_item_profile", "_require_decision_profile"):
        assert f"async def {helper}" in retention
    for ownership_join in (
        "rp.profile_id=$2",
        "es.profile_id=$2",
        "WHERE profile_id=$1",
    ):
        assert ownership_join in retention
    for guarded_call in (
        "await _require_decision_profile(decision_id,profile_id)",
        "await _require_plan_profile(plan_id,profile_id)",
        "await _require_item_profile(item_id,profile_id)",
    ):
        assert guarded_call in retention


def test_frontend_uses_signed_sessions_and_authenticated_authority_proxies():
    auth = read("frontend/lib/auth-session.ts")
    assert "createHmac('sha256',secret())" in auth
    assert "timingSafeEqual" in auth
    assert "issuedAt>Date.now()+60_000" in auth
    assert "Date.now()-value.issuedAt>maxAgeMs" in auth

    api_session = read("frontend/lib/api-session.ts")
    assert "verifySessionToken(token)" in api_session
    assert "default_profile_id=$2" in api_session
    assert "'x-gdpr-internal-key':key" in api_session
    assert "'x-gdpr-profile-id':profileId" in api_session

    proxy_guard = read("frontend/proxy.ts")
    for path in ("/api/connectors", "/api/retention"):
        assert path in proxy_guard
    assert "gdpr-session" in proxy_guard

    for relative_path in (
        "frontend/app/api/connectors/[[...path]]/route.ts",
        "frontend/app/api/retention/[[...path]]/route.ts",
    ):
        proxy = read(relative_path)
        session_check = proxy.index("await requireApiSession(request)")
        forward = proxy.index("await fetch(url")
        assert session_check < forward
        assert "intelligenceAuthorityHeaders(authority.profileId" in proxy


def test_migration_027_binds_every_user_to_a_canonical_profile():
    migration = read("database/migrations/027_task5_authority_and_profile_scope.sql")
    assert "default_profile_id UUID REFERENCES profiles(id) ON DELETE RESTRICT" in migration
    assert "WHERE default_profile_id IS NULL" in migration
    assert "INSERT INTO profiles(identity_name)" in migration
    assert "UPDATE user_profiles SET default_profile_id=created_profile" in migration
    assert "ALTER COLUMN default_profile_id SET NOT NULL" in migration
    assert "idx_user_profiles_default_profile" in migration
