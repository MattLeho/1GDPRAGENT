import { db } from '@/lib/db';

export type WorkflowLogType = 'built_in' | 'n8n' | 'file_processing' | 'graph_ingestion' | 'email_transport';

interface WorkflowLogParams {
    requestId?: string | null;
    workflowName: string;
    workflowType: WorkflowLogType | string;
    details?: Record<string, unknown>;
}

let workflowLogsTableReady = false;

export async function ensureWorkflowLogsTable() {
    if (workflowLogsTableReady) {
        return;
    }

    await db.query(`
        CREATE TABLE IF NOT EXISTS workflow_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
            workflow_name TEXT NOT NULL,
            workflow_type TEXT,
            status TEXT DEFAULT 'started',
            details JSONB,
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT
        )
    `);

    await db.query(`
        CREATE INDEX IF NOT EXISTS idx_workflow_logs_request_id
        ON workflow_logs(request_id)
    `);

    workflowLogsTableReady = true;
}

export async function startWorkflowLog(params: WorkflowLogParams): Promise<string | null> {
    try {
        await ensureWorkflowLogsTable();

        const result = await db.query<{ id: string }>(`
            INSERT INTO workflow_logs (
                request_id, workflow_name, workflow_type, status, details, started_at
            )
            VALUES ($1, $2, $3, 'running', $4::jsonb, NOW())
            RETURNING id
        `, [
            params.requestId || null,
            params.workflowName,
            params.workflowType,
            JSON.stringify(params.details || {}),
        ]);

        return result.rows[0]?.id || null;
    } catch (error) {
        console.warn('[Workflow Logs] Failed to start workflow log:', error);
        return null;
    }
}

export async function completeWorkflowLog(
    logId: string | null,
    details: Record<string, unknown> = {}
) {
    if (!logId) {
        return;
    }

    try {
        await ensureWorkflowLogsTable();
        await db.query(`
            UPDATE workflow_logs
            SET status = 'completed',
                completed_at = NOW(),
                details = COALESCE(details, '{}'::jsonb) || $2::jsonb
            WHERE id = $1
        `, [logId, JSON.stringify(details)]);
    } catch (error) {
        console.warn('[Workflow Logs] Failed to complete workflow log:', error);
    }
}

export async function failWorkflowLog(
    logId: string | null,
    error: unknown,
    details: Record<string, unknown> = {}
) {
    if (!logId) {
        return;
    }

    const message = error instanceof Error ? error.message : String(error || 'Unknown error');

    try {
        await ensureWorkflowLogsTable();
        await db.query(`
            UPDATE workflow_logs
            SET status = 'error',
                completed_at = NOW(),
                error_message = $2,
                details = COALESCE(details, '{}'::jsonb) || $3::jsonb
            WHERE id = $1
        `, [logId, message, JSON.stringify(details)]);
    } catch (logError) {
        console.warn('[Workflow Logs] Failed to fail workflow log:', logError);
    }
}
