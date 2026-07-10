from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5


@lru_cache
def ontology() -> dict:
    path=Path(__file__).resolve().parents[2]/"ontology"/"graph-ontology.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_personal_label(label: str) -> str:
    allowed=set(ontology()["personal_data_labels"])-{"GraphNode"}
    if label not in allowed: raise ValueError(f"{label!r} is not a personal-data ontology label")
    return label


def assert_graph_label(label: str) -> str:
    allowed=(set(ontology()["personal_data_labels"])-{"GraphNode"}) | set(ontology()["onsit_labels"])
    if label not in allowed: raise ValueError(f"{label!r} is not a canonical graph label")
    return label


def is_onsit_label(label: str) -> bool:
    return label in ontology()["onsit_labels"]


def stable_node_id(label: str, canonical_key: str) -> UUID:
    if not canonical_key.strip(): raise ValueError("canonical key cannot be empty")
    return uuid5(NAMESPACE_URL,f"1gdpragent:{label}:{canonical_key}")


def canonical_entity_key(entity_type: str, value: str, *, controller: str | None=None, service: str | None=None, identifier_type: str | None=None) -> str:
    kind=entity_type.strip().lower()
    raw=value.strip()
    if not raw: raise ValueError("entity value cannot be empty")
    if kind=="email": normalized=raw.casefold()
    elif kind=="phone":
        normalized="+"+re.sub(r"\D","",raw) if raw.startswith("+") else re.sub(r"\D","",raw)
    elif kind in {"organisation","organization"}: normalized=re.sub(r"[^a-z0-9]+","-",raw.casefold()).strip("-")
    elif kind=="account":
        if not controller and not service: raise ValueError("account keys require controller or service scope")
        normalized=f"{(controller or '').casefold()}|{(service or '').casefold()}|{raw.casefold()}"
    elif kind in {"identifier","opaqueidentifier"}:
        if not identifier_type: raise ValueError("opaque identifiers require identifier_type")
        if not controller and not service: raise ValueError("opaque identifiers require controller or service scope")
        normalized=f"{identifier_type.casefold()}|{(controller or '').casefold()}|{(service or '').casefold()}|{raw.casefold()}"
    else: normalized=raw.casefold()
    return f"{kind}:{normalized}"


def relationship_type(predicate: str) -> str:
    candidate=re.sub(r"[^A-Z0-9_]","_",predicate.upper())
    return candidate if candidate in ontology()["relationships"] else "RELATES_TO"
