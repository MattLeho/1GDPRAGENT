/**
 * AI Credentials Utilities
 * 
 * Provides functions to retrieve decrypted AI provider credentials.
 * Falls back to environment variables if not configured in database.
 */

import crypto from 'crypto';
import { pool } from '@/lib/db';

export const AI_PROVIDER_IDS = [
    'google',
    'openai',
    'ollama',
    'openrouter',
    'huggingface',
    'nvidia',
] as const;

export type AIProviderId = typeof AI_PROVIDER_IDS[number];

export const DEFAULT_AI_PROVIDER: AIProviderId = 'google';

export const AI_PROVIDER_FORM_FIELDS: Record<AIProviderId, string> = {
    google: 'googleApiKey',
    openai: 'openaiApiKey',
    ollama: 'ollamaApiKey',
    openrouter: 'openrouterApiKey',
    huggingface: 'huggingfaceApiKey',
    nvidia: 'nvidiaApiKey',
};

const PROVIDER_ALIASES: Record<string, AIProviderId> = {
    google: 'google',
    googleai: 'google',
    gemini: 'google',
    openai: 'openai',
    ollama: 'ollama',
    local: 'ollama',
    openrouter: 'openrouter',
    openrouterai: 'openrouter',
    huggingface: 'huggingface',
    huggingfacehub: 'huggingface',
    hf: 'huggingface',
    nvidia: 'nvidia',
    nvidiaai: 'nvidia',
    nim: 'nvidia',
};

export function normalizeAIProvider(provider: unknown): AIProviderId | null {
    if (typeof provider !== 'string') {
        return null;
    }

    const normalized = provider.trim().toLowerCase().replace(/[\s_-]+/g, '');
    return PROVIDER_ALIASES[normalized] || null;
}

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

function decrypt(encryptedText: string): string | null {
    try {
        const [ivHex, encrypted] = encryptedText.split(':');
        const iv = Buffer.from(ivHex, 'hex');
        const decipher = crypto.createDecipheriv('aes-256-cbc', getKey(), iv);
        let decrypted = decipher.update(encrypted, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        return decrypted;
    } catch {
        return null;
    }
}

function getEnvCredential(provider: AIProviderId): string | null {
    const envMap: Record<AIProviderId, string | undefined> = {
        google: process.env.GOOGLE_API_KEY ||
            process.env.GEMINI_API_KEY ||
            process.env.GOOGLE_AI_API_KEY ||
            process.env.GOOGLE_GENERATIVE_AI_API_KEY,
        openai: process.env.OPENAI_API_KEY,
        openrouter: process.env.OPENROUTER_API_KEY || process.env.OPEN_ROUTER_API_KEY,
        ollama: process.env.OLLAMA_API_KEY,
        huggingface: process.env.HUGGINGFACE_API_KEY ||
            process.env.HUGGING_FACE_API_KEY ||
            process.env.HF_TOKEN,
        nvidia: process.env.NVIDIA_API_KEY || process.env.NVIDIA_NIM_API_KEY,
    };

    return envMap[provider] || null;
}

export function hasEnvAICredential(provider: AIProviderId): boolean {
    return Boolean(getEnvCredential(provider));
}

// =============================================================================
// Credential Retrieval
// =============================================================================

/**
 * Get a decrypted AI provider credential.
 * Falls back to environment variables if not in database.
 * 
 * @param provider - Provider name: 'google', 'openai', 'openrouter', 'ollama', 'huggingface', 'nvidia'
 * @returns Decrypted API key or null
 */
export async function getAICredential(provider: string): Promise<string | null> {
    const normalizedProvider = normalizeAIProvider(provider);
    if (!normalizedProvider) {
        return null;
    }

    try {
        const result = await pool.query(
            'SELECT api_key_encrypted FROM ai_credentials WHERE provider = $1',
            [normalizedProvider]
        );

        if (result.rows.length > 0 && result.rows[0].api_key_encrypted) {
            const credential = decrypt(result.rows[0].api_key_encrypted);
            if (credential) {
                return credential;
            }
        }
    } catch {
        // Table doesn't exist or no key found
    }

    return getEnvCredential(normalizedProvider);
}

/**
 * Get all configured AI credentials.
 * Returns an object with provider names as keys and API keys as values.
 */
export async function getAllAICredentials(): Promise<Record<string, string | null>> {
    const credentials: Record<string, string | null> = {};

    for (const provider of AI_PROVIDER_IDS) {
        credentials[provider] = await getAICredential(provider);
    }

    return credentials;
}
