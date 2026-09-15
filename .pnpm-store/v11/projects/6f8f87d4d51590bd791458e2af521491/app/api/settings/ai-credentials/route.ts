/**
 * AI Provider Credentials Settings Route
 * 
 * GET /api/settings/ai-credentials - Retrieve which AI provider keys are configured
 * POST /api/settings/ai-credentials - Save encrypted AI provider credentials
 * 
 * This is SEPARATE from the ONSIT API credentials (api-credentials route).
 * 
 * @security All API keys are encrypted before storage using AES-256
 */

import { NextResponse, NextRequest } from 'next/server';
import type { PoolClient } from 'pg';
import { requireApiSession } from '@/lib/api-session';
import { pool } from '@/lib/db';
import { encryptCredential } from '@/lib/secure-credentials';
import {
    AI_PROVIDER_FORM_FIELDS,
    AI_PROVIDER_IDS,
    hasEnvAICredential,
    normalizeAIProvider,
} from '@/lib/ai-credentials';
import type { AIProviderId } from '@/lib/ai-credentials';

// =============================================================================
// Environment Variable Check
// =============================================================================

function emptyProviderKeyState(): Record<string, boolean> {
    return Object.fromEntries(
        AI_PROVIDER_IDS.map(provider => [AI_PROVIDER_FORM_FIELDS[provider], false])
    );
}

function checkEnvKeys(): Record<string, boolean> {
    return Object.fromEntries(
        AI_PROVIDER_IDS.map(provider => [
            AI_PROVIDER_FORM_FIELDS[provider],
            hasEnvAICredential(provider),
        ])
    );
}

function fieldForProvider(provider: unknown): string | null {
    const normalizedProvider = normalizeAIProvider(provider);
    return normalizedProvider ? AI_PROVIDER_FORM_FIELDS[normalizedProvider] : null;
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
            SELECT provider, api_key_encrypted IS NOT NULL as has_key
            FROM ai_credentials
            WHERE profile_id = $1
        `, [authority.profileId]);

        const savedKeys = emptyProviderKeyState();

        for (const row of result.rows) {
            const fieldName = fieldForProvider(row.provider);
            if (fieldName) {
                savedKeys[fieldName] = row.has_key;
            }
        }

        return NextResponse.json({
            savedKeys,
            envKeys: checkEnvKeys(),
        });
    } catch (error: unknown) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.warn('[AI Credentials GET] Unable to load credentials:', errorMessage);
        return NextResponse.json(
            { error: 'Provider credential settings are temporarily unavailable' },
            { status: 503 },
        );
    }
}

// =============================================================================
// POST Handler
// =============================================================================

interface AICredentialsBody {
    googleApiKey?: string;
    openaiApiKey?: string;
    openrouterApiKey?: string;
    ollamaApiKey?: string;
    huggingfaceApiKey?: string;
    nvidiaApiKey?: string;
}

const credentialFields: Array<{ provider: AIProviderId; field: keyof AICredentialsBody }> = [
    { provider: 'google', field: 'googleApiKey' },
    { provider: 'openai', field: 'openaiApiKey' },
    { provider: 'openrouter', field: 'openrouterApiKey' },
    { provider: 'ollama', field: 'ollamaApiKey' },
    { provider: 'huggingface', field: 'huggingfaceApiKey' },
    { provider: 'nvidia', field: 'nvidiaApiKey' },
];

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    let client: PoolClient | null = null;
    try {
        const body: AICredentialsBody = await request.json();
        const updates = credentialFields.flatMap(({ provider, field }) => {
            const value = body[field]?.trim();
            return value ? [{ provider, field, value }] : [];
        });
        if (updates.length === 0) {
            return NextResponse.json(
                { error: 'Enter at least one provider credential' },
                { status: 400 },
            );
        }
        const savedKeys = emptyProviderKeyState();

        client = await pool.connect();
        await client.query('BEGIN');
        for (const { provider, field, value } of updates) {
            const encryptedKey = encryptCredential(value);
            await client.query(`
                INSERT INTO ai_credentials (provider, api_key_encrypted, updated_at, profile_id)
                VALUES ($1, $2, NOW(), $3)
                ON CONFLICT (profile_id, provider) DO UPDATE SET
                    api_key_encrypted = EXCLUDED.api_key_encrypted,
                    updated_at = NOW()
            `, [provider, encryptedKey, authority.profileId]);
            savedKeys[field] = true;
        }

        // Get current state of all keys
        const result = await client.query(`
            SELECT provider, api_key_encrypted IS NOT NULL as has_key
            FROM ai_credentials
            WHERE profile_id = $1
        `, [authority.profileId]);

        for (const row of result.rows) {
            const fieldName = fieldForProvider(row.provider);
            if (fieldName) {
                savedKeys[fieldName] = row.has_key;
            }
        }

        await client.query('COMMIT');
        return NextResponse.json({
            success: true,
            savedKeys,
            envKeys: checkEnvKeys(),
        });
    } catch (error) {
        if (client) await client.query('ROLLBACK').catch(() => undefined);
        console.error('[AI Credentials POST] Error:', error);
        const missingEncryptionKey = error instanceof Error &&
            error.message.includes('CREDENTIALS_ENCRYPTION_KEY');

        return NextResponse.json(
            {
                error: missingEncryptionKey
                    ? 'Credential encryption key is not configured'
                    : 'Failed to save AI credentials',
            },
            { status: missingEncryptionKey ? 400 : 500 }
        );
    } finally {
        client?.release();
    }
}
