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

import { NextResponse } from 'next/server';
import crypto from 'crypto';
import { pool } from '@/lib/db';
import {
    AI_PROVIDER_FORM_FIELDS,
    AI_PROVIDER_IDS,
    hasEnvAICredential,
    normalizeAIProvider,
} from '@/lib/ai-credentials';
import type { AIProviderId } from '@/lib/ai-credentials';

// =============================================================================
// Encryption Utilities
// =============================================================================

function getEncryptionKey(): string {
    const key = process.env.CREDENTIALS_ENCRYPTION_KEY || process.env.ENCRYPTION_KEY;
    if (!key) {
        if (process.env.NODE_ENV === 'production') {
            throw new Error('CREDENTIALS_ENCRYPTION_KEY or ENCRYPTION_KEY must be set');
        }

        console.warn('[AI Credentials] Using local development encryption fallback. Set CREDENTIALS_ENCRYPTION_KEY before production.');
        return 'gdpr-agent-local-development-credential-key';
    }
    return key;
}

function getKey(): Buffer {
    // Ensure 32-byte key for AES-256
    return crypto.createHash('sha256').update(getEncryptionKey()).digest();
}

function encrypt(text: string): string {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-cbc', getKey(), iv);
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    return iv.toString('hex') + ':' + encrypted;
}

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

async function ensureAICredentialsTable() {
    await pool.query(`
        CREATE TABLE IF NOT EXISTS ai_credentials (
            id SERIAL PRIMARY KEY,
            provider VARCHAR(50) UNIQUE NOT NULL,
            api_key_encrypted TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    `);
}

function fieldForProvider(provider: unknown): string | null {
    const normalizedProvider = normalizeAIProvider(provider);
    return normalizedProvider ? AI_PROVIDER_FORM_FIELDS[normalizedProvider] : null;
}

// =============================================================================
// GET Handler
// =============================================================================

export async function GET() {
    try {
        await ensureAICredentialsTable();

        // Check if table exists and has data
        const result = await pool.query(`
            SELECT provider, api_key_encrypted IS NOT NULL as has_key
            FROM ai_credentials
        `);

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
        // Table might not exist yet - return defaults with env keys
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.warn('[AI Credentials GET] Table may not exist:', errorMessage);
        return NextResponse.json({
            savedKeys: emptyProviderKeyState(),
            envKeys: checkEnvKeys(),
        });
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

export async function POST(request: Request) {
    try {
        const body: AICredentialsBody = await request.json();

        // Ensure table exists
        await ensureAICredentialsTable();

        const savedKeys = emptyProviderKeyState();

        for (const { provider, field } of credentialFields) {
            const key = body[field];
            if (key && key.trim()) {
                const encryptedKey = encrypt(key.trim());
                await pool.query(`
                    INSERT INTO ai_credentials (provider, api_key_encrypted, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (provider) DO UPDATE SET
                        api_key_encrypted = EXCLUDED.api_key_encrypted,
                        updated_at = NOW()
                `, [provider, encryptedKey]);

                savedKeys[field] = true;
            }
        }

        // Get current state of all keys
        const result = await pool.query(`
            SELECT provider, api_key_encrypted IS NOT NULL as has_key
            FROM ai_credentials
        `);

        for (const row of result.rows) {
            const fieldName = fieldForProvider(row.provider);
            if (fieldName) {
                savedKeys[fieldName] = row.has_key;
            }
        }

        return NextResponse.json({
            success: true,
            savedKeys,
            envKeys: checkEnvKeys(),
        });
    } catch (error) {
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
    }
}

