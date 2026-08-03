import { pool } from '@/lib/db';
import type {
    AppendRequestEventInput,
    CreateRequestInput,
    ReceivedDataRecord,
    Request,
    RequestChatMessage,
    RequestContext,
    RequestCounts,
    RequestEvent,
    RequestListOptions,
    RequestMessage,
    TransitionRequestCommand,
} from './types';

export interface RequestQueryResult<Row> {
    rows: Row[];
    rowCount: number | null;
}

export interface RequestDatabaseClient {
    query<Row = Record<string, unknown>>(sql: string, values?: readonly unknown[]): Promise<RequestQueryResult<Row>>;
    release(): void;
}

export interface RequestDatabase {
    query<Row = Record<string, unknown>>(sql: string, values?: readonly unknown[]): Promise<RequestQueryResult<Row>>;
    connect(): Promise<RequestDatabaseClient>;
}

export interface RequestDashboardProjection {
    counts: Record<string, string>;
    states: { state: string; count: string }[];
    artefacts: { company_name: string; artefact_count: string; total_mb: string; overall_artefact_count: string; overall_total_mb: string }[];
    timeline: { date: Date; requests: string; completed: string }[];
    failedWorkflows: string;
    duration: { sample_count: string; average_days: string | null; fastest_days: string | null } | null;
}

const REQUEST_COLUMNS = `
    id, profile_id, company_name, company_url, domain, request_type, status,
    progress, notes, created_at, updated_at, sent_at, controller_received_at,
    identity_requested_at, identity_verified_at, clarification_requested_at,
    clarification_resolved_at, response_received_at, completed_at, deadline_at,
    deadline_basis, extension_notified_at, extension_deadline_at, next_action_at
`;

function requireProfileId(profileId: string): void {
    if (!profileId.trim()) throw new TypeError('profileId is required');
}

export class RequestRepository {
    constructor(private readonly database: RequestDatabase = pool as unknown as RequestDatabase) {}

    async list(profileId: string, options: RequestListOptions = {}): Promise<Request[]> {
        requireProfileId(profileId);
        const values: unknown[] = [profileId];
        const where = ['profile_id = $1'];

        if (options.search?.trim()) {
            values.push(`%${options.search.trim()}%`);
            where.push(`(company_name ILIKE $${values.length} OR domain ILIKE $${values.length})`);
        }
        if (options.status) {
            values.push(options.status);
            where.push(`status = $${values.length}`);
        }

        const orderBy = {
            created_desc: 'created_at DESC',
            created_asc: 'created_at ASC',
            company_asc: 'company_name ASC',
            deadline_asc: 'deadline_at ASC NULLS LAST',
        }[options.sort ?? 'created_desc'];
        const limit = Math.min(200, Math.max(1, Math.trunc(options.limit ?? 100)));
        const offset = Math.max(0, Math.trunc(options.offset ?? 0));
        values.push(limit, offset);

        const result = await this.database.query<Request>(`
            SELECT ${REQUEST_COLUMNS} FROM requests
            WHERE ${where.join(' AND ')}
            ORDER BY ${orderBy}
            LIMIT $${values.length - 1} OFFSET $${values.length}
        `, values);
        return result.rows;
    }

    async get(profileId: string, requestId: string): Promise<Request | null> {
        requireProfileId(profileId);
        const result = await this.database.query<Request>(`
            SELECT ${REQUEST_COLUMNS} FROM requests WHERE id = $1 AND profile_id = $2
        `, [requestId, profileId]);
        return result.rows[0] ?? null;
    }

    async history(profileId: string, domain: string, excludeRequestId?: string): Promise<Request[]> {
        requireProfileId(profileId);
        const values: unknown[] = [domain, profileId];
        let exclusion = '';
        if (excludeRequestId) {
            values.push(excludeRequestId);
            exclusion = 'AND id <> $3';
        }
        const result = await this.database.query<Request>(`
            SELECT ${REQUEST_COLUMNS} FROM requests
            WHERE domain = $1 AND profile_id = $2 ${exclusion}
            ORDER BY created_at DESC LIMIT 10
        `, values);
        return result.rows;
    }

