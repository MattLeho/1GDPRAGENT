"""Versioned, local inference-language candidate detection."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from uuid import UUID

from ingestion.models import FeatureCandidate, FeatureCandidateStatus


DETECTOR_ID = "task3.inference_language.dictionary"
DETECTOR_VERSION = "1.0.0"

INFERENCE_TERMS = (
    "predicted", "inferred", "estimated", "likely", "probability", "confidence",
    "segment", "audience", "interest", "affinity", "classification", "propensity",
    "score", "risk", "profile", "recommendation", "personalisation", "personalization",
    "lookalike",
)

_TERM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(re.escape(term) for term in sorted(INFERENCE_TERMS, key=len, reverse=True)) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _flatten_text(value: object, prefix: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, Mapping):
        for key in sorted(value, key=lambda item: str(item)):
            key_text = str(key)
            yield f"{prefix}.<key>", key_text
            yield from _flatten_text(value[key], f"{prefix}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _flatten_text(item, f"{prefix}[{index}]")


def _bounded_context(text: str, start: int, end: int, radius: int) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right]


def detect_inference_language(
    value: object,
    *,
    source_event_ids: Iterable[UUID] = (),
    source_artifact_ids: Iterable[UUID] = (),
    context_radius: int = 60,
    maximum_matches: int = 64,
) -> tuple[FeatureCandidate, ...]:
    """Return grounded candidates; never assert that an inference occurred."""
    if context_radius < 0 or context_radius > 500:
        raise ValueError("context_radius must be between 0 and 500")
    if maximum_matches < 1 or maximum_matches > 1_000:
        raise ValueError("maximum_matches must be between 1 and 1000")
    event_ids = tuple(source_event_ids)
    artifact_ids = tuple(source_artifact_ids)
    matches: list[dict[str, object]] = []
    total_match_count = 0
    for path, text in _flatten_text(value):
        for match in _TERM_PATTERN.finditer(text):
            total_match_count += 1
            if len(matches) < maximum_matches:
                matches.append(
                    {
                        "term": match.group(0).casefold(),
                        "path": path,
                        "context": _bounded_context(text, match.start(), match.end(), context_radius),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
    if total_match_count == 0:
        return ()
    # One bounded candidate per source value prevents dictionary hits from
    # multiplying semantic work while retaining every mechanical match.
    return (
        FeatureCandidate(
            feature_type="inference_language_candidate",
            detector_id=DETECTOR_ID,
            detector_version=DETECTOR_VERSION,
            source_event_ids=event_ids,
            source_artifact_ids=artifact_ids,
            calculated_values={
                "matches": matches,
                "matched_terms": sorted({str(item["term"]) for item in matches}),
                "match_count": total_match_count,
                "omitted_match_count": total_match_count - len(matches),
                "semantic_claim": None,
            },
            rule_result=True,
            candidate_status=FeatureCandidateStatus.ADJUDICATION_REQUIRED,
        ),
    )
