import { NextResponse } from 'next/server';

const intelligenceUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

export async function POST(request: Request) {
    try {
        const response = await fetch(`${intelligenceUrl()}/insights/media-location-confirmations`, {
            method:'POST',headers:{'Content-Type':'application/json'},body:await request.text(),
            signal:AbortSignal.timeout(120_000),cache:'no-store',
        });
        return NextResponse.json(await response.json(),{status:response.status});
    } catch (error) {
        return NextResponse.json({error:'Location-confirmation service is unavailable',detail:error instanceof Error ? error.message : String(error)},{status:503});
    }
}
