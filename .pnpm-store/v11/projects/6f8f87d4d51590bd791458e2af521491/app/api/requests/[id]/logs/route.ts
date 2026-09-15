import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

interface Activity {
    id: string;
    type: 'workflow' | 'event' | 'file';
    title: string;
    description: string | null;
    status: string;
    timestamp: Date | string | null;
    details?: unknown;
    error?: string | null;
    progress?: number | null;
    graphIngested?: boolean | null;
}

function describeWorkflowType(workflowType: string | null): string {
    switch (workflowType) {
        case 'built_in':
            return 'Built-in Workflow Execution';
        case 'n8n':
            return 'N8N Workflow Execution';
        case 'email_transport':
            return 'Email Transport';
        case 'file_processing':
            return 'File Processing';
        case 'graph_ingestion':
            return 'Graph Ingestion';
        default:
            return 'Workflow Execution';
    }
}

// Get workflow logs and activity for a request
export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { id } = await params;
        const activityRows = await requests.activity(authority.profileId, id);
        if (!activityRows) {
            return NextResponse.json({ success: false, error: 'Request not found' }, { status: 404 });
        }
        const logsResult = { rows: activityRows.logs };
        const eventsResult = { rows: activityRows.events };
        const filesResult = { rows: activityRows.files };

        // Combine into unified activity feed
        const activities: Activity[] = [];

        // Add workflow logs
        logsResult.rows.forEach(log => {
            activities.push({
                id: log.id,
                type: 'workflow',
                title: log.workflow_name,
                description: describeWorkflowType(log.workflow_type),
                status: log.status,
                timestamp: log.started_at,
                details: log.details,
                error: log.error_message,
            });
        });

        // Add request events
        eventsResult.rows.forEach(event => {
            activities.push({
                id: event.id,
                type: 'event',
                title: event.event_type.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
                description: event.event_description,
                status: 'completed',
                timestamp: event.event_date,
            });
        });

        // Add file activities
        filesResult.rows.forEach(file => {
            if (file.status !== 'pending') {
                activities.push({
                    id: `file-${file.id}`,
                    type: 'file',
                    title: `File: ${file.file_name}`,
                    description: file.processing_stage
                        ? `Stage: ${file.processing_stage}`
                        : file.status === 'completed'
                            ? 'Processing complete'
                            : 'Processing',
                    status: file.status,
                    progress: file.processing_progress,
                    graphIngested: file.graph_ingested,
                    timestamp: file.processing_started_at || file.processing_completed_at,
                    error: file.error_message,
                });
            }
        });

        // Sort by timestamp descending
        activities.sort((a, b) =>
            new Date(b.timestamp || 0).getTime() - new Date(a.timestamp || 0).getTime()
        );

        return NextResponse.json({
            success: true,
            activities,
            stats: {
                totalWorkflows: logsResult.rows.length,
                totalEvents: eventsResult.rows.length,
                filesProcessing: filesResult.rows.filter(f => f.status === 'processing').length,
                filesCompleted: filesResult.rows.filter(f => f.status === 'completed').length,
                filesWithErrors: filesResult.rows.filter(f => f.status === 'error').length,
            }
        });
    } catch (error) {
        console.error('Error fetching logs:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to fetch activity logs' },
            { status: 500 }
        );
    }
}
