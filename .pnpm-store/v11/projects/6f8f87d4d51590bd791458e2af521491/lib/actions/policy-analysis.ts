'use server';

import { safeQuery, db } from '@/lib/db';
import { revalidatePath } from 'next/cache';
import { requireServerSessionAuthority } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();
type JsonObject = Record<string, unknown> | null;

interface PolicyAnalysisRow {
    id: string; request_id: string; profile_id: string; url: string;
    dpo_email: string | null; company_address: string | null;
    data_collected: string | string[] | null; retention_period: string | null;
    third_party_sharing: string | string[] | null;
    analysis_raw: string | JsonObject; provenance: string | JsonObject;
    execution_record_id: string | null; created_at: Date;
}

export interface PolicyAnalysis {
    id: string; request_id: string; company_url: string;
    dpo_email: string | null; company_address: string | null;
    data_collected: string[]; retention_period: string | null;
    third_party_sharing: string[]; analysis_raw: JsonObject;
    provenance: JsonObject; execution_record_id: string | null; analyzed_at: Date;
}

export interface SavePolicyAnalysisInput {
    requestId?: string; url: string; dpo_email?: string | null; company_address?: string | null;
    data_collected?: string[]; retention_period?: string | null; third_party_sharing?: string[];
    summary?: string | null; risk_score?: number | null; analysis_raw?: Record<string, unknown> | null;
    provenance?: Record<string, unknown> | null; executionRecordId?: string | null;
}

function domainFromUrl(url: string): string {
    try { return new URL(url).hostname.replace(/^www\./i, ''); } catch { return url; }
}

function jsonObject(value: string | JsonObject): JsonObject {
    if (!value) return null;
    if (typeof value !== 'string') return value;
    try { const parsed = JSON.parse(value); return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null; }
    catch { return null; }
}

function jsonArray(value: string | string[] | null): string[] {
    if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string');
    if (!value) return [];
    try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : []; }
    catch { return []; }
}

function toPolicyAnalysis(row: PolicyAnalysisRow): PolicyAnalysis {
    return {
        id: row.id, request_id: row.request_id, company_url: row.url, dpo_email: row.dpo_email,
        company_address: row.company_address, data_collected: jsonArray(row.data_collected),
        retention_period: row.retention_period, third_party_sharing: jsonArray(row.third_party_sharing),
        analysis_raw: jsonObject(row.analysis_raw), provenance: jsonObject(row.provenance),
        execution_record_id: row.execution_record_id, analyzed_at: row.created_at,
    };
}

/** Persists an analysis only for a request owned by the current profile. */
export async function savePolicyAnalysis(input: SavePolicyAnalysisInput): Promise<{
    success: boolean; analysis?: PolicyAnalysis; error?: string;
}> {
    const { profileId } = await requireServerSessionAuthority();
    if (!input.requestId) return { success: false, error: 'requestId is required to persist policy analysis' };
    if (!await requests.get(profileId, input.requestId)) return { success: false, error: 'Request not found' };
    try {
        const result = await db.query<PolicyAnalysisRow>(`
            INSERT INTO policy_analyses (
                profile_id, request_id, url, domain, dpo_email, company_address,
                data_collected, retention_period, third_party_sharing, summary,
                risk_score, analysis_raw, provenance, execution_record_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (profile_id, request_id, url) DO UPDATE SET
                dpo_email = EXCLUDED.dpo_email, company_address = EXCLUDED.company_address,
                data_collected = EXCLUDED.data_collected, retention_period = EXCLUDED.retention_period,
                third_party_sharing = EXCLUDED.third_party_sharing, summary = EXCLUDED.summary,
                risk_score = EXCLUDED.risk_score, analysis_raw = EXCLUDED.analysis_raw,
                provenance = EXCLUDED.provenance, execution_record_id = EXCLUDED.execution_record_id,
                created_at = NOW()
            RETURNING *`, [
            profileId, input.requestId, input.url, domainFromUrl(input.url), input.dpo_email || null,
            input.company_address || null, JSON.stringify(input.data_collected || []), input.retention_period || null,
            JSON.stringify(input.third_party_sharing || []), input.summary || null, input.risk_score || 0,
            JSON.stringify(input.analysis_raw || {}), JSON.stringify(input.provenance || {}), input.executionRecordId || null,
        ]);
        const row = result.rows[0];
        if (!row) return { success: false, error: 'Policy analysis was not persisted' };
        revalidatePath(`/dashboard/requests/${input.requestId}`);
        return { success: true, analysis: toPolicyAnalysis(row) };
    } catch (error) {
        console.error('Failed to save policy analysis:', error);
        return { success: false, error: 'Failed to save policy analysis' };
    }
}

/** Reads the newest analysis for this exact owned request only. */
export async function getRequestAnalysis(requestId: string): Promise<PolicyAnalysis | null> {
    const { profileId } = await requireServerSessionAuthority();
    if (!await requests.get(profileId, requestId)) return null;
    const result = await safeQuery<PolicyAnalysisRow>(`
        SELECT * FROM policy_analyses
        WHERE request_id = $1 AND profile_id = $2
        ORDER BY created_at DESC LIMIT 1`, [requestId, profileId]);
    return result.error || !result.rows[0] ? null : toPolicyAnalysis(result.rows[0]);
}

/** Lists the current profile's request-owned analyses, newest per request. */
export async function getAllPolicyAnalyses(): Promise<PolicyAnalysis[]> {
    const { profileId } = await requireServerSessionAuthority();
    const result = await safeQuery<PolicyAnalysisRow>(`
        SELECT DISTINCT ON (request_id) * FROM policy_analyses
        WHERE profile_id = $1
        ORDER BY request_id, created_at DESC LIMIT 50`, [profileId]);
    if (result.error) { console.error('Failed to fetch policy analyses:', result.error); return []; }
    return result.rows.map(toPolicyAnalysis);
}

/** Kept for callers that need a profile-owned cached analysis by URL. */
export async function getPolicyAnalysisByUrl(url: string): Promise<PolicyAnalysis | null> {
    const { profileId } = await requireServerSessionAuthority();
    const result = await safeQuery<PolicyAnalysisRow>(`
        SELECT * FROM policy_analyses
        WHERE profile_id = $1 AND url = $2
        ORDER BY created_at DESC LIMIT 1`, [profileId, url]);
    return result.error || !result.rows[0] ? null : toPolicyAnalysis(result.rows[0]);
}
