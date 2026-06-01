import { NextResponse, NextRequest } from 'next/server';
import { getDriver } from '@/lib/graph';

/**
 * Extended GraphNode type including all ONSIT entity types
 * @see https://github.com/reconurge/flowsint - Entity types
 */
export interface GraphNode {
    id: string;
    label: string;
    type: string; // Extended to support all ONSIT types
    properties: Record<string, unknown>;
    source?: 'onsit' | 'gdpr' | 'inference' | 'manual';
    riskLevel?: 'low' | 'medium' | 'high' | 'critical';
}

export interface GraphLink {
    source: string;
    target: string;
    type: string;
    isInferred?: boolean;
}

export interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
    pagination?: {
        hasMore: boolean;
        nextCursor: string | null;
        total: number;
    };
}

interface PaginationParams {
    limit: number;
    skip: number;
    layer?: 'onsit' | 'gdpr' | 'all';
    showInferences: boolean;
}

function parsePaginationParams(request: NextRequest): PaginationParams {
    const searchParams = request.nextUrl.searchParams;
    return {
        limit: Math.min(parseInt(searchParams.get('limit') || '100'), 500),
        skip: parseInt(searchParams.get('skip') || '0'),
        layer: (searchParams.get('layer') as 'onsit' | 'gdpr' | 'all') || 'all',
        showInferences: searchParams.get('showInferences') !== 'false',
    };
}

export async function GET(request: NextRequest) {
    const driver = getDriver();
    const session = driver.session();
    const { limit, skip, layer, showInferences } = parsePaginationParams(request);

    try {
        // Build layer filter clause
        let nodeFilter = '';
        if (layer === 'onsit') {
            nodeFilter = `WHERE n.source = 'onsit' OR n:ONSITFinding OR n:Email OR n:Username OR n:Domain`;
        } else if (layer === 'gdpr') {
            nodeFilter = `WHERE n.source = 'gdpr' OR n:User OR n:Company OR n:DataPoint`;
        }

        // First get total count
        const countResult = await session.run(`
            MATCH (n) ${nodeFilter}
            RETURN count(n) as total
        `);
        const total = countResult.records[0]?.get('total')?.toNumber() || 0;

        // Fetch nodes with pagination
        const nodesResult = await session.run(`
            MATCH (n) ${nodeFilter}
            RETURN id(n) as id, labels(n) as labels, properties(n) as props
            ORDER BY id(n)
            SKIP $skip
            LIMIT $limit
        `, { skip: skip, limit: limit + 1 }); // +1 to check if there's more

        // Check if there are more results
        const hasMore = nodesResult.records.length > limit;
        const nodeRecords = hasMore ? nodesResult.records.slice(0, limit) : nodesResult.records;

        // Build relationship filter
        let relFilter = '';
        if (!showInferences) {
            relFilter = `WHERE NOT r.inferred = true`;
        }

        // Fetch relationships for the nodes
        const nodeIds = nodeRecords.map(r => r.get('id').toNumber());
        const linksResult = await session.run(`
            MATCH (a)-[r]->(b)
            WHERE id(a) IN $nodeIds AND id(b) IN $nodeIds ${showInferences ? '' : 'AND (r.inferred IS NULL OR r.inferred = false)'}
            RETURN id(a) as source, id(b) as target, type(r) as type, r.inferred as inferred
            LIMIT 2000
        `, { nodeIds });

        const nodes: GraphNode[] = nodeRecords.map((record) => {
            const id = record.get('id').toString();
            const labels = record.get('labels') as string[];
            const props = record.get('props') as Record<string, unknown>;

            // Extended type order including ONSIT entity types
            const typeOrder = [
                // Core types
                'User', 'Persona', 'Company', 'Account', 'Attribute', 'DataPoint', 'Inference',
                // ONSIT types (Flowsint entities)
                'Email', 'Username', 'Phone', 'Domain', 'IP', 'ASN', 'CIDR',
                'SocialProfile', 'Individual', 'Organization', 'Website',
                'BreachRecord', 'Credential', 'PublicDocument',
                'CryptoWallet', 'Transaction', 'NFT',
                // Discovery marker
                'ONSITFinding',
            ];
            const type = typeOrder.find(t => labels.includes(t)) || labels[0] || 'Unknown';

            return {
                id,
                label: (props.name as string) || (props.value as string) || (props.label as string) || type,
                type: type as GraphNode['type'],
                properties: props,
                source: props.source as GraphNode['source'],
                riskLevel: props.riskLevel as GraphNode['riskLevel'],
            };
        });

        const links: GraphLink[] = linksResult.records.map((record) => ({
            source: record.get('source').toString(),
            target: record.get('target').toString(),
            type: record.get('type') as string,
            isInferred: record.get('inferred') === true,
        }));

        const nextCursor = hasMore ? String(skip + limit) : null;

        return NextResponse.json({
            nodes,
            links,
            pagination: {
                hasMore,
                nextCursor,
                total,
            },
        });
    } catch (error) {
        console.error('Failed to fetch graph data:', error);

        // Return empty graph with error indicator - NO dummy data
        return NextResponse.json({
            nodes: [],
            links: [],
            pagination: {
                hasMore: false,
                nextCursor: null,
                total: 0,
            },
            error: 'Database connection failed. Please ensure Neo4j is running.',
            dbStatus: 'disconnected',
        });
    } finally {
        await session.close();
    }
}

