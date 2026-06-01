import { NextResponse, NextRequest } from 'next/server';
import { getDriver } from '@/lib/graph';

/**
 * ONSIT Bulk Operations API
 * 
 * Supports bulk actions on ONSIT findings:
 * - Delete multiple findings
 * - Update risk levels in bulk
 * - Tag/categorize findings
 */

interface BulkActionRequest {
    action: 'delete' | 'updateRisk' | 'addTag' | 'removeTag';
    findingIds: string[];
    payload?: {
        riskLevel?: 'low' | 'medium' | 'high' | 'critical';
        tag?: string;
    };
}

export async function POST(request: NextRequest) {
    const driver = getDriver();
    const session = driver.session();

    try {
        const body = await request.json() as BulkActionRequest;
        const { action, findingIds, payload } = body;

        if (!findingIds || findingIds.length === 0) {
            return NextResponse.json(
                { error: 'No finding IDs provided' },
                { status: 400 }
            );
        }

        // Limit bulk operations to 100 items at a time
        if (findingIds.length > 100) {
            return NextResponse.json(
                { error: 'Maximum 100 findings per bulk operation' },
                { status: 400 }
            );
        }

        let result;
        let affectedCount = 0;

        switch (action) {
            case 'delete':
                result = await session.run(`
                    MATCH (n)
                    WHERE id(n) IN $ids AND n.source = 'onsit'
                    DETACH DELETE n
                    RETURN count(n) as deleted
                `, { ids: findingIds.map(id => parseInt(id)) });
                affectedCount = result.records[0]?.get('deleted')?.toNumber() || 0;
                break;

            case 'updateRisk':
                if (!payload?.riskLevel) {
                    return NextResponse.json(
                        { error: 'riskLevel required for updateRisk action' },
                        { status: 400 }
                    );
                }
                result = await session.run(`
                    MATCH (n)
                    WHERE id(n) IN $ids AND n.source = 'onsit'
                    SET n.riskLevel = $riskLevel, n.updatedAt = datetime()
                    RETURN count(n) as updated
                `, { ids: findingIds.map(id => parseInt(id)), riskLevel: payload.riskLevel });
                affectedCount = result.records[0]?.get('updated')?.toNumber() || 0;
                break;

            case 'addTag':
                if (!payload?.tag) {
                    return NextResponse.json(
                        { error: 'tag required for addTag action' },
                        { status: 400 }
                    );
                }
                result = await session.run(`
                    MATCH (n)
                    WHERE id(n) IN $ids AND n.source = 'onsit'
                    SET n.tags = CASE 
                        WHEN n.tags IS NULL THEN [$tag]
                        WHEN NOT $tag IN n.tags THEN n.tags + $tag
                        ELSE n.tags
                    END
                    RETURN count(n) as tagged
                `, { ids: findingIds.map(id => parseInt(id)), tag: payload.tag });
                affectedCount = result.records[0]?.get('tagged')?.toNumber() || 0;
                break;

            case 'removeTag':
                if (!payload?.tag) {
                    return NextResponse.json(
                        { error: 'tag required for removeTag action' },
                        { status: 400 }
                    );
                }
                result = await session.run(`
                    MATCH (n)
                    WHERE id(n) IN $ids AND n.source = 'onsit'
                    SET n.tags = [t IN COALESCE(n.tags, []) WHERE t <> $tag]
                    RETURN count(n) as untagged
                `, { ids: findingIds.map(id => parseInt(id)), tag: payload.tag });
                affectedCount = result.records[0]?.get('untagged')?.toNumber() || 0;
                break;

            default:
                return NextResponse.json(
                    { error: `Unknown action: ${action}` },
                    { status: 400 }
                );
        }

        return NextResponse.json({
            success: true,
            action,
            affected: affectedCount,
            requested: findingIds.length,
        });

    } catch (error) {
        console.error('Bulk operation failed:', error);
        return NextResponse.json(
            { error: 'Bulk operation failed', details: error instanceof Error ? error.message : 'Unknown error' },
            { status: 500 }
        );
    } finally {
        await session.close();
    }
}
