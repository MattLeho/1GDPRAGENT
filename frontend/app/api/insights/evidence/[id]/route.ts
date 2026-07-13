import { NextResponse } from 'next/server';

const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
    const { id } = await context.params;
    try {
        const response = await fetch(`${intelligenceUrl()}/insights/evidence/${encodeURIComponent(id)}`, {
            cache: 'no-store', signal: AbortSignal.timeout(120_000),
        });
        const payload = await response.json().catch(() => ({ detail: `Intelligence service returned ${response.status}` }));
        return NextResponse.json(payload, { status: response.status });
    } catch (error) {
        return NextResponse.json({ error: 'Insight evidence service is unavailable', detail: error instanceof Error ? error.message : String(error) }, { status: 503 });
    }
}
