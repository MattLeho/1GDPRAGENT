"""Presentation wording guardrails for evidence-constrained privacy claims."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

PREFERRED_PREFIXES = (
    "available export evidence indicates", "appears controller-assigned",
    "observed activity shows", "the combination could technically support",
    "possible purpose drift", "no source evidence currently establishes",
)
PROHIBITED_UNSUPPORTED = (
    "you are ", "knows for certain", "illegal", "abusing", "will survive deletion",
)


class ClaimBasis(str, Enum):
    OBSERVED = "observed"
    CONTROLLER_ASSIGNED = "controller_assigned"
    TECHNICAL_POSSIBILITY = "technical_possibility"
    PURPOSE_DISTANCE = "purpose_distance"
    UNKNOWN = "unknown"


def guarded_statement(statement: str, *, basis: ClaimBasis, direct_evidence: bool = False) -> str:
    clean = " ".join(statement.split()).strip()
    if not clean:
        raise ValueError("presentation statement is required")
    lowered = clean.casefold()
    if not direct_evidence and any(term in lowered for term in PROHIBITED_UNSUPPORTED):
        raise ValueError("unsupported certainty, legal conclusion, abuse claim, or deletion-survival wording")
    prefix = {
        ClaimBasis.OBSERVED: PREFERRED_PREFIXES[0],
        ClaimBasis.CONTROLLER_ASSIGNED: PREFERRED_PREFIXES[1],
        ClaimBasis.TECHNICAL_POSSIBILITY: PREFERRED_PREFIXES[3],
        ClaimBasis.PURPOSE_DISTANCE: PREFERRED_PREFIXES[4],
        ClaimBasis.UNKNOWN: PREFERRED_PREFIXES[5],
    }[basis]
    return f"{prefix}: {clean[0].lower() + clean[1:]}"
