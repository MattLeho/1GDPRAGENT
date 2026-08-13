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
import { buildResponseClassificationCommand } from './response-classification';

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

export interface RequestActivityRows {
    logs: Array<{ id: string; workflow_name: string; workflow_type: string | null; status: string;
        details: unknown; started_at: Date | string | null; completed_at: Date | string | null; error_message: string | null }>;
    events: Array<{ id: string; event_type: string; event_description: string | null; event_date: Date | string | null }>;
    files: Array<{ id: string; file_name: string; status: string; processing_stage: string | null;
        processing_progress: number | null; graph_ingested: boolean | null; processing_started_at: Date | string | null;
        processing_completed_at: Date | string | null; error_message: string | null }>;
}

export interface RequestThreadUpdateInput {
    company: string;
    domain?: string | null;
    action: string;
    data: Record<string, unknown>;
    requestId?: string | null;
}

const REQUEST_COLUMNS = `
    id, profile_id, company_name, company_url, domain, request_type, status,
    progress, notes, created_at, updated_at, sent_at, controller_received_at,
    identity_requested_at, identity_verified_at, clarification_requested_at,
    clarification_resolved_at, response_received_at, completed_at, deadline_at,
    deadline_basis, extension_reason, extension_notified_at, extension_deadline_at, next_action_at
`;

function requireProfileId(profileId: string): void {
    if (!profileId.trim()) throw new TypeError('profileId is required');
}

