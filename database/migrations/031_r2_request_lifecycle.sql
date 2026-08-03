-- R2: canonical, evidence-backed request lifecycle.
--
-- Operational timestamps are not legal evidence.  In particular, this
-- migration never derives receipt, response, completion, or deadline dates
-- from created_at, updated_at, or the legacy deadline_date column.

ALTER TABLE requests ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
UPDATE requests SET updated_at = NOW() WHERE updated_at IS NULL;
ALTER TABLE requests ALTER COLUMN updated_at SET DEFAULT NOW();
ALTER TABLE requests ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE requests ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS controller_received_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS identity_requested_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS identity_verified_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS clarification_requested_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS clarification_resolved_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS response_received_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS deadline_basis TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS extension_notified_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS extension_deadline_at TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMPTZ;

-- next_action_date and next_action_at have the same operational meaning.
-- deadline_date is deliberately retained and deliberately not copied.
UPDATE requests
SET next_action_at = next_action_date
WHERE next_action_at IS NULL
  AND next_action_date IS NOT NULL;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS requests_set_updated_at ON requests;
CREATE TRIGGER requests_set_updated_at
BEFORE UPDATE ON requests
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE request_events ADD COLUMN IF NOT EXISTS actor TEXT;
ALTER TABLE request_events ADD COLUMN IF NOT EXISTS previous_state TEXT;
ALTER TABLE request_events ADD COLUMN IF NOT EXISTS next_state TEXT;
ALTER TABLE request_events ADD COLUMN IF NOT EXISTS reason TEXT;
ALTER TABLE request_events ADD COLUMN IF NOT EXISTS evidence_reference TEXT;

-- Preserve legacy provenance without pretending to know an actor or reason.
UPDATE request_events
SET actor = 'legacy/unknown'
WHERE actor IS NULL OR btrim(actor) = '';

UPDATE request_events
SET reason = 'legacy/unknown'
WHERE reason IS NULL OR btrim(reason) = '';

ALTER TABLE request_events ALTER COLUMN actor SET NOT NULL;
ALTER TABLE request_events ALTER COLUMN reason SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'request_events'::regclass
          AND conname = 'request_events_actor_nonempty'
    ) THEN
        ALTER TABLE request_events
            ADD CONSTRAINT request_events_actor_nonempty CHECK (btrim(actor) <> '');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'request_events'::regclass
          AND conname = 'request_events_reason_nonempty'
    ) THEN
        ALTER TABLE request_events
            ADD CONSTRAINT request_events_reason_nonempty CHECK (btrim(reason) <> '');
    END IF;
END $$;

CREATE OR REPLACE FUNCTION reject_request_event_mutation() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'request_events is append-only; % is not permitted', TG_OP
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS request_events_append_only ON request_events;
CREATE TRIGGER request_events_append_only
BEFORE UPDATE OR DELETE ON request_events
FOR EACH ROW EXECUTE FUNCTION reject_request_event_mutation();

-- Status changes must pass through transition_request_state().  The function
-- sets a transaction-local guard only around its locked UPDATE.
CREATE OR REPLACE FUNCTION guard_request_status_transition() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status
       AND COALESCE(current_setting('gdpr.request_transition', true), 'off') <> 'on' THEN
        RAISE EXCEPTION 'requests.status may only be changed by transition_request_state()'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS requests_status_transition_guard ON requests;
CREATE TRIGGER requests_status_transition_guard
BEFORE UPDATE OF status ON requests
FOR EACH ROW EXECUTE FUNCTION guard_request_status_transition();

