/**
 * N8N Webhooks Utilities
 * 
 * Provides functions to retrieve N8N webhook URLs.
 * Falls back to environment variables if not configured in database.
 */

import { Pool } from 'pg';

// =============================================================================
// Database Connection
// =============================================================================

const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
});

// =============================================================================
// Webhook Mappings
// =============================================================================

interface WebhookMapping {
    id: string;
    envVar: string;
}

const webhookMappings: WebhookMapping[] = [
    { id: 'policyAnalyzer', envVar: 'N8N_WEBHOOK_POLICY_ANALYZER' },
    { id: 'requestDrafter', envVar: 'N8N_WEBHOOK_REQUEST_DRAFTER' },
    { id: 'kgIngestor', envVar: 'N8N_WEBHOOK_INGEST_DATA' },
    { id: 'hybridRag', envVar: 'N8N_WEBHOOK_ENHANCED_RAG' },
    { id: 'transcription', envVar: 'N8N_WEBHOOK_TRANSCRIPTION' },
    { id: 'vendorOcr', envVar: 'N8N_WEBHOOK_VENDOR_OCR' },
    { id: 'policyScanner', envVar: 'N8N_WEBHOOK_POLICY_SCANNER' },
];

// =============================================================================
// Webhook URL Retrieval
// =============================================================================

/**
 * Get a webhook URL by its ID.
 * First checks the database, then falls back to environment variables.
 * 
 * @param webhookId - Webhook identifier (e.g., 'policyAnalyzer', 'kgIngestor')
 * @returns Webhook URL or null
 */
export async function getWebhookUrl(webhookId: string): Promise<string | null> {
    try {
        const result = await pool.query(
            'SELECT webhook_url FROM n8n_webhooks WHERE webhook_name = $1 AND is_active = true',
            [webhookId]
        );

        if (result.rows.length > 0) {
            return result.rows[0].webhook_url;
        }
    } catch {
        // Table doesn't exist or no URL found
    }

    // Fall back to environment variable
    const mapping = webhookMappings.find(m => m.id === webhookId);
    if (mapping) {
        return process.env[mapping.envVar] || null;
    }

    return null;
}

/**
 * Get all configured webhook URLs.
 * Returns an object with webhook IDs as keys and URLs as values.
 */
export async function getAllWebhookUrls(): Promise<Record<string, string | null>> {
    const urls: Record<string, string | null> = {};

    for (const { id } of webhookMappings) {
        urls[id] = await getWebhookUrl(id);
    }

    return urls;
}

/**
 * Check if a webhook is configured (either in DB or environment).
 */
export async function isWebhookConfigured(webhookId: string): Promise<boolean> {
    const url = await getWebhookUrl(webhookId);
    return url !== null && url.length > 0;
}
