'use server'

import { db } from '@/lib/db'

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
    try {
        // Simple domain extraction (could be more robust)
        let domain = url.toLowerCase()
        try {
            const u = new URL(url)
            domain = u.hostname.replace('www.', '')
        } catch (e) {
            // fast fail or fallback to string matching
        }

        // Check for analysis on this domain in the last 3 months (90 days)
        const query = `
            SELECT * FROM policy_analyses 
            WHERE domain = $1 
            AND created_at > NOW() - INTERVAL '3 months'
            ORDER BY created_at DESC 
            LIMIT 1
        `
        const res = await db.query(query, [domain])

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
    url: string,
    summary: string,
    risk_score: number,
    data_collected: string[],
    dpo_email: string
}) {
    try {
        // Extract domain
        let domain = data.url
        try {
            const u = new URL(data.url)
            domain = u.hostname.replace('www.', '')
        } catch (e) { }

        const query = `
            INSERT INTO policy_analyses (url, domain, summary, risk_score, data_collected, dpo_email)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        `

        await db.query(query, [
            data.url,
            domain,
            data.summary,
            data.risk_score,
            JSON.stringify(data.data_collected), // store as JSONB or text[] depending on schema. Using JSON string for safety if text.
            data.dpo_email
        ])

        return { success: true }
    } catch (error) {
        console.error("Error saving policy analysis:", error)
        return { success: false }
    }
}
