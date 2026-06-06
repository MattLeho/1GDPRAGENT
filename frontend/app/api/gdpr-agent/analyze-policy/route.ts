/**
 * Privacy Policy Analyzer API Route
 * 
 * Uses Python GDPR agent to analyze privacy policies with UK GDPR context.
 * Fetches policy, converts to markdown, provides AI summary and compliance analysis.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAICredential } from '@/lib/ai-credentials';
import { getWorkflowModelPreference } from '@/lib/model-preferences';

const GDPR_AGENT_URL = process.env.GDPR_AGENT_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { url, company } = body;

        if (!url) {
            return NextResponse.json(
                { success: false, error: 'URL is required' },
                { status: 400 }
            );
        }

        // Try to call Python GDPR agent
        try {
            const response = await fetch(`${GDPR_AGENT_URL}/analyze-policy`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    policy_url: url,
                    company: company || 'Company'
                }),
                signal: AbortSignal.timeout(120000), // 2 minute timeout
            });

            if (!response.ok) {
                throw new Error(`Python agent returned ${response.status}`);
            }

            const result = await response.json();

            // Update request thread
            try {
                await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/api/request-threads`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        company,
                        domain: new URL(url).hostname,
                        action: 'policy_analyzed',
                        data: {
                            policyUrl: url,
                            markdownContent: result.markdown_content,
                            summary: result.summary,
                            dpoEmail: result.dpo_email,
                            complianceScore: result.compliance_score,
                        }
                    })
                });
            } catch (threadError) {
                console.warn('[Policy Analyzer] Failed to update thread:', threadError);
            }

            return NextResponse.json({
                success: true,
                markdownContent: result.markdown_content || result.policy_text,
                summary: result.summary,
                analysis: {
                    complianceScore: result.compliance_score,
                    dataCollected: result.data_collected || [],
                    dpoEmail: result.dpo_email,
                    legalBasis: result.legal_basis,
                    retentionPeriod: result.retention_period,
                    thirdPartySharing: result.third_party_sharing,
                    userRights: result.user_rights || [],
                },
            });

        } catch (error) {
            console.warn('[Policy Analyzer] Python agent unavailable, using fallback:', error);

            // Fallback: Direct Gemini API call
            return await fallbackAnalyzePolicy(url, company);
        }

    } catch (error) {
        console.error('[Policy Analyzer] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to analyze policy' },
            { status: 500 }
        );
    }
}

/**
 * Fallback: Direct Gemini API analysis if Python agent is unavailable
 */
async function fallbackAnalyzePolicy(url: string, company: string) {
    try {
        // Get API key from settings or environment
        const apiKey = await getAICredential('google') ||
            process.env.GOOGLE_API_KEY ||
            process.env.GEMINI_API_KEY;

        if (!apiKey) {
            throw new Error('No Google API key configured');
        }

        // Step 1: Fetch the privacy policy
        const policyResponse = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        });

        if (!policyResponse.ok) {
            throw new Error('Failed to fetch privacy policy');
        }

        const policyHtml = await policyResponse.text();

        // Step 2: Use Gemini to extract and analyze
        const { GoogleGenAI } = await import('@google/genai');
        const ai = new GoogleGenAI({ apiKey });
        const policyModel = await getWorkflowModelPreference('policy');

        const prompt = `You are a GDPR compliance expert. Analyze this privacy policy for ${company}.

PRIVACY POLICY HTML:
${policyHtml.slice(0, 100000)} // Limit to avoid context overflow

TASKS:
1. Convert the policy to clean markdown format
2. Provide a 2-3 sentence summary
3. Analyze UK GDPR compliance (score 0-100)
4. Extract: data collected, DPO email, legal basis, retention periods, third-party sharing, user rights

Reference the UK GDPR law for your analysis. Be specific and cite relevant articles.

Respond in JSON format:
{
  "markdown_content": "...",
  "summary": "...",
  "compliance_score": 0-100,
  "data_collected": ["email", "IP address", ...],
  "dpo_email": "dpo@example.com or null",
  "legal_basis": "...",
  "retention_period": "...",
  "third_party_sharing": true/false,
  "user_rights": ["access", "erasure", ...]
}`;

        const response = await ai.models.generateContent({
            model: policyModel.provider === 'google' ? policyModel.model : 'gemini-3.1-flash',
            contents: prompt,
        });

        const text = response.text || '';

        // Extract JSON from response
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            throw new Error('Failed to parse AI response');
        }

        const analysis = JSON.parse(jsonMatch[0]);

        return NextResponse.json({
            success: true,
            markdownContent: analysis.markdown_content,
            summary: analysis.summary,
            analysis: {
                complianceScore: analysis.compliance_score,
                dataCollected: analysis.data_collected || [],
                dpoEmail: analysis.dpo_email,
                legalBasis: analysis.legal_basis,
                retentionPeriod: analysis.retention_period,
                thirdPartySharing: analysis.third_party_sharing,
                userRights: analysis.user_rights || [],
            },
        });

    } catch (error) {
        console.error('[Fallback Policy Analyzer] Error:', error);
        return NextResponse.json(
            { success: false, error: String(error) },
            { status: 500 }
        );
    }
}