CREATE OR REPLACE FUNCTION transition_request_state(
    p_request_id UUID,
    p_profile_id UUID,
    p_next_state TEXT,
    p_actor TEXT,
    p_reason TEXT,
    p_evidence_reference TEXT DEFAULT NULL,
    p_transitioned_at TIMESTAMPTZ DEFAULT NOW(),
    p_sent_at TIMESTAMPTZ DEFAULT NULL,
    p_controller_received_at TIMESTAMPTZ DEFAULT NULL,
    p_identity_requested_at TIMESTAMPTZ DEFAULT NULL,
    p_identity_verified_at TIMESTAMPTZ DEFAULT NULL,
    p_clarification_requested_at TIMESTAMPTZ DEFAULT NULL,
    p_clarification_resolved_at TIMESTAMPTZ DEFAULT NULL,
    p_response_received_at TIMESTAMPTZ DEFAULT NULL,
    p_completed_at TIMESTAMPTZ DEFAULT NULL,
    p_deadline_at TIMESTAMPTZ DEFAULT NULL,
    p_deadline_basis TEXT DEFAULT NULL,
    p_extension_notified_at TIMESTAMPTZ DEFAULT NULL,
    p_extension_deadline_at TIMESTAMPTZ DEFAULT NULL,
    p_next_action_at TIMESTAMPTZ DEFAULT NULL
) RETURNS requests
LANGUAGE plpgsql
AS $$
DECLARE
    current_request requests%ROWTYPE;
    updated_request requests%ROWTYPE;
    validation_state TEXT;
    allowed BOOLEAN := FALSE;
BEGIN
    IF p_actor IS NULL OR btrim(p_actor) = '' THEN
        RAISE EXCEPTION 'request transition actor is required' USING ERRCODE = '22023';
    END IF;
    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'request transition reason is required' USING ERRCODE = '22023';
    END IF;
    IF p_transitioned_at IS NULL THEN
        RAISE EXCEPTION 'request transition timestamp is required' USING ERRCODE = '22023';
    END IF;
    IF p_next_state IS NULL OR p_next_state <> ALL (ARRAY[
        'draft', 'ready_for_review', 'scheduled', 'sent', 'awaiting_response',
        'identity_action_required', 'clarification_action_required',
        'response_received', 'processing_response', 'completed',
        'closed_incomplete', 'cancelled'
    ]) THEN
        RAISE EXCEPTION 'unknown canonical request state: %', p_next_state
            USING ERRCODE = '22023';
    END IF;

    SELECT * INTO current_request
    FROM requests
    WHERE id = p_request_id AND profile_id = p_profile_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'request not found for canonical profile' USING ERRCODE = 'P0002';
    END IF;

    -- Historical strings remain stored until an explicit transition.  The
    -- mapping below is used only to validate that explicit transition.
    validation_state := CASE current_request.status
        WHEN 'processing' THEN 'processing_response'
        ELSE current_request.status
    END;

    IF current_request.status = 'action_required' THEN
        -- The legacy value did not distinguish identity from clarification.
        -- Require the caller to choose the evidence-supported canonical path.
        allowed := p_next_state = ANY (ARRAY[
            'awaiting_response', 'identity_action_required',
            'clarification_action_required', 'response_received',
            'processing_response', 'closed_incomplete', 'cancelled'
        ]);
    ELSE
        allowed := CASE validation_state
            WHEN 'draft' THEN p_next_state = ANY (ARRAY['ready_for_review', 'cancelled'])
            WHEN 'ready_for_review' THEN p_next_state = ANY (ARRAY['draft', 'scheduled', 'sent', 'cancelled'])
            WHEN 'scheduled' THEN p_next_state = ANY (ARRAY['ready_for_review', 'sent', 'cancelled'])
            WHEN 'sent' THEN p_next_state = ANY (ARRAY['awaiting_response', 'identity_action_required', 'clarification_action_required', 'response_received', 'closed_incomplete', 'cancelled'])
            WHEN 'awaiting_response' THEN p_next_state = ANY (ARRAY['identity_action_required', 'clarification_action_required', 'response_received', 'closed_incomplete', 'cancelled'])
            WHEN 'identity_action_required' THEN p_next_state = ANY (ARRAY['awaiting_response', 'clarification_action_required', 'response_received', 'closed_incomplete', 'cancelled'])
            WHEN 'clarification_action_required' THEN p_next_state = ANY (ARRAY['awaiting_response', 'identity_action_required', 'response_received', 'closed_incomplete', 'cancelled'])
            WHEN 'response_received' THEN p_next_state = ANY (ARRAY['processing_response', 'completed', 'closed_incomplete'])
            WHEN 'processing_response' THEN p_next_state = ANY (ARRAY['response_received', 'completed', 'closed_incomplete'])
            ELSE FALSE
        END;
    END IF;

    IF NOT allowed THEN
        RAISE EXCEPTION 'invalid request transition from % to %', current_request.status, p_next_state
            USING ERRCODE = '22023';
    END IF;

    PERFORM set_config('gdpr.request_transition', 'on', true);
    UPDATE requests
    SET status = p_next_state,
        sent_at = COALESCE(p_sent_at, sent_at),
        controller_received_at = COALESCE(p_controller_received_at, controller_received_at),
        identity_requested_at = COALESCE(p_identity_requested_at, identity_requested_at),
        identity_verified_at = COALESCE(p_identity_verified_at, identity_verified_at),
        clarification_requested_at = COALESCE(p_clarification_requested_at, clarification_requested_at),
        clarification_resolved_at = COALESCE(p_clarification_resolved_at, clarification_resolved_at),
        response_received_at = COALESCE(p_response_received_at, response_received_at),
        completed_at = COALESCE(p_completed_at, completed_at),
        deadline_at = COALESCE(p_deadline_at, deadline_at),
        deadline_basis = COALESCE(p_deadline_basis, deadline_basis),
        extension_notified_at = COALESCE(p_extension_notified_at, extension_notified_at),
        extension_deadline_at = COALESCE(p_extension_deadline_at, extension_deadline_at),
        next_action_at = COALESCE(p_next_action_at, next_action_at)
    WHERE id = p_request_id AND profile_id = p_profile_id
    RETURNING * INTO updated_request;
    PERFORM set_config('gdpr.request_transition', 'off', true);

    INSERT INTO request_events (
        request_id, event_type, event_description, event_date, actor,
        previous_state, next_state, reason, evidence_reference
    ) VALUES (
        p_request_id, 'state_transition', p_reason, p_transitioned_at, p_actor,
        current_request.status, p_next_state, p_reason, p_evidence_reference
    );

    RETURN updated_request;
