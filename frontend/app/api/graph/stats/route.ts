import { NextResponse } from 'next/server';
import { getDriver } from '@/lib/graph';

export interface GraphStats {
    totalNodes: number;
    totalRelationships: number;
    nodesByType: Record<string, number>;
    highRiskConnections: number;
    lastUpdated: string;
}

export async function GET() {
    const driver = getDriver();
    const session = driver.session();

    try {
        // Count nodes by type
        const nodeCountResult = await session.run(`
            MATCH (n:GraphNode)
            WHERE coalesce(n.retired, false) = false
            RETURN coalesce(head([label IN labels(n) WHERE label <> 'GraphNode']), 'GraphNode') as type,
                   count(n) as count
        `);

        // Count relationships
        const relCountResult = await session.run(`
            MATCH (:GraphNode)-[r]->(:GraphNode)
            WHERE coalesce(r.epistemic_basis, '') <> 'model_hypothesis'
              AND (r.inferred IS NULL OR r.inferred = false)
            RETURN count(r) as total
        `);

        // Risk is an explicit source property, not a confidence-based inference.
        const riskResult = await session.run(`
            MATCH (:GraphNode)-[r]->(:GraphNode)
            WHERE toLower(coalesce(r.risk_level, '')) IN ['high', 'critical']
              AND coalesce(r.epistemic_basis, '') <> 'model_hypothesis'
              AND (r.inferred IS NULL OR r.inferred = false)
            RETURN count(r) as count
        `);

        const nodesByType: Record<string, number> = {};
        let totalNodes = 0;

        nodeCountResult.records.forEach((record) => {
            const type = record.get('type') as string || 'Unknown';
            const count = (record.get('count') as { toNumber(): number }).toNumber();
            nodesByType[type] = count;
            totalNodes += count;
        });

        const totalRelationships = relCountResult.records[0]?.get('total')?.toNumber?.() ?? 0;
        const highRiskConnections = riskResult.records[0]?.get('count')?.toNumber?.() ?? 0;

        return NextResponse.json({
            totalNodes,
            totalRelationships,
            nodesByType,
            highRiskConnections,
            lastUpdated: new Date().toISOString(),
            dbStatus: 'connected',
        });
    } catch (error) {
        console.error('Failed to fetch graph stats:', error);

        // Unknown data is represented as unavailable/zero, never as invented graph facts.
        return NextResponse.json({
            totalNodes: 0,
            totalRelationships: 0,
            nodesByType: {},
            highRiskConnections: 0,
            lastUpdated: new Date().toISOString(),
            dbStatus: 'error',
            error: 'Graph statistics are currently unavailable.',
        });
    } finally {
        await session.close();
    }
}
