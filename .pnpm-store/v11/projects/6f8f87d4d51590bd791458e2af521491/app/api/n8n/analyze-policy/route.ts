import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { analyzePolicy } from '@/lib/n8n-client';
import { assertPublicHttpUrl, PublicUrlValidationError } from '@/lib/security/public-url';

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json();
        const { url } = body;

        if (!url) {
            return NextResponse.json(
                { error: 'URL is required' },
                { status: 400 }
            );
        }

        const safeUrl = await assertPublicHttpUrl(url);
        // Call N8N Policy Analyzer Agent only after the target is proven public.
        const result = await analyzePolicy(safeUrl.href, authority.profileId);

        if (!result.success || !result.data) {
            console.error('N8N Policy Analyzer failed:', result.error);
            return NextResponse.json(
                {
                    error: result.error || 'Policy analysis failed',
                    found: false,
                },
                { status: 502 }
            );
        }

        // This endpoint runs before a request exists. Keep the result transient;
        // request submission persists it against the newly created owned request.
        return NextResponse.json({
            found: true,
            cached: false,
            persisted: false,
            analysis: {
                company_url: safeUrl.href,
                dpo_email: result.data.dpo_email,
                company_address: result.data.company_address,
                data_collected: result.data.data_collected || [],
                retention_period: result.data.retention_period,
                third_party_sharing: result.data.third_party_sharing || [],
                summary: result.data.summary,
                risk_score: result.data.risk_score,
                analyzed_at: new Date(),
            },
        });

    } catch (error) {
        console.error('Policy analysis endpoint error:', error);
        return NextResponse.json(
            { error: error instanceof PublicUrlValidationError ? error.message : 'Internal server error' },
            { status: error instanceof PublicUrlValidationError ? 400 : 500 }
        );
    }
}