END;
$$;

CREATE INDEX IF NOT EXISTS requests_profile_status_idx
    ON requests(profile_id, status);
CREATE INDEX IF NOT EXISTS requests_profile_deadline_idx
    ON requests(profile_id, deadline_at)
    WHERE deadline_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS requests_profile_next_action_idx
    ON requests(profile_id, next_action_at)
    WHERE next_action_at IS NOT NULL;

-- Temporary compatibility surface.  Canonical code must use requests.
CREATE OR REPLACE VIEW access_requests AS
SELECT
    id, company_name, company_url, domain, status, request_type, created_at, profile_id,
    progress, data_volume_mb, next_action_date, deadline_date,
    data_period_start, data_period_end, notes, updated_at,
    sent_at, controller_received_at, identity_requested_at, identity_verified_at,
    clarification_requested_at, clarification_resolved_at, response_received_at,
    completed_at, deadline_at, deadline_basis, extension_notified_at,
    extension_deadline_at, next_action_at
FROM requests;

COMMENT ON VIEW access_requests IS
    'Deprecated read-only compatibility view. requests is the canonical profile-scoped request table.';

CREATE OR REPLACE FUNCTION reject_access_requests_write() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'access_requests is a read-only compatibility view; write requests instead'
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS access_requests_read_only ON access_requests;
CREATE TRIGGER access_requests_read_only
INSTEAD OF INSERT OR UPDATE OR DELETE ON access_requests
FOR EACH ROW EXECUTE FUNCTION reject_access_requests_write();

