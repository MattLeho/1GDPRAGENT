"""Evidence-backed deterministic search analysis with privacy-safe summaries."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import re
from uuid import NAMESPACE_URL, UUID, uuid5

from ingestion.models import ActionClass, ActivityEvent

from .models import EvidenceKind, InsightEvidenceRef, InvestigationEpisodeCandidate, SearchInsight


DETECTOR_ID = "task4.search.deterministic"
DETECTOR_VERSION = "1"


def analyse_search_events(
    events: list[ActivityEvent] | tuple[ActivityEvent, ...], *, subject_id: str | None = None,
    analysis_run_id: UUID | None = None, episode_gap: timedelta = timedelta(days=7),
) -> SearchInsight:
    searches = sorted((event for event in events if _is_search(event) and event.occurred_at), key=lambda event: event.occurred_at)  # type: ignore[arg-type]
    subject = subject_id or (searches[0].subject_id if searches else "unknown")
    fingerprints: dict[str, list[ActivityEvent]] = defaultdict(list)
    for event in searches:
        fingerprints[_query_fingerprint(event)].append(event)

    recurring = tuple(
        {"query_fingerprint": key, "count": len(group), "source_count": len({_source(event) for event in group}),
         "revisit_count":sum(1 for previous,current in zip(group,group[1:])
                             if current.occurred_at-previous.occurred_at>=timedelta(hours=24)),
         "first_observed_at":group[0].occurred_at,"latest_observed_at":group[-1].occurred_at}
        for key, group in sorted(fingerprints.items()) if len(group) > 1
    )
    chains = _refinement_chains(searches)
    grouped = _episode_groups(searches, episode_gap)
    episodes = tuple(_episode(group, events, subject, analysis_run_id) for group in grouped if _episode_worthy(group))
    episode_ids = {event.event_id for group in grouped if _episode_worthy(group) for event in group}
    abandoned = sum(1 for group in fingerprints.values() if len(group) == 1 and group[0].event_id not in episode_ids)
    evidence = tuple(_evidence(event) for event in searches)
    insight_id = uuid5(NAMESPACE_URL, f"{DETECTOR_ID}:{subject}:{','.join(str(e.event_id) for e in searches)}")
    return SearchInsight(
        insight_id=insight_id, detector_id=DETECTOR_ID, detector_version=DETECTOR_VERSION,
        analysis_run_id=analysis_run_id, recurring_queries=recurring,
        emerging_clusters=_topic_clusters(searches), refinement_chains=chains,
        abandoned_one_offs=abandoned, episodes=episodes, evidence=evidence,
        calculated_features={"search_count": len(searches), "recurring_fingerprint_count": len(recurring),
                             "total_revisit_count":sum(int(item["revisit_count"]) for item in recurring)},
    )


def _episode(group: list[ActivityEvent], all_events: list[ActivityEvent] | tuple[ActivityEvent, ...], subject: str, run_id: UUID | None) -> InvestigationEpisodeCandidate:
    start, end = group[0].occurred_at, group[-1].occurred_at
    assert start is not None and end is not None
    sources = {_source(event) for event in group}
    topics = sorted({topic for event in group for topic in _topics(event)})
    transition = any(_project_transition(group, event, topics) for event in all_events)
    fingerprints = [_query_fingerprint(event) for event in group]
    recurrence = len(fingerprints) - len(set(fingerprints))
    evidence = tuple(_evidence(event) for event in group)
    return InvestigationEpisodeCandidate(
        insight_id=uuid5(NAMESPACE_URL, f"{DETECTOR_ID}:episode:{','.join(str(e.event_id) for e in group)}"),
        detector_id=DETECTOR_ID, detector_version=DETECTOR_VERSION, analysis_run_id=run_id,
        subject_id=subject, start_at=start, end_at=end, query_count=len(group), recurrence=recurrence,
        domain_diversity=len({_domain(event) for event in group}), refinement_depth=_refinement_depth(group),
        cross_source_count=len(sources), project_transition=transition, topic_labels=tuple(topics), evidence=evidence,
        calculated_features={"event_ids": [str(event.event_id) for event in group]},
    )


def _episode_groups(searches: list[ActivityEvent], gap: timedelta) -> list[list[ActivityEvent]]:
    groups: list[list[ActivityEvent]] = []
    for event in searches:
        if (not groups or event.occurred_at - groups[-1][-1].occurred_at > gap  # type: ignore[operator]
                or not _related_search(groups[-1], event)):
            groups.append([event])
        else:
            groups[-1].append(event)
    return groups


def _episode_worthy(group: list[ActivityEvent]) -> bool:
    return len(group) >= 2 and (len({_source(event) for event in group}) >= 2 or len(group) >= 3)


def _related_search(group: list[ActivityEvent], event: ActivityEvent) -> bool:
    event_topics = set(_topics(event))
    event_tokens = set(_tokens(_raw_query(event)))
    for previous in group:
        if event_topics and event_topics.intersection(_topics(previous)):
            return True
        previous_tokens = set(_tokens(_raw_query(previous)))
        if event_tokens and previous_tokens and event_tokens.intersection(previous_tokens):
            return True
    return False


def _refinement_chains(searches: list[ActivityEvent]) -> tuple[dict[str, object], ...]:
    chains: list[dict[str, object]] = []
    current: list[ActivityEvent] = []
    for event in searches:
        if current and _is_refinement(current[-1], event):
            current.append(event)
        else:
            if len(current) > 1:
                chains.append(_chain_summary(current))
            current = [event]
    if len(current) > 1:
        chains.append(_chain_summary(current))
    return tuple(chains)


def _chain_summary(chain: list[ActivityEvent]) -> dict[str, object]:
    return {"query_fingerprints": tuple(_query_fingerprint(event) for event in chain), "depth": len(chain) - 1, "event_ids": tuple(str(event.event_id) for event in chain)}


def _is_refinement(previous: ActivityEvent, current: ActivityEvent) -> bool:
    if previous.occurred_at and current.occurred_at and current.occurred_at - previous.occurred_at > timedelta(hours=2):
        return False
    parent = current.relationships.get("refines_event_id")
    if parent and str(parent) == str(previous.event_id):
        return True
    before, after = set(_tokens(_raw_query(previous))), set(_tokens(_raw_query(current)))
    return bool(before) and before < after


def _project_transition(searches: list[ActivityEvent], event: ActivityEvent, topics: list[str]) -> bool:
    if event.action_class not in {ActionClass.CREATED, ActionClass.EDITED, ActionClass.CODED} or not event.occurred_at:
        return False
    end = searches[-1].occurred_at
    if end is None or not (end <= event.occurred_at <= end + timedelta(days=30)):
        return False
    linked = {str(item) for item in event.relationships.get("source_event_ids", [])}
    if linked.intersection(str(search.event_id) for search in searches):
        return True
    return bool(set(topics).intersection(_topics(event)))


def _topic_clusters(events: list[ActivityEvent]) -> tuple[dict[str, object], ...]:
    counts: dict[str, set[UUID]] = defaultdict(set)
    for event in events:
        for topic in _topics(event):
            counts[topic].add(event.event_id)
    return tuple({"topic_label": topic, "event_count": len(ids)} for topic, ids in sorted(counts.items()) if len(ids) >= 2)


def _is_search(event: ActivityEvent) -> bool:
    return event.action_class is ActionClass.SEARCHED or event.data_domain.casefold() in {"search", "search_history"}


def _raw_query(event: ActivityEvent) -> str:
    if isinstance(event.object_value, str):
        return event.object_value
    if isinstance(event.object_value, dict):
        return str(event.object_value.get("query") or event.object_value.get("text") or "")
    return ""


def _query_fingerprint(event: ActivityEvent) -> str:
    normalized = " ".join(_tokens(_raw_query(event))) or f"event:{event.event_id}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _topics(event: ActivityEvent) -> tuple[str, ...]:
    value = event.relationships.get("topic_labels") or event.relationships.get("topics") or []
    if isinstance(value, str):
        value = [value]
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _source(event: ActivityEvent) -> str:
    return (event.service or event.product or _domain(event) or "unknown").casefold()


def _domain(event: ActivityEvent) -> str:
    return str(event.relationships.get("domain") or event.identifiers.get("domain") or "unknown").casefold()


def _refinement_depth(group: list[ActivityEvent]) -> int:
    return max((int(chain["depth"]) for chain in _refinement_chains(group)), default=0)


def _evidence(event: ActivityEvent) -> InsightEvidenceRef:
    return InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT, ref_id=event.event_id, occurred_at=event.occurred_at, artifact_id=event.artifact_id, locator_id=event.source_locator_id)


# American-spelling alias for API/service callers.
analyze_search_events = analyse_search_events
