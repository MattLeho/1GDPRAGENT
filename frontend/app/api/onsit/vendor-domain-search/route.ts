import { NextResponse } from 'next/server';

export async function POST(request: Request) {
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

        const res = await fetch(`${intelligenceUrl}/vendor/discover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain }),
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
