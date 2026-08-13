export const CANONICAL_REQUEST_STATES = [
    'draft',
    'ready_for_review',
    'scheduled',
    'sent',
    'awaiting_response',
    'identity_action_required',
    'clarification_action_required',
    'response_received',
    'processing_response',
    'completed',
    'closed_incomplete',
    'cancelled',
] as const;

export type CanonicalRequestState = (typeof CANONICAL_REQUEST_STATES)[number];

/**
 * Historical values remain readable until an explicit, evidence-backed
 * transition occurs. A null mapping is intentionally ambiguous and requires a
 * caller to choose the evidence-supported canonical state.
 */
export const HISTORICAL_REQUEST_STATE_MAP = {
    processing: 'processing_response',
    action_required: null,
    draft_pending_review: 'ready_for_review',
    pending: 'awaiting_response',
    verification_needed: 'identity_action_required',
    data_available: 'response_received',
    data_received: 'response_received',
    partial_data: 'response_received',
    data_analyzed: 'processing_response',
    rejected: 'closed_incomplete',
    extended: 'awaiting_response',
} as const satisfies Record<string, CanonicalRequestState | null>;

export type HistoricalRequestState = keyof typeof HISTORICAL_REQUEST_STATE_MAP;
export type RequestStoredState = CanonicalRequestState | HistoricalRequestState;
export type RequestDate = Date | string;

export interface RequestLifecycleDates {
    sent_at: RequestDate | null;
    controller_received_at: RequestDate | null;
    identity_requested_at: RequestDate | null;
    identity_verified_at: RequestDate | null;
    clarification_requested_at: RequestDate | null;
    clarification_resolved_at: RequestDate | null;
    response_received_at: RequestDate | null;
    completed_at: RequestDate | null;
    deadline_at: RequestDate | null;
    extension_notified_at: RequestDate | null;
    extension_deadline_at: RequestDate | null;
    next_action_at: RequestDate | null;
}

export interface Request extends RequestLifecycleDates {
    id: string;
    profile_id: string;
    company_name: string;
    company_url: string | null;
    domain: string | null;
    request_type: string;
    status: RequestStoredState;
    progress: number;
    notes: string | null;
    deadline_basis: string | null;
    extension_reason: string | null;
    created_at: RequestDate;
    updated_at: RequestDate;
}

export type CreateRequestLifecycleDates = Partial<{
    [Field in keyof RequestLifecycleDates]: RequestLifecycleDates[Field];
}>;

export interface CreateRequestInput extends CreateRequestLifecycleDates {
    company_name: string;
    company_url?: string | null;
    domain?: string | null;
    request_type: string;
    status?: CanonicalRequestState;
    progress?: number;
    notes?: string | null;
    deadline_basis?: string | null;
    extension_reason?: string | null;
}

export interface RequestListOptions {
    search?: string;
    status?: RequestStoredState;
    sort?: 'created_desc' | 'created_asc' | 'company_asc' | 'deadline_asc';
    limit?: number;
    offset?: number;
}

export interface RequestCounts {
    total: number;
    by_state: Partial<Record<RequestStoredState, number>>;
}

export interface TransitionRequestCommand extends Partial<RequestLifecycleDates> {
    request_id: string;
    next_state: CanonicalRequestState;
    actor: string;
    reason: string;
    evidence_reference?: string | null;
    transitioned_at: RequestDate;
    deadline_basis?: string | null;
    extension_reason?: string | null;
}

export interface RequestEvent {
    id: string;
    request_id: string;
    event_type: string;
    event_description: string | null;
    event_date: RequestDate;
    actor: string;
    previous_state: string | null;
    next_state: string | null;
    reason: string;
    evidence_reference: string | null;
}

export interface AppendRequestEventInput {
    request_id: string;
    event_type: string;
    description?: string | null;
    occurred_at: RequestDate;
    actor: string;
    reason: string;
    evidence_reference?: string | null;
}

export interface RequestMessage {
    id: string;
    request_id: string;
    sender: string;
    content: string;
    timestamp: RequestDate;
}

export interface RequestChatMessage {
    id: string | number;
    request_id: string;
    sender: string;
    message: string;
    timestamp: RequestDate;
}

export interface ReceivedDataRecord {
    id: string;
    request_id: string;
    profile_id: string;
    file_name: string;
    file_path: string;
    file_size_mb: number | string | null;
    file_type: string | null;
    category: string | null;
    status: string | null;
    date_received: RequestDate;
    [key: string]: unknown;
}

export interface RequestContext extends Request {
    received_file_count: number;
    received_file_status_counts: Record<string, number>;
}

export function canonicaliseStoredState(state: RequestStoredState): CanonicalRequestState | null {
    if ((CANONICAL_REQUEST_STATES as readonly string[]).includes(state)) {
        return state as CanonicalRequestState;
    }
    return HISTORICAL_REQUEST_STATE_MAP[state as HistoricalRequestState] ?? null;
}
