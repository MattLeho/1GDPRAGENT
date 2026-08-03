import { NextRequest, NextResponse } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const MODULES = new Set(['overview', 'interests', 'search', 'ai-conversations', 'places', 'changes', 'context']);
const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

export async function GET(request: NextRequest, context: { params: Promise<{ module: string }> }) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const { module } = await context.params;
    if (!MODULES.has(module)) return NextResponse.json({ error: 'Unknown Personal Insights module' }, { status: 404 });
    const query = new URLSearchParams(request.nextUrl.searchParams);
    // The authenticated profile is the only subject authority. Ignore any caller value.
    query.set('subject_id', authority.profileId);
    try {
        const target = `${intelligenceUrl()}/insights/${module}?${query}`;
        const response = await fetch(target, {
            headers: intelligenceAuthorityHeaders(authority.profileId, target, 'GET'),
            cache: 'no-store', signal: AbortSignal.timeout(120_000),
        });
        const payload = await response.json().catch(() => ({ detail: `Intelligence service returned ${response.status}` }));
        return NextResponse.json(payload, { status: response.status });
    } catch (error) {
        return NextResponse.json({ error: 'Personal Insights service is unavailable', detail: error instanceof Error ? error.message : String(error) }, { status: 503 });
    }
}
