import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

export async function GET(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
    const authority = await requireApiSession(_request);
    if (authority instanceof NextResponse) return authority;
    const { id } = await context.params;
    try {
        const target = `${intelligenceUrl()}/insights/evidence/${encodeURIComponent(id)}`;
        const response = await fetch(target, {
            headers: intelligenceAuthorityHeaders(authority.profileId, target, 'GET'),
            cache: 'no-store', signal: AbortSignal.timeout(120_000),
        });
        const payload = await response.json().catch(() => ({ detail: `Intelligence service returned ${response.status}` }));
        return NextResponse.json(payload, { status: response.status });
    } catch (error) {
        return NextResponse.json({ error: 'Insight evidence service is unavailable', detail: error instanceof Error ? error.message : String(error) }, { status: 503 });
    }
}
