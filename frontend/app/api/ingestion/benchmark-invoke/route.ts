import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';
import { getTaskRoute } from '@/lib/execution/router';
import { executeTask3Bundle, type Task3BoundedBundle } from '@/lib/execution/task3';

interface BenchmarkRequest {
    case_id: string;
    fixture_authorisation: 'synthetic'|'user_approved';
    bundle: Task3BoundedBundle;
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json() as BenchmarkRequest;
        if (!body.case_id || !['synthetic','user_approved'].includes(body.fixture_authorisation)) {
            return NextResponse.json({ error:'Benchmark fixtures must be synthetic or explicitly user-approved' }, { status:400 });
        }
        const ownership = await pool.query(
            `SELECT ar.id FROM analysis_runs ar
             WHERE ar.id=$1 AND ar.profile_id=$2
               AND (SELECT COUNT(*) FROM source_artifacts sa
                    JOIN export_snapshots es ON es.id=sa.export_snapshot_id
                    WHERE sa.id=ANY($3::uuid[]) AND es.profile_id=$2)=$4`,
            [body.bundle.analysis_run_id, authority.profileId, body.bundle.source_artifact_ids, body.bundle.source_artifact_ids.length],
        );
        if (ownership.rowCount !== 1) return NextResponse.json({ error:'Benchmark bundle not found' }, { status:404 });
        const route = await getTaskRoute(body.bundle.task_key);
        const started = performance.now();
        const memoryBefore = process.memoryUsage().rss;
        const result = await executeTask3Bundle(body.bundle,authority.profileId);
        const latency = performance.now() - started;
        const memoryAfter = process.memoryUsage().rss;
        const executionRecordId = result.executionRecordId;
        const audit = executionRecordId
            ? (await pool.query('SELECT engine_id,provider,model,execution_location FROM execution_records WHERE id=$1', [executionRecordId])).rows[0]
            : null;
        const rawCost = (route.configuration.cost_metadata || {}) as Record<string, unknown>;
        const configuredCost = Object.fromEntries(Object.entries(rawCost).filter(([, value]) =>
            value === null || typeof value === 'string' || typeof value === 'number'
        ));
        return NextResponse.json({
            case_id:body.case_id, task_key:body.bundle.task_key,
            engine_id:audit?.engine_id || route.engine_id,
            provider:audit?.provider || route.provider || 'unknown',
            model:audit?.model || route.model || null,
            execution_location:audit?.execution_location || route.execution_location,
            output:result.ok ? result.output : null,
            structured_error:result.ok ? null : result.error,
            execution_record_id:executionRecordId || null,
            latency_ms:latency,
            peak_memory_bytes:Math.max(memoryBefore, memoryAfter),
            configured_cost:configuredCost,
        });
    } catch (error) {
        return NextResponse.json({ error:error instanceof Error ? error.message : String(error) }, { status:400 });
    }
}
