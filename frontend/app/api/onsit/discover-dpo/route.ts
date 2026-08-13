/**
 * DPO Discovery API Route
 * 
 * Discovers DPO (Data Protection Officer) contact information for companies.
 * Uses AI-powered web search + policy analysis to find DPO emails.
 */

import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { executeTask } from '@/lib/execution/router';

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json();
        const { vendors } = body;

        if (!Array.isArray(vendors) || vendors.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Vendors array is required' },
                { status: 400 }
            );
        }

        // Process each vendor to find DPO email
        const results = await Promise.all(
            vendors.map(vendor => findDPOForVendor(vendor, authority.profileId))
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
async function generatePolicyText(profileId: string, prompt: string): Promise<string> {
    const result = await executeTask({
        taskKey: 'policy.interpretation',
        workflowKey: 'onsit.dpo-discovery',
        profileId,
        input: { text: prompt },
        configuration: { temperature: 0 },
    });
    if (!result.ok) throw new Error(result.error.message);
    const output = result.output as { text?: unknown };
    if (typeof output.text !== 'string') throw new Error('Policy task returned no text');
    return output.text.trim();
}

async function findDPOForVendor(vendor: string, profileId: string) {
    try {
        // Step 1: Try to find the privacy policy URL
        const searchPrompt = `Find the URL of the privacy policy page for ${vendor}.
Return ONLY the URL, nothing else. If you cannot find it, return "NOT_FOUND".`;

        const policyUrl = await generatePolicyText(profileId, searchPrompt);

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

            const dpoEmail = await generatePolicyText(profileId, extractPrompt);

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
