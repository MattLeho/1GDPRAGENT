'use server';

import { safeQuery } from '@/lib/db';

export interface Request {
    id: string;
    company_name: string;
    company_url: string | null;
    domain: string | null;
    status: 'draft' | 'scheduled' | 'processing' | 'action_required' | 'completed';
    request_type: string; // 'access' | 'deletion' | 'access+deletion'
    progress: number;
    data_volume_mb: number;
    next_action_date: Date | null;
    deadline_date: Date | null;
    data_period_start: Date | null;
    data_period_end: Date | null;
    notes: string | null;
    created_at: Date;
}

export async function getRequests(
    search?: string,
    filter?: string,
    sort?: string
): Promise<Request[]> {
    let query = `
        SELECT * FROM requests
        WHERE 1=1
    `;
    const values: (string | number | boolean | null)[] = [];
    let paramIndex = 1;

    if (search) {
        query += ` AND (company_name ILIKE $${paramIndex} OR domain ILIKE $${paramIndex})`;
        values.push(`%${search}%`);
        paramIndex++;
    }

    // Basic filtering implementation (extensible)
    if (filter && filter !== 'all') {
        query += ` AND status = $${paramIndex}`;
        values.push(filter);
        paramIndex++;
    }

    // Basic sorting
    if (sort === 'date') {
        query += ` ORDER BY created_at DESC`;
    } else if (sort === 'name') {
        query += ` ORDER BY company_name ASC`;
    } else {
        // Default sort
        query += ` ORDER BY created_at DESC`;
    }

    const result = await safeQuery<Request>(query, values);

    if (result.error) {
        console.error('Failed to fetch requests:', result.error);
    }

    return result.rows;
}

/**
 * Get request counts by status for dashboard
 */
export async function getRequestCounts(): Promise<{
    total: number;
    pending: number;
    completed: number;
    action_required: number;
}> {
    const result = await safeQuery<{
        total: string;
        pending: string;
        completed: string;
        action_required: string;
    }>(`
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status IN ('scheduled', 'processing') THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'action_required' THEN 1 END) as action_required
        FROM requests
    `);

    if (result.rows.length === 0) {
        return { total: 0, pending: 0, completed: 0, action_required: 0 };
    }

    const row = result.rows[0];
    return {
        total: parseInt(row.total) || 0,
        pending: parseInt(row.pending) || 0,
        completed: parseInt(row.completed) || 0,
        action_required: parseInt(row.action_required) || 0,
    };
}

// ============================================
// MANUAL REQUEST CREATION
// ============================================

export interface ManualRequestInput {
    company_name: string;
    domain?: string;
    status: 'draft' | 'scheduled' | 'processing' | 'action_required' | 'completed';
    request_type: string;
    notes?: string;
    date_started?: Date;
    progress?: number;
}

/**
 * Create a request manually (for requests already initiated outside the app, like TalkTalk)
 */
export async function createManualRequest(input: ManualRequestInput): Promise<{ success: boolean; requestId?: string; error?: string }> {
    try {
        // Calculate progress based on status if not provided
        const progress = input.progress ?? getProgressFromStatus(input.status);

        const result = await safeQuery<{ id: string }>(
            `INSERT INTO requests (
                company_name, 
                domain, 
                status, 
                request_type, 
                progress, 
                notes, 
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id`,
            [
                input.company_name,
                input.domain || input.company_name.toLowerCase().replace(/\s+/g, '') + '.com',
                input.status,
                input.request_type,
                progress,
                input.notes || null,
                input.date_started || new Date()
            ]
        );

        if (result.error || result.rows.length === 0) {
            return { success: false, error: result.error || 'Failed to create request' };
        }

        const requestId = result.rows[0].id;

        // Add initial timeline event
        await addRequestEvent({
            request_id: requestId,
            event_type: 'created',
            event_description: 'Request added manually',
            event_date: input.date_started || new Date()
        });

        // Revalidate paths
        const { revalidatePath } = await import('next/cache');
        revalidatePath('/dashboard/requests');
        revalidatePath('/dashboard/home');

        return { success: true, requestId };
    } catch (error) {
        console.error('Failed to create manual request:', error);
        return { success: false, error: error instanceof Error ? error.message : 'Unknown error' };
    }
}

function getProgressFromStatus(status: string): number {
    switch (status) {
        case 'draft': return 0;
        case 'scheduled': return 10;
        case 'processing': return 40;
        case 'action_required': return 60;
        case 'completed': return 100;
        default: return 0;
    }
}

// ============================================
// REQUEST TIMELINE EVENTS
// ============================================

export interface RequestEvent {
    id: string;
    request_id: string;
    event_type: string;
    event_description: string | null;
    event_date: Date;
}

/**
 * Get all timeline events for a request
 */
export async function getRequestEvents(requestId: string): Promise<RequestEvent[]> {
    const result = await safeQuery<RequestEvent>(
        `SELECT * FROM request_events 
         WHERE request_id = $1 
         ORDER BY event_date ASC`,
        [requestId]
    );

    if (result.error) {
        console.error('Failed to fetch request events:', result.error);
    }

    return result.rows;
}

/**
 * Add a new timeline event to a request
 */
export async function addRequestEvent(event: {
    request_id: string;
    event_type: string;
    event_description?: string;
    event_date?: Date;
}): Promise<{ success: boolean; id?: string }> {
    try {
        const result = await safeQuery<{ id: string }>(
            `INSERT INTO request_events (request_id, event_type, event_description, event_date)
             VALUES ($1, $2, $3, $4)
             RETURNING id`,
            [
                event.request_id,
                event.event_type,
                event.event_description || null,
                event.event_date || new Date()
            ]
        );

        if (result.error || result.rows.length === 0) {
            return { success: false };
        }

        return { success: true, id: result.rows[0].id };
    } catch (error) {
        console.error('Failed to add request event:', error);
        return { success: false };
    }
}