    async counts(profileId: string): Promise<RequestCounts> {
        requireProfileId(profileId);
        const result = await this.database.query<{ status: Request['status']; count: number }>(`
            SELECT status, COUNT(*)::int AS count
            FROM requests WHERE profile_id = $1 GROUP BY status
        `, [profileId]);
        const byState: RequestCounts['by_state'] = {};
        let total = 0;
        for (const row of result.rows) {
            const count = Number(row.count);
            byState[row.status] = count;
            total += count;
        }
        return { total, by_state: byState };
    }

    async contactedCompanyNames(profileId: string, companyNames: string[]): Promise<string[]> {
        requireProfileId(profileId);
        if (companyNames.length === 0) return [];
        const result = await this.database.query<{ company: string }>(`
            SELECT DISTINCT LOWER(company_name) AS company FROM requests
            WHERE profile_id=$1 AND LOWER(company_name)=ANY($2::text[])
              AND status IN ('sent','awaiting_response','response_received','processing_response','completed')
        `, [profileId, companyNames.map(name => name.toLowerCase())]);
        return result.rows.map(row => row.company);
    }

    async create(profileId: string, input: CreateRequestInput): Promise<Request> {
        requireProfileId(profileId);
        const values = [
            profileId, input.company_name, input.company_url ?? null, input.domain ?? null,
            input.request_type, input.status ?? 'draft', input.progress ?? 0, input.notes ?? null,
            input.sent_at ?? null, input.controller_received_at ?? null,
            input.identity_requested_at ?? null, input.identity_verified_at ?? null,
            input.clarification_requested_at ?? null, input.clarification_resolved_at ?? null,
            input.response_received_at ?? null, input.completed_at ?? null,
            input.deadline_at ?? null, input.deadline_basis ?? null,
            input.extension_notified_at ?? null, input.extension_deadline_at ?? null,
            input.next_action_at ?? null,
        ];
        const result = await this.database.query<Request>(`
            INSERT INTO requests (
                profile_id, company_name, company_url, domain, request_type, status,
                progress, notes, sent_at, controller_received_at, identity_requested_at,
                identity_verified_at, clarification_requested_at, clarification_resolved_at,
                response_received_at, completed_at, deadline_at, deadline_basis,
                extension_notified_at, extension_deadline_at, next_action_at
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21
            ) RETURNING ${REQUEST_COLUMNS}
        `, values);
        if (!result.rows[0]) throw new Error('Request creation returned no row');
        return result.rows[0];
    }

    async updateProgress(profileId: string, requestId: string, progress: number): Promise<Request | null> {
        requireProfileId(profileId);
        const result = await this.database.query<Request>(`
            UPDATE requests SET progress = $1
            WHERE id = $2 AND profile_id = $3 RETURNING ${REQUEST_COLUMNS}
        `, [progress, requestId, profileId]);
        return result.rows[0] ?? null;
    }

    async updateNotes(profileId: string, requestId: string, notes: string | null): Promise<Request | null> {
        requireProfileId(profileId);
        const result = await this.database.query<Request>(`
            UPDATE requests SET notes = $1
            WHERE id = $2 AND profile_id = $3 RETURNING ${REQUEST_COLUMNS}
        `, [notes, requestId, profileId]);
        return result.rows[0] ?? null;
    }

    async transition(profileId: string, command: TransitionRequestCommand): Promise<Request | null> {
        requireProfileId(profileId);
        const values = [
            command.request_id, profileId, command.next_state, command.actor, command.reason,
            command.evidence_reference ?? null, command.transitioned_at, command.sent_at ?? null,
            command.controller_received_at ?? null, command.identity_requested_at ?? null,
            command.identity_verified_at ?? null, command.clarification_requested_at ?? null,
            command.clarification_resolved_at ?? null, command.response_received_at ?? null,
            command.completed_at ?? null, command.deadline_at ?? null, command.deadline_basis ?? null,
            command.extension_notified_at ?? null, command.extension_deadline_at ?? null,
            command.next_action_at ?? null,
        ];
        const result = await this.database.query<Request>(`
            WITH transitioned AS MATERIALIZED (
                SELECT transition_request_state(
                    $1::uuid,$2::uuid,$3,$4,$5,$6,$7::timestamptz,$8::timestamptz,
                    $9::timestamptz,$10::timestamptz,$11::timestamptz,$12::timestamptz,
                    $13::timestamptz,$14::timestamptz,$15::timestamptz,$16::timestamptz,
                    $17,$18::timestamptz,$19::timestamptz,$20::timestamptz
                ) AS request
            )
            SELECT (request).* FROM transitioned
        `, values);
        return result.rows[0] ?? null;
    }

