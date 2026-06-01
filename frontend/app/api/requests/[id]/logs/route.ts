import { NextRequest, NextResponse } from 'next/server';
import { pool } from '@/lib/db';

// Get workflow logs and activity for a request
export async function GET(
    request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;

        // Get workflow logs
        const logsResult = await pool.query(
            `SELECT id, workflow_name, workflow_type, status, details, 
                    started_at, completed_at, error_message
             FROM workflow_logs
             WHERE request_id = $1
             ORDER BY started_at DESC
             LIMIT 50`,
            [id]
        );

        // Get request events
        const eventsResult = await pool.query(
            `SELECT id, event_type, event_description, event_date
             FROM request_events
             WHERE request_id = $1
             ORDER BY event_date DESC
             LIMIT 50`,
            [id]
        );

        // Get file processing status
        const filesResult = await pool.query(
            `SELECT id, file_name, status, processing_stage, 
                    processing_progress, graph_ingested, 
                    processing_started_at, processing_completed_at, error_message
             FROM received_data
             WHERE request_id = $1
             ORDER BY date_received DESC`,
            [id]
        );

        // Combine into unified activity feed
        const activities: any[] = [];

        // Add workflow logs
        logsResult.rows.forEach(log => {
            activities.push({
                id: log.id,
                type: 'workflow',
                title: log.workflow_name,
                description: log.workflow_type === 'n8n'
                    ? 'N8N Workflow Execution'
                    : log.workflow_type === 'file_processing'
                        ? 'File Processing'
                        : 'Graph Ingestion',
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
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
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
