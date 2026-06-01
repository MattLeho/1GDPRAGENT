import { NextResponse } from 'next/server';
import { analyzePolicy } from '@/lib/n8n-client';
import { savePolicyAnalysis, getPolicyAnalysisByUrl } from '@/lib/actions/policy-analysis';

export async function POST(request: Request) {
    try {
        const body = await request.json();
        const { url, forceNew = false } = body;

        if (!url) {
            return NextResponse.json(
                { error: 'URL is required' },
                { status: 400 }
            );
        }

        // Check for existing recent analysis (unless forcing new)
        if (!forceNew) {
            const existing = await getPolicyAnalysisByUrl(url);
            if (existing) {
                return NextResponse.json({
                    found: true,
                    cached: true,
                    analysis: existing,
                });
            }
        }

        // Call N8N Policy Analyzer Agent
        const result = await analyzePolicy(url);

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

        // Save the analysis to database
        const saved = await savePolicyAnalysis({
            url,
            dpo_email: result.data.dpo_email,
            company_address: result.data.company_address,
            data_collected: result.data.data_collected,
            retention_period: result.data.retention_period,
            third_party_sharing: result.data.third_party_sharing,
            summary: result.data.summary,
            risk_score: result.data.risk_score,
            analysis_raw: result.data.raw_analysis,
        });

        if (!saved.success) {
            console.warn('Failed to save policy analysis to database');
        }

        return NextResponse.json({
            found: true,
            cached: false,
            analysis: {
                id: saved.id,
                company_url: url,
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
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}