async function executeTransition(
    database: Pick<RequestDatabase, 'query'>,
    profileId: string,
    command: TransitionRequestCommand,
): Promise<Request | null> {
    const values = [
        command.request_id, profileId, command.next_state, command.actor, command.reason,
        command.evidence_reference ?? null, command.transitioned_at, command.sent_at ?? null,
        command.controller_received_at ?? null, command.identity_requested_at ?? null,
        command.identity_verified_at ?? null, command.clarification_requested_at ?? null,
        command.clarification_resolved_at ?? null, command.response_received_at ?? null,
        command.completed_at ?? null, command.deadline_at ?? null, command.deadline_basis ?? null,
        command.extension_notified_at ?? null, command.extension_deadline_at ?? null,
        command.next_action_at ?? null, command.extension_reason ?? null,
    ];
    const result = await database.query<Request>(`
        WITH extension_recorded AS MATERIALIZED (
            UPDATE requests SET extension_reason=COALESCE($21,extension_reason)
            WHERE id=$1 AND profile_id=$2 RETURNING id
        ), transitioned AS MATERIALIZED (
            SELECT transition_request_state(
                $1::uuid,$2::uuid,$3,$4,$5,$6,$7::timestamptz,$8::timestamptz,
                $9::timestamptz,$10::timestamptz,$11::timestamptz,$12::timestamptz,
                $13::timestamptz,$14::timestamptz,$15::timestamptz,$16::timestamptz,
                $17,$18::timestamptz,$19::timestamptz,$20::timestamptz
            ) AS request FROM extension_recorded
        )
        SELECT (request).* FROM transitioned
    `, values);
    return result.rows[0] ?? null;
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
            input.next_action_at ?? null, input.extension_reason ?? null,
        ];
        const result = await this.database.query<Request>(`
            INSERT INTO requests (
                profile_id, company_name, company_url, domain, request_type, status,
                progress, notes, sent_at, controller_received_at, identity_requested_at,
                identity_verified_at, clarification_requested_at, clarification_resolved_at,
                response_received_at, completed_at, deadline_at, deadline_basis,
                extension_notified_at, extension_deadline_at, next_action_at, extension_reason
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22
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
        return executeTransition(this.database, profileId, command);
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

    async registerReceivedDataBatch(profileId: string, requestId: string | null, files: Array<{
        file_name: string; original_name: string; file_path: string; file_size_mb: number; file_type: string; category: string;
    }>): Promise<Array<{ id: string }>> {
        requireProfileId(profileId);
        if (requestId && !await this.get(profileId, requestId)) return [];
        const client = await this.database.connect();
        try {
            await client.query('BEGIN');
            const rows: Array<{ id: string }> = [];
            for (const file of files) {
                const result = await client.query<{ id: string }>(`
                    INSERT INTO received_data(request_id,file_name,original_name,file_path,file_size_mb,file_type,
                        category,status,processing_stage,profile_id)
                    VALUES($1,$2,$3,$4,$5,$6,$7,'pending','upload',$8) RETURNING id`,
                [requestId, file.file_name, file.original_name, file.file_path, file.file_size_mb,
                    file.file_type, file.category, profileId]);
                if (!result.rows[0]) throw new Error('Received-data insert returned no row');
                rows.push(result.rows[0]);
            }
            await client.query('COMMIT');
            return rows;
        } catch (error) {
            await client.query('ROLLBACK');
            throw error;
        } finally {
            client.release();
        }
    }

    async listReceivedData(profileId: string, filter: { fileId?: string | null; requestId?: string | null } = {}) {
        requireProfileId(profileId);
        const values: unknown[] = [profileId];
        let where = 'rd.profile_id=$1';
        if (filter.fileId) { values.push(filter.fileId); where += ` AND rd.id=$${values.length}`; }
        else if (filter.requestId) { values.push(filter.requestId); where += ` AND rd.request_id=$${values.length}`; }
        const result = await this.database.query<Record<string, unknown>>(`
            SELECT rd.* FROM received_data rd
            LEFT JOIN requests r ON r.id=rd.request_id
            WHERE ${where} AND (rd.request_id IS NULL OR r.profile_id=$1)
            ORDER BY rd.date_received DESC LIMIT 50`, values);
        return result.rows;
    }

    async pendingReceivedData(profileId: string): Promise<ReceivedDataRecord[]> {
        requireProfileId(profileId);
        const result = await this.database.query<ReceivedDataRecord>(`
            SELECT rd.* FROM received_data rd LEFT JOIN requests r ON r.id=rd.request_id
            WHERE rd.profile_id=$1 AND (rd.request_id IS NULL OR r.profile_id=$1)
              AND (rd.status IN ('pending','error','uploaded') OR (rd.provenance_status IS NULL AND rd.status<>'processing'))
            ORDER BY rd.date_received ASC LIMIT 100`, [profileId]);
        return result.rows;
    }

    async receivedDataVolume(profileId: string, requestId: string): Promise<number> {
        requireProfileId(profileId);
        const result = await this.database.query<{ total: string }>(`
            SELECT COALESCE(SUM(rd.file_size_mb),0) AS total FROM received_data rd
            JOIN requests r ON r.id=rd.request_id WHERE rd.request_id=$1 AND rd.profile_id=$2 AND r.profile_id=$2`,
        [requestId, profileId]);
        return Number(result.rows[0]?.total ?? 0);
    }

    async receivedDataStatusCounts(profileId: string, requestId: string) {
        requireProfileId(profileId);
        const result = await this.database.query<{ status: string; count: number }>(`
            SELECT rd.status,COUNT(*)::int AS count FROM received_data rd JOIN requests r ON r.id=rd.request_id
            WHERE rd.request_id=$1 AND rd.profile_id=$2 AND r.profile_id=$2 GROUP BY rd.status`,
        [requestId, profileId]);
        return result.rows;
    }

    async searchReceivedData(profileId: string, requestId: string, options: {
        fileName?: string; keywords?: readonly string[]; category?: string; limit?: number;
    } = {}) {
        requireProfileId(profileId);
        const values: unknown[] = [requestId, profileId];
        const where = ['rd.request_id=$1', 'rd.profile_id=$2', 'r.profile_id=$2'];
        if (options.fileName) { values.push(`%${options.fileName}%`); where.push(`LOWER(rd.file_name) LIKE LOWER($${values.length})`); }
        for (const keyword of options.keywords ?? []) {
            values.push(`%${keyword}%`);
            where.push(`(COALESCE(rd.extracted_text,'') ILIKE $${values.length} OR COALESCE(rd.ai_summary,'') ILIKE $${values.length}
                OR COALESCE(rd.transcript,'') ILIKE $${values.length} OR COALESCE(rd.extracted_entities::text,rd.entities_extracted::text,'') ILIKE $${values.length})`);
        }
        if (options.category) { values.push(options.category); where.push(`LOWER(rd.category)=LOWER($${values.length})`); }
        values.push(Math.min(100, Math.max(1, Math.trunc(options.limit ?? 50))));
        const result = await this.database.query<Record<string, unknown>>(`
            SELECT rd.* FROM received_data rd JOIN requests r ON r.id=rd.request_id
            WHERE ${where.join(' AND ')} ORDER BY rd.date_received DESC LIMIT $${values.length}`, values);
        return result.rows;
    }

    async updateReceivedData(profileId: string, fileId: string, input: Record<string, unknown>) {
        requireProfileId(profileId);
        const columns: Record<string, string> = {
            status: 'status', processingStage: 'processing_stage', processingProgress: 'processing_progress',
            extractedText: 'extracted_text', markdownContent: 'markdown_content', transcript: 'transcript',
            aiSummary: 'ai_summary', entitiesExtracted: 'entities_extracted', graphIngested: 'graph_ingested',
            errorMessage: 'error_message',
        };
        const updates: string[] = [];
        const values: unknown[] = [];
        for (const [key, column] of Object.entries(columns)) {
            if (input[key] === undefined) continue;
            values.push(key === 'entitiesExtracted' ? JSON.stringify(input[key]) : input[key]);
            updates.push(`${column}=$${values.length}${key === 'entitiesExtracted' ? '::jsonb' : ''}`);
        }
        if (input.status === 'processing') updates.push('processing_started_at=NOW()');
        if (input.status === 'completed' || input.status === 'error') updates.push('processing_completed_at=NOW()');
        if (updates.length === 0) return null;
        values.push(fileId, profileId);
        const result = await this.database.query<Record<string, unknown>>(`
            UPDATE received_data SET ${updates.join(',')}
            WHERE id=$${values.length - 1} AND profile_id=$${values.length} RETURNING *`, values);
        return result.rows[0] ?? null;
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
                    COUNT(*) FILTER (WHERE deadline_at>=NOW() AND status NOT IN ('completed','closed_incomplete','cancelled')) AS known_upcoming_deadlines,
                    COUNT(*) FILTER (WHERE deadline_at IS NULL AND status NOT IN ('completed','closed_incomplete','cancelled')) AS unknown_deadlines,
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

    async activity(profileId: string, requestId: string): Promise<RequestActivityRows | null> {
        requireProfileId(profileId);
        if (!await this.get(profileId, requestId)) return null;
        const [logs, events, files] = await Promise.all([
            this.database.query<RequestActivityRows['logs'][number]>(`
                SELECT wl.id,wl.workflow_name,wl.workflow_type,wl.status,wl.details,
                       wl.started_at,wl.completed_at,wl.error_message
                FROM workflow_logs wl JOIN requests r ON r.id=wl.request_id
                WHERE wl.request_id=$1 AND r.profile_id=$2
                ORDER BY wl.started_at DESC LIMIT 50`, [requestId, profileId]),
            this.database.query<RequestActivityRows['events'][number]>(`
                SELECT e.id,e.event_type,e.event_description,e.event_date
                FROM request_events e JOIN requests r ON r.id=e.request_id
                WHERE e.request_id=$1 AND r.profile_id=$2
                ORDER BY e.event_date DESC LIMIT 50`, [requestId, profileId]),
            this.database.query<RequestActivityRows['files'][number]>(`
                SELECT rd.id,rd.file_name,rd.status,rd.processing_stage,rd.processing_progress,
                       rd.graph_ingested,rd.processing_started_at,rd.processing_completed_at,rd.error_message
                FROM received_data rd JOIN requests r ON r.id=rd.request_id
                WHERE rd.request_id=$1 AND rd.profile_id=$2 AND r.profile_id=$2
                ORDER BY rd.date_received DESC`, [requestId, profileId]),
        ]);
        return { logs: logs.rows, events: events.rows, files: files.rows };
    }

    async startWorkflowLog(profileId: string, params: {
        requestId: string; workflowName: string; workflowType: string; details?: Record<string, unknown>;
    }): Promise<string | null> {
        requireProfileId(profileId);
        const result = await this.database.query<{ id: string }>(`
            INSERT INTO workflow_logs(request_id,workflow_name,workflow_type,status,details,started_at)
            SELECT r.id,$2,$3,'running',$4::jsonb,NOW() FROM requests r
            WHERE r.id=$1 AND r.profile_id=$5 RETURNING id`,
        [params.requestId, params.workflowName, params.workflowType,
            JSON.stringify(params.details ?? {}), profileId]);
        return result.rows[0]?.id ?? null;
    }

    async finishWorkflowLog(profileId: string, logId: string, input: {
        status: 'completed' | 'error'; details: Record<string, unknown>; errorMessage?: string | null;
    }): Promise<boolean> {
        requireProfileId(profileId);
        const result = await this.database.query(`
            UPDATE workflow_logs wl SET status=$2,completed_at=NOW(),error_message=$3,
                details=COALESCE(wl.details,'{}'::jsonb) || $4::jsonb
            FROM requests r WHERE wl.id=$1 AND r.id=wl.request_id AND r.profile_id=$5`,
        [logId, input.status, input.errorMessage ?? null, JSON.stringify(input.details), profileId]);
        return result.rowCount === 1;
    }

    async recordOutboundMessage(profileId: string, input: {
        requestId: string; transport: string; transportMessageId: string; recipient: string;
        subject: string; metadata: Record<string, unknown>;
    }, connection?: Pick<RequestDatabaseClient, 'query'>): Promise<boolean> {
        requireProfileId(profileId);
        const target = connection ?? this.database;
        const result = await target.query(`
            INSERT INTO outbound_messages(request_id,transport,transport_message_id,recipient,subject,status,metadata,sent_at)
            SELECT r.id,$2,$3,$4,$5,'sent',$6::jsonb,NOW() FROM requests r
            WHERE r.id=$1 AND r.profile_id=$7`,
        [input.requestId, input.transport, input.transportMessageId, input.recipient,
            input.subject, JSON.stringify(input.metadata), profileId]);
        return result.rowCount === 1;
    }

    async createEmailDraft(profileId:string,input:{requestId:string;recipient:string;subject:string;bodyCiphertext:string}){
        requireProfileId(profileId);
        const result=await this.database.query<Record<string,unknown>>(`
            INSERT INTO email_transport_drafts(request_id,recipient,subject,body_ciphertext)
            SELECT r.id,$2,$3,$4 FROM requests r WHERE r.id=$1 AND r.profile_id=$5
            RETURNING id,request_id,recipient,subject,status,reviewed_by,reviewed_at,transport_message_id,created_at,sent_at`,
        [input.requestId,input.recipient,input.subject,input.bodyCiphertext,profileId]);
        return result.rows[0]??null;
    }

    async reviewEmailDraft(profileId:string,draftId:string,reviewedBy:string){
        requireProfileId(profileId);
        const result=await this.database.query<Record<string,unknown>>(`
            UPDATE email_transport_drafts d SET status='reviewed',reviewed_by=$2,reviewed_at=NOW(),error=NULL
            FROM requests r WHERE d.id=$1 AND d.status='draft' AND r.id=d.request_id AND r.profile_id=$3
            RETURNING d.id,d.request_id,d.recipient,d.subject,d.status,d.reviewed_by,d.reviewed_at,d.transport_message_id,d.created_at,d.sent_at`,
        [draftId,reviewedBy,profileId]);
        return result.rows[0]??null;
    }

    async getReviewedEmailDraft(profileId:string,draftId:string){
        requireProfileId(profileId);
        const result=await this.database.query<Record<string,unknown>>(`
            SELECT d.id,d.request_id,d.recipient,d.subject,d.body_ciphertext,d.status
            FROM email_transport_drafts d JOIN requests r ON r.id=d.request_id
            WHERE d.id=$1 AND d.status='reviewed' AND r.profile_id=$2`,[draftId,profileId]);
        return result.rows[0]??null;
    }

    async markEmailDraftSent(profileId:string,draftId:string,messageId:string,connection:Pick<RequestDatabaseClient,'query'>){
        requireProfileId(profileId);
        const result=await connection.query<Record<string,unknown>>(`
            UPDATE email_transport_drafts d SET status='sent',transport_message_id=$2,sent_at=NOW(),error=NULL
            FROM requests r WHERE d.id=$1 AND d.status='reviewed' AND r.id=d.request_id AND r.profile_id=$3
            RETURNING d.id,d.request_id,d.recipient,d.subject,d.status,d.reviewed_by,d.reviewed_at,d.transport_message_id,d.created_at,d.sent_at`,
        [draftId,messageId,profileId]);
        return result.rows[0]??null;
    }

    async markEmailDraftFailed(profileId:string,draftId:string,error:Record<string,unknown>){
        requireProfileId(profileId);
        const result=await this.database.query(`
            UPDATE email_transport_drafts d SET status='failed',error=$2::jsonb
            FROM requests r WHERE d.id=$1 AND d.status='reviewed' AND r.id=d.request_id AND r.profile_id=$3`,
        [draftId,JSON.stringify(error),profileId]);
        return result.rowCount===1;
    }

    async getThread(profileId: string, lookup: { threadId?: string | null; company?: string | null }) {
        requireProfileId(profileId);
        const result = lookup.threadId
            ? await this.database.query<Record<string, unknown>>(
                'SELECT * FROM request_threads WHERE thread_id=$1 AND profile_id=$2',
                [lookup.threadId, profileId],
            )
            : await this.database.query<Record<string, unknown>>(
                'SELECT * FROM request_threads WHERE LOWER(company)=LOWER($1) AND profile_id=$2 ORDER BY created_at DESC LIMIT 1',
                [lookup.company, profileId],
            );
        return result.rows[0] ?? null;
    }

    async updateThread(profileId: string, userId: string, input: RequestThreadUpdateInput) {
        requireProfileId(profileId);
        const client = await this.database.connect();
        try {
            await client.query('BEGIN');
            if (input.requestId) {
                const owned = await client.query('SELECT 1 FROM requests WHERE id=$1 AND profile_id=$2', [input.requestId, profileId]);
                if (!owned.rows[0]) {
                    await client.query('ROLLBACK');
                    return null;
                }
            }
            const existing = await client.query<Record<string, unknown>>(
                'SELECT * FROM request_threads WHERE LOWER(company)=LOWER($1) AND domain=$2 AND profile_id=$3 FOR UPDATE',
                [input.company, input.domain ?? '', profileId],
            );
            let threadId = existing.rows[0]?.thread_id as string | undefined;
            if (!threadId) {
                const inserted = await client.query<Record<string, unknown>>(`
                    INSERT INTO request_threads(company,domain,status,conversation_history,profile_id,request_id)
                    VALUES($1,$2,'initialized','[]'::jsonb,$3,$4)
                    RETURNING thread_id`, [input.company, input.domain ?? null, profileId, input.requestId ?? null]);
                threadId = String(inserted.rows[0]?.thread_id);
            }
            const linked = await client.query<{ request_id: string | null }>(
                'SELECT request_id FROM request_threads WHERE thread_id=$1 AND profile_id=$2 FOR UPDATE',
                [threadId, profileId],
            );
            const canonicalRequestId = linked.rows[0]?.request_id ? String(linked.rows[0].request_id) : null;
            if (['request_drafted', 'email_sent', 'response_received'].includes(input.action) && !canonicalRequestId) {
                await client.query('ROLLBACK');
                throw new Error('Lifecycle actions require a canonical request link');
            }
            const occurredAt = new Date();
            const history = JSON.stringify([{ timestamp: occurredAt.toISOString(), action: input.action, data: input.data }]);
            const data = input.data;

            switch (input.action) {
                case 'policy_analyzed':
                    await client.query(`UPDATE request_threads SET policy_url=$1,policy_markdown=$2,policy_summary=$3,
                        dpo_email=$4,compliance_score=$5,status='policy_analyzed',updated_at=NOW(),
                        conversation_history=conversation_history || $6::jsonb
                        WHERE thread_id=$7 AND profile_id=$8`,
                    [data.policyUrl, data.markdownContent, data.summary, data.dpoEmail, data.complianceScore, history, threadId, profileId]);
                    break;
                case 'request_drafted':
                    await client.query(`UPDATE request_threads SET request_type=$1,draft_subject=$2,draft_body=$3,
                        drafted_at=$4,status='drafted',updated_at=NOW(),conversation_history=conversation_history || $5::jsonb
                        WHERE thread_id=$6 AND profile_id=$7`,
                    [data.requestType, data.subject, data.body, occurredAt, history, threadId, profileId]);
                    await executeTransition(client, profileId, { request_id: canonicalRequestId!, next_state: 'ready_for_review',
                        actor: `user:${userId}`, reason: 'Request thread draft recorded', evidence_reference: `request_thread:${threadId}`,
                        transitioned_at: occurredAt });
                    break;
                case 'email_sent':
                    await client.query(`UPDATE request_threads SET sent_at=$1,sent_via=$2,email_status='sent',status='sent',
                        updated_at=NOW(),conversation_history=conversation_history || $3::jsonb
                        WHERE thread_id=$4 AND profile_id=$5`,
                    [occurredAt, data.sentVia ?? 'built_in', history, threadId, profileId]);
                    await executeTransition(client, profileId, { request_id: canonicalRequestId!, next_state: 'sent',
                        actor: `user:${userId}`, reason: 'Request thread recorded successful send',
                        evidence_reference: `request_thread:${threadId}`, transitioned_at: occurredAt, sent_at: occurredAt });
                    break;
                case 'response_received':
                    await client.query(`UPDATE request_threads SET response_received_at=$1,response_content=$2,response_summary=$3,
                        status='response_received',updated_at=NOW(),conversation_history=conversation_history || $4::jsonb
                        WHERE thread_id=$5 AND profile_id=$6`,
                    [occurredAt, data.content, data.summary, history, threadId, profileId]);
                    await executeTransition(client, profileId, buildResponseClassificationCommand({
                        requestId: canonicalRequestId!,
                        classification: ['partial_response','identity_required','clarification_required'].includes(String(data.classification))
                            ? data.classification as 'partial_response'|'identity_required'|'clarification_required'
                            : 'substantive_response',
                        actor: `user:${userId}`,
                        reason: 'Controller response recorded in request thread',
                        evidenceReference: `request_thread:${threadId}`,
                        occurredAt,
                    }));
                    break;
                case 'follow_up':
                    await client.query(`UPDATE request_threads SET follow_up_needed=$1,follow_up_reason=$2,follow_up_sent_at=$3,
                        status=$4,updated_at=NOW(),conversation_history=conversation_history || $5::jsonb
                        WHERE thread_id=$6 AND profile_id=$7`,
                    [data.needed !== false, data.reason, data.sent ? occurredAt : null,
                        data.sent ? 'follow_up_sent' : 'follow_up_needed', history, threadId, profileId]);
                    break;
                default:
                    await client.query('ROLLBACK');
                    throw new TypeError(`Unknown request-thread action: ${input.action}`);
            }
            const updated = await client.query<Record<string, unknown>>(
                'SELECT * FROM request_threads WHERE thread_id=$1 AND profile_id=$2', [threadId, profileId],
            );
            await client.query('COMMIT');
            return updated.rows[0] ?? null;
        } catch (error) {
            await client.query('ROLLBACK');
            throw error;
        } finally {
            client.release();
        }
    }

    async cancel(profileId: string, requestId: string, actor: string): Promise<Request | null> {
        if (!await this.get(profileId, requestId)) return null;
        return this.transition(profileId, {
            request_id: requestId,
            next_state: 'cancelled',
            actor,
            reason: 'User cancelled request; request and evidence retained',
            transitioned_at: new Date(),
        });
    }
}
