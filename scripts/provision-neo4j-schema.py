#!/usr/bin/env python3
"""Provision Neo4j constraints outside application request/worker runtime."""

from __future__ import annotations

import json
import os
from base64 import b64encode
from urllib.request import Request, urlopen


def execute(statement: str) -> None:
    uri = os.getenv("NEO4J_HTTP_URI", "http://localhost:7474").rstrip("/")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASSWORD"]
    authorization = b64encode(f"{user}:{password}".encode()).decode()
    body = json.dumps({"statements": [{"statement": statement}]}).encode()
    request = Request(
        f"{uri}/db/neo4j/tx/commit",
        data=body,
        method="POST",
        headers={"Authorization": f"Basic {authorization}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])


if __name__ == "__main__":
    execute("CREATE CONSTRAINT graph_node_id IF NOT EXISTS FOR (n:GraphNode) REQUIRE n.node_id IS UNIQUE")
    execute("CREATE INDEX assertion_edge_id IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.assertion_id)")
