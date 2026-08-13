-- Record extension justification separately from the ordinary deadline basis.
ALTER TABLE requests ADD COLUMN IF NOT EXISTS extension_reason TEXT;

CREATE OR REPLACE VIEW access_requests AS
SELECT
    id, company_name, company_url, domain, status, request_type, created_at, profile_id,
    progress, data_volume_mb, next_action_date, deadline_date,
    data_period_start, data_period_end, notes, updated_at,
    sent_at, controller_received_at, identity_requested_at, identity_verified_at,
    clarification_requested_at, clarification_resolved_at, response_received_at,
    completed_at, deadline_at, deadline_basis, extension_notified_at,
    extension_deadline_at, next_action_at, extension_reason
FROM requests;

COMMENT ON VIEW access_requests IS
    'Deprecated read-only compatibility view. requests is the canonical profile-scoped request table.';
