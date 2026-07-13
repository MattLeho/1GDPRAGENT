export type TemporalMode = 'point_in_time' | 'period' | 'compare';
export type PeriodGranularity = 'day' | 'week' | 'month' | 'quarter' | 'year' | 'custom';
export type SignalClass = 'AMBIENT_EXPOSURE' | 'PASSIVE_CONSUMPTION' | 'ACTIVE_INVESTIGATION' | 'CREATION' | 'IMPLEMENTATION' | 'COMMUNICATION' | 'DISENGAGEMENT' | 'UNKNOWN';
export type CorrelationStatus = 'coincidence_candidate' | 'possible_relation' | 'evidence_supported_relation' | 'user_confirmed' | 'rejected';
export type MediaOrigin = 'camera_origin' | 'screenshot' | 'downloaded_media' | 'edited_media' | 'generated_media' | 'unknown';
export type LocationEvidenceClass = 'strong_observation' | 'candidate' | 'user_confirmed' | 'rejected';
export type EvidenceKind = 'activity_event' | 'assertion' | 'temporal_state' | 'temporal_aggregate' | 'source_artifact' | 'evidence_locator' | 'external_context_event' | 'media_location_candidate';

export interface InsightPeriod {
    mode: TemporalMode;
    granularity: PeriodGranularity;
    from_at?: string | null;
    to_at?: string | null;
    point_at?: string | null;
}

export interface InsightComparisonPeriod {
    current: InsightPeriod;
    baseline: InsightPeriod;
}

export interface InsightEvidenceRef {
    kind: EvidenceKind;
    ref_id: string;
    role: 'supporting' | 'exposure' | 'comparison' | 'contradicting' | 'user_confirmation';
    occurred_at?: string | null;
    artifact_id?: string | null;
    locator_id?: string | null;
    label?: string | null;
    weight?: number | null;
}

export interface DerivedInsight {
    insight_id: string;
    detector_id: string;
    detector_version: string;
    analysis_run_id?: string | null;
    calculated_features: Record<string, unknown>;
    evidence: InsightEvidenceRef[];
    model_explanation?: string | null;
}

export interface ActivityDensityBin {
    start_at: string;
    end_at: string;
    event_count: number;
    evidence_event_ids: string[];
}

export interface InsightEngagementProfile extends DerivedInsight {
    subject_id: string;
    window_start: string;
    window_end: string;
    ambient_exposure: number;
    passive_consumption: number;
    active_investigation: number;
    creation: number;
    implementation: number;
    communication: number;
    disengagement: number;
    comparison_delta: Record<string, number>;
}

export interface PeriodOverview {
    subject_id: string;
    period: InsightPeriod;
    active_topic_count: number;
    emerging_topic_count: number;
    returning_topic_count: number;
    project_episode_count: number;
    total_event_count: number;
    density: ActivityDensityBin[];
    engagement?: InsightEngagementProfile | null;
}

export interface ObservedInterestState extends DerivedInsight {
    subject_id: string;
    history_type: 'personal_behavioural';
    topic_id: string;
    topic_path: string[];
    window_start: string;
    window_end: string;
    intensity: number;
    persistence: number;
    recurrence: number;
    breadth: number;
    novelty: number;
    context_dispersion: number;
    first_observed_at: string;
    latest_observed_at: string;
    peak_at?: string | null;
    source_domains: string[];
    change: 'emerging' | 'returning' | 'continuing' | 'declining' | 'one_off';
    previous_period_dimensions: Record<string, number>;
    comparison_delta: Record<string, number>;
    controller_profile_comparison: Array<Record<string, unknown>>;
}

export interface InvestigationEpisode extends DerivedInsight {
    subject_id: string;
    start_at: string;
    end_at: string;
    query_count: number;
    recurrence: number;
    domain_diversity: number;
    refinement_depth: number;
    cross_source_count: number;
    project_transition: boolean;
    topic_labels: string[];
    status: 'candidate' | 'accepted' | 'rejected';
}

export interface SearchInsight extends DerivedInsight {
    recurring_queries: Array<Record<string, unknown>>;
    emerging_clusters: Array<Record<string, unknown>>;
    refinement_chains: Array<Record<string, unknown>>;
    abandoned_one_offs: number;
    episodes: InvestigationEpisode[];
}

export interface AIConversationInsight extends DerivedInsight {
    user_originated_topics: Array<Record<string, unknown>>;
    sustained_clusters: Array<Record<string, unknown>>;
    recurrent_questions: Array<Record<string, unknown>>;
    refinement_chains: Array<Record<string, unknown>>;
    services: string[];
    session_count: number;
    user_turn_count: number;
    assistant_turn_count: number;
    maximum_follow_up_depth: number;
    project_linked_session_ids: string[];
}

