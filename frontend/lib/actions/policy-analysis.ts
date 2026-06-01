'use server';

import { safeQuery, db } from '@/lib/db';
import { revalidatePath } from 'next/cache';

export interface PolicyAnalysis {
    id: string;
    request_id?: string;
    company_url: string;
    dpo_email: string | null;
    company_address: string | null;
    data_collected: string[];
    retention_period: string | null;
    third_party_sharing: string[];
    analysis_raw: Record<string, unknown> | null;
    analyzed_at: Date;
}

/**
 * Saves policy analysis data
 */
export async function savePolicyAnalysis(
    analysis: {
        url: string;
        dpo_email?: string;
        company_address?: string;
        data_collected?: string[];
        retention_period?: string;
        third_party_sharing?: string[];
        summary?: string;
        risk_score?: number;
        analysis_raw?: Record<string, unknown>;
    }
): Promise<{ success: boolean; id?: string }> {
    try {
        // Extract domain from URL
        let domain = analysis.url;
        try {
            const urlObj = new URL(analysis.url);
            domain = urlObj.hostname.replace('www.', '');
        } catch { /* keep original */ }

        const result = await db.query<{ id: string }>(
            `INSERT INTO policy_analyses (
                url, domain, dpo_email, company_address, 
                data_collected, retention_period, third_party_sharing,
                summary, risk_score, analysis_raw
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (url) DO UPDATE SET
                dpo_email = EXCLUDED.dpo_email,
                company_address = EXCLUDED.company_address,
                data_collected = EXCLUDED.data_collected,
                retention_period = EXCLUDED.retention_period,
                third_party_sharing = EXCLUDED.third_party_sharing,
                summary = EXCLUDED.summary,
                risk_score = EXCLUDED.risk_score,
                analysis_raw = EXCLUDED.analysis_raw,
                created_at = NOW()
            RETURNING id`,
            [
                analysis.url,
                domain,
                analysis.dpo_email || null,
                analysis.company_address || null,
                JSON.stringify(analysis.data_collected || []),
                analysis.retention_period || null,
                JSON.stringify(analysis.third_party_sharing || []),
                analysis.summary || null,
                analysis.risk_score || 0,
                JSON.stringify(analysis.analysis_raw || {}),
            ]
        );

        revalidatePath('/dashboard/analyze');
        return { success: true, id: result.rows[0]?.id };
    } catch (error) {
        console.error('Failed to save policy analysis:', error);
        return { success: false };
    }
}

/**
 * Gets policy analysis for a URL/domain (most recent within 3 months)
 */
export async function getPolicyAnalysisByUrl(url: string): Promise<PolicyAnalysis | null> {
    // Extract domain from URL
    let domain = url;
    try {
        const urlObj = new URL(url);
        domain = urlObj.hostname.replace('www.', '');
    } catch { /* keep original */ }

    const result = await safeQuery<{
        id: string;
        url: string;
        dpo_email: string | null;
        company_address: string | null;
        data_collected: string | string[];
        retention_period: string | null;
        third_party_sharing: string | string[];
        analysis_raw: string | Record<string, unknown> | null;
        created_at: Date;
    }>(`
        SELECT * FROM policy_analyses 
        WHERE domain = $1 
        AND created_at > NOW() - INTERVAL '3 months'
        ORDER BY created_at DESC 
        LIMIT 1
    `, [domain]);

    if (result.error || result.rows.length === 0) {
        return null;
    }

    const row = result.rows[0];
    return {
        id: row.id,
        company_url: row.url,
        dpo_email: row.dpo_email,
        company_address: row.company_address,
        data_collected: typeof row.data_collected === 'string'
            ? JSON.parse(row.data_collected)
            : row.data_collected || [],
        retention_period: row.retention_period,
        third_party_sharing: typeof row.third_party_sharing === 'string'
            ? JSON.parse(row.third_party_sharing)
            : row.third_party_sharing || [],
        analysis_raw: typeof row.analysis_raw === 'string'
            ? JSON.parse(row.analysis_raw)
            : row.analysis_raw || null,
        analyzed_at: row.created_at,
    };
}

/**
 * Gets policy analysis for a specific request by its ID
 * Looks up the request's domain and finds the associated policy analysis
 */
export async function getRequestAnalysis(requestId: string): Promise<PolicyAnalysis | null> {
    // First, get the request to find its domain
    const requestResult = await safeQuery<{
        domain: string | null;
        company_name: string;
    }>(`SELECT domain, company_name FROM requests WHERE id = $1`, [requestId]);

    if (requestResult.error || requestResult.rows.length === 0) {
        return null;
    }

    const { domain, company_name } = requestResult.rows[0];

    // Try to find policy analysis by domain first, then by company name
    const searchDomain = domain || company_name.toLowerCase().replace(/\s+/g, '');

    const result = await safeQuery<{
        id: string;
        url: string;
        dpo_email: string | null;
        company_address: string | null;
        data_collected: string | string[];
        retention_period: string | null;
        third_party_sharing: string | string[];
        analysis_raw: string | Record<string, unknown> | null;
        created_at: Date;
    }>(`
        SELECT * FROM policy_analyses 
        WHERE domain ILIKE $1 OR domain ILIKE $2
        ORDER BY created_at DESC 
        LIMIT 1
    `, [searchDomain, `%${company_name}%`]);

    if (result.error || result.rows.length === 0) {
        return null;
    }

    const row = result.rows[0];
    return {
        id: row.id,
        company_url: row.url,
        dpo_email: row.dpo_email,
        company_address: row.company_address,
        data_collected: typeof row.data_collected === 'string'
            ? JSON.parse(row.data_collected)
            : row.data_collected || [],
        retention_period: row.retention_period,
        third_party_sharing: typeof row.third_party_sharing === 'string'
            ? JSON.parse(row.third_party_sharing)
            : row.third_party_sharing || [],
        analysis_raw: typeof row.analysis_raw === 'string'
            ? JSON.parse(row.analysis_raw)
            : row.analysis_raw || null,
        analyzed_at: row.created_at,
    };
}

/**
 * Gets all policy analyses (latest per company)
 */
export async function getAllPolicyAnalyses(): Promise<PolicyAnalysis[]> {
    const result = await safeQuery<{
        id: string;
        url: string;
        dpo_email: string | null;
        company_address: string | null;
        data_collected: string | string[];
        retention_period: string | null;
        third_party_sharing: string | string[];
        analysis_raw: string | Record<string, unknown> | null;
        created_at: Date;
    }>(`
        SELECT DISTINCT ON (domain) *
        FROM policy_analyses
        ORDER BY domain, created_at DESC
        LIMIT 50
    `);

    if (result.error) {
        console.error('Failed to fetch policy analyses:', result.error);
        return [];
    }

    return result.rows.map((row) => ({
        id: row.id,
        company_url: row.url,
        dpo_email: row.dpo_email,
        company_address: row.company_address,
        data_collected: typeof row.data_collected === 'string'
            ? JSON.parse(row.data_collected)
            : row.data_collected || [],
        retention_period: row.retention_period,
        third_party_sharing: typeof row.third_party_sharing === 'string'
            ? JSON.parse(row.third_party_sharing)
            : row.third_party_sharing || [],
        analysis_raw: typeof row.analysis_raw === 'string'
            ? JSON.parse(row.analysis_raw)
            : row.analysis_raw || null,
        analyzed_at: row.created_at,
    }));
}
