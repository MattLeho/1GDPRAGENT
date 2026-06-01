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
import { Pool } from 'pg';
import crypto from 'crypto';

// =============================================================================
// Database Connection
// =============================================================================

const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
});

// =============================================================================
// Encryption Utilities
// =============================================================================

function getEncryptionKey(): string {
    const key = process.env.CREDENTIALS_ENCRYPTION_KEY || process.env.ENCRYPTION_KEY;
    if (!key) {
        throw new Error('CREDENTIALS_ENCRYPTION_KEY or ENCRYPTION_KEY must be set');
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

function decrypt(encryptedText: string): string {
    try {
        const [ivHex, encrypted] = encryptedText.split(':');
        const iv = Buffer.from(ivHex, 'hex');
        const decipher = crypto.createDecipheriv('aes-256-cbc', getKey(), iv);
        let decrypted = decipher.update(encrypted, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        return decrypted;
    } catch {
        return '';
    }
}

// =============================================================================
// Environment Variable Check
// =============================================================================

interface EnvKeys {
    googleApiKey: boolean;
    openaiApiKey: boolean;
    openrouterApiKey: boolean;
    anthropicApiKey: boolean;
}

function checkEnvKeys(): EnvKeys {
    return {
        googleApiKey: !!(process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY),
        openaiApiKey: !!process.env.OPENAI_API_KEY,
        openrouterApiKey: !!process.env.OPENROUTER_API_KEY,
        anthropicApiKey: !!process.env.ANTHROPIC_API_KEY,
    };
}

// =============================================================================
// GET Handler
// =============================================================================

export async function GET() {
    try {
        // Check if table exists and has data
        const result = await pool.query(`
            SELECT provider, api_key_encrypted IS NOT NULL as has_key
            FROM ai_credentials
        `);

        const savedKeys: Record<string, boolean> = {
            googleApiKey: false,
            openaiApiKey: false,
            openrouterApiKey: false,
            anthropicApiKey: false,
        };

        // Map provider names to form field names
        const providerMap: Record<string, string> = {
            'google': 'googleApiKey',
            'openai': 'openaiApiKey',
            'openrouter': 'openrouterApiKey',
            'anthropic': 'anthropicApiKey',
        };

        for (const row of result.rows) {
            const fieldName = providerMap[row.provider];
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
            savedKeys: {
                googleApiKey: false,
                openaiApiKey: false,
                openrouterApiKey: false,
                anthropicApiKey: false,
            },
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
    anthropicApiKey?: string;
}

export async function POST(request: Request) {
    try {
        const body: AICredentialsBody = await request.json();

        // Ensure table exists
        await pool.query(`
            CREATE TABLE IF NOT EXISTS ai_credentials (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(50) UNIQUE NOT NULL,
                api_key_encrypted TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        `);

        // Map form fields to provider names
        const credentials = [
            { provider: 'google', key: body.googleApiKey },
            { provider: 'openai', key: body.openaiApiKey },
            { provider: 'openrouter', key: body.openrouterApiKey },
            { provider: 'anthropic', key: body.anthropicApiKey },
        ];

        const savedKeys: Record<string, boolean> = {};

        for (const { provider, key } of credentials) {
            if (key && key.trim()) {
                const encryptedKey = encrypt(key.trim());
                await pool.query(`
                    INSERT INTO ai_credentials (provider, api_key_encrypted, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (provider) DO UPDATE SET
                        api_key_encrypted = EXCLUDED.api_key_encrypted,
                        updated_at = NOW()
                `, [provider, encryptedKey]);

                savedKeys[`${provider}ApiKey`] = true;
            }
        }

        // Get current state of all keys
        const result = await pool.query(`
            SELECT provider, api_key_encrypted IS NOT NULL as has_key
            FROM ai_credentials
        `);

        const providerMap: Record<string, string> = {
            'google': 'googleApiKey',
            'openai': 'openaiApiKey',
            'openrouter': 'openrouterApiKey',
            'anthropic': 'anthropicApiKey',
        };

        for (const row of result.rows) {
            const fieldName = providerMap[row.provider];
            if (fieldName) {
                savedKeys[fieldName] = row.has_key;
            }
        }

        return NextResponse.json({
            success: true,
            savedKeys,
        });
    } catch (error) {
        console.error('[AI Credentials POST] Error:', error);
        return NextResponse.json(
            { error: 'Failed to save AI credentials' },
            { status: 500 }
        );
    }
}

