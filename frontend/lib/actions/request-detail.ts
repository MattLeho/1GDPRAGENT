'use server';

import { safeQuery, db } from '@/lib/db';
import { Request } from './requests';

/**
 * Gets a single request by ID
 */
export async function getRequestById(id: string): Promise<Request | null> {
    const result = await safeQuery<Request>(
        `SELECT * FROM requests WHERE id = $1`,
        [id]
    );

    if (result.error) {
        console.error('Failed to fetch request:', result.error);
        return null;
    }

    return result.rows[0] || null;
}

/**
 * Updates request status
 */
export async function updateRequestStatus(
    id: string,
    status: 'draft' | 'scheduled' | 'processing' | 'action_required' | 'completed'
): Promise<{ success: boolean }> {
    try {
        await db.query(
            `UPDATE requests SET status = $1 WHERE id = $2`,
            [status, id]
        );
        return { success: true };
    } catch (error) {
        console.error('Failed to update request status:', error);
        return { success: false };
    }
}

/**
 * Updates request progress
 */
export async function updateRequestProgress(
    id: string,
    progress: number
): Promise<{ success: boolean }> {
    try {
        await db.query(
            `UPDATE requests SET progress = $1 WHERE id = $2`,
            [Math.min(100, Math.max(0, progress)), id]
        );
        return { success: true };
    } catch (error) {
        console.error('Failed to update request progress:', error);
        return { success: false };
    }
}

/**
 * Updates request notes
 */
export async function updateRequestNotes(
    id: string,
    notes: string
): Promise<{ success: boolean }> {
    try {
        await db.query(
            `UPDATE requests SET notes = $1 WHERE id = $2`,
            [notes, id]
        );
        return { success: true };
    } catch (error) {
        console.error('Failed to update notes:', error);
        return { success: false };
    }
}

/**
 * Deletes a request
 */
export async function deleteRequest(id: string): Promise<{ success: boolean }> {
    try {
        await db.query(`DELETE FROM requests WHERE id = $1`, [id]);
        return { success: true };
    } catch (error) {
        console.error('Failed to delete request:', error);
        return { success: false };
    }
}

/**
 * Gets requests history for a company (previous requests to same domain)
 */
export async function getRequestHistory(domain: string, excludeId?: string): Promise<Request[]> {
    const query = excludeId
        ? `SELECT * FROM requests WHERE domain = $1 AND id != $2 ORDER BY created_at DESC LIMIT 10`
        : `SELECT * FROM requests WHERE domain = $1 ORDER BY created_at DESC LIMIT 10`;

    const params = excludeId ? [domain, excludeId] : [domain];
    const result = await safeQuery<Request>(query, params);

    if (result.error) {
        console.error('Failed to fetch request history:', result.error);
    }

    return result.rows;
}
