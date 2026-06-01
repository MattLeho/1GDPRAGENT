/**
 * Graph Nodes API Route
 * 
 * Creates nodes in the Neo4j knowledge graph from ONSIT findings or manual input.
 * Follows AI-KG entity storage patterns with proper label handling.
 * 
 * @see https://github.com/robert-mcdermott/ai-knowledge-graph - Entity storage
 * @see https://github.com/reconurge/flowsint - Entity types
 */

import { NextResponse } from 'next/server';
import { getDriver } from '@/lib/graph';

/**
 * Node creation request body
 */
interface CreateNodeRequest {
    type: string;
    label: string;
    properties?: Record<string, unknown>;
    source?: 'onsit' | 'gdpr' | 'manual' | 'inference';
    riskLevel?: 'low' | 'medium' | 'high' | 'critical';
    confidence?: number;
    evidence?: Array<{
        url: string;
        snippet?: string;
    }>;
}

/**
 * Map entity type to Neo4j label
 * Uses Flowsint entity type conventions
 */
function mapTypeToLabel(type: string): string {
    const labelMap: Record<string, string> = {
        // Core ONSIT types
        email: 'Email',
        username: 'Username',
        phone: 'Phone',
        domain: 'Domain',
        ip: 'IP',

        // Social/identity types
        social_profile: 'SocialProfile',
        socialprofile: 'SocialProfile',
        individual: 'Individual',
        organization: 'Organization',

        // OSINT findings
        breach_record: 'BreachRecord',
        breachrecord: 'BreachRecord',
        credential: 'Credential',
        website: 'Website',
        document: 'PublicDocument',
        publicdocument: 'PublicDocument',

        // Crypto types
        cryptowallet: 'CryptoWallet',
        crypto_wallet: 'CryptoWallet',

        // Existing types
        user: 'User',
        persona: 'Persona',
        company: 'Company',
        account: 'Account',
        attribute: 'Attribute',
        datapoint: 'DataPoint',
        inference: 'Inference',
    };

    return labelMap[type.toLowerCase()] || type;
}

/**
 * Sanitize properties for Neo4j storage
 * Converts complex objects to JSON strings
 */
function sanitizeProperties(props: Record<string, unknown>): Record<string, unknown> {
    const sanitized: Record<string, unknown> = {};

    for (const [key, value] of Object.entries(props)) {
        if (value === null || value === undefined) continue;

        if (typeof value === 'object' && !Array.isArray(value)) {
            // Convert objects to JSON string
            sanitized[key] = JSON.stringify(value);
        } else if (Array.isArray(value)) {
            // Keep arrays of primitives, stringify arrays of objects
            if (value.length > 0 && typeof value[0] === 'object') {
                sanitized[key] = JSON.stringify(value);
            } else {
                sanitized[key] = value;
            }
        } else {
            sanitized[key] = value;
        }
    }

    return sanitized;
}

/**
 * POST /api/graph/nodes
 * 
 * Creates a single node in the knowledge graph.
 */
export async function POST(request: Request) {
    const driver = getDriver();
    const session = driver.session();

    try {
        const body: CreateNodeRequest = await request.json();

        // Validate required fields
        if (!body.label) {
            return NextResponse.json(
                { success: false, error: 'Label is required' },
                { status: 400 }
            );
        }

        const nodeLabel = mapTypeToLabel(body.type || 'Entity');
        const source = body.source || 'manual';
        const riskLevel = body.riskLevel || 'low';

        // Build properties
        const baseProperties = {
            label: body.label,
            source,
            riskLevel,
            confidence: body.confidence ?? 1.0,
            createdAt: new Date().toISOString(),
        };

        // Merge with additional properties - use Record to allow dynamic additions
        const allProperties: Record<string, unknown> = {
            ...baseProperties,
            ...sanitizeProperties(body.properties || {}),
        };

        // Store evidence if provided
        if (body.evidence && body.evidence.length > 0) {
            allProperties.evidenceJson = JSON.stringify(body.evidence);
        }

        // Create node with dynamic label
        // Note: Label is interpolated safely since it's mapped from our controlled list
        const result = await session.run(
            `
            CREATE (n:${nodeLabel} $props)
            SET n:ONSITFinding
            RETURN id(n) as id, n as node
            `,
            { props: allProperties }
        );

        const record = result.records[0];
        if (!record) {
            throw new Error('No node created');
        }

        const nodeId = record.get('id').toString();

        return NextResponse.json({
            success: true,
            nodeId,
            type: nodeLabel,
            label: body.label,
        });

    } catch (error) {
        console.error('[Graph Nodes POST] Error:', error);
        return NextResponse.json(
            {
                success: false,
                error: error instanceof Error ? error.message : 'Failed to create node'
            },
            { status: 500 }
        );
    } finally {
        await session.close();
    }
}
