import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';
import { processThroughBulkPipeline } from '@/lib/ingestion/bulk';

async function loadFile(fileId: string, profileId: string) {
    const result = await pool.query('SELECT * FROM received_data WHERE id=$1 AND profile_id=$2', [fileId, profileId]);
    return result.rows[0] || null;
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json() as { fileId?:string; action?:string };
        if (!body.fileId) return NextResponse.json({ success:false,error:'fileId is required' }, { status:400 });
        const file = await loadFile(body.fileId, authority.profileId);
        if (!file) return NextResponse.json({ success:false,error:'File not found' }, { status:404 });
        await pool.query("UPDATE received_data SET status='processing',processing_stage='local_ingestion',processing_progress=5,error_message=NULL WHERE id=$1 AND profile_id=$2", [body.fileId, authority.profileId]);
        const result = await processThroughBulkPipeline(file,body.action,authority.profileId);
        return NextResponse.json({ success:true,fileId:body.fileId,stage:result.specialist_tasks.length?'specialist_tasks':'completed',progress:100,...result });
    } catch (error) {
        return NextResponse.json({ success:false,error:error instanceof Error ? error.message : String(error) }, { status:422 });
    }
}

// The legacy "ingest to graph" action now enters the same evidence pipeline.
// Graph projection occurs only later from reviewed high-value assertions.
export async function PUT(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    return POST(request);
}
