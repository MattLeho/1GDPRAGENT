import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const target = `${intelligenceUrl()}/insights/media-location-confirmations`;
        const body=await request.text();
        const response = await fetch(target, {
            method:'POST',headers:intelligenceAuthorityHeaders(authority.profileId, target, 'POST','application/json',undefined,undefined,body),body,
            signal:AbortSignal.timeout(120_000),cache:'no-store',
        });
        return NextResponse.json(await response.json(),{status:response.status});
    } catch (error) {
        return NextResponse.json({error:'Location-confirmation service is unavailable',detail:error instanceof Error ? error.message : String(error)},{status:503});
    }
}