    async events(profileId: string, requestId: string): Promise<RequestEvent[]> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestEvent>(`
            SELECT e.* FROM request_events e
            JOIN requests r ON r.id = e.request_id
            WHERE e.request_id = $1 AND r.profile_id = $2
            ORDER BY e.event_date ASC
        `, [requestId, profileId]);
        return result.rows;
    }

    async appendEvent(profileId: string, event: AppendRequestEventInput): Promise<RequestEvent | null> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestEvent>(`
            INSERT INTO request_events (
                request_id,event_type,event_description,event_date,actor,reason,evidence_reference
            )
            SELECT r.id,$2,$3,$4,$5,$6,$7 FROM requests r
            WHERE r.id = $1 AND r.profile_id = $8
            RETURNING *
        `, [event.request_id, event.event_type, event.description ?? null, event.occurred_at,
            event.actor, event.reason, event.evidence_reference ?? null, profileId]);
        return result.rows[0] ?? null;
    }

    async messages(profileId: string, requestId: string): Promise<RequestMessage[]> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestMessage>(`
            SELECT m.* FROM messages m JOIN requests r ON r.id = m.request_id
            WHERE m.request_id = $1 AND r.profile_id = $2 ORDER BY m.timestamp ASC
        `, [requestId, profileId]);
        return result.rows;
    }

    async appendMessage(profileId: string, requestId: string, sender: string, content: string): Promise<RequestMessage | null> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestMessage>(`
            INSERT INTO messages (request_id,sender,content)
            SELECT r.id,$2,$3 FROM requests r WHERE r.id = $1 AND r.profile_id = $4
            RETURNING *
        `, [requestId, sender, content, profileId]);
        return result.rows[0] ?? null;
    }

    async chat(profileId: string, requestId: string): Promise<RequestChatMessage[]> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestChatMessage>(`
            SELECT c.* FROM request_chat_messages c JOIN requests r ON r.id = c.request_id
            WHERE c.request_id = $1 AND r.profile_id = $2 ORDER BY c.timestamp ASC
        `, [requestId, profileId]);
        return result.rows;
    }

    async appendChatMessage(profileId: string, requestId: string, sender: string, message: string): Promise<RequestChatMessage | null> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestChatMessage>(`
            INSERT INTO request_chat_messages (request_id,sender,message)
            SELECT r.id,$2,$3 FROM requests r WHERE r.id = $1 AND r.profile_id = $4
            RETURNING *
        `, [requestId, sender, message, profileId]);
        return result.rows[0] ?? null;
    }

    async receivedData(profileId: string, requestId: string): Promise<ReceivedDataRecord[]> {
        requireProfileId(profileId);
        const result = await this.database.query<ReceivedDataRecord>(`
            SELECT rd.* FROM received_data rd JOIN requests r ON r.id = rd.request_id
            WHERE rd.request_id = $1 AND rd.profile_id = $2 AND r.profile_id = $2
            ORDER BY rd.date_received DESC
        `, [requestId, profileId]);
        return result.rows;
    }

    async addReceivedData(profileId:string,requestId:string,input:{file_name:string;file_size_mb:number;file_path?:string|null}):Promise<ReceivedDataRecord|null>{
        requireProfileId(profileId);
        const result=await this.database.query<ReceivedDataRecord>(`
            INSERT INTO received_data(request_id,file_name,file_size_mb,file_path,profile_id)
            SELECT r.id,$2,$3,$4,r.profile_id FROM requests r WHERE r.id=$1 AND r.profile_id=$5
            RETURNING *`,[requestId,input.file_name,input.file_size_mb,input.file_path??null,profileId]);
        return result.rows[0]??null;
    }

    async requestDetails(profileId:string,requestId:string):Promise<Record<string,unknown>[]>{
        requireProfileId(profileId);
        const result=await this.database.query<Record<string,unknown>>(`
            SELECT d.* FROM request_details d JOIN requests r ON r.id=d.request_id
            WHERE d.request_id=$1 AND r.profile_id=$2 ORDER BY d.field_key`,[requestId,profileId]);
        return result.rows;
    }

    async addRequestDetail(profileId:string,requestId:string,fieldKey:string,encryptedValue:string):Promise<boolean>{
        requireProfileId(profileId);
        const result=await this.database.query(`
            INSERT INTO request_details(request_id,field_key,field_value_encrypted)
            SELECT r.id,$2,$3 FROM requests r WHERE r.id=$1 AND r.profile_id=$4`,
            [requestId,fieldKey,encryptedValue,profileId]);
        return result.rowCount===1;
    }

    async reviewItems(profileId:string):Promise<{messages:Record<string,unknown>[];files:Record<string,unknown>[]}>{
        requireProfileId(profileId);
        const [messages,files]=await Promise.all([
            this.database.query<Record<string,unknown>>(`SELECT m.id,m.content,m.timestamp,r.company_name,r.id AS request_id
                FROM messages m JOIN requests r ON m.request_id=r.id
                WHERE m.sender='company' AND r.profile_id=$1 ORDER BY m.timestamp DESC LIMIT 10`,[profileId]),
            this.database.query<Record<string,unknown>>(`SELECT rd.id,rd.file_name,rd.file_size_mb,rd.date_received,r.company_name,r.id AS request_id
                FROM received_data rd JOIN requests r ON rd.request_id=r.id
                WHERE rd.profile_id=$1 AND r.profile_id=$1 ORDER BY rd.date_received DESC LIMIT 5`,[profileId]),
        ]);
        return {messages:messages.rows,files:files.rows};
    }

    async getOwnedReceivedData(profileId: string, receivedDataId: string): Promise<ReceivedDataRecord | null> {
        requireProfileId(profileId);
        const result = await this.database.query<ReceivedDataRecord>(`
            SELECT rd.* FROM received_data rd JOIN requests r ON r.id = rd.request_id
            WHERE rd.id = $1 AND rd.profile_id = $2 AND r.profile_id = $2
        `, [receivedDataId, profileId]);
        return result.rows[0] ?? null;
    }

    async context(profileId: string, requestId: string): Promise<RequestContext | null> {
        requireProfileId(profileId);
        const result = await this.database.query<RequestContext>(`
            SELECT r.*,
                   COALESCE(files.received_file_count, 0)::int AS received_file_count,
                   COALESCE(files.received_file_status_counts, '{}'::jsonb) AS received_file_status_counts
            FROM requests r
            LEFT JOIN LATERAL (
                SELECT SUM(grouped.file_count)::int AS received_file_count,
                       jsonb_object_agg(grouped.status, grouped.file_count) AS received_file_status_counts
                FROM (
                    SELECT COALESCE(rd.status, 'unknown') AS status, COUNT(*)::int AS file_count
                    FROM received_data rd
                    WHERE rd.request_id = r.id AND rd.profile_id = r.profile_id
                    GROUP BY COALESCE(rd.status, 'unknown')
                ) grouped
            ) files ON TRUE
            WHERE r.id = $1 AND r.profile_id = $2
        `, [requestId, profileId]);
        return result.rows[0] ?? null;
    }

    async dashboard(profileId: string): Promise<RequestDashboardProjection> {
        requireProfileId(profileId);
        const [counts, states, artefacts, timeline, failed, duration] = await Promise.all([
            this.database.query<Record<string, string>>(`
                SELECT COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status IN ('ready_for_review','identity_action_required','clarification_action_required','processing_response','action_required','processing')) AS pending,
                    COUNT(*) FILTER (WHERE status='completed') AS completed,
                    COUNT(*) FILTER (WHERE response_received_at IS NOT NULL) AS responses_received,
                    COUNT(*) FILTER (WHERE COALESCE(CASE WHEN extension_notified_at IS NOT NULL AND extension_deadline_at IS NOT NULL THEN extension_deadline_at END,deadline_at)>=NOW() AND status NOT IN ('completed','closed_incomplete','cancelled')) AS known_upcoming_deadlines,
                    COUNT(*) FILTER (WHERE COALESCE(CASE WHEN extension_notified_at IS NOT NULL AND extension_deadline_at IS NOT NULL THEN extension_deadline_at END,deadline_at) IS NULL AND status NOT IN ('completed','closed_incomplete','cancelled')) AS unknown_deadlines,
                    COUNT(*) FILTER (WHERE request_type LIKE '%access%') AS access_count,
                    COUNT(*) FILTER (WHERE request_type LIKE '%deletion%') AS deletion_count
                FROM requests WHERE profile_id=$1`, [profileId]),
            this.database.query<{ state: string; count: string }>(`
                SELECT status AS state,COUNT(*) AS count FROM requests
                WHERE profile_id=$1 GROUP BY status ORDER BY status`, [profileId]),
            this.database.query<RequestDashboardProjection['artefacts'][number]>(`
                SELECT r.company_name,COUNT(rd.id) AS artefact_count,COALESCE(SUM(rd.file_size_mb),0) AS total_mb,
                    SUM(COUNT(rd.id)) OVER () AS overall_artefact_count,
                    SUM(COALESCE(SUM(rd.file_size_mb),0)) OVER () AS overall_total_mb
                FROM requests r JOIN received_data rd ON rd.request_id=r.id AND rd.profile_id=$1
                WHERE r.profile_id=$1 GROUP BY r.company_name
                ORDER BY COUNT(rd.id) DESC,COALESCE(SUM(rd.file_size_mb),0) DESC LIMIT 5`, [profileId]),
            this.database.query<RequestDashboardProjection['timeline'][number]>(`
                SELECT day::date AS date,
                    COUNT(r.id) FILTER (WHERE r.created_at>=day AND r.created_at<day+INTERVAL '1 day') AS requests,
                    COUNT(r.id) FILTER (WHERE r.completed_at>=day AND r.completed_at<day+INTERVAL '1 day') AS completed
                FROM generate_series(date_trunc('day',NOW())-INTERVAL '6 days',date_trunc('day',NOW()),INTERVAL '1 day') AS day
                LEFT JOIN requests r ON r.profile_id=$1 AND ((r.created_at>=day AND r.created_at<day+INTERVAL '1 day') OR (r.completed_at>=day AND r.completed_at<day+INTERVAL '1 day'))
                GROUP BY day ORDER BY day`, [profileId]),
            this.database.query<{ failed: string }>(`
                SELECT COUNT(*) AS failed FROM workflow_logs wl JOIN requests r ON r.id=wl.request_id
                WHERE r.profile_id=$1 AND wl.status='failed'`, [profileId]),
            this.database.query<{ sample_count: string; average_days: string | null; fastest_days: string | null }>(`
                SELECT COUNT(*) AS sample_count,
                    AVG(EXTRACT(EPOCH FROM (response_received_at-controller_received_at))/86400.0) AS average_days,
                    MIN(EXTRACT(EPOCH FROM (response_received_at-controller_received_at))/86400.0) AS fastest_days
                FROM requests WHERE profile_id=$1 AND controller_received_at IS NOT NULL
                    AND response_received_at IS NOT NULL AND response_received_at>=controller_received_at`, [profileId]),
        ]);
        return {
            counts: counts.rows[0] ?? {}, states: states.rows, artefacts: artefacts.rows,
            timeline: timeline.rows, failedWorkflows: failed.rows[0]?.failed ?? '0',
            duration: duration.rows[0] ?? null,
        };
    }

    async delete(profileId: string, requestId: string): Promise<boolean> {
        requireProfileId(profileId);
        const client = await this.database.connect();
        try {
            await client.query('BEGIN');
            const owned = await client.query<{ id: string }>(`
                SELECT id FROM requests WHERE id = $1 AND profile_id = $2 FOR UPDATE
            `, [requestId, profileId]);
            if (!owned.rows[0]) {
                await client.query('ROLLBACK');
                return false;
            }
            const deleted = await client.query<{ id: string }>(`
                DELETE FROM requests WHERE id = $1 AND profile_id = $2 RETURNING id
            `, [requestId, profileId]);
            if (!deleted.rows[0]) throw new Error('Owned request disappeared during deletion');
            await client.query('COMMIT');
            return true;
        } catch (error) {
            await client.query('ROLLBACK');
            throw error;
        } finally {
            client.release();
        }
    }
}
