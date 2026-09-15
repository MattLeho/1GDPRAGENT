import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { domain } = await request.json();

        if (!domain) {
            return NextResponse.json(
                { success: false, error: 'Domain is required' },
                { status: 400 }
            );
        }

        // Call Python intelligence service for AI-powered vendor discovery
        const intelligenceUrl = process.env.INTELLIGENCE_SERVICE_URL || 'http://localhost:8000';

        const target = `${intelligenceUrl}/vendor/discover`;
        const encodedBody=JSON.stringify({ domain });
        const res = await fetch(target, {
            method: 'POST',
            headers: intelligenceAuthorityHeaders(authority.profileId, target, 'POST','application/json',undefined,undefined,encodedBody),
            body: encodedBody,
        });

        if (!res.ok) {
            throw new Error(`Intelligence service returned ${res.status}`);
        }

        const data = await res.json();

        return NextResponse.json({
            success: true,
            vendors: data.vendors || [],
        });
    } catch (error) {
        console.error('[Vendor Domain Search] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Vendor search failed', details: String(error) },
            { status: 500 }
        );
    }
}
