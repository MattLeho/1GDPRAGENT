/**
 * API Credentials Settings Route
 * 
 * GET /api/settings/api-credentials - Retrieve which API keys are configured
 * POST /api/settings/api-credentials - Save encrypted API credentials
 * 
 * @security All API keys are encrypted before storage using AES-256
 */

import { NextResponse } from 'next/server';
import { getDriver } from '@/lib/graph';
import { obfuscate, type APICredentials } from '@/lib/credentials';

/**
 * GET /api/settings/api-credentials
 * 
 * Returns which API keys are configured (not the actual keys for security)
 */
export async function GET() {
    const driver = getDriver();
    const session = driver.session();

    try {
        const result = await session.run(`
            MATCH (c:APICredentials {id: 'main'})
            RETURN c
        `);

        if (result.records.length === 0) {
            return NextResponse.json({
                savedKeys: {
                    hibpApiKey: false,
                    hunterApiKey: false,
                    shodanApiKey: false,
                    whoisApiKey: false,
                },
            });
        }

        const credentials = result.records[0].get('c').properties;

        return NextResponse.json({
            savedKeys: {
                hibpApiKey: !!credentials.hibpApiKey,
                hunterApiKey: !!credentials.hunterApiKey,
                shodanApiKey: !!credentials.shodanApiKey,
                whoisApiKey: !!credentials.whoisApiKey,
            },
        });
    } catch (error) {
        console.error('[API Credentials GET] Error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch credentials' },
            { status: 500 }
        );
    } finally {
        await session.close();
    }
}

/**
 * POST /api/settings/api-credentials
 * 
 * Saves encrypted API credentials to Neo4j
 */
export async function POST(request: Request) {
    const driver = getDriver();
    const session = driver.session();

    try {
        const body: APICredentials = await request.json();

        // Encrypt the credentials
        const encrypted: Record<string, string | null> = {};
        if (body.hibpApiKey) encrypted.hibpApiKey = obfuscate(body.hibpApiKey);
        if (body.hunterApiKey) encrypted.hunterApiKey = obfuscate(body.hunterApiKey);
        if (body.shodanApiKey) encrypted.shodanApiKey = obfuscate(body.shodanApiKey);
        if (body.whoisApiKey) encrypted.whoisApiKey = obfuscate(body.whoisApiKey);

        // Use MERGE to create or update
        await session.run(`
            MERGE (c:APICredentials {id: 'main'})
            SET c += $props, c.updatedAt = datetime()
        `, { props: encrypted });

        // Return which keys are now saved
        const savedKeys = {
            hibpApiKey: !!encrypted.hibpApiKey,
            hunterApiKey: !!encrypted.hunterApiKey,
            shodanApiKey: !!encrypted.shodanApiKey,
            whoisApiKey: !!encrypted.whoisApiKey,
        };

        return NextResponse.json({
            success: true,
            savedKeys,
        });
    } catch (error) {
        console.error('[API Credentials POST] Error:', error);
        return NextResponse.json(
            { error: 'Failed to save credentials' },
            { status: 500 }
        );
    } finally {
        await session.close();
    }
}
