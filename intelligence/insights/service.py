"""Personal Insights application service.

One cold request builds a complete, evidence-indexed snapshot from canonical
partitions and temporal catalogues. Every module endpoint then reads that same
versioned snapshot cache; cards never perform independent full event scans.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid5

from db.postgres import PostgresClient, get_postgres_client
from ingestion.models import ActionClass, ActivityEvent
from insights.ai_conversations import analyse_ai_conversations
from insights.context import ExposureObservation, correlate_change, semantic_relevance, temporal_proximity
from insights.evidence import InsightEvidenceTracer
from insights.materialization import (
    DERIVATION_METHOD, DERIVATION_VERSION, INSIGHT_NAMESPACE,
    floor_bucket, materialisation_cache_key, next_bucket,
)
from insights.media import (
    LocationObservation, build_place_insight, classify_media_origin,
    create_location_candidate, create_media_content_candidate,
)
from insights.models import (
    ActivityDensityBin, ChangeInsight, EvidenceKind, ExternalContextEvent, InsightComparisonPeriod,
    InsightEngagementProfile, InsightEvidenceRef, InsightPeriod, InsightSnapshot,
    LocationBasis, LocationEvidenceClass, MediaLocationCandidate, MediaOrigin,
    ObservedInterestState, PeriodGranularity, PeriodOverview, PersonalEraView,
    ProjectEpisodeView, SignalClass, TemporalMode,
)
from insights.repository import InsightRepository
from insights.search import analyse_search_events
from insights.signals import ClassifiedSignal, classify_events, effective_signal_weight
from temporal.interest import aggregate_interest_states
from temporal.models import TopicAssignment
from temporal.routines import build_routine_distributions, build_routine_drift


SNAPSHOT_VERSION = "2.0.0"
API_EVIDENCE_REFERENCE_LIMIT = 100


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _bounds(period: InsightPeriod) -> tuple[datetime, datetime]:
    if period.mode is TemporalMode.POINT_IN_TIME:
        assert period.point_at is not None
        granularity = period.granularity if period.granularity is not PeriodGranularity.CUSTOM else PeriodGranularity.DAY
        return floor_bucket(period.point_at, granularity), period.point_at + timedelta(microseconds=1)
    assert period.from_at is not None and period.to_at is not None
    return period.from_at, period.to_at


def _event_ref(event: ActivityEvent, *, role: str = "supporting", weight: float | None = None) -> InsightEvidenceRef:
    return InsightEvidenceRef(
        kind=EvidenceKind.ACTIVITY_EVENT, ref_id=event.event_id, role=role,
        occurred_at=event.occurred_at, artifact_id=event.artifact_id,
        locator_id=event.source_locator_id, weight=weight,
    )


def _topics(event: ActivityEvent) -> tuple[str, ...]:
    value = event.relationships.get("topic_labels") or event.relationships.get("topics") or ()
    if isinstance(value, str): value = (value,)
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _topic_assignments(events: tuple[ActivityEvent, ...], rows: Iterable[dict[str, Any]]) -> tuple[TopicAssignment, ...]:
    result: list[TopicAssignment] = []
    event_ids = {event.event_id for event in events}
    for row in rows:
        source_ids = tuple(UUID(str(value)) for value in row["source_event_ids"] if UUID(str(value)) in event_ids)
        if source_ids:
            result.append(TopicAssignment(
                topic_id=row["topic_id"], topic_path=tuple(row["topic_path"]),
                source_event_ids=source_ids, assignment_method=row["assignment_method"],
                assignment_version=row["assignment_version"], confidence=float(row["confidence"]),
            ))
    for event in events:
        for topic in _topics(event):
            path = tuple(part for part in topic.split("/") if part) or (topic,)
            result.append(TopicAssignment(
                topic_id=topic, topic_path=path, source_event_ids=(event.event_id,),
                assignment_method="source-explicit-topic", assignment_version="1", confidence=1.0,
            ))
    return tuple(result)


def _engagement(
    events: tuple[ActivityEvent, ...], signals: tuple[ClassifiedSignal, ...], *,
    subject_id: str, start: datetime, end: datetime, analysis_run_id: UUID | None,
    baseline: "InsightEngagementProfile | None" = None,
) -> InsightEngagementProfile:
    counts = Counter(signal.signal_class.value for signal in signals)
    names = {
        "ambient_exposure":SignalClass.AMBIENT_EXPOSURE,
        "passive_consumption":SignalClass.PASSIVE_CONSUMPTION,
        "active_investigation":SignalClass.ACTIVE_INVESTIGATION,
        "creation":SignalClass.CREATION,
        "implementation":SignalClass.IMPLEMENTATION,
        "communication":SignalClass.COMMUNICATION,
        "disengagement":SignalClass.DISENGAGEMENT,
    }
    values = {name:float(counts[value.value]) for name,value in names.items()}
    delta = {name:values[name] - float(getattr(baseline,name)) for name in names} if baseline else {}
    identity = uuid5(INSIGHT_NAMESPACE, f"engagement:{subject_id}:{start.isoformat()}:{end.isoformat()}:{SNAPSHOT_VERSION}")
    return InsightEngagementProfile(
        insight_id=identity, detector_id="task4.signal-hierarchy", detector_version=SNAPSHOT_VERSION,
        analysis_run_id=analysis_run_id, calculated_features={
            "event_count":len(events),
            "average_source_reliability":(sum(signal.source_reliability for signal in signals)/len(signals) if signals else 0.0),
            "source_rules":dict(Counter(signal.source_rule for signal in signals)),
        },
        evidence=tuple(_event_ref(signal.event, role="exposure" if not signal.interest_contributing else "supporting", weight=signal.weight) for signal in signals),
        subject_id=subject_id, window_start=start, window_end=end,
        comparison_delta=delta, **values,
    )


def _peak_time(events: Iterable[ActivityEvent]) -> datetime | None:
    counts: dict[datetime, int] = defaultdict(int)
    for event in events:
        if event.occurred_at:
            counts[event.occurred_at.replace(hour=0,minute=0,second=0,microsecond=0)] += 1
    return min(((-count, at) for at,count in counts.items()), default=(0,None))[1]


def _interest_views(
    *, subject_id: str, events: tuple[ActivityEvent, ...], signals: tuple[ClassifiedSignal, ...],
    assignments: tuple[TopicAssignment, ...], search_episode_ids: set[UUID],
    start: datetime, end: datetime, baseline_events: tuple[ActivityEvent, ...],
    prior_topic_ids: set[str], analysis_run_id: UUID | None,
    baseline_states: Mapping[str, ObservedInterestState] | None = None,
) -> tuple[ObservedInterestState, ...]:
    signal_by_id = {signal.event.event_id:signal for signal in signals}
    effective_weights = {
        event_id: effective_signal_weight(signal, as_of=end)
        for event_id, signal in signal_by_id.items()
    }
    contributing = {
        event_id for event_id,signal in signal_by_id.items()
        if signal.interest_contributing and (signal.event.action_class is not ActionClass.SEARCHED or event_id in search_episode_ids)
    }
    filtered_events = tuple(event for event in events if event.event_id in contributing)
    filtered_assignments = tuple(
        assignment.model_copy(update={"source_event_ids":tuple(value for value in assignment.source_event_ids if value in contributing)})
        for assignment in assignments if any(value in contributing for value in assignment.source_event_ids)
    )
    states = aggregate_interest_states(
        filtered_events, filtered_assignments, subject_id=subject_id,
        window_start=start, window_end=end,
        previously_seen_event_ids=(event.event_id for event in baseline_events),
    )
    result = []
    comparison_fields = ("intensity","persistence","recurrence","breadth","novelty","context_dispersion")
    event_by_id = {event.event_id:event for event in filtered_events}
    baseline_topics = {topic for event in baseline_events for topic in _topics(event)}
    for state in states:
        topic_events = [event_by_id[value] for value in state.evidence_event_ids]
        average_weight = sum(effective_weights[event.event_id] for event in topic_events) / len(topic_events)
        if state.topic_id in prior_topic_ids and state.topic_id not in baseline_topics:
            change = "returning"
        elif len(topic_events) == 1:
            change = "one_off"
        elif state.topic_id not in baseline_topics:
            change = "emerging"
        else:
            change = "continuing"
        current_dimensions = {
            "intensity":state.intensity * average_weight,
            "persistence":state.persistence,"recurrence":state.recurrence,"breadth":state.breadth,
            "novelty":state.novelty,"context_dispersion":state.context_dispersion,
        }
        baseline_state = (baseline_states or {}).get(state.topic_id)
        previous = ({name:float(getattr(baseline_state,name)) for name in comparison_fields} if baseline_state else {})
        result.append(ObservedInterestState(
            insight_id=uuid5(INSIGHT_NAMESPACE, f"interest:{subject_id}:{state.topic_id}:{start.isoformat()}:{end.isoformat()}:{SNAPSHOT_VERSION}"),
            detector_id=state.detector_id, detector_version=state.detector_version,
            analysis_run_id=analysis_run_id,
            calculated_features={"signal_weight":average_weight,"evidence_count":len(topic_events)},
            evidence=tuple(_event_ref(event, weight=effective_weights[event.event_id]) for event in topic_events),
            subject_id=subject_id, topic_id=state.topic_id, topic_path=state.topic_path,
            window_start=start, window_end=end, **current_dimensions,
            first_observed_at=min(event.occurred_at for event in topic_events if event.occurred_at),
            latest_observed_at=max(event.occurred_at for event in topic_events if event.occurred_at),
            peak_at=_peak_time(topic_events),
            source_domains=tuple(sorted({event.data_domain for event in topic_events})), change=change,
            previous_period_dimensions=previous,
            comparison_delta={name:current_dimensions[name]-previous.get(name,0.0) for name in comparison_fields} if baseline_state else {},
        ))
    return tuple(sorted(result, key=lambda item:(-item.intensity,item.topic_path)))


class InsightService:
    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def get_snapshot(
        self, *, subject_id: str, period: InsightPeriod,
        comparison: InsightComparisonPeriod | None = None,
    ) -> InsightSnapshot:
        pool = await self.postgres._get_pool()
        async with pool.acquire() as connection:
            repository = InsightRepository(connection)
            start,end = _bounds(period)
            await self._materialize_media_locations(connection,subject_id)
            partitions = await repository.discover_event_partitions(from_at=start,to_at=end)
            history_start=start-timedelta(days=730)
            history_partitions=tuple(
                item for item in await repository.discover_event_partitions(from_at=history_start,to_at=start)
                if item.partition_id not in {current.partition_id for current in partitions}
            )
            dependency_tokens = await repository.dependency_tokens(subject_id=subject_id,from_at=start,to_at=end)
            baseline_partitions = ()
            if comparison:
                baseline_start,baseline_end = _bounds(comparison.baseline)
                baseline_partitions = await repository.discover_event_partitions(from_at=baseline_start,to_at=baseline_end)
                dependency_tokens += await repository.dependency_tokens(subject_id=subject_id,from_at=baseline_start,to_at=baseline_end)
            partition_hashes = tuple(item.file_hash for item in (*partitions,*baseline_partitions,*history_partitions)) + dependency_tokens
            cache_key = materialisation_cache_key(
                subject_id=subject_id, period=period, comparison=comparison,
                module_key="snapshot", partition_hashes=partition_hashes,
                derivation_version=SNAPSHOT_VERSION,
            )
            cached = await repository.cached_payload(cache_key,SNAPSHOT_VERSION)
            if cached:
                return InsightSnapshot.model_validate(cached["payload"])
            await connection.execute("SELECT pg_advisory_lock(hashtextextended($1,0))",cache_key)
            try:
                cached = await repository.cached_payload(cache_key,SNAPSHOT_VERSION)
                if cached:
                    return InsightSnapshot.model_validate(cached["payload"])
                return await self._build_snapshot(
                    repository=repository, connection=connection, subject_id=subject_id,
                    period=period, comparison=comparison, partitions=partitions,
                    baseline_partitions=baseline_partitions,history_partitions=history_partitions, cache_key=cache_key,
                    source_tokens=partition_hashes,
                )
            finally:
                await connection.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))",cache_key)

    async def _build_snapshot(
        self, *, repository: InsightRepository, connection, subject_id: str,
        period: InsightPeriod, comparison: InsightComparisonPeriod | None,
        partitions, baseline_partitions, history_partitions=(), cache_key: str="", source_tokens: tuple[str,...]=(),
    ) -> InsightSnapshot:
        start,end = _bounds(period)
        events = repository.load_activity_events(partitions,subject_id=subject_id,from_at=start,to_at=end)
        history_events=repository.load_activity_events(
            history_partitions,subject_id=subject_id,from_at=start-timedelta(days=730),to_at=start,
        )
        baseline_events: tuple[ActivityEvent,...] = ()
        baseline_engagement = None
        baseline_interests: tuple[ObservedInterestState,...] = ()
        baseline_assignments: tuple[TopicAssignment,...] = ()
        if comparison:
            baseline_start,baseline_end = _bounds(comparison.baseline)
            baseline_events = repository.load_activity_events(
                baseline_partitions,subject_id=subject_id,from_at=baseline_start,to_at=baseline_end,
            )
            baseline_signals = classify_events(baseline_events)
            baseline_engagement = _engagement(
                baseline_events,baseline_signals,subject_id=subject_id,start=baseline_start,end=baseline_end,analysis_run_id=None,
            )
            baseline_search = analyse_search_events(baseline_events,subject_id=subject_id,analysis_run_id=None)
            baseline_episode_ids = {ref.ref_id for episode in baseline_search.episodes for ref in episode.evidence if ref.kind is EvidenceKind.ACTIVITY_EVENT}
            baseline_assignment_rows = await repository.read_topic_assignments(event.event_id for event in baseline_events)
            baseline_assignments = _topic_assignments(baseline_events,baseline_assignment_rows)
            baseline_interests = _interest_views(
                subject_id=subject_id,events=baseline_events,signals=baseline_signals,
                assignments=baseline_assignments,search_episode_ids=baseline_episode_ids,
                start=baseline_start,end=baseline_end,baseline_events=(),prior_topic_ids=set(),
                analysis_run_id=None,baseline_states={},
            )
        run_ids = tuple(sorted({item.analysis_run_id for item in (*partitions,*baseline_partitions,*history_partitions)},key=str))
        run_id = run_ids[0] if len(run_ids)==1 else None
        signals = classify_events(events)
        search = analyse_search_events(events,subject_id=subject_id,analysis_run_id=run_id)
        ai = analyse_ai_conversations(events,analysis_run_id=run_id)
        episode_search_ids = {ref.ref_id for episode in search.episodes for ref in episode.evidence if ref.kind is EvidenceKind.ACTIVITY_EVENT}
        assignment_rows = await repository.read_topic_assignments(event.event_id for event in events)
        assignments = _topic_assignments(events,assignment_rows)
        history_assignment_rows=await repository.read_topic_assignments(event.event_id for event in history_events)
        history_assignments=_topic_assignments(history_events,history_assignment_rows)
        accepted_assertions = await repository.read_accepted_assertions(subject_id=subject_id,from_at=start,to_at=end)
        temporal_states = await repository.read_temporal_states(subject_id=subject_id,from_at=start,to_at=end)
        temporal_aggregates = await repository.read_temporal_aggregates(subject_id=subject_id,from_at=start,to_at=end)
        prior_rows = await connection.fetch(
            """SELECT payload FROM insight_materialisations WHERE subject_id=$1 AND module_key='snapshot'
               AND to_at IS NOT NULL AND to_at<=$2 ORDER BY to_at DESC LIMIT 12""",subject_id,start,
        )
        prior_topics = {
            item.get("topic_id") for row in prior_rows
            for item in (json.loads(row["payload"]) if isinstance(row["payload"],str) else row["payload"]).get("interests",[])
        }
        prior_topics.update(topic for event in history_events for topic in _topics(event))
        prior_topics.update(assignment.topic_id for assignment in history_assignments)
        interests = _interest_views(
            subject_id=subject_id,events=events,signals=signals,assignments=assignments,
            search_episode_ids=episode_search_ids,start=start,end=end,baseline_events=baseline_events,
            prior_topic_ids={value for value in prior_topics if value},analysis_run_id=run_id,
            baseline_states={item.topic_id:item for item in baseline_interests},
        )
        interests = self._augment_interest_sources(interests,accepted_assertions,temporal_states)
        engagement = _engagement(events,signals,subject_id=subject_id,start=start,end=end,analysis_run_id=run_id,baseline=baseline_engagement)
        engagement = self._augment_engagement_sources(engagement,temporal_states,temporal_aggregates)
        routine_drifts=()
        if comparison:
            current_routines=build_routine_distributions(events,window_start=start,window_end=end,topic_assignments=assignments)
            baseline_start,baseline_end=_bounds(comparison.baseline)
            baseline_routines=build_routine_distributions(
                baseline_events,window_start=baseline_start,window_end=baseline_end,topic_assignments=baseline_assignments,
            )
            routine_drifts=build_routine_drift(baseline_routines,current_routines)
        granularity = period.granularity if period.granularity is not PeriodGranularity.CUSTOM else PeriodGranularity.DAY
        density,density_rows = await self._selective_density(
            repository=repository,subject_id=subject_id,period=period,
            comparison=comparison,partitions=partitions,events=events,
            start=start,end=end,granularity=granularity,cache_key=cache_key,
        )
        episodes = await repository.read_episode_candidates(subject_id=subject_id,from_at=start,to_at=end)
        eras = await repository.read_personal_eras(subject_id=subject_id,from_at=start,to_at=end)
        project_views = tuple(self._project_view(row,events,run_id) for row in episodes if row["episode_kind"]=="ProjectEpisodeCandidate")
        era_views = tuple(PersonalEraView(
            insight_id=row["id"],detector_id=row["detector_id"],detector_version=row["detector_version"],
            analysis_run_id=row["analysis_run_id"],calculated_features={"change_point_indices":row["change_point_indices"]},
            evidence=tuple(InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT,ref_id=UUID(str(value))) for value in row["evidence_event_ids"]),
            start_at=row["start_at"],end_at=row["end_at"],machine_label=row.get("machine_label"),human_label=row.get("human_label"),
        ) for row in eras)
        changes = self._changes(
            interests,engagement,baseline_engagement,project_views,routine_drifts,run_id,
            baseline_interests=baseline_interests,
        )
        place = await self._places(repository,subject_id,run_id,start,end,project_views)
        correlations = await self._correlations(
            repository,connection,changes,events,signals,run_id,start,end,accepted_assertions,
        )
        overview = PeriodOverview(
            subject_id=subject_id,period=period,active_topic_count=len(interests),
            emerging_topic_count=sum(item.change=="emerging" for item in interests),
            returning_topic_count=sum(item.change=="returning" for item in interests),
            project_episode_count=len(project_views),total_event_count=len(events),density=density,
            engagement=engagement,
        )
        snapshot = InsightSnapshot(
            snapshot_id=uuid5(INSIGHT_NAMESPACE,cache_key),subject_id=subject_id,period=period,
            comparison=comparison,analysis_run_ids=run_ids,derivation_method=DERIVATION_METHOD,
            # The immutable DB row has its own created_at. The payload uses the
            # effective derivation boundary so independent rebuilds are byte-stable.
            derivation_version=SNAPSHOT_VERSION,generated_at=end,
            canonical_source_counts={
                "activity_events":len(events),"accepted_assertions":len(accepted_assertions),
                "temporal_states":len(temporal_states),"temporal_aggregates":len(temporal_aggregates),
                "project_episodes":len(project_views),"personal_eras":len(era_views),
            },overview=overview,
            interests=interests,search=search,ai_conversations=ai,places=place,changes=changes,
            project_episodes=project_views,personal_eras=era_views,contextual_correlations=correlations,
        )
        # Normalise tuple/datetime values nested inside open calculated-feature
        # dictionaries exactly as they will be stored in JSONB. Cold and warm
        # returns therefore have identical value semantics.
        snapshot = InsightSnapshot.model_validate(snapshot.model_dump(mode="json"))
        full_items=self._derived_items(snapshot)
        snapshot=self._compact_snapshot(snapshot)
        materialisation_id = await repository.persist_materialisation(
            subject_id=subject_id,period=period,module_key="snapshot",cache_key=cache_key,
            partition_hashes=source_tokens,
            payload=snapshot.model_dump(mode="json"),derivation_method=DERIVATION_METHOD,
            derivation_version=SNAPSHOT_VERSION,analysis_run_id=run_id,
            compare_from_at=comparison.baseline.from_at if comparison else None,
            compare_to_at=comparison.baseline.to_at if comparison else None,
        )
        await repository.persist_aggregate_buckets(
            materialisation_id,subject_id=subject_id,granularity=granularity.value,
            aggregate_type="activity_density",aggregate_key="all-events",
            buckets=density_rows,
        )
        for item in full_items:
            await repository.persist_insight_catalogue(materialisation_id,item)
            await repository.persist_evidence_index(materialisation_id,item.insight_id,item.evidence)
        return snapshot

    @staticmethod
    def _partition_hashes_for_bucket(partitions, start_at: datetime, end_at: datetime) -> tuple[str, ...]:
        return tuple(sorted({
            partition.file_hash for partition in partitions
            if (partition.max_occurred_at is None or partition.max_occurred_at >= start_at)
            and (partition.min_occurred_at is None or partition.min_occurred_at < end_at)
        }))

    async def _selective_density(
        self, *, repository: InsightRepository, subject_id: str,
        period: InsightPeriod, comparison: InsightComparisonPeriod | None,
        partitions, events: tuple[ActivityEvent, ...], start: datetime, end: datetime,
        granularity: PeriodGranularity, cache_key: str,
    ) -> tuple[tuple[ActivityDensityBin, ...], tuple[dict[str, Any], ...]]:
        """Reuse unaffected immutable buckets and calculate only changed ones."""
        previous = await repository.previous_aggregate_buckets(
            subject_id=subject_id,period=period,module_key="snapshot",
            derivation_version=SNAPSHOT_VERSION,exclude_cache_key=cache_key,
            aggregate_type="activity_density",aggregate_key="all-events",
            compare_from_at=comparison.baseline.from_at if comparison else None,
            compare_to_at=comparison.baseline.to_at if comparison else None,
        )
        previous_by_start = {
            row["start_at"]: row for row in (previous or {}).get("buckets", ())
        }
        definitions: list[tuple[datetime, datetime, tuple[str, ...], dict[str, Any] | None]] = []
        cursor=floor_bucket(start,granularity)
        while cursor<end:
            boundary=next_bucket(cursor,granularity)
            bucket_start=max(cursor,start);bucket_end=min(boundary,end)
            definitions.append((
                bucket_start,bucket_end,
                self._partition_hashes_for_bucket(partitions,bucket_start,bucket_end),
                previous_by_start.get(bucket_start),
            ))
            cursor=boundary

        affected_starts={
            bucket_start for bucket_start,bucket_end,hashes,prior in definitions
            if prior is None or prior["end_at"] != bucket_end
            or tuple(prior.get("values",{}).get("source_partition_hashes",())) != hashes
        }
        grouped: dict[datetime,list[UUID]] = defaultdict(list)
        for event in events:
            if event.occurred_at is None:
                continue
            bucket_start=max(floor_bucket(event.occurred_at,granularity),start)
            if bucket_start in affected_starts:
                grouped[bucket_start].append(event.event_id)

        bins=[];rows=[]
        previous_id=(previous or {}).get("materialisation_id")
        for bucket_start,bucket_end,hashes,prior in definitions:
            if bucket_start not in affected_starts and prior is not None:
                evidence_ids=tuple(UUID(str(value)) for value in prior["evidence_event_ids"])
                count=int(prior["source_event_count"])
                values={
                    "event_count":count,
                    "source_partition_hashes":list(hashes),
                    "reused_from_materialisation_id":str(previous_id),
                }
            else:
                evidence_ids=tuple(sorted(set(grouped.get(bucket_start,())),key=str))
                count=len(evidence_ids)
                values={"event_count":count,"source_partition_hashes":list(hashes)}
            bins.append(ActivityDensityBin(
                start_at=bucket_start,end_at=bucket_end,event_count=count,
                evidence_event_ids=evidence_ids,
            ))
            rows.append({
                "start_at":bucket_start,"end_at":bucket_end,"values":values,
                "evidence_event_ids":evidence_ids,
            })
        return tuple(bins),tuple(rows)

    @staticmethod
    def _compact_snapshot(snapshot: InsightSnapshot) -> InsightSnapshot:
        """Bound API evidence arrays while the full immutable index remains complete."""
        payload=snapshot.model_dump(mode="json")
        def visit(value):
            if isinstance(value,dict):
                evidence=value.get("evidence")
                if value.get("insight_id") and isinstance(evidence,list):
                    features=dict(value.get("calculated_features") or {})
                    features["evidence_reference_count"]=len(evidence)
                    features["evidence_references_truncated"]=len(evidence)>API_EVIDENCE_REFERENCE_LIMIT
                    value["calculated_features"]=features
                    value["evidence"]=evidence[:API_EVIDENCE_REFERENCE_LIMIT]
                for nested in value.values():visit(nested)
            elif isinstance(value,list):
                for nested in value:visit(nested)
        visit(payload)
        return InsightSnapshot.model_validate(payload)

    @staticmethod
    def _augment_interest_sources(interests,assertions,states):
        result=[]
        for interest in interests:
            tokens={interest.topic_id.casefold(),*(value.casefold() for value in interest.topic_path)}
            matching_assertions=[row for row in assertions if any(token in _json({
                "predicate":row.get("predicate"),"object_ref":row.get("object_ref"),
                "object_value":row.get("object_value"),
            }).casefold() for token in tokens)]
            topic_states=[row for row in states if any(token in str(row.get("state_key") or "").casefold() for token in tokens)]
            matching_states=[row for row in topic_states if row.get("history_type")=="personal_behavioural"]
            controller_states=[row for row in topic_states if row.get("history_type")=="controller_profile"]
            evidence=interest.evidence + tuple(
                InsightEvidenceRef(kind=EvidenceKind.ASSERTION,ref_id=row["id"],role="supporting")
                for row in matching_assertions
            ) + tuple(
                InsightEvidenceRef(kind=EvidenceKind.TEMPORAL_STATE,ref_id=row["id"],role="supporting")
                for row in matching_states
            ) + tuple(
                InsightEvidenceRef(kind=EvidenceKind.TEMPORAL_STATE,ref_id=row["id"],role="comparison")
                for row in controller_states
            )
            features={**interest.calculated_features,"accepted_assertion_count":len(matching_assertions),
                      "temporal_state_count":len(matching_states),
                      "controller_profile_state_count":len(controller_states)}
            controller_comparison=tuple({
                "state_key":row.get("state_key"),"state_type":row.get("state_type"),
                "dimensions":row.get("dimensions"),"detector_id":row.get("detector_id"),
                "detector_version":row.get("detector_version"),
            } for row in controller_states)
            result.append(interest.model_copy(update={"evidence":evidence,"calculated_features":features,
                                                       "controller_profile_comparison":controller_comparison}))
        return tuple(result)

    @staticmethod
    def _augment_engagement_sources(engagement,states,aggregates):
        matching_states=[row for row in states if row.get("state_type")=="engagement_profile"]
        matching_aggregates=[row for row in aggregates if row.get("aggregate_type")=="engagement_profile"]
        evidence=engagement.evidence + tuple(
            InsightEvidenceRef(kind=EvidenceKind.TEMPORAL_STATE,ref_id=row["id"],role="supporting")
            for row in matching_states
        ) + tuple(
            InsightEvidenceRef(kind=EvidenceKind.TEMPORAL_AGGREGATE,ref_id=row["id"],role="supporting")
            for row in matching_aggregates
        )
        features={**engagement.calculated_features,
                  "canonical_temporal_state_count":len(matching_states),
                  "canonical_temporal_aggregate_count":len(matching_aggregates),
                  "canonical_aggregate_values":tuple(row.get("values") for row in matching_aggregates)}
        return engagement.model_copy(update={"evidence":evidence,"calculated_features":features})

    @staticmethod
    def _project_view(row: dict[str,Any],events: tuple[ActivityEvent,...],run_id: UUID|None) -> ProjectEpisodeView:
        evidence_ids={UUID(str(value)) for value in row["evidence_event_ids"]}
        selected=[event for event in events if event.event_id in evidence_ids]
        topics=tuple(sorted({topic for event in selected for topic in _topics(event)}))
        return ProjectEpisodeView(
            insight_id=row["id"],detector_id=row["detector_id"],detector_version=row["detector_version"],
            analysis_run_id=row["analysis_run_id"] or run_id,calculated_features={"evidence_count":len(evidence_ids)},
            evidence=tuple(_event_ref(event) for event in selected),start_at=row["start_at"],end_at=row["end_at"],
            topic_ids=topics,topic_co_emergence=topics if len(topics)>1 else (),
            progressed_to_creation=any(event.action_class in {ActionClass.CREATED,ActionClass.PUBLISHED} for event in selected),
            progressed_to_implementation=any(event.action_class in {ActionClass.EDITED,ActionClass.CODED} for event in selected),
            peak_investigation_at=_peak_time(event for event in selected if event.action_class is ActionClass.SEARCHED),
        )

    @staticmethod
    def _changes(interests,engagement,baseline,projects,routine_drifts,run_id,baseline_interests=()):
        result=[]
        now=engagement.window_end
        for item in interests:
            kind={"emerging":"EMERGING","returning":"RETURNING"}.get(item.change)
            if kind:
                result.append(ChangeInsight(
                    insight_id=uuid5(INSIGHT_NAMESPACE,f"change:{item.insight_id}:{kind}"),detector_id="task4.interest-change",
                    detector_version=SNAPSHOT_VERSION,analysis_run_id=run_id,
                    calculated_features={**item.calculated_features,"behavioural_persistence":item.persistence},
                    evidence=item.evidence,change_type=kind,state_key="/".join(item.topic_path),detected_at=item.latest_observed_at,magnitude=item.intensity,
                ))
        current_topics={item.topic_id for item in interests}
        for item in baseline_interests:
            if item.topic_id in current_topics: continue
            result.append(ChangeInsight(
                insight_id=uuid5(INSIGHT_NAMESPACE,f"change:{item.insight_id}:DECLINING:{now}"),
                detector_id="task4.interest-change",detector_version=SNAPSHOT_VERSION,
                analysis_run_id=run_id,calculated_features={**item.calculated_features,"baseline_intensity":item.intensity,
                                                            "behavioural_persistence":item.persistence},
                evidence=tuple(ref.model_copy(update={"role":"comparison"}) for ref in item.evidence),
                change_type="DECLINING",state_key="/".join(item.topic_path),detected_at=now,magnitude=item.intensity,
            ))
        if baseline and baseline.calculated_features.get("event_count",0)>=5:
            before=sum(float(getattr(baseline,name)) for name in ("passive_consumption","active_investigation","creation","implementation","communication"))
            after=sum(float(getattr(engagement,name)) for name in ("passive_consumption","active_investigation","creation","implementation","communication"))
            if before and abs(after-before)/before>=0.5:
                result.append(ChangeInsight(
                    insight_id=uuid5(INSIGHT_NAMESPACE,f"change:engagement:{engagement.insight_id}"),detector_id="task4.engagement-regime",
                    detector_version=SNAPSHOT_VERSION,analysis_run_id=run_id,calculated_features={"before":before,"after":after,"behavioural_persistence":1.0},
                    evidence=engagement.evidence,change_type="REGIME_SHIFT",state_key="overall engagement",detected_at=now,magnitude=(after-before)/before,
                ))
        for project in projects:
            result.append(ChangeInsight(
                insight_id=uuid5(INSIGHT_NAMESPACE,f"change:project:{project.insight_id}"),detector_id=project.detector_id,
                detector_version=project.detector_version,analysis_run_id=project.analysis_run_id,
                calculated_features={**project.calculated_features,"behavioural_persistence":max(0.0,(project.end_at-project.start_at).total_seconds()/86400)},evidence=project.evidence,change_type="TEMPORARY_BURST",
                state_key="project activity",detected_at=project.start_at,magnitude=float(len(project.evidence)),
            ))
        for drift in routine_drifts:
            if drift.total_variation_distance < 0.25: continue
            result.append(ChangeInsight(
                insight_id=uuid5(INSIGHT_NAMESPACE,f"change:routine:{drift.subject_id}:{drift.dimension}:{drift.current_end}"),
                detector_id=drift.detector_id,detector_version=drift.detector_version,analysis_run_id=run_id,
                calculated_features={"dimension":drift.dimension,"baseline_distribution":drift.baseline_distribution,
                                     "current_distribution":drift.current_distribution,"behavioural_persistence":1.0},
                evidence=tuple(InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT,ref_id=value,role="comparison") for value in drift.evidence_event_ids),
                change_type="ROUTINE_CHANGE",state_key=f"routine:{drift.dimension}",detected_at=drift.current_end,
                magnitude=drift.total_variation_distance,
            ))
        return tuple(result)

    async def _places(self,repository,subject_id,run_id,start,end,project_views=()):
        await self._materialize_media_locations(repository.connection,subject_id)
        rows=await repository.read_media_location_candidates(subject_id=subject_id,from_at=start,to_at=end)
        candidates=[]
        for row in rows:
            locator=row["evidence_locator_id"]
            candidates.append(MediaLocationCandidate(
                insight_id=row["id"],detector_id=row["detector_id"],detector_version=row["detector_version"],
                analysis_run_id=row["analysis_run_id"] or run_id,calculated_features={"evidence_locator_id":str(locator)},
                evidence=(InsightEvidenceRef(kind=EvidenceKind.SOURCE_ARTIFACT,ref_id=row["artifact_id"],artifact_id=row["artifact_id"]),
                          InsightEvidenceRef(kind=EvidenceKind.EVIDENCE_LOCATOR,ref_id=locator,artifact_id=row["locator_artifact_id"],locator_id=locator)),
                artifact_id=row["artifact_id"],occurred_at=row["occurred_at"],temporal_precision=row["temporal_precision"],
                location_type=row["location_type"],lat=row["lat"],lon=row["lon"],place_label=row["place_label"],
                basis=LocationBasis(row["basis"]),confidence=float(row["confidence"]),
                evidence_class=LocationEvidenceClass(row["evidence_class"]),media_origin=MediaOrigin(row["media_origin"]),
                reviewed_by=row["reviewed_by"],
            ))
        content_candidates=await self._media_content_candidates(repository.connection,subject_id,run_id)
        return build_place_insight(
            tuple(candidates),insight_id=uuid5(INSIGHT_NAMESPACE,f"places:{subject_id}:{start}:{end}"),
            analysis_run_id=run_id,project_episodes=project_views,
            media_content_candidates=content_candidates,
        )

    async def _media_content_candidates(self,connection,subject_id,run_id):
        rows=await connection.fetch(
            """SELECT sr.analysis_run_id,sr.artifact_id,sr.task_key,sr.output_manifest,
                      sr.input_manifest,sa.original_path,
                      COALESCE((sr.input_manifest->>'evidence_locator_id')::uuid,eu.evidence_locator_id) AS locator_id
               FROM specialist_task_requests sr
               JOIN source_artifacts sa ON sa.id=sr.artifact_id
               JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               LEFT JOIN LATERAL (
                 SELECT evidence_locator_id FROM extraction_units
                 WHERE artifact_id=sr.artifact_id AND unit_type='image_metadata'
                 ORDER BY ordinal LIMIT 1
               ) eu ON TRUE
               WHERE sr.status='completed' AND sr.task_key IN
                 ('image.origin_classification','image.ocr','image.caption')
                 AND es.profile_id::text=$1
               ORDER BY sr.artifact_id,sr.task_key""", subject_id,
        )
        grouped=defaultdict(dict); metadata={}
        for row in rows:
            output=row["output_manifest"]
            if isinstance(output,str):
                try:output=json.loads(output)
                except json.JSONDecodeError:output={}
            grouped[row["artifact_id"]][row["task_key"]]=dict(output or {})
            metadata[row["artifact_id"]]=(row["analysis_run_id"],row["locator_id"],row["original_path"])
        result=[]
        for artifact_id,outputs in grouped.items():
            analysis_run_id,locator_id,path=metadata[artifact_id]
            if locator_id is None or not ({"image.ocr","image.caption"} & set(outputs)):
                continue
            origin=classify_media_origin({},original_path=path or "",routed_result=outputs.get("image.origin_classification"))
            result.append(create_media_content_candidate(
                artifact_id=artifact_id,evidence_locator_id=locator_id,origin=origin,
                task_outputs=outputs,analysis_run_id=analysis_run_id or run_id,
            ))
        return tuple(result)

    @staticmethod
    def _capture_time(metadata: dict[str,Any]) -> datetime | None:
        raw=metadata.get("capture_timestamp")
        if not raw:return None
        text=str(raw).strip()
        parsed=None
        for pattern in ("%Y:%m:%d %H:%M:%S","%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S"):
            try: parsed=datetime.strptime(text,pattern);break
            except ValueError: continue
        if parsed is None:
            try: parsed=datetime.fromisoformat(text.replace("Z","+00:00"))
            except ValueError:return None
        if parsed.tzinfo is None:
            offset=str(metadata.get("timezone") or "")
            try:
                sign=-1 if offset.startswith("-") else 1
                hours,minutes=offset.lstrip("+-").split(":",1)
                parsed=parsed.replace(tzinfo=timezone(sign*timedelta(hours=int(hours),minutes=int(minutes))))
            except (ValueError,AttributeError):
                parsed=parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    async def _materialize_media_locations(self,connection,subject_id: str) -> None:
        routed_rows=await connection.fetch(
            """SELECT sr.artifact_id,sr.task_key,sr.output_manifest
               FROM specialist_task_requests sr
               JOIN source_artifacts sa ON sa.id=sr.artifact_id
               JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               WHERE es.profile_id::text=$1 AND sr.status='completed'
                 AND sr.task_key IN ('image.origin_classification','image.landmark_candidate')""",
            subject_id,
        )
        routed: dict[tuple[UUID,str],dict[str,Any]]={}
        for row in routed_rows:
            value=row["output_manifest"]
            if isinstance(value,str):
                try:value=json.loads(value)
                except json.JSONDecodeError:value={}
            routed[(row["artifact_id"],row["task_key"])]=dict(value or {})
        units=await connection.fetch(
            """SELECT eu.analysis_run_id,eu.artifact_id,eu.structured_payload,eu.evidence_locator_id,
                      sa.original_path,sidecar.structured_payload AS sidecar_payload,
                      sidecar.evidence_locator_id AS sidecar_locator_id,
                      sidecar.artifact_id AS sidecar_artifact_id
               FROM extraction_units eu JOIN source_artifacts sa ON sa.id=eu.artifact_id
               JOIN export_snapshots es ON es.id=sa.export_snapshot_id
               LEFT JOIN LATERAL (
                 SELECT eu2.structured_payload,eu2.evidence_locator_id,eu2.artifact_id
                 FROM extraction_units eu2 JOIN source_artifacts sa2 ON sa2.id=eu2.artifact_id
                 WHERE sa2.export_snapshot_id=sa.export_snapshot_id
                   AND sa2.original_path IN (
                   sa.original_path||'.json',
                   regexp_replace(sa.original_path,'\\.[^.]+$','.json')
                 ) AND (eu2.structured_payload ? 'geoData'
                        OR eu2.structured_payload ? 'geoDataExif'
                        OR eu2.structured_payload ? 'takeout_sidecar')
                 ORDER BY eu2.ordinal LIMIT 1
               ) sidecar ON TRUE
               WHERE es.profile_id::text=$1 AND eu.unit_type='image_metadata'
                 AND (eu.structured_payload ? 'gps' OR sidecar.structured_payload IS NOT NULL OR EXISTS(
                     SELECT 1 FROM specialist_task_requests sr WHERE sr.artifact_id=eu.artifact_id
                       AND sr.task_key='image.landmark_candidate' AND sr.status='completed'))
                 AND NOT EXISTS(SELECT 1 FROM media_location_candidates ml
                                WHERE ml.artifact_id=eu.artifact_id AND ml.evidence_locator_id=eu.evidence_locator_id)""",
            subject_id,
        )
        for row in units:
            metadata=row["structured_payload"]
            if isinstance(metadata,str):
                try:metadata=json.loads(metadata)
                except json.JSONDecodeError:metadata={}
            metadata=dict(metadata or {})
            origin=classify_media_origin(
                metadata,original_path=row["original_path"] or "",
                routed_result=routed.get((row["artifact_id"],"image.origin_classification")),
            )
            observations=[]
            gps=metadata.get("gps") if isinstance(metadata.get("gps"),dict) else None
            occurred=self._capture_time(metadata)
            if gps and gps.get("latitude") is not None and gps.get("longitude") is not None:
                observations.append(LocationObservation(
                    basis=LocationBasis.EXIF_GPS,evidence_locator_id=row["evidence_locator_id"],
                    occurred_at=occurred,temporal_precision="SECOND" if occurred else "UNKNOWN",
                    location_type="EXACT_COORDINATE",lat=float(gps["latitude"]),lon=float(gps["longitude"]),
                    confidence=0.95,credible_original_capture_time=bool(occurred and metadata.get("device")),
                ))
            sidecar=row["sidecar_payload"]
            if isinstance(sidecar,str):
                try:sidecar=json.loads(sidecar)
                except json.JSONDecodeError:sidecar={}
            sidecar=dict(sidecar or {})
            sidecar_geo=(sidecar.get("takeout_sidecar") if isinstance(sidecar.get("takeout_sidecar"),dict) else None) or (
                sidecar.get("geoDataExif") if isinstance(sidecar.get("geoDataExif"),dict) else None
            ) or (sidecar.get("geoData") if isinstance(sidecar.get("geoData"),dict) else None)
            if sidecar_geo:
                lat=sidecar_geo.get("latitude")
                lon=sidecar_geo.get("longitude")
                if lat is not None and lon is not None and row["sidecar_locator_id"]:
                    sidecar_time=self._sidecar_time(sidecar) or occurred
                    observations.append(LocationObservation(
                        basis=LocationBasis.TAKEOUT_SIDECAR,evidence_locator_id=row["sidecar_locator_id"],
                        evidence_artifact_id=row["sidecar_artifact_id"],occurred_at=sidecar_time,
                        temporal_precision="SECOND" if sidecar_time else "UNKNOWN",location_type="EXACT_COORDINATE",
                        lat=float(lat),lon=float(lon),confidence=0.9,
                        credible_original_capture_time=bool(sidecar_time and metadata.get("device")),
                    ))
            landmark=routed.get((row["artifact_id"],"image.landmark_candidate"))
            candidate=(landmark.get("candidate") if isinstance(landmark,dict) else None) or landmark
            if isinstance(candidate,dict) and candidate.get("place_label"):
                observations.append(LocationObservation(
                    basis=LocationBasis.VISUAL_LANDMARK,evidence_locator_id=row["evidence_locator_id"],
                    occurred_at=occurred,temporal_precision="SECOND" if occurred else "UNKNOWN",
                    location_type="PLACE",place_label=str(candidate["place_label"]),
                    confidence=max(0.0,min(1.0,float(candidate.get("confidence",0.0)))),
                    credible_original_capture_time=False,
                ))
            for observation in observations:
                item=create_location_candidate(
                    row["artifact_id"],origin,observation,analysis_run_id=row["analysis_run_id"],
                )
                await connection.execute(
                    """INSERT INTO media_location_candidates
                    (id,analysis_run_id,artifact_id,occurred_at,temporal_precision,location_type,lat,lon,
                     place_label,basis,confidence,evidence_class,media_origin,evidence_locator_id,
                     detector_id,detector_version,reviewed_by)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
                    ON CONFLICT(id) DO NOTHING""",
                    item.insight_id,item.analysis_run_id,item.artifact_id,item.occurred_at,item.temporal_precision,
                    item.location_type,item.lat,item.lon,item.place_label,item.basis.value,item.confidence,
                    item.evidence_class.value,item.media_origin.value,observation.evidence_locator_id,
                    item.detector_id,item.detector_version,item.reviewed_by,
                )

    @staticmethod
    def _sidecar_time(payload: dict[str,Any]) -> datetime | None:
        value=payload.get("photoTakenTime") or payload.get("creationTime")
        if isinstance(value,dict): value=value.get("timestamp") or value.get("formatted")
        if value is None:return None
        try:
            if str(value).isdigit(): return datetime.fromtimestamp(int(value),tz=timezone.utc)
            parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
        except (ValueError,OverflowError,OSError):
            return None

    async def _correlations(self,repository,connection,changes,events,signals,run_id,start,end,assertions=()):
        external_rows=await repository.read_external_context_events(from_at=start-timedelta(days=90),to_at=end+timedelta(days=45))
        external=tuple(ExternalContextEvent(
            id=row["id"],title=row["title"],event_type=row["event_type"],occurred_at=row["occurred_at"],ended_at=row["ended_at"],
            topics=tuple(row["topics"]),jurisdiction=row["jurisdiction"],source_uri=row["source_uri"],
            source_artifact_id=row["source_artifact_id"],ingested_at=row["ingested_at"],
        ) for row in external_rows)
        signal_by_id={signal.event.event_id:signal for signal in signals}
        observations=[]
        for event in events:
            signal=signal_by_id[event.event_id]
            if signal.signal_class in {SignalClass.UNKNOWN,SignalClass.AMBIENT_EXPOSURE} or event.occurred_at is None:
                continue
            text=event.object_value if isinstance(event.object_value,str) else _json(event.object_value or {})
            observations.append(ExposureObservation(
                evidence=_event_ref(event,role="exposure",weight=signal.weight),occurred_at=event.occurred_at,
                topics=_topics(event),text=text,relevance=min(1.0,signal.weight),
                direct_user_statement=bool(event.relationships.get("confirms_external_relation")),
            ))
        result=[]
        for change in changes:
            candidates=[]
            relevant_count=sum(
                1 for event in external
                if temporal_proximity(change,event,timedelta(days=45))>0
                and semantic_relevance(change,event)>=0.25
            )
            for context_event in external:
                confirmations=[]
                for assertion in assertions:
                    if str(assertion.get("epistemic_basis"))!="human_confirmed" or str(assertion.get("assertion_type"))!="relationship":
                        continue
                    assertion_text=_json({
                        "predicate":assertion.get("predicate"),"object_ref":assertion.get("object_ref"),
                        "object_value":assertion.get("object_value"),
                    }).casefold()
                    if str(change.insight_id).casefold() not in assertion_text or str(context_event.id).casefold() not in assertion_text:
                        continue
                    confirmations.append(InsightEvidenceRef(
                        kind=EvidenceKind.ASSERTION,ref_id=assertion["id"],role="user_confirmation",
                        occurred_at=assertion.get("valid_from") or assertion.get("system_asserted_at"),
                    ))
                candidates.extend(correlate_change(
                    change,(context_event,),observations,confirmation_evidence=tuple(confirmations),
                    behavioural_persistence=float(change.calculated_features.get("behavioural_persistence",0.0)),
                    competing_explanations_count=max(0,relevant_count-1),analysis_run_id=run_id,
                ))
            candidates=tuple(candidates)
            for item in candidates:
                if run_id is not None:
                    await connection.execute(
                        """INSERT INTO temporal_correlation_candidates
                        (id,analysis_run_id,local_change_id,external_event_id,temporal_proximity,semantic_relevance,
                         user_exposure_evidence,direct_user_statement,preceding_related_activity,behavioural_persistence,
                         competing_explanations_count,status,detector_id,detector_version,calculated_features)
                        VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)
                        ON CONFLICT(analysis_run_id,local_change_id,external_event_id,detector_version) DO NOTHING""",
                        item.insight_id,run_id,item.local_change_id,item.external_event_id,item.temporal_proximity,
                        item.semantic_relevance,_json([ref.model_dump(mode="json") for ref in item.user_exposure_evidence]),
                        item.direct_user_statement,item.preceding_related_activity,item.behavioural_persistence,
                        item.competing_explanations_count,item.status.value,item.detector_id,item.detector_version,
                        _json(item.calculated_features),
                    )
            result.extend(candidates)
        return tuple(result)

    @staticmethod
    def _derived_items(snapshot: InsightSnapshot):
        items=[]
        if snapshot.overview.engagement: items.append(snapshot.overview.engagement)
        items.extend(snapshot.interests)
        if snapshot.search:
            items.append(snapshot.search);items.extend(snapshot.search.episodes)
        if snapshot.ai_conversations: items.append(snapshot.ai_conversations)
        if snapshot.places:
            items.append(snapshot.places);items.extend(snapshot.places.candidates);items.extend(snapshot.places.media_content_candidates)
        items.extend(snapshot.changes);items.extend(snapshot.project_episodes);items.extend(snapshot.personal_eras);items.extend(snapshot.contextual_correlations)
        return tuple(items)

    async def get_period_overview(self,**kwargs): return (await self.get_snapshot(**kwargs)).overview
    async def get_interest_states(self,**kwargs): return (await self.get_snapshot(**kwargs)).interests
    async def get_search_insights(self,**kwargs): return (await self.get_snapshot(**kwargs)).search
    async def get_ai_conversation_insights(self,**kwargs): return (await self.get_snapshot(**kwargs)).ai_conversations
    async def get_place_insights(self,**kwargs): return (await self.get_snapshot(**kwargs)).places
    async def get_engagement_profile(self,**kwargs): return (await self.get_snapshot(**kwargs)).overview.engagement
    async def get_project_episodes(self,**kwargs): return (await self.get_snapshot(**kwargs)).project_episodes
    async def get_routine_changes(self,**kwargs): return (await self.get_snapshot(**kwargs)).changes
    async def get_personal_drift(self,*,subject_id:str,period:InsightPeriod,comparison:InsightComparisonPeriod|None=None):
        start,end=_bounds(period)
        pool=await self.postgres._get_pool()
        async with pool.acquire() as connection:
            rows=await InsightRepository(connection).read_export_deltas(subject_id=subject_id,from_at=start,to_at=end)
        grouped={"PERSONAL_DRIFT":[],"CONTROLLER_DRIFT":[],"UNDERSTANDING_DRIFT":[]}
        for row in rows: grouped[row["drift_type"]].append(row)
        return grouped
    async def get_contextual_correlations(self,**kwargs): return (await self.get_snapshot(**kwargs)).contextual_correlations

    async def confirm_media_location(
        self, *, artifact_id: UUID, evidence_locator_id: UUID, reviewed_by: str,
        occurred_at: datetime | None = None, lat: float | None = None,
        lon: float | None = None, place_label: str | None = None,
        analysis_run_id: UUID | None = None,
    ) -> MediaLocationCandidate:
        pool=await self.postgres._get_pool()
        async with pool.acquire() as connection:
            exists=await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM evidence_locators WHERE id=$1 AND artifact_id=$2)",
                evidence_locator_id,artifact_id,
            )
            if not exists: raise LookupError("artifact evidence locator not found")
            item=create_location_candidate(
                artifact_id,classify_media_origin({},original_path=""),LocationObservation(
                    basis=LocationBasis.USER_CONFIRMED,evidence_locator_id=evidence_locator_id,
                    occurred_at=occurred_at,temporal_precision="SECOND" if occurred_at else "UNKNOWN",
                    location_type="EXACT_COORDINATE" if lat is not None else "PLACE",
                    lat=lat,lon=lon,place_label=place_label,confidence=1.0,
                    reviewed_by=reviewed_by,
                ),analysis_run_id=analysis_run_id,
            )
            await connection.execute(
                """INSERT INTO media_location_candidates
                (id,analysis_run_id,artifact_id,occurred_at,temporal_precision,location_type,lat,lon,
                 place_label,basis,confidence,evidence_class,media_origin,evidence_locator_id,
                 detector_id,detector_version,reviewed_by)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
                ON CONFLICT(id) DO NOTHING""",
                item.insight_id,item.analysis_run_id,item.artifact_id,item.occurred_at,item.temporal_precision,
                item.location_type,item.lat,item.lon,item.place_label,item.basis.value,item.confidence,
                item.evidence_class.value,item.media_origin.value,evidence_locator_id,item.detector_id,
                item.detector_version,item.reviewed_by,
            )
            return item

    async def trace_insight(self,insight_id:UUID):
        pool=await self.postgres._get_pool()
        async with pool.acquire() as connection:
            return await InsightEvidenceTracer(connection).trace(insight_id)
