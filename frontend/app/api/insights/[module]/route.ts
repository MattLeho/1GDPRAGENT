import { NextRequest, NextResponse } from 'next/server';
import { pool } from '@/lib/db';

const MODULES = new Set(['overview', 'interests', 'search', 'ai-conversations', 'places', 'changes', 'context']);
const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

async function defaultSubjectId(): Promise<string> {
    const profile = await pool.query('SELECT id FROM user_profiles ORDER BY created_at LIMIT 1');
    return profile.rows[0]?.id ? String(profile.rows[0].id) : 'primary';
}

export async function GET(request: NextRequest, context: { params: Promise<{ module: string }> }) {
    const { module } = await context.params;
    if (!MODULES.has(module)) return NextResponse.json({ error: 'Unknown Personal Insights module' }, { status: 404 });
    const query = new URLSearchParams(request.nextUrl.searchParams);
    if (!query.get('subject_id')) query.set('subject_id', await defaultSubjectId());
    try {
        const response = await fetch(`${intelligenceUrl()}/insights/${module}?${query}`, {
            cache: 'no-store', signal: AbortSignal.timeout(120_000),
        });
        const payload = await response.json().catch(() => ({ detail: `Intelligence service returned ${response.status}` }));
        return NextResponse.json(payload, { status: response.status });
    } catch (error) {
        return NextResponse.json({ error: 'Personal Insights service is unavailable', detail: error instanceof Error ? error.message : String(error) }, { status: 503 });
    }
}
