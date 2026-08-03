'use server';

import { safeQuery } from '@/lib/db';
import { requireServerSessionAuthority } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests=new RequestService();

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
    const {profileId}=await requireServerSessionAuthority();
    const result = await safeQuery<ReceivedDataFile>(
        `SELECT received_data.*, file_path AS download_url FROM received_data 
         WHERE request_id = $1 AND profile_id=$2
         ORDER BY date_received DESC`,
        [requestId,profileId]
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
    const {profileId}=await requireServerSessionAuthority();
    const result = await safeQuery<{ total: string }>(
        `SELECT COALESCE(SUM(file_size_mb), 0) as total
         FROM received_data 
         WHERE request_id = $1 AND profile_id=$2`,
        [requestId,profileId]
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
        const {profileId}=await requireServerSessionAuthority();
        const created=await requests.addReceivedData(profileId,data.request_id,{file_name:data.file_name,
            file_size_mb:data.file_size_mb,file_path:data.download_url||null});
        return created?{success:true,id:created.id}:{success:false};
    } catch (error) {
        console.error('Failed to add received data:', error);
        return { success: false };
    }
}