export interface MediaLocationCandidate extends DerivedInsight {
    artifact_id: string;
    occurred_at?: string | null;
    temporal_precision: string;
    location_type?: string | null;
    lat?: number | null;
    lon?: number | null;
    place_label?: string | null;
    basis: 'exif_gps' | 'takeout_sidecar' | 'visual_landmark' | 'user_confirmed';
    confidence: number;
    evidence_class: LocationEvidenceClass;
    media_origin: MediaOrigin;
    reviewed_by?: string | null;
}

export interface MediaContentCandidate extends DerivedInsight {
    artifact_id: string;
    evidence_locator_id: string;
    media_origin: MediaOrigin;
    ocr_word_count: number;
    ocr_text_fingerprint?: string | null;
    application_candidates: string[];
    interface_candidates: string[];
    webpage_candidates: string[];
    service_candidates: string[];
    visible_topic_candidates: string[];
    visible_entity_candidates: string[];
    caption_available: boolean;
}

export interface PlaceInsight extends DerivedInsight {
    recurrent_places: Array<Record<string, unknown>>;
    new_places: Array<Record<string, unknown>>;
    activity_centre_changes: Array<Record<string, unknown>>;
    travel_periods: Array<Record<string, unknown>>;
    place_linked_project_episodes: Array<Record<string, unknown>>;
    media_content_candidates: MediaContentCandidate[];
    candidates: MediaLocationCandidate[];
}

export interface ChangeInsight extends DerivedInsight {
    change_type: 'EMERGING' | 'DECLINING' | 'RETURNING' | 'TEMPORARY_BURST' | 'REGIME_SHIFT' | 'ROUTINE_CHANGE';
    state_key: string;
    detected_at: string;
    magnitude: number;
}

export interface ProjectEpisodeView extends DerivedInsight {
    start_at: string;
    end_at: string;
    topic_ids: string[];
    topic_co_emergence: string[];
    machine_label?: string | null;
    human_label?: string | null;
    peak_investigation_at?: string | null;
    progressed_to_creation: boolean;
    progressed_to_implementation: boolean;
}

export interface PersonalEraView extends DerivedInsight {
    start_at: string;
    end_at: string;
    machine_label?: string | null;
    human_label?: string | null;
}

export interface TemporalCorrelationCandidate extends DerivedInsight {
    local_change_id: string;
    external_event_id: string;
    local_change: { change_type?: string; state_key?: string; detected_at?: string; magnitude?: number };
    external_event: { title?: string; event_type?: string; occurred_at?: string; ended_at?: string | null; topics?: string[]; jurisdiction?: string | null; source_uri?: string | null };
    temporal_proximity: number;
    semantic_relevance: number;
    user_exposure_evidence: InsightEvidenceRef[];
    direct_user_statement: boolean;
    preceding_related_activity: boolean;
    behavioural_persistence: number;
    competing_explanations_count: number;
    status: CorrelationStatus;
    causal_claim: false;
}

export interface InsightTrace {
    insight_id: string;
    detector_id: string;
    detector_version: string;
    analysis_run_id?: string | null;
    time_window?: [string, string] | null;
    calculated_features: Record<string, unknown>;
    source_counts: Record<string, number>;
    activity_events: Array<Record<string, unknown>>;
    assertions: Array<Record<string, unknown>>;
    temporal_states: Array<Record<string, unknown>>;
    temporal_aggregates: Array<Record<string, unknown>>;
    external_context_events: Array<Record<string, unknown>>;
    source_artifacts: Array<Record<string, unknown>>;
    evidence_locators: Array<Record<string, unknown>>;
    model_explanation?: string | null;
}

export interface InsightSnapshot {
    snapshot_id: string;
    subject_id: string;
    period: InsightPeriod;
    comparison?: InsightComparisonPeriod | null;
    analysis_run_ids: string[];
    derivation_method: string;
    derivation_version: string;
    generated_at: string;
    canonical_source_counts: Record<string, number>;
    overview: PeriodOverview;
    interests: ObservedInterestState[];
    search?: SearchInsight | null;
    ai_conversations?: AIConversationInsight | null;
    places?: PlaceInsight | null;
    changes: ChangeInsight[];
    project_episodes: ProjectEpisodeView[];
    personal_eras: PersonalEraView[];
    contextual_correlations: TemporalCorrelationCandidate[];
}
