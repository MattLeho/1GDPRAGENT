import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

export type WorkflowLogType = 'built_in' | 'n8n' | 'file_processing' | 'graph_ingestion' | 'email_transport';

interface WorkflowLogParams {
    profileId: string;
    requestId?: string | null;
    workflowName: string;
    workflowType: WorkflowLogType | string;
    details?: Record<string, unknown>;
}

export async function startWorkflowLog(params: WorkflowLogParams): Promise<string | null> {
    try {
        if (!params.requestId) return null;
        return await requests.startWorkflowLog(params.profileId, {
            requestId: params.requestId, workflowName: params.workflowName,
            workflowType: params.workflowType, details: params.details,
        });
    } catch (error) {
        console.warn('[Workflow Logs] Failed to start workflow log:', error);
        return null;
    }
}

export async function completeWorkflowLog(
    profileId: string,
    logId: string | null,
    details: Record<string, unknown> = {}
) {
    if (!logId) {
        return;
    }

    try {
        await requests.finishWorkflowLog(profileId, logId, { status: 'completed', details });
    } catch (error) {
        console.warn('[Workflow Logs] Failed to complete workflow log:', error);
    }
}

export async function failWorkflowLog(
    profileId: string,
    logId: string | null,
    error: unknown,
    details: Record<string, unknown> = {}
) {
    if (!logId) {
        return;
    }

    const message = error instanceof Error ? error.message : String(error || 'Unknown error');

    try {
        await requests.finishWorkflowLog(profileId, logId, {
            status: 'error', details, errorMessage: message,
        });
    } catch (logError) {
        console.warn('[Workflow Logs] Failed to fail workflow log:', logError);
    }
}
