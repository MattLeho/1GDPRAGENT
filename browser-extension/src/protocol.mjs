export const PROTOCOL_VERSION = 1;
export const MAX_BATCH_RECORDS = 250;

function normalise(value) {
  if (Array.isArray(value)) return value.map(normalise);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, normalise(value[key])]));
  }
  return value;
}

export function canonicalJson(value) {
  return JSON.stringify(normalise(value));
}

function pythonIsoTimestamp(value) {
  const iso = new Date(value).toISOString();
  return iso.endsWith('.000Z') ? iso.replace('.000Z', 'Z') : iso.replace(/\.(\d{3})Z$/, '.$1000Z');
}

async function sha256Hex(value) {
  const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value;
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

export function visitPayload(visit) {
  return new TextEncoder().encode(canonicalJson({
    browser_profile_connector_id: visit.browserProfileConnectorId,
    referring_visit_id: visit.referringVisitId ?? null,
    transition_type: visit.transitionType ?? 'unknown',
    url: visit.url,
    visit_id: String(visit.visitId),
    visit_time: new Date(visit.visitTime).toISOString(),
  }));
}

export async function toBrowserVisitRecord(visit) {
  if (!visit.url || !Number.isFinite(visit.visitTime) || !visit.browserProfileConnectorId) {
    throw new TypeError('browser visit requires URL, visitTime and browser profile connector ID');
  }
  const payload = visitPayload(visit);
  const sourceMetadata = {
    browser_profile_connector_id: visit.browserProfileConnectorId,
    local_or_synced_origin: visit.isLocal === true ? 'local' : visit.isLocal === false ? 'synchronised_or_remote' : 'unknown',
    referring_visit_id: visit.referringVisitId ?? null,
    transition_type: visit.transitionType ?? 'unknown'
  };
  const occurredAt = new Date(visit.visitTime).toISOString();
  const descriptor = {
    data_class: 'browser.visit', media_type: 'application/json', occurred_at: pythonIsoTimestamp(visit.visitTime),
    payload_sha256: await sha256Hex(payload), source_metadata: sourceMetadata,
    source_record_id: `${visit.browserProfileConnectorId}:${String(visit.visitId)}`,
    source_record_version: '1'
  };
  return {
    source_record_id: descriptor.source_record_id,
    source_record_version: '1',
    record_signature: await sha256Hex(canonicalJson(descriptor)),
    data_class: 'browser.visit', occurred_at: occurredAt,
    observed_at: new Date().toISOString(), media_type: 'application/json',
    payload_base64: bytesToBase64(payload), source_metadata: sourceMetadata,
    required_permissions: ['history.read']
  };
}

function bytesToBase64(bytes) {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

export function frame(records, connectorInstanceId, messageId = crypto.randomUUID()) {
  if (!Array.isArray(records) || records.length < 1 || records.length > MAX_BATCH_RECORDS) {
    throw new RangeError(`frame must contain 1-${MAX_BATCH_RECORDS} records`);
  }
  return {
    protocol: 'gdpr-agent-connector', version: PROTOCOL_VERSION,
    message_id: messageId, connector_instance_id: connectorInstanceId,
    sent_at: new Date().toISOString(), records
  };
}

export function assertAcknowledgement(value, expectedMessageId) {
  if (!value || value.protocol !== 'gdpr-agent-connector' || value.version !== PROTOCOL_VERSION ||
      value.message_id !== expectedMessageId || value.status !== 'acknowledged') {
    throw new Error('invalid or mismatched local bridge acknowledgement');
  }
  return value;
}
