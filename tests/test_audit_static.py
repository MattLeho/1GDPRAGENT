from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def service_block(compose: str, service_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(service_name)}:\n(?P<block>.*?)(?=^  [A-Za-z0-9_-]+:\n|^networks:\n|^volumes:\n|\Z)",
        compose,
    )
    assert match, f"{service_name} service should be defined in docker-compose.yml."
    return match.group("block")


def test_compose_host_ports_are_configurable_to_avoid_local_collisions():
    compose = read("docker-compose.yml")

    hard_coded_bindings = [
        '"3000:3000"',
        '"8000:8000"',
        '"5432:5432"',
    ]

    for binding in hard_coded_bindings:
        assert binding not in compose, (
            f"{binding} is hard-coded; host ports should be configurable so the "
            "GDPR stack can run beside other local containers."
        )


def test_next_proxy_convention_replaces_deprecated_middleware():
    proxy_path = ROOT / "frontend/proxy.ts"
    middleware_path = ROOT / "frontend/middleware.ts"

    assert proxy_path.exists(), "Next.js 16 proxy convention should use frontend/proxy.ts."
    assert not middleware_path.exists(), "frontend/middleware.ts is deprecated in Next.js 16."

    proxy = read("frontend/proxy.ts")

    assert "export function proxy" in proxy, "frontend/proxy.ts should export a proxy function."
    assert "export function middleware" not in proxy, "Deprecated middleware export should not remain."


def test_compose_defines_n8n_and_celery_healthchecks():
    compose = read("docker-compose.yml")
    n8n = service_block(compose, "n8n")
    celery = service_block(compose, "celery-worker")

    assert "healthcheck:" in n8n and "/healthz/readiness" in n8n, (
        "n8n should expose a Docker healthcheck using its readiness endpoint."
    )
    assert "healthcheck:" in celery and "celery -A tasks inspect ping" in celery, (
        "celery-worker should expose a Docker healthcheck that pings the worker."
    )
    assert "$$HOSTNAME" in celery, (
        "Celery healthcheck should escape HOSTNAME so Docker Compose passes it "
        "to the container shell."
    )


def test_initial_schema_defines_tables_used_by_routes_and_migrations():
    schema = read("docker/init/01_schema.sql")

    assert re.search(r"CREATE TABLE IF NOT EXISTS\s+vendor_lists\b", schema, re.I), (
        "ONSIT vendor routes and migration 006 use vendor_lists, but the "
        "initial schema does not create that table."
    )


def test_request_routes_use_columns_present_in_initial_schema():
    schema = read("docker/init/01_schema.sql")
    send_bulk = read("frontend/app/api/onsit/send-bulk-emails/route.ts")

    assert "company_name" in send_bulk, (
        "send-bulk-emails should use requests.company_name; the schema does not "
        "define a requests.company column."
    )
    assert "date_started" not in send_bulk or "date_started" in schema, (
        "send-bulk-emails inserts date_started, but requests has created_at "
        "instead in the initial schema."
    )


def test_chat_route_matches_initial_chat_message_schema():
    schema = read("docker/init/01_schema.sql")
    chat_route = read("frontend/app/api/request-threads/[id]/chat/route.ts")

    schema_uses_sender_message = "sender TEXT NOT NULL" in schema and "message TEXT NOT NULL" in schema
    route_uses_sender_message = "sender as role" in chat_route and "message as content" in chat_route

    assert schema_uses_sender_message and route_uses_sender_message, (
        "request_chat_messages must use sender/message consistently between "
        "the init schema and chat route."
    )


def test_example_env_does_not_contain_live_looking_secrets():
    example = read(".env.example")

    forbidden_patterns = [
        r"AIza[0-9A-Za-z_-]{20,}",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"eyJhbGciOiJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    ]

    for pattern in forbidden_patterns:
        assert not re.search(pattern, example), (
            ".env.example should contain placeholders only, not live-looking secrets."
        )
