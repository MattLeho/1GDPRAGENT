"""R1 static authority coverage for every Next.js app API route.

The explicit inventory is intentional: adding a route or method must fail this test
until its authority policy is reviewed and recorded.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "frontend" / "app" / "api"

PUBLIC = "public"
READ = "authenticated read"
MUTATION = "authenticated mutation"
INTERNAL = "internal only"
OAUTH = "OAuth callback"
SENSITIVE = {READ, MUTATION, INTERNAL}


ROUTES: dict[str, dict[str, str]] = {
    "auth/check-setup": {"GET": PUBLIC},
    "auth/login": {"POST": PUBLIC},
    "auth/logout": {"POST": PUBLIC},
    "auth/register": {"POST": PUBLIC},
    "auth/session": {"GET": READ},
    "connectors/[[...path]]": {"GET": READ, "POST": MUTATION, "PUT": MUTATION, "DELETE": MUTATION},
    "execution": {"POST": MUTATION},
    "gdpr-agent/analyze-policy": {"POST": MUTATION},
    "gdpr-agent/draft": {"POST": MUTATION},
    "graph": {"GET": READ},
    "graph/chat": {"POST": MUTATION},
    "graph/nodes": {"POST": MUTATION, "PUT": MUTATION, "DELETE": MUTATION},
    "graph/nodes/bulk": {"POST": MUTATION},
    "graph/nodes/merge": {"POST": MUTATION},
    "graph/stats": {"GET": READ},
    "graph/upsert-identity": {"POST": MUTATION},
    "identities": {"GET": READ},
    "identities/account": {"POST": MUTATION},
    "ingestion/benchmark-invoke": {"POST": MUTATION},
    "ingestion/feature-adjudication": {"POST": MUTATION},
    "ingestion/schema-interpretation": {"POST": MUTATION},
    "insights/[module]": {"GET": READ},
    "insights/context-events": {"POST": MUTATION},
    "insights/evidence/[id]": {"GET": READ},
    "insights/media-analysis": {"GET": READ, "POST": MUTATION},
    "insights/media-location-confirmations": {"POST": MUTATION},
    "n8n/analyze-policy": {"POST": MUTATION},
    "n8n/test-imap": {"POST": MUTATION},
    "onsit/bulk": {"POST": MUTATION},
    "onsit/discover": {"POST": MUTATION},
    "onsit/discover-dpo": {"POST": MUTATION},
    "onsit/export": {"GET": READ},
    "onsit/extract-vendors": {"POST": MUTATION},
    "onsit/findings/[id]": {"GET": READ, "DELETE": MUTATION},
    "onsit/send-bulk-emails": {"POST": MUTATION},
    "onsit/status/[taskId]": {"GET": READ},
    "onsit/vendor-bulk-email": {"POST": MUTATION},
    "onsit/vendor-domain-search": {"POST": MUTATION},
    "onsit/vendor-dpo-discovery": {"POST": MUTATION},
    "policy/check": {"POST": MUTATION},
    "request-threads": {"GET": READ, "POST": MUTATION},
    "request-threads/[id]/chat": {"GET": READ, "POST": MUTATION},
    "requests/[id]": {"DELETE": MUTATION},
    "requests/[id]/logs": {"GET": READ},
    "retention/[[...path]]": {"GET": READ, "POST": MUTATION},
    "settings/ai-credentials": {"GET": READ, "POST": MUTATION},
    "settings/ai-models": {"GET": READ},
    "settings/api-credentials": {"GET": READ, "POST": MUTATION},
    "settings/engine-health/[engineId]": {"GET": READ},
    "settings/execution-audit": {"GET": READ},
    "settings/id-documents": {"GET": READ, "POST": MUTATION, "DELETE": MUTATION},
    "settings/model-preferences": {"GET": READ, "POST": MUTATION},
    "settings/n8n-webhooks": {"GET": READ, "POST": MUTATION},
    "settings/processing": {"GET": READ, "POST": MUTATION},
    "settings/profile": {"GET": READ, "POST": MUTATION, "PUT": MUTATION},
    "settings/profile/password": {"POST": MUTATION},
    "settings/task-routes": {"GET": READ, "POST": MUTATION},
    "settings/workflows": {"GET": READ, "POST": MUTATION},
    "upload": {"GET": READ, "POST": MUTATION, "PATCH": MUTATION, "DELETE": MUTATION},
    "upload/process": {"POST": MUTATION, "PUT": MUTATION},
    "upload/scan": {"POST": MUTATION},
    "workflows/inbox-monitor": {"POST": MUTATION},
}


def route_files() -> dict[str, Path]:
    return {
        path.parent.relative_to(API_ROOT).as_posix(): path
        for path in API_ROOT.rglob("route.ts")
    }


def exported_methods(source: str) -> set[str]:
    return set(re.findall(r"export\s+(?:async\s+function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b", source))


class RouteAuthorityCoverage(unittest.TestCase):
    def test_every_route_and_method_is_classified(self) -> None:
        files = route_files()
        self.assertEqual(set(files), set(ROUTES), "New or removed API route requires an authority review")
        for route, path in files.items():
            self.assertEqual(exported_methods(path.read_text(encoding="utf-8")), set(ROUTES[route]), route)

    def test_sensitive_routes_use_the_canonical_guard(self) -> None:
        for route, methods in ROUTES.items():
            if not any(policy in SENSITIVE for policy in methods.values()):
                continue
            source = route_files()[route].read_text(encoding="utf-8")
            self.assertIn("await requireApiSession(", source, route)

    def test_personal_insights_subject_is_authority_derived(self) -> None:
        source = route_files()["insights/[module]"].read_text(encoding="utf-8")
        self.assertIn("query.set('subject_id', authority.profileId)", source)
        self.assertNotRegex(source, r"SELECT\s+id\s+FROM\s+user_profiles.*LIMIT\s+1")


if __name__ == "__main__":
    unittest.main()
