/**
 * N8N Webhooks Settings Route
 * 
 * GET /api/settings/n8n-webhooks - Retrieve configured webhook URLs
 * POST /api/settings/n8n-webhooks - Save webhook URL overrides
 * 
 * URLs saved here override environment variables.
 * Falls back to .env if not configured in-app.
 */

import { NextResponse } from 'next/server';
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
// Environment Variable Check
// =============================================================================

function checkEnvUrls(): Record<string, boolean> {
    const result: Record<string, boolean> = {};
    for (const { id, envVar } of webhookMappings) {
        result[id] = !!process.env[envVar];
    }
    return result;
}

function getEnvUrls(): Record<string, string | undefined> {
    const result: Record<string, string | undefined> = {};
    for (const { id, envVar } of webhookMappings) {
        result[id] = process.env[envVar];
    }
    return result;
}

// =============================================================================
// GET Handler
// =============================================================================

export async function GET() {
    try {
        // Check if table exists and has data
        const result = await pool.query(`
            SELECT webhook_name, webhook_url, is_active
            FROM n8n_webhooks
            WHERE is_active = true
        `);

        const savedUrls: Record<string, boolean> = {};
        const currentUrls: Record<string, string> = {};

        // First, populate with env variables as defaults
        const envUrls = getEnvUrls();
        for (const [id, url] of Object.entries(envUrls)) {
            if (url) currentUrls[id] = url;
        }

        // Then override with saved URLs
        for (const row of result.rows) {
            savedUrls[row.webhook_name] = true;
            currentUrls[row.webhook_name] = row.webhook_url;
        }

        return NextResponse.json({
            savedUrls,
            envUrls: checkEnvUrls(),
            currentUrls,
        });
    } catch (error: unknown) {
        // Table might not exist yet - return env defaults
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.warn('[N8N Webhooks GET] Table may not exist:', errorMessage);
        return NextResponse.json({
            savedUrls: {},
            envUrls: checkEnvUrls(),
            currentUrls: getEnvUrls(),
        });
    }
}

// =============================================================================
// POST Handler
// =============================================================================

export async function POST(request: Request) {
    try {
        const body = await request.json();

        // Ensure table exists
        await pool.query(`
            CREATE TABLE IF NOT EXISTS n8n_webhooks (
                id SERIAL PRIMARY KEY,
                webhook_name VARCHAR(100) UNIQUE NOT NULL,
                webhook_url TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        `);

        const savedUrls: Record<string, boolean> = {};

        for (const { id } of webhookMappings) {
            const url = body[id];
            if (url && url.trim()) {
                await pool.query(`
                    INSERT INTO n8n_webhooks (webhook_name, webhook_url, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (webhook_name) DO UPDATE SET
                        webhook_url = EXCLUDED.webhook_url,
                        is_active = TRUE,
                        updated_at = NOW()
                `, [id, url.trim()]);

                savedUrls[id] = true;
            }
        }

        // Get current state
        const result = await pool.query(`
            SELECT webhook_name FROM n8n_webhooks WHERE is_active = true
        `);

        for (const row of result.rows) {
            savedUrls[row.webhook_name] = true;
        }

        return NextResponse.json({
            success: true,
            savedUrls,
        });
    } catch (error) {
        console.error('[N8N Webhooks POST] Error:', error);
        return NextResponse.json(
            { error: 'Failed to save webhooks' },
            { status: 500 }
        );
    }
}

