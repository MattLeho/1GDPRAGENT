import { db } from '@/lib/db';

export type WorkflowLogType = 'built_in' | 'n8n' | 'file_processing' | 'graph_ingestion' | 'email_transport';

interface WorkflowLogParams {
    requestId?: string | null;
    workflowName: string;
    workflowType: WorkflowLogType | string;
    details?: Record<string, unknown>;
}

export async function startWorkflowLog(params: WorkflowLogParams): Promise<string | null> {
    try {
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
