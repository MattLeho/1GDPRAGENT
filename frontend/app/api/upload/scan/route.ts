import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';
import { processThroughBulkPipeline } from '@/lib/ingestion/bulk';

/** Process pending uploads through the registry/adapter pipeline only. */
export async function POST() {
    const files = await pool.query(`
        SELECT rd.* FROM received_data rd
        WHERE rd.status IN ('pending','error','uploaded')
           OR (rd.provenance_status IS NULL AND rd.status<>'processing')
        ORDER BY rd.date_received ASC LIMIT 100
    `);
    const results = { scanned:files.rows.length,processed:0,errors:[] as string[] };
    for (const file of files.rows) {
        try {
            await pool.query("UPDATE received_data SET status='processing',processing_stage='local_ingestion',processing_progress=5,error_message=NULL WHERE id=$1", [file.id]);
            await processThroughBulkPipeline(file);
            results.processed += 1;
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            results.errors.push(`${file.file_name}: ${message}`);
            await pool.query("UPDATE received_data SET status='error',processing_stage='local_ingestion',error_message=$2 WHERE id=$1", [file.id,message.slice(0,500)]);
        }
    }
    return NextResponse.json({ success:results.errors.length===0,...results });
}
