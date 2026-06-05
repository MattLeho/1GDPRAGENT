/**
 * Graph Nodes Bulk API Route
 * 
 * Creates multiple nodes in the Neo4j knowledge graph efficiently.
 * Uses batch operations for better performance with large imports from ONSIT.
 * 
 * @see https://github.com/robert-mcdermott/ai-knowledge-graph - Batch ingestion
 */

import { NextResponse } from 'next/server';
import { getDriver } from '@/lib/graph';
import { mapTypeToLabel, normalizeRiskLevel, sanitizeProperties } from '@/lib/graph/schema';

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
}

interface BulkCreateRequest {
    nodes: CreateNodeRequest[];
}

/**
 * POST /api/graph/nodes/bulk
 * 
 * Creates multiple nodes in a single transaction.
 * More efficient than individual POST calls for bulk operations.
 */
export async function POST(request: Request) {
    const driver = getDriver();
    const session = driver.session();

    try {
        const body: BulkCreateRequest = await request.json();

        if (!body.nodes || !Array.isArray(body.nodes) || body.nodes.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Nodes array is required and cannot be empty' },
                { status: 400 }
            );
        }

        // Limit batch size for safety
        const MAX_BATCH_SIZE = 100;
        if (body.nodes.length > MAX_BATCH_SIZE) {
            return NextResponse.json(
                {
                    success: false,
                    error: `Maximum batch size is ${MAX_BATCH_SIZE} nodes`
                },
                { status: 400 }
            );
        }

        const results: Array<{ label: string; nodeId: string; type: string }> = [];
        const errors: Array<{ label: string; error: string }> = [];

        // Process nodes in a transaction
        const txc = session.beginTransaction();

        try {
            for (const nodeData of body.nodes) {
                if (!nodeData.label) {
                    errors.push({ label: 'unknown', error: 'Label is required' });
                    continue;
                }

                const nodeLabel = mapTypeToLabel(nodeData.type || 'Entity');
                const source = nodeData.source || 'onsit';
                const riskLevel = normalizeRiskLevel(nodeData.riskLevel);

                const baseProperties = {
                    label: nodeData.label,
                    source,
                    riskLevel,
                    confidence: nodeData.confidence ?? 1.0,
                    createdAt: new Date().toISOString(),
                };

                const allProperties = {
                    ...baseProperties,
                    ...sanitizeProperties(nodeData.properties || {}),
                };

                try {
                    // Create node - using MERGE to avoid duplicates
                    const result = await txc.run(
                        `
                        MERGE (n:${nodeLabel} {label: $label, source: $source})
                        ON CREATE SET n += $props, n:ONSITFinding
                        ON MATCH SET n.updatedAt = datetime()
                        RETURN id(n) as id
                        `,
                        {
                            label: nodeData.label,
                            source,
                            props: allProperties,
                        }
                    );

                    const record = result.records[0];
                    if (record) {
                        results.push({
                            label: nodeData.label,
                            nodeId: record.get('id').toString(),
                            type: nodeLabel,
                        });
                    }
                } catch (nodeError) {
                    errors.push({
                        label: nodeData.label,
                        error: nodeError instanceof Error ? nodeError.message : 'Unknown error'
                    });
                }
            }

            // Commit transaction
            await txc.commit();

        } catch (txError) {
            // Rollback on error
            await txc.rollback();
            throw txError;
        }

        return NextResponse.json({
            success: true,
            created: results.length,
            failed: errors.length,
            nodes: results,
            errors: errors.length > 0 ? errors : undefined,
        });

    } catch (error) {
        console.error('[Graph Nodes Bulk POST] Error:', error);
        return NextResponse.json(
            {
                success: false,
                error: error instanceof Error ? error.message : 'Failed to create nodes'
            },
            { status: 500 }
        );
    } finally {
        await session.close();
    }
}
