/**
 * N8N Integration Client
 * 
 * Provides functions to call N8N webhooks for GDPR automation workflows.
 * Configure webhook paths via environment variables.
 */

const N8N_INTERNAL_URL = process.env.N8N_INTERNAL_URL || 'http://n8n:5678';
const N8N_PUBLIC_URL = process.env.N8N_PUBLIC_URL || 'http://localhost:5678';

// Webhook paths - configure these in .env or they'll use defaults
const WEBHOOK_PATHS = {
    analyzePolicy: process.env.N8N_WEBHOOK_ANALYZE_POLICY || 'analyze-policy',
    draftRequest: process.env.N8N_WEBHOOK_DRAFT_REQUEST || 'draft-request',
    sendEmail: process.env.N8N_WEBHOOK_SEND_EMAIL || 'send-email',
    testImap: process.env.N8N_WEBHOOK_TEST_IMAP || 'test-imap',
    ingestData: process.env.N8N_WEBHOOK_INGEST_DATA || 'ingest-data',
    ingestIdentity: process.env.N8N_WEBHOOK_INGEST_IDENTITY || 'ingest-identity',
};

export type N8NWebhookType = keyof typeof WEBHOOK_PATHS;

interface N8NResponse<T = unknown> {
    success: boolean;
    data?: T;
    error?: string;
}

/**
 * Call an N8N webhook with the given payload.
 * Uses internal Docker network URL for server-side calls.
 */
export async function callN8NWebhook<T = unknown>(
    webhookType: N8NWebhookType,
    payload: Record<string, unknown>,
    options: { timeout?: number; usePublicUrl?: boolean } = {}
): Promise<N8NResponse<T>> {
    const { timeout = 30000, usePublicUrl = false } = options;
    const baseUrl = usePublicUrl ? N8N_PUBLIC_URL : N8N_INTERNAL_URL;
    const webhookPath = WEBHOOK_PATHS[webhookType];
    const url = `${baseUrl}/webhook/${webhookPath}`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        console.log(`[N8N] Calling webhook: ${webhookType} at ${url}`);

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`[N8N] Webhook ${webhookType} failed:`, response.status, errorText);
            return {
                success: false,
                error: `N8N returned ${response.status}: ${errorText}`,
            };
        }

        const data = await response.json();
        console.log(`[N8N] Webhook ${webhookType} succeeded`);

        return {
            success: true,
            data: data as T,
        };
    } catch (error: unknown) {
        clearTimeout(timeoutId);

        if (error instanceof Error && error.name === 'AbortError') {
            console.error(`[N8N] Webhook ${webhookType} timed out after ${timeout}ms`);
            return {
                success: false,
                error: `Request timed out after ${timeout}ms`,
            };
        }

        const message = error instanceof Error ? error.message : 'Unknown error';
        console.error(`[N8N] Webhook ${webhookType} error:`, message);

        return {
            success: false,
            error: `Failed to call N8N: ${message}`,
        };
    }
}

/**
 * Policy Analysis Response Type
 */
export interface PolicyAnalysisResult {
    dpo_email?: string;
    company_address?: string;
    data_collected?: string[];
    retention_period?: string;
    third_party_sharing?: string[];
    summary?: string;
    risk_score?: number;
    raw_analysis?: Record<string, unknown>;
}

/**
 * Analyze a company's privacy policy via N8N
 */
export async function analyzePolicy(url: string): Promise<N8NResponse<PolicyAnalysisResult>> {
    return callN8NWebhook<PolicyAnalysisResult>('analyzePolicy', {
        url,
        timestamp: new Date().toISOString(),
    }, { timeout: 60000 }); // Policy analysis can take longer
}

/**
 * Draft a GDPR request email via N8N
 */
export async function draftRequest(params: {
    companyName: string;
    companyUrl: string;
    requestType: string;
    identity: Record<string, unknown>;
    notes?: string;
    datePeriod?: { from?: string; to?: string };
}): Promise<N8NResponse<{ subject: string; body: string; to: string }>> {
    return callN8NWebhook('draftRequest', params);
}

/**
 * Send an email via N8N
 */
export async function sendEmail(params: {
    to: string;
    subject: string;
    body: string;
    replyTo?: string;
}): Promise<N8NResponse<{ messageId: string }>> {
    return callN8NWebhook('sendEmail', params);
}

/**
 * Test IMAP connection via N8N
 */
export async function testImapConnection(params: {
    email: string;
    host: string;
    port: number;
    password: string;
}): Promise<N8NResponse<{ connected: boolean; mailboxCount?: number }>> {
    return callN8NWebhook('testImap', params, { timeout: 15000 });
}

/**
 * Ingest data into Knowledge Graph via N8N
 */
export async function ingestToKnowledgeGraph(params: {
    companyName: string;
    requestId: string;
    extractedData: Record<string, unknown>;
    categories: string[];
}): Promise<N8NResponse<{ nodesCreated: number; relationshipsCreated: number }>> {
    return callN8NWebhook('ingestData', params);
}

/**
 * Ingest identity data into Knowledge Graph via N8N
 */
export async function ingestIdentity(params: {
    personaName: string;
    emails?: string[];
    phones?: string[];
    names?: { firstName?: string; lastName?: string }[];
    usernames?: string[];
    notes?: string;
}): Promise<N8NResponse<{ personaId: string; entitiesCreated: number }>> {
    return callN8NWebhook('ingestIdentity', params);
}
