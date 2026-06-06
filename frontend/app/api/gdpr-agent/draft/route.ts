/**
 * GDPR Agent API Route
 * 
 * Proxies requests to the Python GDPR agent FastAPI server.
 * Handles drafting GDPR requests using the RLM approach.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAICredential } from '@/lib/ai-credentials';
import { getWorkflowModelPreference } from '@/lib/model-preferences';

const GDPR_AGENT_URL = process.env.GDPR_AGENT_URL || 'http://localhost:8000';

/**
 * POST /api/gdpr-agent/draft
 * 
 * Draft a GDPR request using the Python RLM agent.
 */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        const {
            requestType,
            company,
            userQuery,
            userName,
            userEmail,
            policyUrl,
        } = body;

        // Validate required fields
        if (!requestType || !company || !userQuery || !userName || !userEmail) {
            return NextResponse.json(
                { success: false, error: 'Missing required fields' },
                { status: 400 }
            );
        }

        // Get API key from database or environment
        const apiKey = await getAICredential('google') ||
            process.env.GOOGLE_API_KEY ||
            process.env.GEMINI_API_KEY;

        // Call Python agent
        const response = await fetch(`${GDPR_AGENT_URL}/draft-request`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request_type: requestType,
                company: company,
                user_query: userQuery,
                user_name: userName,
                user_email: userEmail,
                policy_url: policyUrl,
                api_key: apiKey,
            }),
        });

        if (!response.ok) {
            const error = await response.text();
            console.error('[GDPR Agent] Python server error:', error);

            // Fall back to direct Gemini call if Python server unavailable
            return await fallbackDraft(requestType, company, userQuery, userName, userEmail);
        }

        const data = await response.json();

        return NextResponse.json({
            success: true,
            draft: {
                subject: data.subject,
                body: data.body,
                articlesCited: data.articles_cited,
                company: data.company,
                requestType: data.request_type,
                deadlineDays: data.deadline_days,
            }
        });
    } catch (error) {
        console.error('[GDPR Agent] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to draft request' },
            { status: 500 }
        );
    }
}

/**
 * Fallback: Draft request directly using Gemini if Python server unavailable.
 */
async function fallbackDraft(
    requestType: string,
    company: string,
    userQuery: string,
    userName: string,
    userEmail: string
): Promise<NextResponse> {
    try {
        // Dynamic import to avoid issues if not installed
        const { GoogleGenAI } = await import('@google/genai');

        const preferences = await getWorkflowModelPreference('drafting');
        const apiKey = await getAICredential('google') ||
            process.env.GOOGLE_API_KEY ||
            process.env.GEMINI_API_KEY;
        if (!apiKey) {
            return NextResponse.json(
                { success: false, error: 'No API key configured' },
                { status: 500 }
            );
        }

        const ai = new GoogleGenAI({ apiKey });

        const requestTypes: Record<string, string> = {
            'access': 'Subject Access Request (Article 15)',
            'erasure': 'Erasure Request (Article 17)',
            'rectification': 'Rectification Request (Article 16)',
            'portability': 'Data Portability Request (Article 20)',
            'objection': 'Objection to Processing (Article 21)',
        };

        const prompt = `Draft a formal GDPR ${requestTypes[requestType] || 'request'} to ${company}.

User: ${userName} (${userEmail})
Request: ${userQuery}

Requirements:
1. Formal, professional language
2. Cite relevant GDPR articles
3. Set 30-day deadline per Article 12(3)
4. Offer identity verification
5. Mention ICO complaint right

Format as a complete letter.`;

        const response = await ai.models.generateContent({
            model: preferences.provider === 'google' ? preferences.model : 'gemini-3.1-flash',
            contents: prompt,
        });

        const body = response.text || '';

        return NextResponse.json({
            success: true,
            draft: {
                subject: `${requestTypes[requestType] || 'GDPR Request'} - ${userName}`,
                body: body,
                articlesCited: requestType === 'access' ? [15] :
                    requestType === 'erasure' ? [17] :
                        requestType === 'rectification' ? [16] :
                            requestType === 'portability' ? [20] : [21],
                company: company,
                requestType: requestType,
                deadlineDays: 30,
            },
            fallback: true
        });
    } catch (error) {
        console.error('[GDPR Agent Fallback] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to draft request' },
            { status: 500 }
        );
    }
}
