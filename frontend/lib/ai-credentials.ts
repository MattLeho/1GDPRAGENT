/**
 * AI Credentials Utilities
 * 
 * Provides functions to retrieve decrypted AI provider credentials.
 * Falls back to environment variables if not configured in database.
 */

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
    return crypto.createHash('sha256').update(getEncryptionKey()).digest();
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
// Credential Retrieval
// =============================================================================

/**
 * Get a decrypted AI provider credential.
 * Falls back to environment variables if not in database.
 * 
 * @param provider - Provider name: 'google', 'openai', 'openrouter', 'anthropic'
 * @returns Decrypted API key or null
 */
export async function getAICredential(provider: string): Promise<string | null> {
    try {
        const result = await pool.query(
            'SELECT api_key_encrypted FROM ai_credentials WHERE provider = $1',
            [provider]
        );

        if (result.rows.length > 0 && result.rows[0].api_key_encrypted) {
            return decrypt(result.rows[0].api_key_encrypted);
        }
    } catch {
        // Table doesn't exist or no key found
    }

    // Fall back to environment variables
    const envMap: Record<string, string | undefined> = {
        'google': process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY,
        'openai': process.env.OPENAI_API_KEY,
        'openrouter': process.env.OPENROUTER_API_KEY,
        'anthropic': process.env.ANTHROPIC_API_KEY,
    };

    return envMap[provider] || null;
}

/**
 * Get all configured AI credentials.
 * Returns an object with provider names as keys and API keys as values.
 */
export async function getAllAICredentials(): Promise<Record<string, string | null>> {
    const providers = ['google', 'openai', 'openrouter', 'anthropic'];
    const credentials: Record<string, string | null> = {};

    for (const provider of providers) {
        credentials[provider] = await getAICredential(provider);
    }

    return credentials;
}
