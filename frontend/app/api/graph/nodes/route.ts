/**
 * Graph Nodes API Route
 * 
 * Creates nodes in the Neo4j knowledge graph from ONSIT findings or manual input.
 * Follows AI-KG entity storage patterns with proper label handling.
 * 
 * @see https://github.com/robert-mcdermott/ai-knowledge-graph - Entity storage
 * @see https://github.com/reconurge/flowsint - Entity types
 */

import { NextRequest, NextResponse } from 'next/server';
import { getDriver } from '@/lib/graph';
import { mapTypeToLabel, normalizeRiskLevel, sanitizeProperties } from '@/lib/graph/schema';

/**
 * Node creation request body
 */
interface CreateNodeRequest {
    id?: string;
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
 * POST /api/graph/nodes
 * 
 * Creates a single node in the knowledge graph.
 */
export async function POST(request: Request) {
    let session;
    try {
        const driver = getDriver();
        session = driver.session();
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
        const riskLevel = normalizeRiskLevel(body.riskLevel);

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
        await session?.close();
    }
}

/**
 * PUT /api/graph/nodes
 *
 * Upserts a node by internal Neo4j id when provided, otherwise by type+label+source.
 */
export async function PUT(request: Request) {
    let session;

    try {
        const driver = getDriver();
        session = driver.session();
        const body: CreateNodeRequest = await request.json();

        if (!body.label) {
            return NextResponse.json(
                { success: false, error: 'Label is required' },
                { status: 400 }
            );
        }

        const nodeLabel = mapTypeToLabel(body.type || 'Entity');
        const source = body.source || 'manual';
        const now = new Date().toISOString();
        const props: Record<string, unknown> = {
            label: body.label,
            source,
            riskLevel: normalizeRiskLevel(body.riskLevel),
            confidence: body.confidence ?? 1.0,
            updatedAt: now,
            ...sanitizeProperties(body.properties || {}),
        };

        if (body.evidence && body.evidence.length > 0) {
            props.evidenceJson = JSON.stringify(body.evidence);
        }

        const result = body.id
            ? await session.run(
                `
                MATCH (n)
                WHERE id(n) = toInteger($id)
                SET n:${nodeLabel}
                SET n += $props
                RETURN id(n) as id, labels(n) as labels, properties(n) as props
                `,
                { id: body.id, props }
            )
            : await session.run(
                `
                MERGE (n:${nodeLabel} {label: $label, source: $source})
                ON CREATE SET n.createdAt = $createdAt
                SET n += $props
                RETURN id(n) as id, labels(n) as labels, properties(n) as props
                `,
                { label: body.label, source, createdAt: now, props }
            );

        const record = result.records[0];
        if (!record) {
            return NextResponse.json(
                { success: false, error: 'Node not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({
            success: true,
            nodeId: record.get('id').toString(),
            labels: record.get('labels'),
            properties: record.get('props'),
        });
    } catch (error) {
        console.error('[Graph Nodes PUT] Error:', error);
        return NextResponse.json(
            {
                success: false,
                error: error instanceof Error ? error.message : 'Failed to upsert node'
            },
            { status: 500 }
        );
    } finally {
        await session?.close();
    }
}

/**
 * DELETE /api/graph/nodes?id=<neo4j-id>
 */
export async function DELETE(request: NextRequest) {
    let session;

    try {
        const nodeId = request.nextUrl.searchParams.get('id');

        if (!nodeId || !/^\d+$/.test(nodeId)) {
            return NextResponse.json(
                { success: false, error: 'Valid numeric node id is required' },
                { status: 400 }
            );
        }

        const driver = getDriver();
        session = driver.session();

        const result = await session.run(
            `
            MATCH (n)
            WHERE id(n) = toInteger($nodeId)
            WITH n, labels(n) as labels, coalesce(n.label, n.name, n.value, n.address, toString(id(n))) as label
            DETACH DELETE n
            RETURN labels, label
            `,
            { nodeId }
        );

        const record = result.records[0];
        if (!record) {
            return NextResponse.json(
                { success: false, error: 'Node not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({
            success: true,
            deletedNodeId: nodeId,
            label: record.get('label'),
            labels: record.get('labels'),
        });
    } catch (error) {
        console.error('[Graph Nodes DELETE] Error:', error);
        return NextResponse.json(
            {
                success: false,
                error: error instanceof Error ? error.message : 'Failed to delete node'
            },
            { status: 500 }
        );
    } finally {
        await session?.close();
    }
}
