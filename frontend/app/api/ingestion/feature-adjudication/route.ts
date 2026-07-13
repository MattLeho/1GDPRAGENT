import { NextRequest, NextResponse } from 'next/server';
import { executeTask3Bundle, type Task3BoundedBundle } from '@/lib/execution/task3';

export async function POST(request: NextRequest) {
    try {
        const bundle = await request.json() as Task3BoundedBundle;
        if (bundle.task_key !== 'semantic.adjudication' && bundle.task_key !== 'semantic.topic_labelling') {
            return NextResponse.json({ error:'Only feature adjudication or topic-labelling bundles are accepted' }, { status:400 });
        }
        const result = await executeTask3Bundle(bundle);
        return NextResponse.json(result, { status:result.ok ? 200 : 422 });
    } catch (error) {
        return NextResponse.json({ error:error instanceof Error ? error.message : String(error) }, { status:400 });
    }
}
