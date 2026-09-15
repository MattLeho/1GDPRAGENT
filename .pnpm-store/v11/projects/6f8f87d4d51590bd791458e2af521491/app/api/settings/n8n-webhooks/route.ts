/**
 * N8N Webhooks Settings Route
 * 
 * GET /api/settings/n8n-webhooks - Retrieve configured webhook URLs
 * POST /api/settings/n8n-webhooks - Save webhook URL overrides
 * 
 * URLs saved here override environment variables.
 * Falls back to .env if not configured in-app.
 */

import { NextResponse, NextRequest } from 'next/server';
import type { PoolClient } from 'pg';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';
import { N8N_WEBHOOK_MAPPINGS } from '@/lib/workflows/registry';
import { validateN8nWebhookUrl, WebhookUrlValidationError } from '@/lib/security/webhook-url';

// =============================================================================
// Database Connection
// =============================================================================

const webhookMappings=N8N_WEBHOOK_MAPPINGS;

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

// =============================================================================
// GET Handler
// =============================================================================

export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        // Check if table exists and has data
        const result = await pool.query(`
            SELECT webhook_name, webhook_url, is_active
            FROM n8n_webhooks
            WHERE profile_id = $1 AND is_active = true
        `, [authority.profileId]);

        const savedUrls: Record<string, boolean> = {};
        const currentUrls: Record<string, string> = {};

        // Environment configuration is reported only as present/absent. Raw
        // operator-managed URLs are not disclosed to signed-in browser clients.
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
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.warn('[N8N Webhooks GET] Unable to load settings:', errorMessage);
        return NextResponse.json(
            { error: 'N8N webhook settings are temporarily unavailable' },
            { status: 503 },
        );
    }
}

// =============================================================================
// POST Handler
// =============================================================================

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    let client: PoolClient | null = null;
    try {
        const body = await request.json();
        const validatedUrls: Record<string, string> = {};
        const savedUrls: Record<string, boolean> = {};

        // Validate the complete update before opening the transaction so one
        // invalid override can never leave a partially changed configuration.
        for (const { id } of webhookMappings) {
            const url = typeof body[id] === 'string' ? body[id].trim() : '';
            if (url) validatedUrls[id] = validateN8nWebhookUrl(url);
        }

        client = await pool.connect();
        await client.query('BEGIN');
        for (const { id } of webhookMappings) {
            const url = validatedUrls[id] || '';
            if (url) {
                await client.query(`
                    INSERT INTO n8n_webhooks (profile_id, webhook_name, webhook_url, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (profile_id, webhook_name) DO UPDATE SET
                        webhook_url = EXCLUDED.webhook_url,
                        is_active = TRUE,
                        updated_at = NOW()
                `, [authority.profileId, id, url]);

                savedUrls[id] = true;
            } else {
                await client.query(`
                    UPDATE n8n_webhooks SET is_active = false, updated_at = NOW()
                    WHERE profile_id = $1 AND webhook_name = $2
                `, [authority.profileId, id]);
            }
        }

        // Get current state
        const result = await client.query(`
            SELECT webhook_name FROM n8n_webhooks WHERE profile_id = $1 AND is_active = true
        `, [authority.profileId]);

        for (const row of result.rows) {
            savedUrls[row.webhook_name] = true;
        }

        await client.query('COMMIT');
        return NextResponse.json({
            success: true,
            savedUrls,
        });
    } catch (error) {
        if (client) await client.query('ROLLBACK').catch(() => undefined);
        if (error instanceof WebhookUrlValidationError) {
            return NextResponse.json({ error: error.message }, { status: 400 });
        }
        console.error('[N8N Webhooks POST] Error:', error);
        return NextResponse.json(
            { error: 'Failed to save webhooks' },
            { status: 500 }
        );
    } finally {
        client?.release();
    }
}
