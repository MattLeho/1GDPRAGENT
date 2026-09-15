import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';
import { executeTask3Bundle } from '@/lib/execution/task3';

interface InterpretationManifest {
    task_key: 'schema.interpretation';
    analysis_run_id: string;
    source_artifact_ids: string[];
    purpose: string;
    samples: Array<Record<string, unknown>>;
    maximum_sample_bytes: number;
    omitted_record_count: number;
    fingerprint_id: string;
}

function parseManifest(value: unknown): InterpretationManifest {
    const manifest = (typeof value === 'string' ? JSON.parse(value) : value) as Partial<InterpretationManifest>;
    if (manifest.task_key !== 'schema.interpretation' || !manifest.analysis_run_id || !manifest.fingerprint_id) throw new Error('Invalid schema interpretation manifest');
    if (!Array.isArray(manifest.samples) || !Array.isArray(manifest.source_artifact_ids)) throw new Error('Interpretation samples and source artifacts are required');
    const byteSize = Buffer.byteLength(JSON.stringify(manifest.samples));
    if (!Number.isInteger(manifest.maximum_sample_bytes) || manifest.maximum_sample_bytes! <= 0 || byteSize > manifest.maximum_sample_bytes!) throw new Error('Interpretation bundle exceeds its declared byte budget');
    return manifest as InterpretationManifest;
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json() as { interpretation_request_id?: string };
        if (!body.interpretation_request_id) return NextResponse.json({ error:'interpretation_request_id is required' }, { status:400 });
        const result = await pool.query(
            `SELECT sir.id,sir.analysis_run_id,sir.execution_record_id,sir.sample_manifest,sf.fingerprint_hash
             FROM schema_interpretation_requests sir
             JOIN structure_fingerprints sf ON sf.id=sir.structure_fingerprint_id
             JOIN analysis_runs ar ON ar.id=sir.analysis_run_id
             WHERE sir.id=$1 AND ar.profile_id=$2`, [body.interpretation_request_id,authority.profileId],
        );
        if (!result.rows[0]) return NextResponse.json({ error:'Interpretation request not found' }, { status:404 });
        const row = result.rows[0];
        if (row.execution_record_id) return NextResponse.json({ error:'Interpretation request was already executed', execution_record_id:row.execution_record_id }, { status:409 });
        const manifest = parseManifest(row.sample_manifest);
        if (manifest.analysis_run_id !== row.analysis_run_id || manifest.fingerprint_id !== row.fingerprint_hash) throw new Error('Interpretation manifest does not match its catalogue record');
        const routed = await executeTask3Bundle(manifest,authority.profileId);
        if (!routed.ok) return NextResponse.json(routed, { status:422 });
        await pool.query(
            'UPDATE schema_interpretation_requests SET execution_record_id=$2 WHERE id=$1 AND execution_record_id IS NULL',
            [body.interpretation_request_id, routed.executionRecordId],
        );
        return NextResponse.json({
            interpretation_request_id:body.interpretation_request_id,
            fingerprint_id:manifest.fingerprint_id, review_status:'proposed',
            proposal:routed.output, execution_record_id:routed.executionRecordId,
        });
    } catch (error) {
        return NextResponse.json({ error:error instanceof Error ? error.message : String(error) }, { status:400 });
    }
}
