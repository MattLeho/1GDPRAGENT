import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { executeTask3Bundle, type Task3BoundedBundle } from '@/lib/execution/task3';
import { pool } from '@/lib/db';

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const bundle = await request.json() as Task3BoundedBundle;
        if (bundle.task_key !== 'semantic.adjudication' && bundle.task_key !== 'semantic.topic_labelling') {
            return NextResponse.json({ error:'Only feature adjudication or topic-labelling bundles are accepted' }, { status:400 });
        }
        const ownership = await pool.query('SELECT id FROM analysis_runs WHERE id=$1 AND profile_id=$2',[bundle.analysis_run_id,authority.profileId]);
        if (ownership.rowCount !== 1) return NextResponse.json({ error:'Analysis run not found' }, { status:404 });
        const result = await executeTask3Bundle(bundle,authority.profileId);
        return NextResponse.json(result, { status:result.ok ? 200 : 422 });
    } catch (error) {
        return NextResponse.json({ error:error instanceof Error ? error.message : String(error) }, { status:400 });
    }
}
