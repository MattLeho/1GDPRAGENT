-- R2 lifecycle hardening: finish reconciliation of historical status strings.
-- Every changed row receives an immutable request_events entry. Ambiguous or
-- unknown historical values are conservatively routed to ready_for_review.

CREATE TEMP TABLE r2_status_reconciliation ON COMMIT DROP AS
SELECT
    id AS request_id,
    status AS previous_state,
    CASE status
        WHEN 'draft_pending_review' THEN 'ready_for_review'
        WHEN 'pending' THEN 'awaiting_response'
        WHEN 'verification_needed' THEN 'identity_action_required'
        WHEN 'data_available' THEN 'response_received'
        WHEN 'data_received' THEN 'response_received'
        WHEN 'partial_data' THEN 'response_received'
        WHEN 'processing' THEN 'processing_response'
        WHEN 'data_analyzed' THEN 'processing_response'
        WHEN 'rejected' THEN 'closed_incomplete'
        WHEN 'extended' THEN 'awaiting_response'
        WHEN 'action_required' THEN 'ready_for_review'
        ELSE 'ready_for_review'
    END AS next_state
FROM requests
WHERE status IS NULL OR status NOT IN (
    'draft', 'ready_for_review', 'scheduled', 'sent', 'awaiting_response',
    'identity_action_required', 'clarification_action_required',
    'response_received', 'processing_response', 'completed',
    'closed_incomplete', 'cancelled'
);

SELECT set_config('gdpr.request_transition', 'on', true);

UPDATE requests AS r
SET status = m.next_state
FROM r2_status_reconciliation AS m
WHERE r.id = m.request_id;

SELECT set_config('gdpr.request_transition', 'off', true);

INSERT INTO request_events (
    request_id, event_type, event_description, event_date, actor,
    previous_state, next_state, reason, evidence_reference
)
SELECT
    request_id,
    'state_reconciled',
    'Historical request status reconciled during R2 lifecycle hardening',
    NOW(),
    'migration:032',
    previous_state,
    next_state,
    CASE
        WHEN previous_state IS NULL THEN 'Null historical status conservatively routed to human review'
        WHEN previous_state IN ('action_required', 'verification_needed')
            THEN 'Ambiguous historical action state conservatively routed to the closest review queue'
        WHEN previous_state IN (
            'draft_pending_review', 'pending', 'data_available', 'data_received',
            'partial_data', 'processing', 'data_analyzed', 'rejected', 'extended'
        ) THEN 'Explicit historical-to-canonical lifecycle mapping'
        ELSE 'Unknown historical status conservatively routed to human review'
    END,
    'migration:032'
FROM r2_status_reconciliation;

ALTER TABLE requests
    ALTER COLUMN status SET DEFAULT 'draft',
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE requests
    DROP CONSTRAINT IF EXISTS requests_status_canonical_check;

ALTER TABLE requests
    ADD CONSTRAINT requests_status_canonical_check CHECK (status IN (
        'draft', 'ready_for_review', 'scheduled', 'sent', 'awaiting_response',
        'identity_action_required', 'clarification_action_required',
        'response_received', 'processing_response', 'completed',
        'closed_incomplete', 'cancelled'
    ));
