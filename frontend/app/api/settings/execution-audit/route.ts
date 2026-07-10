import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';

export async function GET(request:Request){
    const url=new URL(request.url); const externalOnly=url.searchParams.get('external')!=='false';
    const result=await pool.query(`SELECT id,analysis_run_id,task_key,workflow_key,engine_id,provider,model,execution_location,
        source_artifact_ids,started_at,completed_at,status,input_size,output_size,error FROM execution_records
        WHERE ($1::boolean=false OR execution_location='external') ORDER BY started_at DESC LIMIT 200`,[externalOnly]);
    return NextResponse.json({records:result.rows});
}
