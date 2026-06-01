/**
 * API Credentials Utility Library
 * 
 * Functions for securely retrieving and managing API credentials
 * stored in Neo4j for ONSIT enrichers.
 */

import { getDriver } from '@/lib/graph';

/**
 * API Credentials interface
 */
export interface APICredentials {
    hibpApiKey?: string;
    hunterApiKey?: string;
    shodanApiKey?: string;
    whoisApiKey?: string;
}

function getEncryptionKey(): string {
    const key = process.env.ENCRYPTION_KEY || process.env.CREDENTIALS_ENCRYPTION_KEY;
    if (!key) {
        throw new Error('ENCRYPTION_KEY or CREDENTIALS_ENCRYPTION_KEY must be set');
    }
    return key;
}

export function obfuscate(value: string): string {
    if (!value) return '';
    const key = getEncryptionKey();
    let result = '';
    for (let i = 0; i < value.length; i++) {
        result += String.fromCharCode(value.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }
    return Buffer.from(result).toString('base64');
}

export function deobfuscate(encoded: string): string {
    if (!encoded) return '';
    const key = getEncryptionKey();
    const value = Buffer.from(encoded, 'base64').toString();
    let result = '';
    for (let i = 0; i < value.length; i++) {
        result += String.fromCharCode(value.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }
    return result;
}

/**
 * Retrieve decrypted credentials for use in ONSIT enrichers
 * This is called internally by the intelligence service
 */
export async function getDecryptedCredentials(): Promise<APICredentials> {
    const driver = getDriver();
    const session = driver.session();

    try {
        const result = await session.run(`
            MATCH (c:APICredentials {id: 'main'})
            RETURN c
        `);

        if (result.records.length === 0) {
            return {};
        }

        const credentials = result.records[0].get('c').properties;

        return {
            hibpApiKey: credentials.hibpApiKey ? deobfuscate(credentials.hibpApiKey) : undefined,
            hunterApiKey: credentials.hunterApiKey ? deobfuscate(credentials.hunterApiKey) : undefined,
            shodanApiKey: credentials.shodanApiKey ? deobfuscate(credentials.shodanApiKey) : undefined,
            whoisApiKey: credentials.whoisApiKey ? deobfuscate(credentials.whoisApiKey) : undefined,
        };
    } finally {
        await session.close();
    }
}

/**
 * Check if a specific API is configured
 */
export async function isApiConfigured(apiId: keyof APICredentials): Promise<boolean> {
    const credentials = await getDecryptedCredentials();
    return !!credentials[apiId];
}
