'use server'

import { db } from '@/lib/db'
import { requireServerSessionAuthority } from '@/lib/api-session'
import { savePolicyAnalysis as saveRequestPolicyAnalysis } from '@/lib/actions/policy-analysis'

export type PolicyAnalysis = {
    id: string
    url: string
    domain: string
    summary: string | null
    risk_score: number
    data_collected: string[]
    dpo_email: string | null
    created_at: Date
}

/**
 * Checks if a valid (recent) policy analysis exists for the given URL/Domain.
 * "Recent" is defined as within the last 3 months.
 */
export async function getPolicyAnalysis(url: string): Promise<PolicyAnalysis | null> {
    const { profileId } = await requireServerSessionAuthority()
    try {
        // Simple domain extraction (could be more robust)
        let domain = url.toLowerCase()
        try {
            const u = new URL(url)
            domain = u.hostname.replace('www.', '')
        } catch {
            // fast fail or fallback to string matching
        }

        // Check for analysis on this domain in the last 3 months (90 days)
        const query = `
            SELECT * FROM policy_analyses 
            WHERE profile_id = $1
            AND domain = $2
            AND created_at > NOW() - INTERVAL '3 months'
            ORDER BY created_at DESC 
            LIMIT 1
        `
        const res = await db.query(query, [profileId, domain])

        if (res.rows && res.rows.length > 0) {
            return res.rows[0] as PolicyAnalysis
        }
        return null
    } catch (error) {
        console.error("Error fetching policy analysis:", error)
        return null
    }
}

/**
 * Saves a new policy analysis result.
 */
export async function savePolicyAnalysis(data: {
    request_id: string,
    url: string,
    summary: string,
    risk_score: number,
    data_collected: string[],
    dpo_email: string
}) {
    try {
        return await saveRequestPolicyAnalysis({
            requestId: data.request_id,
            url: data.url,
            summary: data.summary,
            risk_score: data.risk_score,
            data_collected: data.data_collected,
            dpo_email: data.dpo_email,
        })
    } catch (error) {
        console.error("Error saving policy analysis:", error)
        return { success: false }
    }
}
