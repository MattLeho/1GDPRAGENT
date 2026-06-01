'use server';

import { safeQuery } from '@/lib/db';

export interface ReceivedDataFile {
    id: string;
    request_id: string;
    file_name: string;
    original_name: string;
    file_path: string;
    file_size_mb: number;
    file_type: string;
    category: string;
    status: string;
    processing_stage: string;
    processing_progress: number;
    extracted_text: string | null;
    markdown_content: string | null;
    transcript: string | null;
    ai_summary: string | null;
    entities_extracted: Record<string, unknown> | null;
    extracted_entities: Record<string, unknown> | null;
    graph_ingested: boolean;
    error_message: string | null;
    processing_started_at: string | null;
    processing_completed_at: string | null;
    date_received: string;
    download_url: string | null;
}

/**
 * Fetches all received data files for a specific request
 */
export async function getReceivedData(requestId: string): Promise<ReceivedDataFile[]> {
    const result = await safeQuery<ReceivedDataFile>(
        `SELECT * FROM received_data 
         WHERE request_id = $1 
         ORDER BY date_received DESC`,
        [requestId]
    );

    if (result.error) {
        console.error('Failed to fetch received data:', result.error);
    }

    return result.rows;
}

/**
 * Gets the total data volume for a request
 */
export async function getRequestDataVolume(requestId: string): Promise<number> {
    const result = await safeQuery<{ total: string }>(
        `SELECT COALESCE(SUM(file_size_mb), 0) as total
         FROM received_data 
         WHERE request_id = $1`,
        [requestId]
    );

    if (result.error) {
        console.error('Failed to fetch data volume:', result.error);
        return 0;
    }

    return parseFloat(result.rows[0]?.total || '0');
}

/**
 * Add a received data file entry
 */
export async function addReceivedData(data: {
    request_id: string;
    file_name: string;
    file_size_mb: number;
    download_url?: string;
}): Promise<{ success: boolean; id?: string }> {
    try {
        const { db } = await import('@/lib/db');
        const result = await db.query<{ id: string }>(
            `INSERT INTO received_data (request_id, file_name, file_size_mb, download_url)
             VALUES ($1, $2, $3, $4)
             RETURNING id`,
            [data.request_id, data.file_name, data.file_size_mb, data.download_url || null]
        );
        return { success: true, id: result.rows[0]?.id };
    } catch (error) {
        console.error('Failed to add received data:', error);
        return { success: false };
    }
}
