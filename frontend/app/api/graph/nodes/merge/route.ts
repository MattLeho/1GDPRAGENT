import { NextResponse } from 'next/server';
import { getDriver } from '@/lib/graph';
import { sanitizeProperties, sanitizeRelationshipType } from '@/lib/graph/schema';

interface MergeNodeRequest {
    sourceId: string;
    targetId: string;
}

type RelationshipRecord = {
    neighborId: string;
    type: string;
    props: Record<string, unknown>;
}

function isNumericNodeId(value: unknown): value is string {
    return typeof value === 'string' && /^\d+$/.test(value);
}

export async function POST(request: Request) {
    let session;
    const body: MergeNodeRequest = await request.json();

    if (!isNumericNodeId(body.sourceId) || !isNumericNodeId(body.targetId)) {
        return NextResponse.json(
            { success: false, error: 'sourceId and targetId must be numeric Neo4j ids' },
            { status: 400 }
        );
    }

    if (body.sourceId === body.targetId) {
        return NextResponse.json(
            { success: false, error: 'sourceId and targetId must be different nodes' },
            { status: 400 }
        );
    }

    try {
        const driver = getDriver();
        session = driver.session();
        const tx = session.beginTransaction();

        try {
            const nodeResult = await tx.run(
                `
                MATCH (source), (target)
                WHERE id(source) = toInteger($sourceId)
                  AND id(target) = toInteger($targetId)
                RETURN properties(source) as sourceProps, properties(target) as targetProps
                `,
                body
            );

            const nodeRecord = nodeResult.records[0];
            if (!nodeRecord) {
                await tx.rollback();
                return NextResponse.json(
                    { success: false, error: 'Source or target node not found' },
                    { status: 404 }
                );
            }

            const sourceProps = nodeRecord.get('sourceProps') as Record<string, unknown>;
            const targetProps = nodeRecord.get('targetProps') as Record<string, unknown>;
            const existingMergedFrom = Array.isArray(targetProps.mergedFrom)
                ? targetProps.mergedFrom
                : targetProps.mergedFrom
                    ? [String(targetProps.mergedFrom)]
                    : [];

            const mergedProps = sanitizeProperties({
                ...sourceProps,
                ...targetProps,
                mergedFrom: [...existingMergedFrom, body.sourceId],
                mergedAt: new Date().toISOString(),
            });

            await tx.run(
                `
                MATCH (target)
                WHERE id(target) = toInteger($targetId)
                SET target += $mergedProps
                RETURN id(target) as id
                `,
                { targetId: body.targetId, mergedProps }
            );

            const outgoingResult = await tx.run(
                `
                MATCH (source)-[r]->(neighbor)
                WHERE id(source) = toInteger($sourceId)
                  AND id(neighbor) <> toInteger($targetId)
                RETURN id(neighbor) as neighborId, type(r) as type, properties(r) as props
                `,
                body
            );

            const incomingResult = await tx.run(
                `
                MATCH (neighbor)-[r]->(source)
                WHERE id(source) = toInteger($sourceId)
                  AND id(neighbor) <> toInteger($targetId)
                RETURN id(neighbor) as neighborId, type(r) as type, properties(r) as props
                `,
                body
            );

            const outgoing: RelationshipRecord[] = outgoingResult.records.map(record => ({
                neighborId: record.get('neighborId').toString(),
                type: record.get('type') as string,
                props: record.get('props') as Record<string, unknown>,
            }));

            const incoming: RelationshipRecord[] = incomingResult.records.map(record => ({
                neighborId: record.get('neighborId').toString(),
                type: record.get('type') as string,
                props: record.get('props') as Record<string, unknown>,
            }));

            for (const relationship of outgoing) {
                const relationshipType = sanitizeRelationshipType(relationship.type);
                await tx.run(
                    `
                    MATCH (target), (neighbor)
                    WHERE id(target) = toInteger($targetId)
                      AND id(neighbor) = toInteger($neighborId)
                    MERGE (target)-[merged:${relationshipType}]->(neighbor)
                    SET merged += $props, merged.updatedAt = datetime()
                    `,
                    {
                        targetId: body.targetId,
                        neighborId: relationship.neighborId,
                        props: sanitizeProperties(relationship.props || {}),
                    }
                );
            }

            for (const relationship of incoming) {
                const relationshipType = sanitizeRelationshipType(relationship.type);
                await tx.run(
                    `
                    MATCH (neighbor), (target)
                    WHERE id(neighbor) = toInteger($neighborId)
                      AND id(target) = toInteger($targetId)
                    MERGE (neighbor)-[merged:${relationshipType}]->(target)
                    SET merged += $props, merged.updatedAt = datetime()
                    `,
                    {
                        targetId: body.targetId,
                        neighborId: relationship.neighborId,
                        props: sanitizeProperties(relationship.props || {}),
                    }
                );
            }

            await tx.run(
                `
                MATCH (source)
                WHERE id(source) = toInteger($sourceId)
                DETACH DELETE source
                `,
                { sourceId: body.sourceId }
            );

            await tx.commit();

            return NextResponse.json({
                success: true,
                sourceId: body.sourceId,
                targetId: body.targetId,
                relationshipsRewired: outgoing.length + incoming.length,
            });
        } catch (error) {
            await tx.rollback();
            throw error;
        }
    } catch (error) {
        console.error('[Graph Nodes Merge] Error:', error);
        return NextResponse.json(
            {
                success: false,
                error: error instanceof Error ? error.message : 'Failed to merge nodes',
            },
            { status: 500 }
        );
    } finally {
        await session?.close();
    }
}
