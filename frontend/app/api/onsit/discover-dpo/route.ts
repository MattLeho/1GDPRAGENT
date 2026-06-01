/**
 * DPO Discovery API Route
 * 
 * Discovers DPO (Data Protection Officer) contact information for companies.
 * Uses AI-powered web search + policy analysis to find DPO emails.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAICredential } from '@/lib/ai-credentials';

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { vendors } = body;

        if (!Array.isArray(vendors) || vendors.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Vendors array is required' },
                { status: 400 }
            );
        }

        // Get API key
        const apiKey = await getAICredential('google') ||
            process.env.GOOGLE_API_KEY ||
            process.env.GEMINI_API_KEY;

        if (!apiKey) {
            return NextResponse.json(
                { success: false, error: 'No Google API key configured' },
                { status: 500 }
            );
        }

        // Process each vendor to find DPO email
        const results = await Promise.all(
            vendors.map(vendor => findDPOForVendor(vendor, apiKey))
        );

        return NextResponse.json({
            success: true,
            results,
        });

    } catch (error) {
        console.error('[DPO Discovery] Error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to discover DPOs' },
            { status: 500 }
        );
    }
}

/**
 * Find DPO email for a specific vendor
 */
async function findDPOForVendor(vendor: string, apiKey: string) {
    try {
        const { GoogleGenAI } = await import('@google/genai');
        const ai = new GoogleGenAI({ apiKey });

        // Step 1: Try to find the privacy policy URL
        const searchPrompt = `Find the URL of the privacy policy page for ${vendor}.
Return ONLY the URL, nothing else. If you cannot find it, return "NOT_FOUND".`;

        const searchResponse = await ai.models.generateContent({
            model: 'gemini-3-flash-preview',
            contents: searchPrompt,
        });

        const policyUrl = (searchResponse.text || '').trim();

        if (policyUrl === 'NOT_FOUND' || !policyUrl.startsWith('http')) {
            return {
                vendor,
                dpoEmail: null,
                policyUrl: null,
                status: 'not_found',
            };
        }

        // Step 2: Fetch and analyze the privacy policy
        try {
            const policyResponse = await fetch(policyUrl, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                },
            });

            if (!policyResponse.ok) {
                throw new Error('Failed to fetch policy');
            }

            const policyHtml = await policyResponse.text();

            // Step 3: Extract DPO email using AI
            const extractPrompt = `Extract the Data Protection Officer (DPO) or privacy contact email from this privacy policy.
Look for:
- DPO email
- Privacy officer email
- Data protection contact
- GDPR contact

PRIVACY POLICY:
${policyHtml.slice(0, 50000)}

Return ONLY the email address, nothing else. If not found, return "NOT_FOUND".`;

            const extractResponse = await ai.models.generateContent({
                model: 'gemini-3-flash-preview',
                contents: extractPrompt,
            });

            const dpoEmail = (extractResponse.text || '').trim();

            if (dpoEmail === 'NOT_FOUND' || !dpoEmail.includes('@')) {
                return {
                    vendor,
                    dpoEmail: null,
                    policyUrl,
                    status: 'email_not_found',
                };
            }

            return {
                vendor,
                dpoEmail,
                policyUrl,
                status: 'found',
            };

        } catch (error) {
            console.error(`[DPO Discovery] Failed to fetch policy for ${vendor}:`, error);
            return {
                vendor,
                dpoEmail: null,
                policyUrl,
                status: 'fetch_failed',
            };
        }

    } catch (error) {
        console.error(`[DPO Discovery] Error processing ${vendor}:`, error);
        return {
            vendor,
            dpoEmail: null,
            policyUrl: null,
            status: 'error',
        };
    }
}
