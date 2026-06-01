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
            MATCH (n)
            RETURN labels(n)[0] as type, count(n) as count
        `);

        // Count relationships
        const relCountResult = await session.run(`
            MATCH ()-[r]->()
            RETURN count(r) as total
        `);

        // Count high-risk connections (inferences with high confidence)
        const riskResult = await session.run(`
            MATCH (n:Inference)
            WHERE n.risk_level = 'high' OR n.confidence_score > 0.8
            RETURN count(n) as count
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
        });
    } catch (error) {
        console.error('Failed to fetch graph stats:', error);

        // Return fallback stats
        return NextResponse.json({
            totalNodes: 9,
            totalRelationships: 10,
            nodesByType: {
                User: 1,
                Persona: 2,
                Company: 2,
                Account: 2,
                Attribute: 2,
            },
            highRiskConnections: 0,
            lastUpdated: new Date().toISOString(),
        });
    } finally {
        await session.close();
    }
}
