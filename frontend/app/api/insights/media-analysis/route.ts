import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';
import { executeTask, type TaskResult } from '@/lib/execution/router';

type MediaMode = 'metadata_only' | 'selective_visual' | 'full_visual';

interface MediaAnalysisBody {
    mode: MediaMode;
    analysisRunId?: string;
    artifactId?: string;
    evidenceLocatorId?: string;
}

const MODES = new Set<MediaMode>(['metadata_only', 'selective_visual', 'full_visual']);

export async function GET() {
    const result = await pool.query('SELECT media_analysis_mode,updated_at FROM insight_settings WHERE singleton=TRUE');
    return NextResponse.json(result.rows[0] || { media_analysis_mode:'metadata_only' });
}

export async function POST(request: Request) {
    const body = await request.json() as MediaAnalysisBody;
    if (!MODES.has(body.mode)) return NextResponse.json({ error:'Invalid media analysis mode' }, { status:400 });
    await pool.query('UPDATE insight_settings SET media_analysis_mode=$1,updated_at=NOW() WHERE singleton=TRUE', [body.mode]);
    if (body.mode === 'metadata_only') {
        return NextResponse.json({ mode:body.mode, tasks:[], external_calls:0 });
    }
    if (!body.analysisRunId || !body.artifactId || !body.evidenceLocatorId) {
        return NextResponse.json({ error:'Visual analysis requires analysisRunId, artifactId and evidenceLocatorId' }, { status:400 });
    }
    const resolved = {
        analysisRunId:body.analysisRunId,
        artifactId:body.artifactId,
        evidenceLocatorId:body.evidenceLocatorId,
    };
    const source = await pool.query(`SELECT cb.storage_uri,
        (SELECT input_manifest->>'file_path' FROM specialist_task_requests
         WHERE analysis_run_id=$1 AND artifact_id=$2 AND input_manifest ? 'file_path'
         ORDER BY created_at LIMIT 1) AS prior_file_path
        FROM source_artifacts sa
        JOIN export_snapshots es ON es.id=sa.export_snapshot_id
        JOIN content_blobs cb ON cb.id=sa.content_blob_id
        JOIN evidence_locators el ON el.artifact_id=sa.id AND el.id=$3
        WHERE sa.id=$2 AND es.analysis_run_id=$1`,
    [body.analysisRunId,body.artifactId,body.evidenceLocatorId]);
    if (!source.rowCount) return NextResponse.json({ error:'Artifact/locator/run provenance did not resolve' }, { status:404 });
    const filePath = source.rows[0].prior_file_path || localPath(String(source.rows[0].storage_uri));
    const input = { file_path:filePath, evidence_locator_id:body.evidenceLocatorId };
    const results: Array<{ task_key:string; result:TaskResult }> = [];

    const origin = await invokeAndPersist('image.origin_classification', resolved, input);
    results.push({ task_key:'image.origin_classification', result:origin });
    if (!origin.ok) return NextResponse.json({ mode:body.mode, tasks:results }, { status:422 });
    const originValue = String((origin.output as { origin?:unknown })?.origin || 'unknown');
    const remaining = body.mode === 'full_visual'
        ? ['image.ocr','image.caption','image.landmark_candidate']
        : originValue === 'screenshot'
            ? ['image.ocr','image.caption']
            : originValue === 'unknown' ? ['image.landmark_candidate'] : [];
    for (const taskKey of remaining) {
        results.push({ task_key:taskKey, result:await invokeAndPersist(taskKey,resolved,input) });
    }
    return NextResponse.json({ mode:body.mode, media_origin:originValue, tasks:results });
}

async function invokeAndPersist(taskKey: string, body: Required<Pick<MediaAnalysisBody,'analysisRunId'|'artifactId'|'evidenceLocatorId'>>, input: Record<string,string>): Promise<TaskResult> {
    await pool.query(`INSERT INTO specialist_task_requests(analysis_run_id,artifact_id,task_key,input_manifest,status)
        VALUES($1,$2,$3,$4::jsonb,'running')
        ON CONFLICT(analysis_run_id,artifact_id,task_key) DO UPDATE
        SET input_manifest=EXCLUDED.input_manifest,status='running',output_manifest=NULL,error=NULL,completed_at=NULL`,
    [body.analysisRunId,body.artifactId,taskKey,JSON.stringify(input)]);
    const result = await executeTask({
        taskKey,input,analysisRunId:body.analysisRunId,
        sourceArtifactIds:[body.artifactId],workflowKey:'task4.media-analysis',
    });
    await pool.query(`UPDATE specialist_task_requests SET status=$4,execution_record_id=$5,
        output_manifest=$6::jsonb,error=$7::jsonb,completed_at=NOW()
        WHERE analysis_run_id=$1 AND artifact_id=$2 AND task_key=$3`,
    [body.analysisRunId,body.artifactId,taskKey,
        result.ok ? 'completed' : result.error.code === 'PRIVACY_POLICY_BLOCK' ? 'blocked' : 'failed',
        result.executionRecordId || null,JSON.stringify(result.ok ? result.output : null),
        JSON.stringify(result.ok ? null : result.error)]);
    return result;
}

function localPath(storageUri: string): string {
    if (!storageUri.startsWith('file:')) return storageUri;
    const parsed = new URL(storageUri);
    const decoded = decodeURIComponent(parsed.pathname);
    return /^\/[A-Za-z]:\//.test(decoded) ? decoded.slice(1) : decoded;
}
